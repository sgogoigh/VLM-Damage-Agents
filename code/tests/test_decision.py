"""Tests for pipeline/decision.py - requirements-aware decision rules."""
from pipeline.claim_parser import ParsedClaim
from pipeline.decision import decide, match_requirement
from pipeline.image_analysis import ImageFinding

REQS = [
    {"requirement_id": "REQ_GENERAL_OBJECT_PART", "claim_object": "all",
     "applies_to": "general", "minimum_image_evidence": "object visible"},
    {"requirement_id": "REQ_CAR_BODY_PANEL", "claim_object": "car",
     "applies_to": "dent or scratch", "minimum_image_evidence": "panel visible"},
]


def _finding(**kw):
    base = dict(image_id="img_1", rel_path="p.jpg", shows_claimed_object=True,
                object_seen="car", visible_part="rear_bumper", issue_visible=True,
                issue_type="dent", issue_part="rear_bumper", severity="medium",
                usable_for_review=True, quality_flags=[])
    base.update(kw)
    return ImageFinding(**base)


def test_match_requirement_prefers_object_and_family():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    r = match_requirement("car", parsed, REQS)
    assert r["requirement_id"] == "REQ_CAR_BODY_PANEL"


def test_supported_when_issue_visible():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    d = decide("car", parsed, [_finding()], REQS)
    assert d.claim_status == "supported"
    assert d.evidence_standard_met is True
    assert d.valid_image is True
    assert d.supporting_image_ids == "img_1"
    assert d.issue_type == "dent" and d.object_part == "rear_bumper"


def test_contradicted_when_object_visible_no_issue():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    f = _finding(issue_visible=False)
    d = decide("car", parsed, [f], REQS)
    assert d.claim_status == "contradicted"
    assert "damage_not_visible" in d.risk_flags


def test_nei_when_no_usable_images():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    f = _finding(usable_for_review=False, shows_claimed_object=False)
    d = decide("car", parsed, [f], REQS)
    assert d.claim_status == "not_enough_information"
    assert d.valid_image is False
    assert d.supporting_image_ids == "none"


def test_quality_flags_propagate_to_risk():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    f = _finding(quality_flags=["blurry_image"])
    d = decide("car", parsed, [f], REQS)
    assert "blurry_image" in d.risk_flags
