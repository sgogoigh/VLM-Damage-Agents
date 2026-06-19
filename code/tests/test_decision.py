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
    base = dict(image_id="img_1", rel_path="p.jpg", object_match="match",
                object_color="silver", identity_descriptor="silver sedan",
                claimed_part_visible=True, actual_part="rear_bumper",
                claimed_issue_present="yes", actual_issue_type="dent",
                severity="medium", usable_for_review=True, quality_flags=[])
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


def test_contradicted_when_part_visible_no_issue():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    f = _finding(claimed_issue_present="no", actual_issue_type="none")
    d = decide("car", parsed, [f], REQS)
    assert d.claim_status == "contradicted"
    assert "damage_not_visible" in d.risk_flags


def test_contradicted_with_different_issue_sets_claim_mismatch():
    parsed = ParsedClaim(claimed_parts=["hood"], claimed_issue="scratch")
    f = _finding(claimed_part_visible=True, claimed_issue_present="no",
                 actual_issue_type="broken_part", actual_part="front_bumper",
                 severity="high")
    d = decide("car", parsed, [f], REQS)
    assert d.claim_status == "contradicted"
    assert d.issue_type == "broken_part" and d.object_part == "front_bumper"
    assert "claim_mismatch" in d.risk_flags


def test_nei_when_no_usable_images():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    f = _finding(usable_for_review=False)
    d = decide("car", parsed, [f], REQS)
    assert d.claim_status == "not_enough_information"
    assert d.valid_image is False
    assert d.supporting_image_ids == "none"


def test_nei_when_claimed_part_not_visible():
    parsed = ParsedClaim(claimed_parts=["headlight"], claimed_issue="crack")
    f = _finding(claimed_part_visible=False, claimed_issue_present="unclear")
    d = decide("car", parsed, [f], REQS)
    assert d.claim_status == "not_enough_information"
    assert d.object_part == "headlight"


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


def test_identity_conflict_when_images_disagree_on_object():
    # One image shows the claimed object, another shows a different object.
    parsed = ParsedClaim(claimed_parts=["front_bumper"], claimed_issue="scratch")
    f1 = _finding(image_id="img_1", object_match="match")
    f2 = _finding(image_id="img_2", object_match="mismatch")
    d = decide("car", parsed, [f1, f2], REQS)
    assert d.claim_status == "not_enough_information"
    assert "wrong_object" in d.risk_flags
    assert "manual_review_required" in d.risk_flags


def test_same_object_closeup_does_not_trigger_conflict():
    # Two photos of the SAME object (both match) must NOT be flagged as conflict;
    # one showing the issue -> supported.
    parsed = ParsedClaim(claimed_parts=["hinge"], claimed_issue="broken_part")
    f1 = _finding(image_id="img_1", object_match="match", claimed_issue_present="yes",
                  actual_issue_type="broken_part", actual_part="hinge")
    f2 = _finding(image_id="img_2", object_match="match", claimed_issue_present="no",
                  actual_issue_type="none")
    d = decide("laptop", parsed, [f1, f2], REQS)
    assert d.claim_status == "supported"
