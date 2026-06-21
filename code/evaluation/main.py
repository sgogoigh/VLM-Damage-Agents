"""
Evaluation entry point (AGENTS.md S6 contract).

Runs the pipeline on dataset/sample_claims.csv and scores predictions against
the labeled expected outputs, printing per-field and claim_status metrics.

The VLM provider is selectable so the SAME pipeline can be evaluated with either
Gemini or Claude (Opus 4.8) as the perception layer — useful for a side-by-side
model comparison / demo. Claude runs in mock mode unless ANTHROPIC_API_KEY is set.

Usage:
    python code/evaluation/main.py                       # Gemini (default)
    python code/evaluation/main.py --provider claude     # Claude Opus 4.8 VLM
    LLM_MOCK=1 python code/evaluation/main.py            # offline scaffold run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the parent `code/` package importable when run directly.
CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_DIR))

import config  # noqa: E402
from data_io import (  # noqa: E402
    read_claims,
    read_evidence_requirements,
    read_sample_with_labels,
    read_user_history,
)
from evaluation import metrics as M  # noqa: E402
from llm import make_client  # noqa: E402
from llm.cache import AnalysisCache  # noqa: E402
from pipeline import run_pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate the pipeline on the labeled sample set")
    p.add_argument("--provider", choices=["gemini", "claude"], default="gemini",
                   help="VLM provider for the perception layer (default: gemini)")
    args = p.parse_args(argv)

    print(f"[config] {config.summary()}", file=sys.stderr)
    print(f"[provider] {args.provider}", file=sys.stderr)

    client = make_client(args.provider)
    if client.mock:
        print("[mode] MOCK_MODE - metrics reflect placeholder analysis, not real "
              "model quality (no API key for this provider).", file=sys.stderr)

    records = read_claims(config.SAMPLE_CLAIMS_CSV)
    expected = read_sample_with_labels(config.SAMPLE_CLAIMS_CSV)
    history = read_user_history()
    requirements = read_evidence_requirements()

    cache = AnalysisCache()

    predicted = [
        run_pipeline(r, history=history, requirements=requirements,
                     client=client, cache=cache).to_csv_dict()
        for r in records
    ]

    result = M.score(predicted, expected)
    strategy = f"{args.provider}:{client.model} / chain{' / MOCK' if client.mock else ''}"
    print(M.format_report(result, strategy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
