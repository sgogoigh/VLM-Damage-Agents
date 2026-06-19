"""
Offline operational estimate (NO API calls).

Computes, for the sample and test sets: claim counts, image refs, unique images
after content-hash dedup, decider-eligible claims, projected live API calls, and
rough token/cost/runtime estimates under the free-tier 5 RPM limit. Feeds the
operational analysis in evaluation_report.md.

Run:  python code/evaluation/estimate_ops.py
"""
from __future__ import annotations

import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_DIR))

import config  # noqa: E402
import data_io as IO  # noqa: E402
from llm.cache import image_content_hash  # noqa: E402
from pipeline.claim_parser import detect_injection  # noqa: E402

# Rough per-call token assumptions (documented; adjust if measured).
TOK_PARSE_IN, TOK_PARSE_OUT = 350, 80
TOK_IMAGE_IN, TOK_IMAGE_OUT = 600, 150        # image tokens dominate the input
TOK_DECIDER_IN, TOK_DECIDER_OUT = 700, 160
RPM = config.GEMINI_RPM


def estimate(csv_path: Path, label: str) -> dict:
    claims = IO.read_claims(csv_path)
    n_claims = len(claims)
    all_refs, hashes = 0, {}
    multi_image = 0
    injection_single = 0
    for c in claims:
        present = []
        for rel in c.image_path_list:
            all_refs += 1
            p = IO.resolve_image_path(rel)
            if p.exists():
                present.append(p)
                h = image_content_hash(p)
                hashes[h] = hashes.get(h, 0) + 1
        if len(present) >= 2:
            multi_image += 1
        elif detect_injection(c.user_claim):
            injection_single += 1

    unique_images = len(hashes)
    decider_calls = multi_image + injection_single

    parse_calls = n_claims
    image_calls = unique_images           # cached/deduped
    total_calls = parse_calls + image_calls + decider_calls

    in_tok = (parse_calls * TOK_PARSE_IN + image_calls * TOK_IMAGE_IN
              + decider_calls * TOK_DECIDER_IN)
    out_tok = (parse_calls * TOK_PARSE_OUT + image_calls * TOK_IMAGE_OUT
               + decider_calls * TOK_DECIDER_OUT)
    runtime_min = total_calls / max(1, RPM)

    return {
        "label": label, "claims": n_claims, "image_refs": all_refs,
        "unique_images": unique_images, "dup_images": all_refs - unique_images,
        "multi_image_claims": multi_image, "injection_single": injection_single,
        "parse_calls": parse_calls, "image_calls": image_calls,
        "decider_calls": decider_calls, "total_calls": total_calls,
        "in_tokens": in_tok, "out_tokens": out_tok,
        "runtime_min_at_rpm": round(runtime_min, 1),
    }


def main() -> int:
    print(f"[assumptions] RPM={RPM}, model={config.GEMINI_MODEL}")
    print(f"[token/call] parse~{TOK_PARSE_IN}/{TOK_PARSE_OUT} "
          f"image~{TOK_IMAGE_IN}/{TOK_IMAGE_OUT} "
          f"decider~{TOK_DECIDER_IN}/{TOK_DECIDER_OUT} (in/out)\n")
    for path, label in [(config.SAMPLE_CLAIMS_CSV, "sample"),
                        (config.CLAIMS_CSV, "test")]:
        e = estimate(path, label)
        print(f"=== {label.upper()} ===")
        for k, v in e.items():
            if k != "label":
                print(f"  {k:22s}: {v}")
        print()
    print("Free-tier cost: $0 (within free quota). Paid-tier cost depends on the "
          "model's per-1M token price x tokens above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
