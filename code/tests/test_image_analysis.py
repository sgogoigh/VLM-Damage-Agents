"""Tests for pipeline/image_analysis.py - per-image chain findings + caching."""
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline.claim_parser import ParsedClaim
from pipeline.image_analysis import analyze_image, analyze_images, ImageFinding


def _parsed(parts=("rear_bumper",)):
    return ParsedClaim(claimed_parts=list(parts), claimed_issue="dent",
                       claimed_severity="medium")


def test_missing_image_flagged(tmp_path):
    f = analyze_image("images/test/case_999/none.jpg", "car", _parsed(),
                      GeminiClient(), AnalysisCache(cache_dir=tmp_path))
    assert f.missing is True and f.image_id == "none"


def test_real_image_mock_finding(tmp_path):
    f = analyze_image("images/test/case_001/img_1.jpg", "car", _parsed(),
                      GeminiClient(), AnalysisCache(cache_dir=tmp_path))
    assert isinstance(f, ImageFinding) and f.missing is False
    assert f.object_match == "unclear"
    assert f.severity_vs_claim == "unclear"
    # mock builds a verdict per claimed part
    assert f.parts and f.parts[0].part == "rear_bumper"
    assert f.parts[0].issue_present == "unclear"


def test_verdict_for_lookup(tmp_path):
    f = analyze_image("images/test/case_001/img_1.jpg", "car",
                      _parsed(parts=("rear_bumper", "door")), GeminiClient(),
                      AnalysisCache(cache_dir=tmp_path))
    assert f.verdict_for("door") is not None
    assert f.verdict_for("nonexistent") is not None  # falls back to first


def test_cache_populated(tmp_path):
    cache = AnalysisCache(cache_dir=tmp_path)
    analyze_image("images/test/case_001/img_1.jpg", "car", _parsed(), GeminiClient(), cache)
    assert any(tmp_path.iterdir())


def test_analyze_images_multi(tmp_path):
    fs = analyze_images(
        ["images/test/case_004/img_1.jpg", "images/test/case_004/img_2.jpg"],
        "car", _parsed(), GeminiClient(), AnalysisCache(cache_dir=tmp_path))
    assert {f.image_id for f in fs} == {"img_1", "img_2"}
