"""Tests for the decider-gating heuristic in pipeline/orchestrator.py."""
from pipeline.orchestrator import _needs_decider
from pipeline.claim_parser import ParsedClaim
from pipeline.image_analysis import ImageFinding


def _f(image_id="img_1", **kw):
    base = dict(image_id=image_id, rel_path="p.jpg", usable_for_review=True)
    base.update(kw)
    return ImageFinding(**base)


def test_single_clean_image_skips_decider():
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    assert _needs_decider(parsed, [_f()]) is False


def test_multi_image_triggers_decider():
    parsed = ParsedClaim(claimed_parts=["door"], claimed_issue="dent")
    assert _needs_decider(parsed, [_f("img_1"), _f("img_2")]) is True


def test_injection_triggers_decider():
    parsed = ParsedClaim(claimed_parts=["seal"], claimed_issue="torn_packaging",
                         injection_detected=True)
    assert _needs_decider(parsed, [_f()]) is True


def test_non_original_triggers_decider():
    parsed = ParsedClaim(claimed_parts=["screen"], claimed_issue="crack")
    assert _needs_decider(parsed, [_f(looks_non_original=True)]) is True


def test_missing_images_not_counted():
    parsed = ParsedClaim(claimed_parts=["box"], claimed_issue="crushed_packaging")
    findings = [_f("img_1"), ImageFinding("img_2", "q.jpg", missing=True)]
    # only one present image, no flags -> no decider
    assert _needs_decider(parsed, findings) is False
