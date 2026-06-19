"""Tests for llm/gemini_client.py - mock mode, JSON parsing, live path (faked)."""
import types as pytypes

import pytest

from llm.gemini_client import GeminiClient


def test_mock_mode_returns_factory_value():
    client = GeminiClient()
    assert client.mock is True
    out = client.generate_json("prompt", mock_factory=lambda p, imgs: {"x": 1})
    assert out == {"x": 1}


def test_mock_default_when_no_factory():
    client = GeminiClient()
    assert client.generate_json("prompt") == {"_mock": True}


@pytest.mark.parametrize("raw,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 2}\n```', {"a": 2}),
    ('here is the result: {"a": 3} done', {"a": 3}),
])
def test_parse_json_variants(raw, expected):
    assert GeminiClient.parse_json(raw) == expected


def test_live_call_path_with_faked_sdk(monkeypatch):
    """Exercise _live_call without network by faking the SDK client."""
    client = GeminiClient(model="gemini-3.5-flash")
    client.mock = False  # force the live branch

    def fake_generate_content(model, contents, config):
        assert model == "gemini-3.5-flash"
        # prompt + 1 image part
        assert len(contents) == 2
        return pytypes.SimpleNamespace(text='{"issue_visible": true, "issue_type": "dent"}')

    fake_client = pytypes.SimpleNamespace(
        models=pytypes.SimpleNamespace(generate_content=fake_generate_content)
    )
    monkeypatch.setattr(client, "_ensure_sdk", lambda: fake_client)

    out = client.generate_json("analyze this", [b"\xff\xd8fakejpeg"])
    assert out == {"issue_visible": True, "issue_type": "dent"}


def test_live_retry_then_success(monkeypatch):
    client = GeminiClient()
    client.mock = False
    calls = {"n": 0}

    def flaky(prompt, imgs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("429 transient")
        return {"ok": True}

    monkeypatch.setattr(client, "_live_call", flaky)
    monkeypatch.setattr("time.sleep", lambda *_: None)  # no real backoff wait
    out = client.generate_json("p", [b"x"])
    assert out == {"ok": True} and calls["n"] == 2
