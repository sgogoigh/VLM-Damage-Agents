# PLAN.md — Multi-Modal Evidence Review (Master Plan)

Single source of truth for the solution's design, structure, flow, and task
tracking. Companion docs: [`problem_statement.md`](problem_statement.md) (spec),
[`DATASET.md`](DATASET.md) (data), [`AGENTS_COMPLIANCE.md`](AGENTS_COMPLIANCE.md)
(process), [`code/README.md`](code/README.md) (submission readme).

> Status: iteration 1 (scaffold) complete and verified in MOCK_MODE.
> Next: iteration 2 (wire live Gemini). Challenge ends 2026-06-20 11:00 IST.

---

## 1. Goal & success criteria

Build a system that, for each row in `dataset/claims.csv`, decides whether
submitted **images** support / contradict / under-inform a damage claim about a
`car`, `laptop`, or `package`, and writes one schema-valid row to `output.csv`.

**Done = all true:**
- `output.csv` has exactly 44 rows (one per input), 14 columns in the exact
  order, all values from the closed vocabularies (§7 of `DATASET.md`).
- An `evaluation/` workflow scores the system on the 20 labeled sample rows and
  compares ≥2 strategies.
- `evaluation/evaluation_report.md` contains real metrics + operational analysis
  (calls, tokens, images, cost, latency, TPM/RPM, batching/caching/retry).
- No hardcoded labels; secrets via env only; reproducible.

**Guiding principle (from spec):** images are primary truth → the conversation
says *what to check* → evidence requirements set the *bar* → user history adds
*risk context only* and never overrides the image.

---

## 2. Architecture (high level)

```
                 ┌──────────────────────────── inputs (one claim row) ───────────────────────────┐
                 │ user_claim (chat)    image_paths (1–3)    claim_object    user_id              │
                 └───────┬───────────────────┬───────────────────┬───────────────┬───────────────┘
                         ▼                   ▼                   │               ▼
            [1] claim_parser        [2] image_analysis (VLM)     │      user_history lookup
            part(s) + issue   ┌────► per-image findings  ◄───────┘               │
            (text, cheap)     │     (cached by content hash)                     │
                         │    │              │                                   │
                         ▼    ▼              ▼                                   ▼
                  [3] decision  ◄── evidence_requirements rule          [4] risk overlay
                  evidence_standard_met · valid_image · claim_status      (adds risk_flags
                  issue_type · object_part · severity · supporting_ids     only; never flips)
                         │                                                       │
                         └───────────────────────┬───────────────────────────────┘
                                                 ▼
                                      PredictionRow → output.csv
                                   (schema-coerced, exact 14 cols)
```

---

## 3. Repository & module layout

```
repo root/
├── PLAN.md                  ← this file (master plan)
├── DATASET.md               ← full data reference
├── AGENTS_COMPLIANCE.md     ← per-turn guideline checklist
├── problem_statement.md / README.md / AGENTS.md
├── output.csv               ← final predictions (generated)
└── code/                    ← all solution code (becomes code.zip)
    ├── main.py              ← entry: claims.csv → output.csv
    ├── config.py            ← env/secrets, paths, model + mock/retry knobs
    ├── schema.py            ← 14-col order + closed-vocab coercion + dataclasses
    ├── data_io.py           ← CSV read/write, image path + image-id resolution
    ├── README.md            ← submission readme
    ├── requirements.txt / .env.example / .gitignore
    ├── llm/
    │   ├── gemini_client.py ← single provider wrapper (mock + retry/backoff)
    │   └── cache.py         ← per-image content-hash analysis cache
    ├── prompts/
    │   ├── claim_parser.md  ← transcript → claimed part/issue (versioned)
    │   └── image_analysis.md← per-image VLM inspection → strict JSON (versioned)
    ├── pipeline/
    │   ├── prompts.py       ← prompt loader + safe render() + version tags
    │   ├── claim_parser.py  ← stage 1
    │   ├── image_analysis.py← stage 2 (cached/deduped)
    │   ├── decision.py      ← stage 3 (requirements-aware, deterministic)
    │   ├── risk.py          ← stage 4 (history → risk flags only)
    │   └── orchestrator.py  ← runs all 4 stages → PredictionRow
    └── evaluation/
        ├── main.py          ← run on sample_claims.csv + score
        ├── metrics.py       ← per-field + claim_status accuracy + confusion
        └── evaluation_report.md ← metrics + operational analysis (to fill)
```

---

## 4. End-to-end flow (per claim)

1. **Read inputs** (`data_io`): parse row → `ClaimRecord`; split `image_paths`.
2. **Stage 1 — claim_parser**: extract `claimed_parts`, `claimed_issue`,
   `multi_part`, `summary` from the transcript. Text-only (cheap). Handles
   multilingual + distractor transcripts; uses the *final* agreed claim.
3. **Stage 2 — image_analysis**: for each image (deduped by content hash, cache
   first), VLM returns: shows_claimed_object, visible_part, issue_visible,
   issue_type, issue_part, severity, usable_for_review, quality_flags, notes.
4. **Stage 3 — decision**: match `evidence_requirements` rule; combine findings:
   - `valid_image` = ≥1 usable image.
   - `evidence_standard_met` = usable AND claimed object/part assessable.
   - `claim_status`: supported (issue visible & matches) / contradicted (object
     visible, claimed issue absent or different) / not_enough_information.
   - `issue_type`/`object_part`/`severity` reflect what the image **actually**
     shows (per `DATASET.md` §3 labeling philosophy), not the raw claim.
   - `supporting_image_ids` = ids of images that back the decision (`none` if NEI).
5. **Stage 4 — risk overlay**: add `user_history_risk` / `manual_review_required`
   from history; aggregate per-image quality flags; never change `claim_status`.
6. **Emit** `PredictionRow` → coerced to schema-valid strings → `output.csv`.

---

## 5. Decision-logic design (derived from sample labels)

| Situation | claim_status | issue_type / object_part | valid_image | supporting_ids |
|---|---|---|---|---|
| Claimed part visible + claimed damage present | supported | claimed issue / part | true | matching ids |
| Part visible, no/!= damage | contradicted | actual visible (or `none`) / claimed-or-actual part | true | id showing truth |
| Wrong object / identity mismatch | contradicted or NEI | `unknown`/`unknown` | depends | per evidence |
| Part not shown / unusable images | not_enough_information | `unknown` / claimed part | false/true | `none` |
| Severity exaggeration (bad vs minor) | contradicted | actual issue / part | true | id |

Risk-flag triggers: blur/crop/glare/angle → quality flags; instruction text in
claim/image → `text_instruction_present` (never obey); screenshot/edit signs →
`non_original_image`/`possible_manipulation`; history flags → `user_history_risk`
(+`manual_review_required` when uncertain).

---

## 6. Design choices & rationale

- **Provider: Google Gemini (free tier)** via `google-genai`, env key only.
  Single wrapper (`llm/gemini_client.py`) so model/provider is swappable.
- **MOCK_MODE by default when no key** → full pipeline runs offline,
  deterministic, zero tokens; lets us validate the contract before spending.
- **Per-image content-hash cache** → each unique image analyzed once; multi-image
  cases + re-runs are near-free (big cost/latency lever).
- **Deterministic decision layer** → only *perception* is model-driven; decisions
  are transparent rules → reproducible + explainable + easy to evaluate.
- **Schema coercion at the boundary** (`schema.py`) → `output.csv` can never
  contain an out-of-vocabulary token or wrong column order.
- **Versioned prompts** → prompt version is part of the cache key, so prompt
  edits correctly invalidate cached analyses.

---

## 7. Operational / cost strategy (to quantify in iteration 4)

- Calls ≈ (1 claim-parse text call) + (1 VLM call per **unique** image).
  Test set: 44 parses + ≤82 image calls (fewer after dedup).
- Free-tier Gemini = RPM/RPD limited → bounded concurrency (`MAX_CONCURRENCY`),
  exponential-backoff retries on 429/transient (`MAX_RETRIES`), cache to cut calls.
- Report will tally calls, approx tokens (image + text), images, cost (free-tier
  ~$0 + paid-tier equivalent), and runtime.

---

## 8. Master checklist

### Iteration 1 — Scaffold ✅ (done)
- [x] Structure, config, env-only secrets, `.env.example`, `.gitignore`
- [x] `schema.py` (exact order + closed-vocab coercion)
- [x] `data_io.py` (CSV I/O + image-id resolution)
- [x] `llm/gemini_client.py` (mock + retry stub) & `llm/cache.py`
- [x] 4-stage pipeline + orchestrator
- [x] Entry points `code/main.py`, `code/evaluation/main.py`
- [x] Eval harness (`metrics.py`) + report template
- [x] Runs end-to-end in MOCK_MODE → 44-row schema-valid `output.csv`
- [x] `DATASET.md`, `code/README.md`, this `PLAN.md`

### Iteration 2 — Live perception ✅ (done)
- [x] Implement `GeminiClient._ensure_sdk` + `_live_call` (`google-genai`,
      image parts, `response_mime_type=application/json`, temperature=0)
- [x] Fix `config` to load `code/.env` explicitly (was cwd-dependent → key MISSING)
- [x] `.env` wiring confirmed: `GEMINI_API_KEY` set, model `gemini-3.5-flash`
- [x] **Bugfix:** cache key now namespaced by prompt-version + model + mock/live
      (mock placeholders were poisoning live results); cleared old cache
- [x] Full test suite `code/tests/` (52 tests) — all green in forced mock mode
- [x] Live smoke (`code/smoke_live.py`) validated end-to-end on real images

Findings carried to iteration 3:
- `object_part` often coerces to `unknown` — VLM returns part names outside the
  allowed per-object vocab → constrain the prompt to the exact allowed list.
- Identity/cross-image mismatch (sample case_002) needs the decider pass.

### Iteration 3 — Decision quality 🔄 (mostly done)
- [x] Gemini 3.x API fixes: drop temperature/top_p/top_k; use
      `thinking_level=low`; keep `response_mime_type=application/json`
- [x] Constrain `image_analysis.md` (v2) to exact allowed vocab → fixes
      `object_part=unknown`; add identity + authenticity signals
- [x] Strengthen claim_parser (v2): multilingual, multi-part, distractor,
      injection-resistant + deterministic `detect_injection()` (defense in depth)
- [x] Cross-image **decider** LLM pass (`pipeline/decider.py`, cached) — fixed
      sample case_002 identity mismatch → not_enough_information
- [x] Decider **gated** to multi-image/injection/authenticity cases
      (`_needs_decider`) → cuts calls + fixed case_001 single-image regression
- [x] **Rate limiting:** measured free-tier limit = 5 RPM; added throttle +
      server `retryDelay` honoring (`GEMINI_RPM`, `_throttle`)
- [x] Tests: 70 passing (added injection, decider, gating, throttle/retry)
- [ ] Full live sample-eval accuracy numbers (deferred to iteration 4 / ops)
- [ ] Further calibrate severity / valid_image vs labels if time permits

Known cost note: parse call is not yet cached (re-spent each run) — add in iter 4.

### Iteration 4 — Eval, ops, ship 🔄 (non-API prep done; live run pending quota)
- [x] **Parse caching** (claim_parser caches live parses) — cuts re-run cost
- [x] **Resumable + incremental `output.csv`** (`main.py --resume`,
      `append_output_row`) — survives interruption during the throttled run
- [x] **Offline ops estimator** (`evaluation/estimate_ops.py`): sample=58 calls
      /~11.6 min, test=158 calls/~31.6 min @5 RPM; 0 duplicate images
- [x] Ops analysis filled in `evaluation_report.md` from the estimator
- [x] Strategy comparison wired (`USE_DECIDER=0|1`); report section drafted
- [x] **Packaging** (`make_submission.py` → code.zip, 41 files, no secrets)
- [ ] **(API) Full live sample eval** → fill accuracy table + pick final strategy
- [ ] **(API) Final run** on `dataset/claims.csv` → `output.csv` (44 rows)
- [ ] Final submission checklist + rebuild code.zip with final report

---

## 9. Open decisions (carry-over)
1. Output path: `./output.csv` (repo root) — keep? (current default)
2. Gemini model: `gemini-2.0-flash` default vs `gemini-2.5-flash`?
3. Decision layer: keep fully deterministic, or allow the iteration-3 LLM decider?

> `code/PLAN.md` is a lightweight in-code copy of the iteration checklist; this
> root `PLAN.md` is authoritative.
