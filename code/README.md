# Multi-Modal Evidence Review — Solution (`code/`)

Verifies damage claims (car / laptop / package) from submitted images, a claim
conversation, user history, and minimum evidence requirements. For each row in
`dataset/claims.csv` it produces one schema-valid row in `output.csv`.

Provider: **Google Gemini** (free tier) via `google-genai`. Secrets are read
from the environment only.

> **Iteration 1 status:** full scaffold. Runs end-to-end in **MOCK_MODE** (no
> API calls) and produces a schema-valid `output.csv`. The live Gemini call is
> stubbed (`llm/gemini_client.py::_live_call`) and wired in iteration 2.

## Quickstart

```bash
pip install -r code/requirements.txt          # optional for mock run

# Offline scaffold run (no key needed):
LLM_MOCK=1 python code/main.py --input dataset/sample_claims.csv --output out_sample.csv

# Evaluate against labeled sample set:
LLM_MOCK=1 python code/evaluation/main.py

# Run the test suite (forced mock mode, no network):
python -m pytest code/tests/ -q

# Live smoke test on real images (makes real Gemini calls):
python code/smoke_live.py 2

# Live run (iteration 2): set a key, then:
#   cp code/.env.example code/.env  &&  edit GEMINI_API_KEY
#   python code/main.py             # dataset/claims.csv -> ./output.csv
```

On Windows PowerShell, set the mock flag with `$env:LLM_MOCK=1` before running.

## Architecture

```
main.py                      CLI: read claims.csv -> output.csv
evaluation/main.py           score pipeline on sample_claims.csv labels
config.py                    env/secret loading, paths, model + mock flags
schema.py                    exact output columns + closed allowed-value lists
data_io.py                   CSV read/write, image path + image-id resolution
llm/
  gemini_client.py           single provider wrapper (mock + retry/backoff)
  cache.py                   per-image content-hash analysis cache
prompts/
  claim_parser.md            transcript -> claimed part/issue
  image_analysis.md          per-image VLM inspection -> strict JSON
pipeline/
  claim_parser.py   (1)      parse the claim
  image_analysis.py (2)      per-image VLM findings (cached/deduped)
  decision.py       (3)      requirements-aware deterministic decision
  risk.py           (4)      user-history risk overlay (context only)
  orchestrator.py            run all 4 stages -> PredictionRow
```

### Design principles
- **Images are the source of truth.** History only adds `risk_flags`; it never
  flips `claim_status` (`pipeline/risk.py`).
- **Schema can't break.** Every emitted value is coerced to an allowed token in
  `schema.py` before writing, in the exact required column order.
- **Cost/latency aware.** Each unique image is analyzed once (content-hash
  cache); re-runs are near-free. Retries use exponential backoff for free-tier
  rate limits.
- **Deterministic decisions.** Only perception is model-driven; the decision
  layer is transparent rules, so behavior is reproducible.

## Environment variables

| Var | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini key (live mode). Missing key ⇒ MOCK_MODE. |
| `GEMINI_MODEL` | model id (default `gemini-2.0-flash`) |
| `LLM_MOCK` | `1` to force offline mock mode |
| `MAX_CONCURRENCY`, `MAX_RETRIES` | throughput / resilience knobs |

## Output
14 columns in the exact order from `problem_statement.md`, lowercase
`true`/`false` booleans, semicolon-joined `risk_flags`/`supporting_image_ids`.

## Roadmap (iteration 2+)
- Wire `_ensure_sdk` / `_live_call` for real Gemini vision calls.
- Add a final "decider" LLM pass for hard multi-image cases (identity mismatch).
- Fill `evaluation/evaluation_report.md` with real metrics + ≥2 strategies.
- Add concurrency + structured-output (`response_mime_type=application/json`).
