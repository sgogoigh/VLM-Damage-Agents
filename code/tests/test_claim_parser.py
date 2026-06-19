"""Tests for pipeline/claim_parser.py - mock heuristic parsing."""
from llm.gemini_client import GeminiClient
from pipeline.claim_parser import ParsedClaim, parse_claim, _heuristic_parse


def test_heuristic_detects_part_and_issue():
    p = _heuristic_parse("car", "the rear bumper has a dent now")
    assert "rear_bumper" in p.claimed_parts
    assert p.claimed_issue == "dent"


def test_heuristic_multi_part_flag():
    p = _heuristic_parse("car", "front bumper and headlight both damaged")
    assert p.multi_part is True
    assert "front_bumper" in p.claimed_parts and "headlight" in p.claimed_parts


def test_heuristic_unknown_when_nothing_matches():
    p = _heuristic_parse("laptop", "something is wrong but I cannot say what")
    assert p.claimed_parts == ["unknown"]
    assert p.claimed_issue == "unknown"


def test_parse_claim_uses_mock_in_mock_mode():
    client = GeminiClient()
    assert client.mock is True
    parsed = parse_claim("laptop", "the screen has a crack", client)
    assert isinstance(parsed, ParsedClaim)
    assert "screen" in parsed.claimed_parts
    assert parsed.claimed_issue == "crack"
