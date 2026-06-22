"""Content-addressed cache + prompt loading/rendering."""
from __future__ import annotations

from app.core import prompts
from app.core.cache import AnalysisCache, NullCache


def test_cache_put_get_roundtrip(tmp_path):
    c = AnalysisCache(tmp_path)
    payload, ns = b"image-bytes", "v1|model|mock"
    assert c.get(payload, ns) is None
    c.put(payload, ns, {"k": "v"})
    assert c.get(payload, ns) == {"k": "v"}


def test_cache_namespace_isolation(tmp_path):
    c = AnalysisCache(tmp_path)
    payload = b"same-bytes"
    c.put(payload, "gemini-model", {"who": "gemini"})
    c.put(payload, "claude-model", {"who": "claude"})
    assert c.get(payload, "gemini-model") == {"who": "gemini"}
    assert c.get(payload, "claude-model") == {"who": "claude"}


def test_null_cache_never_stores():
    n = NullCache()
    n.put(b"x", "ns", {"a": 1})
    assert n.get(b"x", "ns") is None


def test_prompt_versions_loaded():
    assert prompts.IMAGE_ANALYSIS_VERSION.startswith("image_analysis")
    assert prompts.CLAIM_PARSER_VERSION.startswith("claim_parser")


def test_render_substitutes_only_named_tokens():
    out = prompts.render('keep {"json": true} but fill {name}', name="Alice")
    assert "Alice" in out
    assert '{"json": true}' in out   # literal JSON braces untouched
