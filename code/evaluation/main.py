"""
Evaluation entry point (AGENTS.md S6 contract).

Runs the pipeline on dataset/sample_claims.csv and scores predictions against
the labeled expected outputs, printing per-field and claim_status metrics.

Usage:
    python code/evaluation/main.py
    LLM_MOCK=1 python code/evaluation/main.py     # offline scaffold run
"""
from __future__ import annotations

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
from llm.cache import AnalysisCache  # noqa: E402
from llm.gemini_client import GeminiClient  # noqa: E402
from pipeline import run_pipeline  # noqa: E402


def main() -> int:
    print(f"[config] {config.summary()}", file=sys.stderr)
    if config.MOCK_MODE:
        print("[mode] MOCK_MODE - metrics reflect placeholder analysis, not real "
              "model quality.", file=sys.stderr)

    records = read_claims(config.SAMPLE_CLAIMS_CSV)
    expected = read_sample_with_labels(config.SAMPLE_CLAIMS_CSV)
    history = read_user_history()
    requirements = read_evidence_requirements()

    client = GeminiClient()
    cache = AnalysisCache()

    predicted = [
        run_pipeline(r, history=history, requirements=requirements,
                     client=client, cache=cache).to_csv_dict()
        for r in records
    ]

    result = M.score(predicted, expected)
    strategy = f"baseline ({config.GEMINI_MODEL}{' / MOCK' if config.MOCK_MODE else ''})"
    print(M.format_report(result, strategy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
