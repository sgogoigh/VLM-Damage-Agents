"""Tests for pipeline/risk.py - history risk overlay (context only)."""
from pipeline.risk import apply_user_history

HIST = {
    "user_005": {"history_flags": "user_history_risk", "last_90_days_claim_count": "4"},
    "user_001": {"history_flags": "none", "last_90_days_claim_count": "1"},
}


def test_history_risk_added_when_flagged():
    flags = apply_user_history("user_005", HIST, [], "supported")
    assert "user_history_risk" in flags


def test_no_risk_for_clean_user():
    flags = apply_user_history("user_001", HIST, [], "supported")
    assert flags == []


def test_manual_review_when_risky_and_uncertain():
    flags = apply_user_history("user_005", HIST, [], "not_enough_information")
    assert "manual_review_required" in flags


def test_unknown_user_no_change():
    flags = apply_user_history("user_999", HIST, ["blurry_image"], "supported")
    assert flags == ["blurry_image"]


def test_history_never_changes_status_only_flags():
    # function returns flags only; it cannot and does not return a status.
    before = ["claim_mismatch"]
    after = apply_user_history("user_005", HIST, before, "contradicted")
    assert "claim_mismatch" in after  # preserved
    assert "user_history_risk" in after
