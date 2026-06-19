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


def test_non_original_and_on_image_text_flags():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    f = _finding(looks_non_original=True, has_on_image_instruction_text=True)
    d = decide("car", parsed, [f], REQS)
    assert "non_original_image" in d.risk_flags
    assert "text_instruction_present" in d.risk_flags


def test_injection_in_claim_sets_text_instruction_present():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent",
                         injection_detected=True)
    d = decide("car", parsed, [_finding()], REQS)
    assert "text_instruction_present" in d.risk_flags


def test_identity_mismatch_flags_wrong_object():
    parsed = ParsedClaim(claimed_parts=["front_bumper"], claimed_issue="scratch")
    f1 = _finding(image_id="img_1", identity_descriptor="silver sedan",
                  shows_claimed_object=True)
    f2 = _finding(image_id="img_2", identity_descriptor="red hatchback",
                  shows_claimed_object=False)
    d = decide("car", parsed, [f1, f2], REQS)
    assert "wrong_object" in d.risk_flags
    assert "manual_review_required" in d.risk_flags
