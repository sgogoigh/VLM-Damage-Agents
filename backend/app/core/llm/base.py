"""
Provider-agnostic VLM client base.

Every provider exposes the identical surface::

    client.generate_json(prompt, image_bytes_list=None, *, mock_factory=None) -> dict

so the pipeline is completely provider-agnostic — swapping Gemini for Claude is a
one-line change at the entry point. Shared concerns (mock handling, retry with
backoff, a rolling-window rate limiter, robust JSON extraction, and image MIME
sniffing) live here so each concrete provider only implements ``_live_call``.
"""
from __future__ import annotations

import json
import re
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Any, Callable

from app.config import Settings, get_settings

MockFactory = Callable[[str, list[bytes]], dict]

# Per-provider rolling windows of recent live-call timestamps, shared across all
# instances of the same provider so concurrent requests respect one RPM budget.
_CALL_TIMES: dict[str, deque[float]] = defaultdict(deque)
_RATE_LOCK = threading.Lock()

_RETRY_DELAY_RE = re.compile(r"retry(?:Delay)?['\"]?[:\s]+['\"]?([\d.]+)s", re.IGNORECASE)

# Non-transient client errors: retrying cannot help, so fail fast (a wrong model
# name or a bad key should not burn ~60s of exponential backoff).
_NON_RETRYABLE_RE = re.compile(
    r"\b(400|401|403|404)\b|INVALID_ARGUMENT|NOT_FOUND|PERMISSION_DENIED|UNAUTHENTICATED",
    re.IGNORECASE,
)


def is_retryable_error(err: Exception) -> bool:
    """False for clear client errors (4xx); True for transient/unknown errors."""
    return not _NON_RETRYABLE_RE.search(str(err))


def detect_mime(image_bytes: bytes) -> str:
    """Sniff the real image format from magic bytes.

    Many dataset files have a .jpg extension but are actually PNG / WEBP / AVIF.
    Sending the wrong mime_type to a VLM can make it reject or misread the image.
    """
    b = image_bytes[:16]
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b[4:8] == b"ftyp":
        brand = b[8:12]
        if brand[:2] == b"av":   # avif / avis
            return "image/avif"
        if brand in (b"heic", b"heix", b"mif1", b"heim", b"hevc"):
            return "image/heic"
        return "image/jpeg"      # fallback for other ISO-BMFF brands
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"


def parse_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from a model text response."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


class BaseLLMClient(ABC):
    """Common machinery for all VLM providers."""

    #: short provider id ("gemini" | "claude"); set by subclasses.
    name: str = "base"

    def __init__(self, model: str, *, mock: bool, rpm: int, settings: Settings | None = None) -> None:
        self.model = model
        self.mock = mock
        self.rpm = max(1, rpm)
        self.settings = settings or get_settings()
        self._sdk: Any = None  # lazily created in _ensure_sdk()

    # -- public API ---------------------------------------------------------
    def generate_json(
        self,
        prompt: str,
        image_bytes_list: list[bytes] | None = None,
        *,
        mock_factory: MockFactory | None = None,
    ) -> dict[str, Any]:
        """Return a JSON object from the model.

        In mock mode, calls ``mock_factory(prompt, images)`` if provided,
        otherwise returns a neutral stub — so the pipeline runs end-to-end with
        no network and no key.
        """
        if self.mock:
            if mock_factory is not None:
                return mock_factory(prompt, image_bytes_list or [])
            return {"_mock": True, "_provider": self.name}

        last_err: Exception | None = None
        for attempt in range(self.settings.max_retries):
            try:
                self._throttle()
                return self._live_call(prompt, image_bytes_list or [])
            except Exception as e:  # noqa: BLE001 — backoff on any transient error
                last_err = e
                if not is_retryable_error(e):
                    raise RuntimeError(f"{self.name} call failed (non-retryable): {e}") from e
                delay = self._retry_delay_from_error(e)
                if delay is None:
                    delay = self.settings.retry_base_delay_s * (2 ** attempt)
                time.sleep(delay)
        raise RuntimeError(f"{self.name} call failed after retries: {last_err}")

    # -- rate limiting ------------------------------------------------------
    def _throttle(self) -> None:
        """Block until making a call keeps us within ``rpm`` per rolling 60s."""
        bucket = _CALL_TIMES[self.name]
        while True:
            with _RATE_LOCK:
                now = time.monotonic()
                while bucket and now - bucket[0] >= 60.0:
                    bucket.popleft()
                if len(bucket) < self.rpm:
                    bucket.append(now)
                    return
                sleep_for = 60.0 - (now - bucket[0]) + 0.05
            time.sleep(max(0.05, sleep_for))

    @staticmethod
    def _retry_delay_from_error(err: Exception) -> float | None:
        m = _RETRY_DELAY_RE.search(str(err))
        if m:
            try:
                return float(m.group(1)) + 1.0  # small buffer
            except ValueError:
                return None
        return None

    # -- helpers exposed to subclasses --------------------------------------
    parse_json = staticmethod(parse_json)

    # -- to implement -------------------------------------------------------
    @abstractmethod
    def _ensure_sdk(self) -> Any:
        """Lazily import + construct the provider SDK; raise if no key."""

    @abstractmethod
    def _live_call(self, prompt: str, image_bytes_list: list[bytes]) -> dict[str, Any]:
        """Make one real provider call and return parsed JSON."""

    # -- introspection ------------------------------------------------------
    def status(self) -> dict[str, Any]:
        return {"provider": self.name, "model": self.model, "mock": self.mock}
