"""
Anthropic Claude VLM client — alternative provider (available, off by default).

Exposes the same ``generate_json`` surface as ``GeminiClient`` so the pipeline
runs with Claude as the VLM simply by selecting ``provider="claude"``. Runs in
deterministic mock mode unless ``ANTHROPIC_API_KEY`` is set.

Model: **Claude Opus 4.8** (`claude-opus-4-8`) — vision-capable, most capable
Opus-tier model.

Vision request shape + limits (per the official vision docs):
- Images are base64 content blocks placed BEFORE the text block ("Claude works
  best when images come before text").
- Supported source media types are ONLY image/jpeg, image/png, image/gif,
  image/webp. Dataset files mislabeled .jpg that are actually AVIF/HEIC are
  re-encoded to JPEG via Pillow before sending.
- Per-image limits: ≤10 MB base64, ≤8000×8000 px; we downscale the long edge to
  the model's 2576 px native resolution to bound token cost.
- Opus 4.8 removed temperature/top_p/top_k (sending them 400s); thinking is
  adaptive-only and omitted here for cheap, low-variance JSON extraction;
  ``max_tokens`` is required.
"""
from __future__ import annotations

import base64
import io
from typing import Any

from app.config import Settings, get_settings
from app.core.llm.base import BaseLLMClient, detect_mime

# Anthropic vision accepts ONLY these source media types.
_SUPPORTED_MEDIA = {"image/jpeg", "image/png", "image/gif", "image/webp"}
# Opus 4.7+ native resolution: long edge ≤ 2576 px.
_MAX_EDGE_PX = 2576
# Keep raw bytes well under the 10 MB *base64* per-image cap (base64 ≈ +33%).
_MAX_RAW_BYTES = 7_000_000

# Best-effort: register AVIF/HEIC decoders with Pillow if pillow-heif is present.
try:  # pragma: no cover - optional dependency
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
    try:
        pillow_heif.register_avif_opener()
    except Exception:
        pass
except Exception:
    pass


class ClaudeClient(BaseLLMClient):
    name = "claude"

    def __init__(self, model: str | None = None, settings: Settings | None = None) -> None:
        s = settings or get_settings()
        super().__init__(
            model=model or s.claude_model,
            mock=s.claude_mock,
            # Claude has generous limits; reuse Gemini's RPM knob as a gentle pace.
            rpm=s.gemini_rpm,
            settings=s,
        )

    # -- image prep (enforce the vision-docs format/size constraints) -------
    @staticmethod
    def _prepare_image(image_bytes: bytes) -> tuple[str, str]:
        """Return (media_type, base64_data) ready for an image content block.

        Guarantees a Claude-supported media type and bounds the image to the
        model's native resolution / size limits. Falls back to raw bytes +
        sniffed mime if Pillow is unavailable or cannot decode the image.
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

    # -- internals ----------------------------------------------------------
    def _ensure_sdk(self) -> Any:
        if self._sdk is not None:
            return self._sdk
        if not self.settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; cannot make live Claude calls.")
        import anthropic  # lazily imported so mock mode needs no SDK

        self._sdk = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self._sdk

    def _live_call(self, prompt: str, image_bytes_list: list[bytes]) -> dict[str, Any]:
        client = self._ensure_sdk()

        content: list[dict[str, Any]] = []
        for img in image_bytes_list:  # images first, then text (docs)
            media_type, data = self._prepare_image(img)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })
        content.append({"type": "text", "text": prompt})

        message = client.messages.create(
            model=self.model,
            max_tokens=self.settings.claude_max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(
            b.text for b in message.content if getattr(b, "type", None) == "text"
        )
        return self.parse_json(text)
