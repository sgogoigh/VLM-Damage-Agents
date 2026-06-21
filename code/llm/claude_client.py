"""
Thin Anthropic Claude wrapper that returns structured JSON.

This is the Claude analog of `llm/gemini_client.py`: it exposes the exact same
`generate_json(prompt, image_bytes_list, *, mock_factory=...)` surface, so the
pipeline can run with **Claude as the VLM** simply by swapping the client at the
entry point (`--provider claude`). Nothing else in the pipeline changes.

Model: **Claude Opus 4.8** (`claude-opus-4-8`) — vision-capable, the most
capable Opus-tier model.

Design goals (mirrors GeminiClient):
- Single place that talks to Anthropic (easy to swap models / providers).
- MOCK_MODE (the default when no `ANTHROPIC_API_KEY` is set) returns the same
  deterministic stub JSON the Gemini mock does, so the whole pipeline runs
  end-to-end with **no API calls and no key** — exactly what's needed to wire up
  and demo the Claude path without spending tokens.
- Client-side throttle + exponential-backoff retry for rate limits. (The
  official `anthropic` SDK also auto-retries 429/5xx; the throttle just paces
  batch runs so we don't trip the limit in the first place.)

The `anthropic` SDK is imported lazily inside `_live_call`, so mock-mode runs
need neither the package nor a key.

Vision request shape + limits (verified against the official vision docs:
https://platform.claude.com/docs/en/build-with-claude/vision):
- Images are base64 content blocks: `{"type": "image", "source": {"type":
  "base64", "media_type": ..., "data": ...}}`, placed BEFORE the text block
  (docs: "Claude works best when images come before text").
- Supported media types are ONLY image/jpeg, image/png, image/gif, image/webp.
  Many dataset files are actually PNG/WEBP/AVIF saved with a .jpg extension, so
  we sniff the true type and re-encode anything unsupported (e.g. AVIF/HEIC) to
  JPEG via Pillow before sending — otherwise the API rejects it.
- Per-image limits: ≤10 MB base64, ≤8000×8000 px. Opus 4.7+ native resolution is
  2576 px on the long edge (≈4784 visual tokens); the docs recommend pre-resizing
  to that to control token cost and latency, so we downscale to 2576 px.
- One image per request here (the pipeline analyzes images individually), so the
  100/600-images-per-request caps never apply.

Other Opus 4.8 API notes:
- `temperature` / `top_p` / `top_k` are removed on Opus 4.8 (sending them 400s),
  so we send none — prompting drives behavior.
- Thinking is adaptive-only; omitting the `thinking` field runs without thinking,
  which is deterministic and cheap for structured JSON extraction.
- `max_tokens` is required.
"""
from __future__ import annotations

import base64
import io
import time
from typing import Any

import config
# Reuse the Gemini wrapper's helpers so behavior is identical across providers:
#   detect_mime  -> sniff the true image type from magic bytes (many dataset
#                   files are mislabeled .jpg); maps 1:1 to Anthropic media_type.
#   _throttle    -> shared rolling-window rate limiter.
#   parse_json   -> best-effort JSON extraction from a model text response.
from llm.gemini_client import GeminiClient, detect_mime

# Anthropic vision accepts ONLY these source media types (vision docs §FAQ).
_SUPPORTED_MEDIA = {"image/jpeg", "image/png", "image/gif", "image/webp"}
# Opus 4.7+ native resolution: long edge ≤ 2576 px. Pre-resizing to this caps
# token cost/latency without losing fidelity Claude would keep anyway.
_MAX_EDGE_PX = 2576
# Keep raw bytes well under the 10 MB *base64* per-image cap (base64 ≈ +33%).
_MAX_RAW_BYTES = 7_000_000

# Best-effort: register AVIF/HEIC decoders with Pillow if pillow-heif is
# installed, so the ~8 AVIF dataset images (mislabeled .jpg) can be re-encoded.
try:  # pragma: no cover - optional dependency
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
    try:
        pillow_heif.register_avif_opener()
    except Exception:
        pass
except Exception:
    pass


class ClaudeClient:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or config.CLAUDE_MODEL
        self.mock = config.CLAUDE_MOCK
        self._sdk = None  # lazily created in _ensure_sdk()

    # -- public API (identical signature to GeminiClient.generate_json) -------
    def generate_json(
        self,
        prompt: str,
        image_bytes_list: list[bytes] | None = None,
        *,
        mock_factory=None,
    ) -> dict[str, Any]:
        """Return a JSON object from Claude.

        In MOCK_MODE, calls `mock_factory(prompt, image_bytes_list)` (if given)
        to produce a deterministic stub; otherwise returns a neutral stub. This
        matches GeminiClient exactly, so the pipeline's per-stage mocks work
        unchanged when the provider is Claude.
        """
        if self.mock:
            if mock_factory is not None:
                return mock_factory(prompt, image_bytes_list or [])
            return {"_mock": True, "_provider": "claude"}

        last_err: Exception | None = None
        for attempt in range(config.MAX_RETRIES):
            try:
                self._throttle()
                return self._live_call(prompt, image_bytes_list or [])
            except Exception as e:  # noqa: BLE001 - backoff on any transient error
                last_err = e
                time.sleep(config.RETRY_BASE_DELAY_S * (2 ** attempt))
        raise RuntimeError(f"Claude call failed after retries: {last_err}")

    # -- rate limiting / parsing (shared with GeminiClient) -------------------
    _throttle = staticmethod(GeminiClient._throttle)
    parse_json = staticmethod(GeminiClient.parse_json)

    # -- image prep (enforce the vision-docs format/size constraints) ---------
    @staticmethod
    def _prepare_image(image_bytes: bytes) -> tuple[str, str]:
        """Return (media_type, base64_data) ready for an image content block.

        Guarantees a Claude-supported media type and bounds the image to the
        model's native resolution / size limits:
          - already a supported format AND within limits -> sent unchanged;
          - otherwise (unsupported type like AVIF/HEIC, oversized, or too large)
            -> decoded and re-encoded to JPEG, downscaled so the long edge ≤
            2576 px.
        Falls back to the raw bytes + sniffed mime if Pillow is unavailable or
        cannot decode the image (the API will then reject a truly unsupported
        format, which is the correct, visible failure mode).
        """
        mime = detect_mime(image_bytes)
        try:
            from PIL import Image
        except Exception:  # Pillow not installed -> best effort
            return mime, base64.standard_b64encode(image_bytes).decode("utf-8")

        try:
            with Image.open(io.BytesIO(image_bytes)) as im:
                w, h = im.size
                if (mime in _SUPPORTED_MEDIA
                        and max(w, h) <= _MAX_EDGE_PX
                        and len(image_bytes) <= _MAX_RAW_BYTES):
                    # Compliant already — avoid a needless re-encode.
                    return mime, base64.standard_b64encode(image_bytes).decode("utf-8")
                im = im.convert("RGB")  # flatten alpha/palette for JPEG
                scale = _MAX_EDGE_PX / max(w, h)
                if scale < 1.0:
                    im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))))
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=90)
                return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            return mime, base64.standard_b64encode(image_bytes).decode("utf-8")

    # -- internals ------------------------------------------------------------
    def _ensure_sdk(self):
        """Lazily import and configure the anthropic SDK."""
        if self._sdk is not None:
            return self._sdk
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set; cannot make live Claude calls."
            )
        import anthropic  # imported lazily so mock mode needs no SDK

        self._sdk = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        return self._sdk

    def _live_call(self, prompt: str, image_bytes_list: list[bytes]) -> dict[str, Any]:
        client = self._ensure_sdk()

        # Images first, then the text instruction (docs: images before text).
        content: list[dict[str, Any]] = []
        for img in image_bytes_list:
            media_type, data = self._prepare_image(img)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            })
        content.append({"type": "text", "text": prompt})

        # No temperature/top_p (removed on Opus 4.8); no thinking config (omitted
        # => thinking off => deterministic, cheap JSON extraction).
        message = client.messages.create(
            model=self.model,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(
            b.text for b in message.content if getattr(b, "type", None) == "text"
        )
        return self.parse_json(text)
