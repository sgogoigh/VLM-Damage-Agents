# Build Plan

> **The authoritative master plan is [`../PLAN.md`](../PLAN.md)** (repo root).
> This file is a lightweight in-code iteration checklist kept for `code.zip`.


## Iteration 1 — Scaffold (DONE)
- [x] Project structure, config, env-only secrets (`.env.example`, `.gitignore`)
- [x] Exact output schema + closed allowed-value coercion (`schema.py`)
- [x] CSV I/O + image-path / image-id resolution (`data_io.py`)
- [x] Gemini client wrapper with **mock mode** + retry/backoff (stub `_live_call`)
- [x] Per-image content-hash analysis **cache** (`llm/cache.py`)
- [x] 4-stage pipeline: parse → image analysis → decision → risk overlay
- [x] Entry points: `code/main.py`, `code/evaluation/main.py`
- [x] Evaluation harness with per-field + claim_status metrics
- [x] Runs end-to-end in MOCK_MODE → schema-valid `output.csv` (44 rows), no API calls
- [x] README + evaluation_report template

**Validated:** `LLM_MOCK=1 python code/main.py` produces 44 rows; eval scores 20 sample rows.
Mock metrics are placeholders (no real perception) — they only prove wiring.

## Iteration 2 — Live perception
- [ ] Implement `GeminiClient._ensure_sdk` / `_live_call` with `google-genai`
      (image parts + `response_mime_type="application/json"`).
- [ ] Verify per-image JSON parsing + caching against a few real sample images.
- [ ] Tune `image_analysis.md` prompt against sample labels.

## Iteration 3 — Decision quality
- [ ] Add optional final "decider" LLM pass for hard multi-image cases
      (e.g. sample case_002: two photos of different cars → not_enough_information
      with `wrong_object;claim_mismatch;manual_review_required`).
- [ ] Improve claim-parser (multilingual transcripts, multi-part claims).
- [ ] Calibrate risk-flag and severity mapping to sample labels.

## Iteration 4 — Eval + ops + ship
- [ ] Compare ≥2 strategies; fill real metrics in `evaluation_report.md`.
- [ ] Add concurrency (`MAX_CONCURRENCY`) + measured operational analysis
      (calls, tokens, images, cost, latency, TPM/RPM).
- [ ] Final run on `dataset/claims.csv` → `output.csv`; package `code.zip`.

## Open questions for the user
1. Output location: currently `./output.csv` (repo root). Keep, or `dataset/output.csv`?
2. Gemini model: default `gemini-2.0-flash`. OK, or prefer `gemini-2.5-flash`?
3. Decision layer: keep fully deterministic, or allow the iteration-3 LLM decider?
