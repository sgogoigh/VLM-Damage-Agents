"""Tests for llm/cache.py - content-addressed analysis cache."""
from llm.cache import AnalysisCache, image_content_hash


def test_put_then_get_hit(tmp_path):
    c = AnalysisCache(cache_dir=tmp_path)
    data = {"issue_type": "dent", "ok": True}
    c.put(b"imagebytes", "v1", data)
    assert c.get(b"imagebytes", "v1") == data


def test_get_miss_returns_none(tmp_path):
    c = AnalysisCache(cache_dir=tmp_path)
    assert c.get(b"other", "v1") is None


def test_prompt_version_is_part_of_key(tmp_path):
    c = AnalysisCache(cache_dir=tmp_path)
    c.put(b"img", "v1", {"a": 1})
    # same bytes, different prompt version -> separate cache slot (miss)
    assert c.get(b"img", "v2") is None


def test_image_content_hash_stable(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    h1 = image_content_hash(f)
    h2 = image_content_hash(f)
    assert h1 == h2 and len(h1) == 64
