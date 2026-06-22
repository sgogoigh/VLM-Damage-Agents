"""VLM provider registry.

Two interchangeable providers expose the identical ``generate_json`` surface:
  - ``gemini`` (GeminiClient)  — default, operational provider
  - ``claude`` (ClaudeClient)  — available; runs in mock mode without a key

``make_client(provider)`` picks one at the entry point so the pipeline stays
provider-agnostic. Unknown providers raise rather than silently mis-route.
"""
from __future__ import annotations

from app.config import Settings, get_settings
from app.core.llm.base import BaseLLMClient

PROVIDERS = ("gemini", "claude")


def make_client(provider: str | None = None, settings: Settings | None = None) -> BaseLLMClient:
    s = settings or get_settings()
    name = (provider or s.default_provider or "gemini").strip().lower()
    if name == "claude":
        from app.core.llm.claude_client import ClaudeClient

        return ClaudeClient(settings=s)
    if name == "gemini":
        from app.core.llm.gemini_client import GeminiClient

        return GeminiClient(settings=s)
    raise ValueError(f"Unknown provider {provider!r}; expected one of {PROVIDERS}.")


__all__ = ["make_client", "BaseLLMClient", "PROVIDERS"]
