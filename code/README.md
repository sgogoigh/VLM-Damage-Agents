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

# Evaluate with Claude (Opus 4.8) as the VLM instead of Gemini:
#   runs in mock mode unless ANTHROPIC_API_KEY is set (handy for a demo).
python code/evaluation/main.py --provider claude

# Run the test suite (forced mock mode, no network):
python -m pytest code/tests/ -q

# Live smoke test on real images (makes real Gemini calls):
python code/smoke_live.py 2

# Live run: set a key in code/.env (GEMINI_API_KEY, GEMINI_MODEL), then:
#   python code/main.py             # dataset/claims.csv -> ./output.csv
#   python code/main.py --resume    # continue an interrupted (throttled) run

# Offline operational estimate (no API):
python code/evaluation/estimate_ops.py

# Build the submission archive (code.zip, excludes secrets/caches):
python make_submission.py
```

Free-tier `gemini-3.5-flash` is **~5 requests/minute**, so a full run is rate-
limited (~32 min for the test set). The client throttles to `GEMINI_RPM` and the
run is **resumable** (`--resume`) and **cached**, so it can be stopped/restarted.

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
| `GEMINI_API_KEY` | Gemini key (live mode). Missing key ⇒ Gemini MOCK_MODE. |
| `GEMINI_MODEL` | model id (default `gemini-2.0-flash`) |
| `ANTHROPIC_API_KEY` | Claude key for `--provider claude`. Missing key ⇒ Claude MOCK_MODE. |
| `CLAUDE_MODEL` | Claude model id (default `claude-opus-4-8`) |
| `LLM_MOCK` | `1` to force offline mock mode (both providers) |
| `MAX_CONCURRENCY`, `MAX_RETRIES` | throughput / resilience knobs |

Both `main.py` and `evaluation/main.py` accept `--provider {gemini,claude}`. The
provider is decided at the entry point; the pipeline is provider-agnostic because
both clients expose the same `generate_json(...)` interface (`llm/make_client`).

## Output
14 columns in the exact order from `problem_statement.md`, lowercase
`true`/`false` booleans, semicolon-joined `risk_flags`/`supporting_image_ids`.

## Roadmap (iteration 2+)
- Wire `_ensure_sdk` / `_live_call` for real Gemini vision calls.
- Add a final "decider" LLM pass for hard multi-image cases (identity mismatch).
- Fill `evaluation/evaluation_report.md` with real metrics + ≥2 strategies.
- Add concurrency + structured-output (`response_mime_type=application/json`).
