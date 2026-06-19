"""
Entry point (AGENTS.md S6 contract).

Reads an input claims CSV and writes a schema-valid output.csv.

Usage:
    python code/main.py                         # claims.csv -> ./output.csv
    python code/main.py --input dataset/sample_claims.csv --output out_sample.csv
    LLM_MOCK=1 python code/main.py              # force offline mock run

By default (no GEMINI_API_KEY set) it runs in MOCK_MODE: the full pipeline
executes and produces a schema-valid output.csv WITHOUT any API calls.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from data_io import (
    read_claims,
    read_evidence_requirements,
    read_user_history,
    write_output,
)
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline import run_pipeline


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Multi-Modal Evidence Review runner")
    p.add_argument("--input", type=Path, default=config.CLAIMS_CSV,
                   help="input claims CSV (default: dataset/claims.csv)")
    p.add_argument("--output", type=Path, default=config.DEFAULT_OUTPUT_CSV,
                   help="output predictions CSV (default: ./output.csv)")
    p.add_argument("--limit", type=int, default=0,
                   help="process only the first N rows (0 = all)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    print(f"[config] {config.summary()}", file=sys.stderr)
    if config.MOCK_MODE:
        print("[mode] MOCK_MODE - no API calls; output is placeholder analysis.",
              file=sys.stderr)

    records = read_claims(args.input)
    if args.limit:
        records = records[: args.limit]
    history = read_user_history()
    requirements = read_evidence_requirements()

    client = GeminiClient()
    cache = AnalysisCache()

    predictions = []
    for i, rec in enumerate(records, 1):
        predictions.append(
            run_pipeline(rec, history=history, requirements=requirements,
                         client=client, cache=cache)
        )
        print(f"[run] {i}/{len(records)} {rec.user_id}", file=sys.stderr)

    write_output(predictions, args.output)
    print(f"[done] wrote {len(predictions)} rows -> {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
