"""
Standalone batch runner — read an input claims CSV and write a schema-valid
output.csv, reusing the exact same pipeline the API serves.

Usage (from backend/)::

    python -m app.cli                                   # claims.csv -> ./output.csv
    python -m app.cli --input ../dataset/sample_claims.csv --output out_sample.csv
    python -m app.cli --resume                          # continue an interrupted run
    LLM_MOCK=1 python -m app.cli                        # force offline mock run

Incremental + resumable: each prediction is appended as soon as it is computed,
so a long throttled run (free-tier ~5 RPM) can be stopped and resumed with
--resume without losing completed rows or re-spending cached calls.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.core.data_io import append_output_row, count_output_rows, read_claims, write_output
from app.service import ClaimVerifierService


def parse_args(argv: list[str]) -> argparse.Namespace:
    settings = get_settings()
    p = argparse.ArgumentParser(description="Multi-Modal Evidence Review batch runner")
    p.add_argument("--input", type=Path, default=settings.claims_csv,
                   help="input claims CSV (default: dataset/claims.csv)")
    p.add_argument("--output", type=Path, default=settings.dataset_dir.parent / "output.csv",
                   help="output predictions CSV (default: ./output.csv at repo root)")
    p.add_argument("--limit", type=int, default=0,
                   help="process only the first N rows (0 = all)")
    p.add_argument("--resume", action="store_true",
                   help="skip rows already present in --output and append the rest")
    p.add_argument("--provider", choices=["gemini", "claude"], default=None,
                   help="VLM provider (default: server-configured DEFAULT_PROVIDER)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    settings = get_settings()
    service = ClaimVerifierService(settings)
    client = service.get_client(args.provider)

    print(f"[config] {settings.public_summary()}", file=sys.stderr)
    print(f"[provider] {client.name} (mock={client.mock})", file=sys.stderr)
    if client.mock:
        print("[mode] MOCK_MODE — no API calls; placeholder analysis "
              "(no API key for this provider).", file=sys.stderr)

    records = read_claims(args.input)
    if args.limit:
        records = records[: args.limit]

    done = count_output_rows(args.output) if args.resume else 0
    if not args.resume:
        write_output([], args.output)  # truncate/create with just the header
    if done:
        print(f"[resume] {done} rows already done; continuing.", file=sys.stderr)

    total = len(records)
    for i, rec in enumerate(records):
        if i < done:
            continue
        pred = service.verify(
            user_id=rec.user_id,
            claim_object=rec.claim_object,
            user_claim=rec.user_claim,
            image_paths=rec.image_path_list,
            provider=args.provider,
            strict_images=False,
        )
        append_output_row(pred, args.output)
        print(f"[run] {i + 1}/{total} {rec.user_id} -> {pred.claim_status}", file=sys.stderr)

    print(f"[done] {args.output} now has {count_output_rows(args.output)} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
