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

Both strategies share the same vocab-constrained per-image VLM analysis; they
differ only in the final decision step (toggle with the `USE_DECIDER` env var):

| Strategy | How to run | Description | claim_status acc |
|---|---|---|---|
| A. Deterministic | `USE_DECIDER=0 python code/evaluation/main.py` | per-image findings + transparent rule layer (`decision.py`) | _fill after live run_ |
| B. Decider | `USE_DECIDER=1 python code/evaluation/main.py` | adds a cross-image LLM synthesis pass for multi-image / injection / authenticity cases | _fill after live run_ |

Observed so far (single-claim live checks, pre-full-eval):
- Strategy B fixed the multi-image identity-mismatch case (sample case_002 →
  `not_enough_information`) that Strategy A got wrong.
- Strategy A is preferable on simple single-image claims (no over-skepticism);
  this is why B is *gated* to only the harder cases via `_needs_decider`.

Final strategy chosen for `output.csv`: **B with gating** (decider only where it
helps; deterministic elsewhere). Full sample-set accuracy table to be filled
once the free-tier quota resets (run is ~12 min for the sample set at 5 RPM).

## 3. Sample-set metrics

_Run:_ `python code/evaluation/main.py`

- rows scored: _TBD_
- claim_status accuracy: _TBD_
- per-field accuracy: _TBD_
- claim_status confusion (expected→predicted): _TBD_

## 4. Operational analysis

Computed offline by `python code/evaluation/estimate_ops.py` (no API).
Token figures use documented per-call assumptions (parse ~350/80, image
~600/150, decider ~700/160 in/out); image input tokens dominate.

| Metric | Sample set | Full test set | Notes |
|---|---|---|---|
| Claims (rows) | 20 | 44 | CSV row counts |
| Image references | 29 | 82 | from `image_paths` |
| Unique images (deduped) | 29 | 82 | content-hash; **0 duplicates** in this data |
| Parse calls | 20 | 44 | 1 text call/claim (cached on re-run) |
| Image (VLM) calls | 29 | 82 | 1/unique image (cached) |
| Decider calls | 9 | 32 | only multi-image / injection / authenticity |
| **Total model calls** | **58** | **158** | parse + image + decider |
| Input tokens (approx) | ~30.7k | ~87.0k | image tokens dominate |
| Output tokens (approx) | ~7.4k | ~20.9k | small JSON/call |
| Cost | $0 (free tier) | $0 (free tier) | paid-tier = price/1M × tokens above |
| Runtime @ 5 RPM | ~11.6 min | ~31.6 min | dominated by the rate limit, not compute |

Re-runs are far cheaper: parse + image + decider results are all cached, so a
repeat run makes ~0 new calls unless prompts/model change.

## 5. Rate limits, batching, caching, retries

- **TPM/RPM (measured):** free-tier `gemini-3.5-flash` returned HTTP 429
  `RESOURCE_EXHAUSTED` with `limit: 5` — i.e. **5 requests/minute** per project
  per model on the free tier (plus daily RPD caps). This dominates runtime.
- **Client-side throttle:** `GeminiClient._throttle()` spaces calls to stay
  within `GEMINI_RPM` (default 5) over a rolling 60s window, so batch runs do
  not trip the limit.
- **Retry strategy:** on 429 we parse the server's suggested `retryDelay`
  (e.g. "retry in 39s") and wait exactly that long; otherwise exponential
  backoff. `MAX_RETRIES` default 5.
- **Caching:** per-image content-hash cache (`code/llm/cache.py`), namespaced by
  prompt-version + model, avoids re-analyzing duplicate/repeated images and
  makes re-runs near-free. The decider response is cached too (keyed by its full
  text input).
- **Call reduction:** the cross-image decider runs only for multi-image /
  injection / authenticity cases (`_needs_decider`); simple single-image claims
  use the free deterministic decision layer.
- **Runtime implication:** at 5 RPM, the full test set (~157 calls worst case)
  takes ~30+ minutes wall-clock; a paid tier or higher `GEMINI_RPM` cuts this
  proportionally. Caching makes re-runs far cheaper.
- **Determinism:** Gemini 3.x ignores temperature/top_p/top_k; we use
  `thinking_level=low` for low-variance JSON, and the decision layer is
  deterministic, so only perception is model-driven.
