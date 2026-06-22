# Orchestrate — Multi-Modal Evidence Review

Verify damage claims from photos. Given a claim conversation, one or more
submitted images, the user's claim history, and minimum evidence requirements,
the system decides whether the images **support** the claim, **contradict** it,
or give **not enough information** — across three object types: **car**,
**laptop**, and **package**.

This repo ships three pieces:

| Piece | What it is | Path |
|---|---|---|
| **Backend** | Standalone FastAPI service that runs the verification pipeline (Gemini + Claude). | [`backend/`](./backend/) |
| **Frontend** | Next.js "Claims Desk" — a customer-support chat that renders a verdict dossier. | [`frontend/`](./frontend/) |
| **Reference solution** | The original batch pipeline + evaluation for the hackathon contract. | [`code/`](./code/) |

> Full task spec, I/O schema, and allowed values: [`problem_statement.md`](./problem_statement.md).
> Each piece has its own README — [backend](./backend/README.md) · [frontend](./frontend/README.md).

---

## Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Run the full stack](#run-the-full-stack) ← install + run backend and frontend together
4. [Verify it's working](#verify-its-working)
5. [Run the tests](#run-the-tests)
6. [Batch run (CSV → output.csv)](#batch-run-csv--outputcsv)
7. [Repository layout](#repository-layout)
8. [Evaluation, logging & submission](#evaluation-logging--submission)

---

## Architecture

```
            ┌─────────────────────────┐         ┌──────────────────────────────┐
 browser ──▶│  frontend (Next.js)     │  HTTP   │  backend (FastAPI)           │
  :3000     │  "Claims Desk" chat     │────────▶│  :8000  /api/*  + /dataset   │
            └─────────────────────────┘  CORS   └──────────────┬───────────────┘
                                                                │
                                                  ┌─────────────▼─────────────┐
                                                  │ pipeline: parse → per-image│
                                                  │ VLM → decision → history   │
                                                  │ provider: Gemini (default) │
                                                  └─────────────┬─────────────┘
                                                                │ reads
                                                        ┌───────▼────────┐
                                                        │   dataset/     │
                                                        └────────────────┘
```

The frontend calls the backend over HTTP (CORS is preconfigured for
`http://localhost:3000`). Both read images from the shared `dataset/` directory.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.10+ (tested 3.12) | for the backend |
| Node.js | 18+ (tested 22) | for the frontend |
| npm | 9+ | ships with Node |
| Gemini API key | optional | **without a key the backend runs in deterministic mock mode**, so the full stack works offline. Add a key for live VLM analysis. Get one at <https://aistudio.google.com/apikey>. |

You run two long-running servers, so use **two terminals** (one for the backend,
one for the frontend).

---

## Run the full stack

### 1 · Backend (terminal 1)

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # then edit .env and set GEMINI_API_KEY (optional)
uvicorn app.main:app --reload --port 8000
```

**macOS / Linux**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env and set GEMINI_API_KEY (optional)
uvicorn app.main:app --reload --port 8000
```

The API is now on <http://localhost:8000> (interactive docs at `/docs`).
Leave it running.

> No API key? Skip editing `.env` — the service starts in mock mode and every
> endpoint still works (deterministic placeholder analysis). To force mock mode
> even with a key present, set `LLM_MOCK=1`.

### 2 · Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

Open **<http://localhost:3000>** and start a claim — or click a case from the
library on the right to load real photos and conversation, then hit **Verify**.

> Pointing at a non-default backend origin? Create `frontend/.env.local` from
> `frontend/.env.local.example` and set `NEXT_PUBLIC_API_BASE`.

### Production frontend (optional)

```bash
cd frontend
npm run build
npm run start                      # serves the optimized build on :3000
```

---

## Verify it's working

With both servers up:

```bash
# backend liveness + provider/mock status
curl http://localhost:8000/api/health
curl http://localhost:8000/api/providers

# a sample case (labeled) and a static evidence image
curl "http://localhost:8000/api/samples?split=sample"
curl -I http://localhost:8000/dataset/images/sample/case_001/img_1.jpg

# run one verification end-to-end
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user_001","claim_object":"car","user_claim":"The rear bumper has a dent. Photo attached.","image_paths":["images/sample/case_001/img_1.jpg"]}'
```

Then load <http://localhost:3000> in a browser — the status pill should read
**live** (or **mock** label on the provider) and the case library should populate.

---

## Run the tests

**Backend** (mock mode — no network, no key):

```bash
cd backend
pytest                       # full suite
RUN_LIVE=1 pytest -m live     # also runs the gated live Gemini smoke test (spends quota)
```

**Frontend** (type-check + lint via the production build):

```bash
cd frontend
npm run build
```

---

## Batch run (CSV → output.csv)

Produce predictions for an entire claims CSV using the same pipeline the API
serves (incremental + resumable):

```bash
cd backend
python -m app.cli --input ../dataset/claims.csv --output ../output.csv
python -m app.cli --resume         # continue an interrupted run
LLM_MOCK=1 python -m app.cli        # force offline mock run
```

The original reference implementation under [`code/`](./code/) provides the same
capability for the hackathon contract (`code/main.py`, `code/evaluation/`).

---

## Repository layout

```text
.
├── AGENTS.md                 # rules for AI coding tools + transcript logging
├── problem_statement.md      # full task description and I/O schema
├── README.md                 # you are here
├── backend/                  # standalone FastAPI service (see backend/README.md)
│   ├── app/                  # main, config, schemas, service, cli, api/, core/
│   └── tests/                # pytest suite
├── frontend/                 # Next.js "Claims Desk" chat (see frontend/README.md)
│   ├── app/                  # layout, page, globals.css
│   ├── components/           # ClaimsDesk, Composer, VerdictDossier, ...
│   └── lib/                  # typed API client + types
├── code/                     # reference solution + evaluation
└── dataset/
    ├── sample_claims.csv     # inputs + expected outputs (labeled)
    ├── claims.csv            # inputs only; run your system on these
    ├── user_history.csv      # historical claim counts and risk context
    ├── evidence_requirements.csv
    └── images/{sample,test}/ # images referenced by the CSVs
```

### Output contract (per claim)

`output.csv` / the API prediction carries these fields, all coerced to a closed
allowed-value vocabulary:

| Column | Meaning |
|---|---|
| `evidence_standard_met` | Whether the image set is sufficient to evaluate the claim |
| `evidence_standard_met_reason` | Short reason for the evidence decision |
| `risk_flags` | Semicolon-separated risk flags, or `none` |
| `issue_type` | Visible issue type |
| `object_part` | Relevant object part |
| `claim_status` | `supported`, `contradicted`, or `not_enough_information` |
| `claim_status_justification` | Concise explanation grounded in the image evidence |
| `supporting_image_ids` | Image IDs supporting the decision, or `none` |
| `valid_image` | Whether the image set is usable for automated review |
| `severity` | `none`, `low`, `medium`, `high`, or `unknown` |

---

## Evaluation, logging & submission

- **Evaluation** lives under [`code/evaluation/`](./code/evaluation/) and reports
  metrics on `dataset/sample_claims.csv`, compares strategies/model configs, and
  covers operational cost (model calls, tokens, runtime, RPM/TPM).
- **Chat-transcript logging** is mandated by [`AGENTS.md`](./AGENTS.md): AI coding
  tools append every turn to a shared log file
  (`%USERPROFILE%\hackerrank_orchestrate\log.txt` on Windows,
  `$HOME/hackerrank_orchestrate/log.txt` on macOS/Linux). Never paste secrets;
  use environment variables / `.env` (gitignored).
- **Submission**: zip the runnable solution + READMEs + evaluation, attach the
  final `output.csv` (one row per `dataset/claims.csv` row, exact column order),
  and include the chat transcript. See [`problem_statement.md`](./problem_statement.md).
