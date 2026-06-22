"""
Google Gemini VLM client — the default operational provider.

Returns structured JSON via the ``google-genai`` SDK, imported lazily so mock
mode needs neither the package nor a key. Inherits retry/backoff, rolling-window
throttling, and JSON parsing from ``BaseLLMClient``.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.llm.base import BaseLLMClient, detect_mime


class GeminiClient(BaseLLMClient):
    name = "gemini"

    def __init__(self, model: str | None = None, settings: Settings | None = None) -> None:
        s = settings or get_settings()
        super().__init__(
            model=model or s.gemini_model,
            mock=s.gemini_mock,
            rpm=s.gemini_rpm,
            settings=s,
        )

    # -- internals ----------------------------------------------------------
    def _ensure_sdk(self) -> Any:
        if self._sdk is not None:
            return self._sdk
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set; cannot make live Gemini calls.")
        from google import genai  # lazily imported so mock mode needs no SDK

        self._sdk = genai.Client(api_key=self.settings.gemini_api_key)
        return self._sdk

    def _live_call(self, prompt: str, image_bytes_list: list[bytes]) -> dict[str, Any]:
        from google.genai import types

        client = self._ensure_sdk()
        contents: list[Any] = [prompt]
        for img in image_bytes_list:
            contents.append(types.Part.from_bytes(data=img, mime_type=detect_mime(img)))

        # Gemini 3.x: temperature/top_p/top_k removed; use thinking_level.
        # low/minimal => deterministic + low-latency JSON extraction.
        cfg_kwargs: dict[str, Any] = {"response_mime_type": "application/json"}
        if self.settings.gemini_thinking_level:
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=self.settings.gemini_thinking_level
            )

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(**cfg_kwargs),
        )
        return self.parse_json(response.text or "")
