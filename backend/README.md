# Orchestrate Claim Verifier — Backend

A **standalone** FastAPI service for multi-modal damage-claim evidence review.
It verifies whether submitted images **support**, **contradict**, or give
**not enough information** for a customer's damage claim, using a claim-grounded
VLM chain plus deterministic decision rules, user-history risk, and minimum
evidence requirements.

This service is fully self-contained — it does **not** depend on the sibling
`code/` package. The entire pipeline is ported into `app/core/`.

## Why standalone

The original `backend/` imported the sibling `code/` package. That package name
collides with Python's stdlib `code` module and relied on fragile mixed imports,
so the service failed to start (`ModuleNotFoundError: 'code' is not a package`).
Everything now lives under the `app/` package with clean, absolute imports.

## Architecture

```
backend/
├── app/
│   ├── main.py            # FastAPI app factory, lifespan, CORS, error handlers
│   ├── config.py          # env-only Settings (pydantic-settings), provider readiness
│   ├── schemas.py         # API request/response models
│   ├── service.py         # ClaimVerifierService — caches deps + clients
│   ├── cli.py             # batch runner: claims.csv -> output.csv
│   ├── api/
│   │   └── routes.py      # /health, /providers, /verify, /batch
│   └── core/              # the standalone pipeline (no `code` dependency)
│       ├── contract.py    # output columns + closed vocab + coercion
│       ├── data_io.py     # CSV + image-path resolution
│       ├── prompts.py     # prompt loading/rendering (+ prompts/*.md)
│       ├── cache.py       # content-addressed analysis cache
│       ├── llm/           # base client + gemini + claude + registry
│       └── pipeline/      # claim_parser, image_analysis, decision, risk, orchestrator
└── tests/                 # pytest suite (mock by default; gated live smoke test)
```

### Pipeline (per claim)

1. **Parse claim** — extract claimed part(s)/issue/severity from the (possibly
   multilingual) chat transcript; deterministic prompt-injection detection.
2. **Per-image VLM analysis** — each image independently answers a fixed chain:
   object check → per-part issue → severity-welfare → usability/authenticity.
   Cached by image content hash.
3. **Deterministic decision** — OR-merge confirming parts across usable images;
   handle wrong-object, identity-conflict, wrong-part, exaggeration, undamaged.
4. **History overlay** — adds risk context / manual-review flags only; never
   flips a decision that has clear visual evidence.

Every output value is coerced to the closed allowed-value vocabulary, so a
response can never contain an out-of-vocabulary token.

## Providers

| Provider | Status | Model | Notes |
|---|---|---|---|
| `gemini` | **operational** (default) | `gemini-3.5-flash` | `google-genai` SDK |
| `claude` | available | `claude-opus-4-8` | runs in mock mode unless `ANTHROPIC_API_KEY` is set |

A provider with no API key (or global `LLM_MOCK=1`) runs deterministic offline
stubs, so the whole service runs end-to-end with no network and no key.

## Setup

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows; use bin/activate on *nix
pip install -r requirements.txt
cp .env.example .env        # then add GEMINI_API_KEY
```

Secrets are read from the environment / `backend/.env` only — never hardcoded,
never committed (`.env` is gitignored).

## Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: <http://localhost:8000/docs>
- The Next.js `frontend/` posts to `http://localhost:8000/api/verify`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | liveness + links |
| GET | `/api/health` | health + reference-data counts + (secret-free) config |
| GET | `/api/providers` | provider list with mock/operational status |
| POST | `/api/verify` | verify one claim |
| POST | `/api/batch` | verify many claims (per-item failures isolated) |

#### `POST /api/verify`

```json
{
  "user_id": "user_001",
  "claim_object": "car",
  "user_claim": "Customer: The rear bumper has a dent. Photo attached.",
  "image_paths": ["images/sample/case_001/img_1.jpg"],
  "provider": "gemini"
}
```

`provider` is optional (defaults to the server's `DEFAULT_PROVIDER`).
`image_paths` resolve against `DATASET_DIR` (default: the repo-level `dataset/`).

## Batch CSV run (standalone replacement for `code/main.py`)

```bash
python -m app.cli --input ../dataset/claims.csv --output ../output.csv
python -m app.cli --resume          # continue an interrupted run
LLM_MOCK=1 python -m app.cli         # force offline mock run
```

## Tests

```bash
cd backend
pytest                 # mock-mode suite — no network, no key
RUN_LIVE=1 pytest -m live   # also runs the gated live Gemini smoke test (spends quota)
```

## Configuration reference

See `.env.example`. Key variables: `DEFAULT_PROVIDER`, `GEMINI_API_KEY`,
`GEMINI_MODEL`, `GEMINI_RPM`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `LLM_MOCK`,
`MAX_RETRIES`, `DATASET_DIR`, `CORS_ORIGINS`, `LOG_LEVEL`.
