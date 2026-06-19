# Evaluation Report — Multi-Modal Evidence Review

> **Status: TEMPLATE (iteration 1).** Numbers below are placeholders to be
> filled once live Gemini calls are wired in (iteration 2). The scaffold
> currently runs in MOCK_MODE, so any metrics it prints reflect placeholder
> analysis, not real model quality.

## 1. Approach summary

Four-stage pipeline (see `code/README.md`):
1. Claim parsing (text) → claimed part(s) + issue
2. Per-image VLM analysis (Gemini, cached by image content hash)
3. Requirements-aware deterministic decision layer
4. User-history risk overlay (context only)

## 2. Strategies compared (required: ≥2)

| Strategy | Description | claim_status acc | Notes |
|---|---|---|---|
| A. baseline | one VLM call per image + rule decision | _TBD_ | |
| B. _TBD_ | e.g. combined multi-image single call, or final decider LLM | _TBD_ | |

Final strategy chosen for `output.csv`: _TBD_.

## 3. Sample-set metrics

_Run:_ `python code/evaluation/main.py`

- rows scored: _TBD_
- claim_status accuracy: _TBD_
- per-field accuracy: _TBD_
- claim_status confusion (expected→predicted): _TBD_

## 4. Operational analysis (required)

| Metric | Sample set | Full test set | Assumptions |
|---|---|---|---|
| Claims (rows) | 20 | 44 | from CSV row counts |
| Images processed | _TBD_ | _TBD_ | counted from image_paths; deduped by content hash |
| Model calls | _TBD_ | _TBD_ | ≈ 1 parse + 1 per unique image |
| Input tokens (approx) | _TBD_ | _TBD_ | image tokens + prompt text |
| Output tokens (approx) | _TBD_ | _TBD_ | small JSON per call |
| Cost (approx) | _TBD_ | _TBD_ | Gemini free tier → ~$0; note paid-tier equivalent |
| Runtime / latency | _TBD_ | _TBD_ | with concurrency=N |

## 5. Rate limits, batching, caching, retries

- **TPM/RPM:** Gemini free tier is RPM/RPD limited — describe the limit used.
- **Caching:** per-image content-hash cache (`code/llm/cache.py`) avoids
  re-analyzing duplicate/repeated images and makes re-runs near-free.
- **Throttling/concurrency:** `MAX_CONCURRENCY` bounds parallel calls.
- **Retries:** exponential backoff on transient/429 errors (`MAX_RETRIES`).
- **Determinism:** decision layer is fully deterministic; only perception is
  model-driven.
