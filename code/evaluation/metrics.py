"""
Scoring helpers for evaluating predictions against sample_claims.csv labels.

We report per-field accuracy plus the headline claim_status accuracy and a
confusion matrix, since claim_status is the core decision.
"""
from __future__ import annotations

from collections import defaultdict

# Fields we score against the labeled sample set.
SCORED_FIELDS = [
    "evidence_standard_met",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "valid_image",
    "severity",
]


def _norm(v: str) -> str:
    return (v or "").strip().lower()


def _risk_set(v: str) -> set[str]:
    return {t for t in _norm(v).split(";") if t}


def score(predicted: list[dict], expected: list[dict]) -> dict:
    """Return a metrics dict comparing aligned predicted/expected rows."""
    n = min(len(predicted), len(expected))
    field_correct: dict[str, int] = defaultdict(int)
    confusion: dict[tuple[str, str], int] = defaultdict(int)

    for i in range(n):
        p, e = predicted[i], expected[i]
        for fld in SCORED_FIELDS:
            pv, ev = _norm(p.get(fld, "")), _norm(e.get(fld, ""))
            if fld == "risk_flags":
                if _risk_set(p.get(fld, "")) == _risk_set(e.get(fld, "")):
                    field_correct[fld] += 1
            elif pv == ev:
                field_correct[fld] += 1
        confusion[(_norm(e.get("claim_status", "")), _norm(p.get("claim_status", "")))] += 1

    return {
        "n": n,
        "field_accuracy": {f: (field_correct[f] / n if n else 0.0) for f in SCORED_FIELDS},
        "claim_status_accuracy": field_correct["claim_status"] / n if n else 0.0,
        "claim_status_confusion": {f"{k[0]}->{k[1]}": v for k, v in sorted(confusion.items())},
    }


def format_report(metrics: dict, strategy_name: str) -> str:
    lines = [f"### Strategy: {strategy_name}", f"- rows scored: {metrics['n']}",
             f"- claim_status accuracy: {metrics['claim_status_accuracy']:.2%}",
             "- per-field accuracy:"]
    for f, acc in metrics["field_accuracy"].items():
        lines.append(f"    - {f}: {acc:.2%}")
    lines.append("- claim_status confusion (expected->predicted):")
    for k, v in metrics["claim_status_confusion"].items():
        lines.append(f"    - {k}: {v}")
    return "\n".join(lines)
