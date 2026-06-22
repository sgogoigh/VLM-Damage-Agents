"""LLM/VLM provider layer with mock mode and caching.

Two interchangeable providers expose the same `generate_json(...)` surface:
  - Google Gemini  (`gemini_client.GeminiClient`)  — default runnable provider
  - Anthropic Claude (`claude_client.ClaudeClient`) — Opus 4.8 VLM (demo/compare)

`make_client(provider)` picks one at the entry point so the pipeline stays
provider-agnostic.
"""
from __future__ import annotations


def make_client(provider: str = "gemini"):
    """Return a VLM client for the given provider ("gemini" | "claude").

    Both clients share the identical `generate_json` interface, so the pipeline
    does not care which one it gets. Unknown providers fall back to Gemini.
    """
    name = (provider or "gemini").strip().lower()
    if name == "claude":
        from code.llm.claude_client import ClaudeClient

        return ClaudeClient()
    from code.llm.gemini_client import GeminiClient

    return GeminiClient()
