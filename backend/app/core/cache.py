"""
Content-addressed cache for per-image VLM analysis and text parses.

Keyed by sha256(payload bytes) + a namespace string (prompt version | model |
mock/live), so:
- the same image referenced by multiple claims is analyzed once, and
- re-running the pipeline reuses prior analysis (cost/latency control), while
- different providers/models never read each other's cached results.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.config import get_settings


def _key(payload: bytes, namespace: str) -> str:
    h = hashlib.sha256()
    h.update(payload)
    h.update(b"::")
    h.update(namespace.encode("utf-8"))
    return h.hexdigest()


def image_content_hash(image_path: Path) -> str:
    """Stable hash of an image's bytes (used for cache keys and dedup)."""
    return hashlib.sha256(Path(image_path).read_bytes()).hexdigest()


class AnalysisCache:
    """Tiny JSON-file cache. Swap for sqlite/redis later if needed."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.dir = Path(cache_dir or get_settings().cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, payload: bytes, namespace: str) -> dict | None:
        p = self._path(_key(payload, namespace))
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def put(self, payload: bytes, namespace: str, value: dict) -> None:
        p = self._path(_key(payload, namespace))
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class NullCache:
    """No-op cache (handy for tests / forcing fresh analysis)."""

    def get(self, payload: bytes, namespace: str) -> dict | None:  # noqa: ARG002
        return None

    def put(self, payload: bytes, namespace: str, value: dict) -> None:  # noqa: ARG002
        return None
