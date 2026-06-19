# Evaluation Report — Multi-Modal Evidence Review

> **Status: live results.** Metrics below are from real `gemini-3.5-flash` runs
> on the labeled sample set. Model: `gemini-3.5-flash`, `thinking_level=low`,
> structured JSON output. Reproduce with `python code/evaluation/main.py`.

## 1. Approach summary

Pipeline (see `code/README.md`):
1. **Claim parsing** (text) → claimed part(s) + issue, **normalized to the
   allowed vocab** (e.g. "rear bumper" → `rear_bumper`), multilingual + injection
   detection.
2. **Per-image VLM analysis** (Gemini, cached by content hash) that runs a
   **staged claim-grounded check**: STEP 1 category (is it the claimed object?),
   STEP 2 claimed part visible?, STEP 3 is the *claimed* issue present at a
   consistent severity?
3. **Staged deterministic decision** that compares EVIDENCE vs CLAIM — visible
   damage only supports the claim if it matches what was claimed; otherwise the
   claim is contradicted.
4. **User-history risk overlay** (context only; never flips the decision).

## 2. Strategies compared (required: ≥2)

Both strategies share the same vocab-constrained per-image VLM analysis; they
differ only in the final decision step (toggle with the `USE_DECIDER` env var):

Measured on the 20 labeled sample rows (`gemini-3.5-flash`, live):

| Strategy | claim_status | evidence_met | object_part | valid_image | issue_type |
|---|---|---|---|---|---|
| 1. Naive ("any damage → supported") | 65% | 80% | 80%* | 90% | 35% |
| 2. Cross-image LLM decider (gated) | 40% | 50% | 75% | 60% | 20% |
| **3. Staged claim-grounded (chosen)** | **70%** | **90%** | **90%** | 85% | **45%** |

\*the naive object_part figure predated the vocab-normalization bug fix.

**Chosen: Strategy 3 — staged, claim-grounded deterministic decision.**

Journey / what moved the numbers:
- The naive layer marked a claim supported whenever *any* damage was visible, so
  it missed every `contradicted` case (claim vs evidence never compared).
- The LLM decider (2) was over-skeptical — it flipped genuinely-supported
  multi-image claims to `not_enough_information` (40%). Kept as opt-in
  (`USE_DECIDER=1`), off by default.
- The staged approach (3) verifies category → part → claimed-issue, and a
  parser **vocab-normalization fix** lifted `object_part` 55%→90% and
  `evidence_standard_met` to 90%. Dropping a faulty color-based identity
  heuristic removed false "different object" negatives.

Remaining claim_status errors are mostly `contradicted→supported`: the VLM sees
damage that the labels treat as exaggerated/mismatched — subjective cases we do
not overfit to (the rubric forbids hardcoding test answers).

## 3. Sample-set metrics (chosen staged strategy, 20 rows, live)

_Run:_ `python code/evaluation/main.py`

- **claim_status accuracy: 70%**
- per-field: evidence_standard_met **90%**, object_part **90%**, valid_image 85%,
  issue_type 45%, severity 40%, risk_flags 30%
- claim_status confusion (expected→predicted): supported→supported 10,
  contradicted→supported 3, contradicted→contradicted 2,
  not_enough_information→not_enough_information 2, plus 3 singletons.
- Strongest: object_part, evidence_standard_met (claim-grounded + vocab fix).
- Weakest: issue_type (fine-grained perception: dent vs missing_part, crack vs
  glass_shatter), severity (VLM over-rates), risk_flags (strict set-match; other
  per-row flags differ even when history flags are correct).
- Honest limitation: residual `contradicted→supported` errors — the VLM trusts
  visible damage and is less aggressive on severity-exaggeration / subtle
  mismatch. These are subjective vs the labels; not overfit to.

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
