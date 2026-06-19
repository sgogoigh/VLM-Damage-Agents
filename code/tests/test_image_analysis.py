"""Tests for pipeline/image_analysis.py - per-image findings + caching."""
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline.claim_parser import ParsedClaim
from pipeline.image_analysis import analyze_image, analyze_images, ImageFinding


def _parsed():
    return ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")


def test_missing_image_flagged(tmp_path):
    client = GeminiClient()
    cache = AnalysisCache(cache_dir=tmp_path)
    f = analyze_image("images/test/case_999/does_not_exist.jpg", "car",
                      _parsed(), client, cache)
    assert f.missing is True
    assert f.image_id == "does_not_exist"


def test_real_image_mock_finding(tmp_path):
    client = GeminiClient()
    cache = AnalysisCache(cache_dir=tmp_path)
    f = analyze_image("images/test/case_001/img_1.jpg", "car", _parsed(),
                      client, cache)
    assert isinstance(f, ImageFinding)
    assert f.missing is False
    assert f.image_id == "img_1"
    # mock returns neutral, non-committal analysis
    assert f.issue_visible is False
    assert f.usable_for_review is False


def test_cache_is_populated_after_analysis(tmp_path):
    client = GeminiClient()
    cache = AnalysisCache(cache_dir=tmp_path)
    analyze_image("images/test/case_001/img_1.jpg", "car", _parsed(), client, cache)
    # second call should read from cache (file present in cache dir)
    assert any(tmp_path.iterdir())


def test_analyze_images_multi(tmp_path):
    client = GeminiClient()
    cache = AnalysisCache(cache_dir=tmp_path)
    findings = analyze_images(
        ["images/test/case_004/img_1.jpg", "images/test/case_004/img_2.jpg"],
        "car", _parsed(), client, cache,
    )
    assert len(findings) == 2
    assert {f.image_id for f in findings} == {"img_1", "img_2"}
