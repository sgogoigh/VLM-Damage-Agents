"""
Content-addressed cache for per-image VLM analysis.

Keyed by sha256(image bytes) + prompt version, so:
- the same image referenced by multiple claims is analyzed once, and
- re-running the pipeline reuses prior analysis (cost/latency control).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import config


def _key(image_bytes: bytes, prompt_version: str) -> str:
    h = hashlib.sha256()
    h.update(image_bytes)
    h.update(b"::")
    h.update(prompt_version.encode("utf-8"))
    return h.hexdigest()


def image_content_hash(image_path: Path) -> str:
    """Stable hash of an image's bytes (used for cache keys and dedup)."""
    return hashlib.sha256(image_path.read_bytes()).hexdigest()


class AnalysisCache:
    """Tiny JSON-file cache. Swap for sqlite/redis later if needed."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.dir = cache_dir or config.CACHE_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, image_bytes: bytes, prompt_version: str) -> dict | None:
        p = self._path(_key(image_bytes, prompt_version))
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def put(self, image_bytes: bytes, prompt_version: str, value: dict) -> None:
        p = self._path(_key(image_bytes, prompt_version))
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
