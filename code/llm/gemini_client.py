"""
Thin Gemini wrapper that returns structured JSON.

Design goals:
- Single place that talks to the provider (easy to swap models / providers).
- MOCK_MODE returns deterministic stub JSON so the whole pipeline runs
  end-to-end with no API calls (iteration-1 default).
- Retries with exponential backoff for transient/429 errors (free-tier RPM).

The actual SDK call is intentionally NOT wired up yet in this scaffold. The
`_live_call` method raises NotImplementedError with a clear TODO so we make a
deliberate decision before spending tokens.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import deque
from typing import Any

from code import config

# Shared across all client instances: timestamps (monotonic secs) of recent
# live calls, used to throttle to GEMINI_RPM requests per rolling 60s window.
_CALL_TIMES: deque[float] = deque()
_RATE_LOCK = threading.Lock()

_RETRY_DELAY_RE = re.compile(r"retry(?:Delay)?['\"]?[:\s]+['\"]?([\d.]+)s", re.IGNORECASE)


def detect_mime(image_bytes: bytes) -> str:
    """Sniff the real image format from magic bytes.

    Many dataset files have a .jpg extension but are actually PNG / WEBP / AVIF.
    Sending the wrong mime_type to the VLM can cause it to reject or misread the
    image, so we detect the true type from the content.
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


class GeminiClient:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or config.GEMINI_MODEL
        self.mock = config.MOCK_MODE
        self._sdk = None  # lazily created in _ensure_sdk()

    # -- public API ---------------------------------------------------------
    def generate_json(
        self,
        prompt: str,
        image_bytes_list: list[bytes] | None = None,
        *,
        mock_factory=None,
    ) -> dict[str, Any]:
        """
        Return a JSON object from the model.

        In MOCK_MODE, calls `mock_factory(prompt, image_bytes_list)` (if given)
        to produce a deterministic stub; otherwise returns a neutral stub.
        """
        if self.mock:
            if mock_factory is not None:
                return mock_factory(prompt, image_bytes_list or [])
            return self._default_mock()

        last_err: Exception | None = None
        for attempt in range(config.MAX_RETRIES):
            try:
                self._throttle()
                return self._live_call(prompt, image_bytes_list or [])
            except Exception as e:  # noqa: BLE001 - backoff on any transient error
                last_err = e
                # Honor the server's suggested retry delay on 429 if present,
                # else exponential backoff.
                delay = self._retry_delay_from_error(e)
                if delay is None:
                    delay = config.RETRY_BASE_DELAY_S * (2 ** attempt)
                time.sleep(delay)
        raise RuntimeError(f"Gemini call failed after retries: {last_err}")

    # -- rate limiting ------------------------------------------------------
    @staticmethod
    def _throttle() -> None:
        """Block until making a call keeps us within GEMINI_RPM per 60s."""
        rpm = max(1, config.GEMINI_RPM)
        while True:
            with _RATE_LOCK:
                now = time.monotonic()
                while _CALL_TIMES and now - _CALL_TIMES[0] >= 60.0:
                    _CALL_TIMES.popleft()
                if len(_CALL_TIMES) < rpm:
                    _CALL_TIMES.append(now)
                    return
                sleep_for = 60.0 - (now - _CALL_TIMES[0]) + 0.05
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

    # -- internals ----------------------------------------------------------
    def _ensure_sdk(self):
        """Lazily import and configure the google-genai SDK."""
        if self._sdk is not None:
            return self._sdk
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set; cannot make live calls.")
        from google import genai  # imported lazily so mock mode needs no SDK

        self._sdk = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._sdk

    def _live_call(self, prompt: str, image_bytes_list: list[bytes]) -> dict[str, Any]:
        from google.genai import types

        client = self._ensure_sdk()
        contents: list[Any] = [prompt]
        for img in image_bytes_list:
            contents.append(types.Part.from_bytes(data=img, mime_type=detect_mime(img)))

        # Gemini 3.x: temperature/top_p/top_k are removed; use thinking_level.
        # low/minimal => deterministic + low-latency JSON extraction.
        cfg_kwargs: dict[str, Any] = {"response_mime_type": "application/json"}
        if config.GEMINI_THINKING_LEVEL:
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=config.GEMINI_THINKING_LEVEL
            )

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(**cfg_kwargs),
        )
        return self.parse_json(response.text or "")

    @staticmethod
    def _default_mock() -> dict[str, Any]:
        return {"_mock": True}

    @staticmethod
    def parse_json(text: str) -> dict[str, Any]:
        """Best-effort JSON extraction from a model text response."""
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
        return json.loads(text)
