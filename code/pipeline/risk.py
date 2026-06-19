"""
Stage 4 - user-history risk overlay.

History adds risk CONTEXT only. Per problem_statement.md it must NOT override
clear visual evidence by itself - so this stage only appends risk_flags and
can request manual review; it never flips claim_status.
"""
from __future__ import annotations


def apply_user_history(
    user_id: str,
    history: dict[str, dict[str, str]],
    risk_flags: list[str],
    claim_status: str,
) -> list[str]:
    flags = list(risk_flags)
    row = history.get(user_id)
    if not row:
        return flags

    hist_flags = (row.get("history_flags", "") or "").strip().lower()
    if hist_flags and hist_flags != "none":
        flags.append("user_history_risk")

    # Recent burst of claims is a soft risk signal.
    try:
        recent = int(row.get("last_90_days_claim_count", "0") or "0")
    except ValueError:
        recent = 0
    if recent >= 4:
        flags.append("user_history_risk")

    # If the claim is uncertain AND the user is risky, route to manual review.
    if "user_history_risk" in flags and claim_status == "not_enough_information":
        flags.append("manual_review_required")

    return flags
