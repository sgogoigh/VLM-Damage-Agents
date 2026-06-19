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
import time
from typing import Any

import config


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
                return self._live_call(prompt, image_bytes_list or [])
            except Exception as e:  # noqa: BLE001 - backoff on any transient error
                last_err = e
                delay = config.RETRY_BASE_DELAY_S * (2 ** attempt)
                time.sleep(delay)
        raise RuntimeError(f"Gemini call failed after retries: {last_err}")

    # -- internals ----------------------------------------------------------
    def _ensure_sdk(self):
        """Lazily import and configure the google-genai SDK."""
        if self._sdk is not None:
            return self._sdk
        # TODO(iteration-2): wire up the real SDK, e.g.
        #   from google import genai
        #   self._sdk = genai.Client(api_key=config.GEMINI_API_KEY)
        # Image parts are built with genai.types.Part.from_bytes(...).
        raise NotImplementedError(
            "Live Gemini SDK not wired yet. Set LLM_MOCK=1 (default without a "
            "key) to run the scaffold, or implement _ensure_sdk/_live_call in "
            "iteration 2."
        )

    def _live_call(self, prompt: str, image_bytes_list: list[bytes]) -> dict[str, Any]:
        client = self._ensure_sdk()  # raises until implemented
        # TODO(iteration-2): build contents = [prompt, *image_parts], request
        # response_mime_type="application/json", parse and return the JSON.
        raise NotImplementedError

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
