"""Tests for pipeline/decider.py - decider parsing with a faked LLM client."""
import types as pytypes

from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline.claim_parser import ParsedClaim
from pipeline.decider import run_decider, _findings_payload
from pipeline.image_analysis import ImageFinding

REQS = [{"requirement_id": "REQ_CAR_BODY_PANEL", "claim_object": "car",
         "applies_to": "dent or scratch", "minimum_image_evidence": "panel visible"}]


def _finding(**kw):
    base = dict(image_id="img_1", rel_path="p.jpg", shows_claimed_object=True,
                identity_descriptor="silver sedan front", visible_part="rear_bumper",
                issue_visible=True, issue_type="dent", issue_part="rear_bumper",
                severity="medium", usable_for_review=True)
    base.update(kw)
    return ImageFinding(**base)


def test_findings_payload_handles_missing():
    payload = _findings_payload([_finding(), ImageFinding("img_2", "q.jpg", missing=True)])
    assert payload[0]["image_id"] == "img_1"
    assert payload[1] == {"image_id": "img_2", "missing": True}


def test_run_decider_parses_faked_response(tmp_path, monkeypatch):
    client = GeminiClient()
    client.mock = False  # decider issues a live (faked) call
    cache = AnalysisCache(cache_dir=tmp_path)

    def fake_generate_json(prompt, *a, **k):
        return {
            "evidence_standard_met": True,
            "evidence_standard_met_reason": "panel visible",
            "risk_flags": ["claim_mismatch"],
            "issue_type": "dent", "object_part": "rear_bumper",
            "claim_status": "supported",
            "claim_status_justification": "img_1 shows the dent",
            "supporting_image_ids": ["img_1"],
            "valid_image": True, "severity": "medium",
        }
    monkeypatch.setattr(client, "generate_json", fake_generate_json)

    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    d = run_decider("car", parsed, [_finding()], REQS, client, cache)
    assert d.claim_status == "supported"
    assert d.supporting_image_ids == "img_1"
    assert "claim_mismatch" in d.risk_flags


def test_run_decider_appends_injection_flag(tmp_path, monkeypatch):
    client = GeminiClient()
    client.mock = False
    cache = AnalysisCache(cache_dir=tmp_path)
    monkeypatch.setattr(client, "generate_json",
                        lambda *a, **k: {"claim_status": "supported",
                                         "supporting_image_ids": "none",
                                         "risk_flags": []})
    parsed = ParsedClaim(claimed_parts=["seal"], claimed_issue="torn_packaging",
                         injection_detected=True)
    d = run_decider("package", parsed, [_finding()], REQS, client, cache)
    assert "text_instruction_present" in d.risk_flags


def test_run_decider_uses_cache(tmp_path, monkeypatch):
    client = GeminiClient()
    client.mock = False
    cache = AnalysisCache(cache_dir=tmp_path)
    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return {"claim_status": "supported", "supporting_image_ids": "none"}
    monkeypatch.setattr(client, "generate_json", counting)
    parsed = ParsedClaim(claimed_parts=["rear_bumper"], claimed_issue="dent")
    run_decider("car", parsed, [_finding()], REQS, client, cache)
    run_decider("car", parsed, [_finding()], REQS, client, cache)
    assert calls["n"] == 1  # second call served from cache
