"""
Entry point (AGENTS.md S6 contract).

Reads an input claims CSV and writes a schema-valid output.csv.

Usage:
    python code/main.py                         # claims.csv -> ./output.csv
    python code/main.py --input dataset/sample_claims.csv --output out_sample.csv
    python code/main.py --resume                # continue an interrupted run
    LLM_MOCK=1 python code/main.py              # force offline mock run

Incremental + resumable: each prediction is appended as soon as it is computed,
so a long throttled run (free-tier ~5 RPM) can be stopped and resumed with
--resume without losing completed rows or re-spending cached calls.

By default (no GEMINI_API_KEY set) it runs in MOCK_MODE: the full pipeline
executes and produces a schema-valid output.csv WITHOUT any API calls.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from code import config
from code.data_io import (
    append_output_row,
    count_output_rows,
    read_claims,
    read_evidence_requirements,
    read_user_history,
    write_output,
)
from llm import make_client
from llm.cache import AnalysisCache
from pipeline import run_pipeline


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Multi-Modal Evidence Review runner")
    p.add_argument("--input", type=Path, default=config.CLAIMS_CSV,
                   help="input claims CSV (default: dataset/claims.csv)")
    p.add_argument("--output", type=Path, default=config.DEFAULT_OUTPUT_CSV,
                   help="output predictions CSV (default: ./output.csv)")
    p.add_argument("--limit", type=int, default=0,
                   help="process only the first N rows (0 = all)")
    p.add_argument("--resume", action="store_true",
                   help="skip rows already present in --output and append the rest")
    p.add_argument("--provider", choices=["gemini", "claude"], default="gemini",
                   help="VLM provider for the perception layer (default: gemini)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    print(f"[config] {config.summary()}", file=sys.stderr)

    records = read_claims(args.input)
    if args.limit:
        records = records[: args.limit]
    history = read_user_history()
    requirements = read_evidence_requirements()

    client = make_client(args.provider)
    print(f"[provider] {args.provider}", file=sys.stderr)
    if client.mock:
        print("[mode] MOCK_MODE - no API calls; output is placeholder analysis "
              "(no API key for this provider).", file=sys.stderr)
    cache = AnalysisCache()

    # Resume support: completed rows are written in input order, so we can skip
    # the first `done` rows. Without --resume we start a fresh output file.
    done = count_output_rows(args.output) if args.resume else 0
    if not args.resume:
        # Truncate/create with just the header so appends produce a clean file.
        write_output([], args.output)
    if done:
        print(f"[resume] {done} rows already done; continuing.", file=sys.stderr)

    total = len(records)
    for i, rec in enumerate(records):
        if i < done:
            continue
        pred = run_pipeline(rec, history=history, requirements=requirements,
                            client=client, cache=cache)
        append_output_row(pred, args.output)
        print(f"[run] {i + 1}/{total} {rec.user_id} -> {pred.claim_status}",
              file=sys.stderr)

    print(f"[done] {args.output} now has {count_output_rows(args.output)} rows",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
