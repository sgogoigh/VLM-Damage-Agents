"""Tests for pipeline/decision.py - chain aggregation + deterministic buckets."""
from pipeline.claim_parser import ParsedClaim
from pipeline.decision import decide, match_requirement, _calibrate_severity
from pipeline.image_analysis import ImageFinding, PartVerdict

REQS = [
    {"requirement_id": "REQ_GENERAL_OBJECT_PART", "claim_object": "all",
     "applies_to": "general", "minimum_image_evidence": "object visible"},
    {"requirement_id": "REQ_CAR_BODY_PANEL", "claim_object": "car",
     "applies_to": "dent or scratch", "minimum_image_evidence": "panel visible"},
]


def _img(image_id="img_1", object_match="match", severity_vs_claim="reasonable",
         usable=True, non_original=False, parts=None, **kw):
    return ImageFinding(
        image_id=image_id, rel_path="p.jpg", object_match=object_match,
        object_color="silver", severity_vs_claim=severity_vs_claim,
        usable_for_review=usable, looks_non_original=non_original,
        parts=parts or [], **kw)


def _pv(part, visible=True, issue_present="yes", actual_issue="dent", severity="medium"):
    return PartVerdict(part=part, visible=visible, issue_present=issue_present,
                       actual_issue=actual_issue, severity=severity)


def _claim(parts=("rear_bumper",), issue="dent", severity="unspecified"):
    return ParsedClaim(claimed_parts=list(parts), claimed_issue=issue,
                       claimed_severity=severity)


def test_supported_when_part_confirmed():
    f = _img(parts=[_pv("rear_bumper")])
    d = decide("car", _claim(), [f], REQS)
    assert d.claim_status == "supported"
    assert d.object_part == "rear_bumper" and d.issue_type == "dent"
    assert d.supporting_image_ids == "img_1" and d.evidence_standard_met is True


def test_multi_image_merge_either_supports():
    f1 = _img("img_1", parts=[_pv("rear_bumper", issue_present="no", actual_issue="none", severity="none")])
    f2 = _img("img_2", parts=[_pv("rear_bumper", issue_present="yes")])
    d = decide("car", _claim(), [f1, f2], REQS)
    assert d.claim_status == "supported"           # either image supporting => merge
    assert d.supporting_image_ids == "img_2"


def test_welfare_check_exaggerated_is_contradicted():
    f = _img(severity_vs_claim="exaggerated",
             parts=[_pv("rear_bumper", issue_present="yes", actual_issue="scratch", severity="low")])
    d = decide("car", _claim(issue="dent", severity="high"), [f], REQS)
    assert d.claim_status == "contradicted"
    assert "claim_mismatch" in d.risk_flags


def test_contradicted_when_issue_absent():
    f = _img(parts=[_pv("rear_bumper", issue_present="no", actual_issue="none", severity="none")])
    d = decide("car", _claim(), [f], REQS)
    assert d.claim_status == "contradicted"
    assert d.severity == "none" and "damage_not_visible" in d.risk_flags


def test_wrong_object_contradicted():
    f = _img(object_match="mismatch", parts=[_pv("box", visible=False, issue_present="no")])
    d = decide("package", _claim(parts=("box",), issue="crushed_packaging"), [f], REQS)
    assert d.claim_status == "contradicted" and "wrong_object" in d.risk_flags


def test_identity_conflict_two_objects_nei():
    f1 = _img("img_1", object_match="match", parts=[_pv("front_bumper")])
    f2 = _img("img_2", object_match="mismatch", parts=[_pv("front_bumper", visible=False)])
    d = decide("car", _claim(parts=("front_bumper",), issue="scratch"), [f1, f2], REQS)
    assert d.claim_status == "not_enough_information"
    assert "wrong_object" in d.risk_flags and "manual_review_required" in d.risk_flags


def test_nei_when_no_usable():
    f = _img(usable=False, parts=[_pv("rear_bumper")])
    d = decide("car", _claim(), [f], REQS)
    assert d.claim_status == "not_enough_information" and d.valid_image is False


def test_nei_when_part_not_visible():
    f = _img(parts=[_pv("headlight", visible=False, issue_present="unclear")])
    d = decide("car", _claim(parts=("headlight",), issue="crack"), [f], REQS)
    assert d.claim_status == "not_enough_information" and d.object_part == "headlight"


def test_ambiguous_risky_history_adds_manual_review():
    f = _img(parts=[_pv("trackpad", visible=True, issue_present="unclear",
                        actual_issue="unknown", severity="unknown")])
    d = decide("laptop", _claim(parts=("trackpad",), issue="crack"), [f], REQS,
               user_history_risky=True)
    assert d.claim_status == "not_enough_information"
    assert "manual_review_required" in d.risk_flags


def test_non_original_image_invalidates():
    f = _img(non_original=True, parts=[_pv("front_bumper", actual_issue="broken_part", severity="high")])
    d = decide("car", _claim(parts=("front_bumper",), issue="broken_part"), [f], REQS)
    assert d.valid_image is False
    assert "non_original_image" in d.risk_flags


def test_injection_sets_text_instruction_present():
    f = _img(parts=[_pv("seal", actual_issue="torn_packaging")])
    parsed = ParsedClaim(claimed_parts=["seal"], claimed_issue="torn_packaging",
                         injection_detected=True)
    d = decide("package", parsed, [f], REQS)
    assert "text_instruction_present" in d.risk_flags


def test_calibrate_severity_caps_cosmetic():
    assert _calibrate_severity("scratch", "high") == "medium"
    assert _calibrate_severity("broken_part", "high") == "high"
    assert _calibrate_severity("none", "high") == "high"  # untouched non-issue path


def test_match_requirement_prefers_family():
    r = match_requirement("car", _claim(issue="dent"), REQS)
    assert r["requirement_id"] == "REQ_CAR_BODY_PANEL"
