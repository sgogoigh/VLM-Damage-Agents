# Evaluation Report — Multi-Modal Evidence Review

> **Status: live results.** Metrics below are from real `gemini-3.5-flash` runs
> on the labeled sample set. Model: `gemini-3.5-flash`, `thinking_level=low`,
> structured JSON output. Reproduce with `python code/evaluation/main.py`.

## 1. Approach summary

Four-stage pipeline (see `code/README.md`):
1. Claim parsing (text) → claimed part(s) + issue
2. Per-image VLM analysis (Gemini, cached by image content hash)
3. Requirements-aware deterministic decision layer
4. User-history risk overlay (context only)

## 2. Strategies compared (required: ≥2)

Both strategies share the same vocab-constrained per-image VLM analysis; they
differ only in the final decision step (toggle with the `USE_DECIDER` env var):

Measured on the 20 labeled sample rows (`gemini-3.5-flash`, live):

| Strategy | How to run | claim_status | evidence_met | object_part | valid_image | severity |
|---|---|---|---|---|---|---|
| **A. Deterministic (chosen)** | `USE_DECIDER=0 python code/evaluation/main.py` | **65%** | 80% | 80% | 90% | 50% |
| B. Decider (gated) | `USE_DECIDER=1 python code/evaluation/main.py` | 40% | 50% | 75% | 60% | 40% |

**Decision:** Strategy A (deterministic rule layer over per-image findings) is
the chosen strategy for `output.csv`. Although the decider (B) was designed to
catch cross-image identity mismatches (and does fix sample case_002), on the
full sample it is **over-skeptical** — it flipped 5 genuinely-supported
multi-image claims to `not_enough_information`, dropping claim_status accuracy to
40%. The deterministic layer already includes an identity-mismatch heuristic, so
A keeps most of B's upside without the false negatives. The decider remains
available via `USE_DECIDER=1` as a documented alternative.

claim_status confusion (A, expected→predicted): supported→supported 12,
contradicted→supported 3, contradicted→not_enough_information 2,
not_enough_information→supported 2, not_enough_information→not_enough_information 1.

## 3. Sample-set metrics (chosen strategy A, 20 rows, live)

_Run:_ `python code/evaluation/main.py`

- claim_status accuracy: **65%**
- per-field accuracy: evidence_standard_met 80%, object_part 80%,
  valid_image 90%, severity 50%, issue_type 35%, risk_flags 30%
- Strongest fields: valid_image, evidence_standard_met, object_part (the
  vocab-constraint fix). Weakest: issue_type (fine-grained perception, e.g.
  dent vs missing_part, crack vs glass_shatter) and risk_flags (gold is
  selective about user_history_risk/manual_review).
- Honest limitation: the main error mode is missing some `contradicted` cases
  (predicted `supported`) — the system trusts visible damage and is less
  aggressive at severity-exaggeration / subtle-mismatch detection.

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
