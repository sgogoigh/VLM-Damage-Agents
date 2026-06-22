"""Provider registry + base client behavior (mock mode)."""
from __future__ import annotations

import json

import pytest

from app.core.llm import PROVIDERS, make_client
from app.core.llm.base import detect_mime, is_retryable_error, parse_json
from app.core.llm.claude_client import ClaudeClient
from app.core.llm.gemini_client import GeminiClient


def test_make_client_returns_correct_provider(settings):
    assert isinstance(make_client("gemini", settings), GeminiClient)
    assert isinstance(make_client("claude", settings), ClaudeClient)
    # default provider
    assert make_client(None, settings).name in PROVIDERS


def test_make_client_unknown_provider_raises(settings):
    with pytest.raises(ValueError):
        make_client("dalle", settings)


def test_clients_are_mock_without_keys(settings):
    assert make_client("gemini", settings).mock is True
    assert make_client("claude", settings).mock is True


def test_generate_json_uses_mock_factory(settings):
    client = make_client("gemini", settings)
    out = client.generate_json("prompt", mock_factory=lambda p, imgs: {"hello": "world", "n": len(imgs)})
    assert out == {"hello": "world", "n": 0}


def test_generate_json_default_mock_stub(settings):
    client = make_client("claude", settings)
    out = client.generate_json("prompt")
    assert out["_mock"] is True
    assert out["_provider"] == "claude"


def test_detect_mime():
    assert detect_mime(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert detect_mime(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert detect_mime(b"RIFF????WEBPVP8 ") == "image/webp"
    assert detect_mime(b"GIF89a....") == "image/gif"
    assert detect_mime(b"unknownbytes...") == "image/jpeg"  # fallback


def test_parse_json_handles_fenced_and_prose():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('here is the result: {"b": 2} thanks') == {"b": 2}
    assert parse_json(json.dumps({"c": [1, 2, 3]})) == {"c": [1, 2, 3]}


def test_is_retryable_error():
    # transient / unknown -> retry
    assert is_retryable_error(Exception("429 RESOURCE_EXHAUSTED")) is True
    assert is_retryable_error(Exception("503 Service Unavailable")) is True
    assert is_retryable_error(Exception("connection reset")) is True
    # clear client errors -> fail fast
    assert is_retryable_error(Exception("404 NOT_FOUND model gone")) is False
    assert is_retryable_error(Exception("400 INVALID_ARGUMENT")) is False
    assert is_retryable_error(Exception("403 PERMISSION_DENIED")) is False


def test_client_status(settings):
    s = make_client("gemini", settings).status()
    assert s["provider"] == "gemini"
    assert s["mock"] is True
    assert "model" in s
