"""
Stage 4 — user-history risk overlay.

History adds risk CONTEXT only. Per problem_statement.md it must NOT override
clear visual evidence by itself — so this stage only appends risk_flags and can
request manual review; it never flips claim_status.
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

    hist = (row.get("history_flags", "") or "").strip().lower()
    hist_set = {h.strip() for h in hist.split(";") if h.strip() and h.strip() != "none"}

    # Mirror the labeled convention: a user flagged user_history_risk is also
    # routed to manual review; an explicit manual_review_required carries over.
    if "user_history_risk" in hist_set:
        flags.append("user_history_risk")
        flags.append("manual_review_required")
    if "manual_review_required" in hist_set:
        flags.append("manual_review_required")

    return flags
