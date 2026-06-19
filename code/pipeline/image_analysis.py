"""
Stage 2 - per-image VLM analysis (claim-grounded, staged).

Each image is analyzed independently against the specific claim and answers
the staged verification questions (category -> part visible -> issue present).
Cached by content hash; in MOCK_MODE a neutral, deterministic finding is
returned (no API call).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import config
from data_io import image_id_from_path, resolve_image_path
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline.claim_parser import ParsedClaim
from schema import ISSUE_TYPES, OBJECT_PARTS


@dataclass
class ImageFinding:
    image_id: str
    rel_path: str
    # Stage 1 - category
    object_match: str = "unclear"          # match | mismatch | unclear
    object_color: str = ""
    identity_descriptor: str = ""
    # Stage 2 - part
    claimed_part_visible: bool = False
    actual_part: str = "unknown"
    # Stage 3 - issue
    claimed_issue_present: str = "unclear"  # yes | no | unclear
    actual_issue_type: str = "unknown"
    severity: str = "unknown"
    # Stage 4 - usability / authenticity
    usable_for_review: bool = False
    looks_non_original: bool = False
    has_on_image_instruction_text: bool = False
    quality_flags: list[str] = field(default_factory=list)
    notes: str = ""
    missing: bool = False  # image file not found on disk


def _mock_finding(_prompt: str, _imgs) -> dict:
    # Neutral placeholder: must not pretend to "see" anything.
    return {
        "object_match": "unclear",
        "object_color": "",
        "identity_descriptor": "",
        "claimed_part_visible": False,
        "actual_part": "unknown",
        "claimed_issue_present": "unclear",
        "actual_issue_type": "unknown",
        "severity": "unknown",
        "usable_for_review": False,
        "looks_non_original": False,
        "has_on_image_instruction_text": False,
        "quality_flags": [],
        "notes": "(mock) no live VLM analysis performed",
    }


def analyze_image(
    rel_path: str,
    claim_object: str,
    parsed: ParsedClaim,
    client: GeminiClient,
    cache: AnalysisCache,
) -> ImageFinding:
    from pipeline import prompts

    image_id = image_id_from_path(rel_path)
    abs_path: Path = resolve_image_path(rel_path)

    if not abs_path.exists():
        return ImageFinding(image_id=image_id, rel_path=rel_path, missing=True,
                            notes="image file not found")

    image_bytes = abs_path.read_bytes()

    # Namespace includes prompt version + model + mode so mock placeholders never
    # collide with live results and prompt/model changes invalidate the cache.
    cache_ns = (
        f"{prompts.IMAGE_ANALYSIS_VERSION}|{config.GEMINI_MODEL}|"
        f"{'mock' if client.mock else 'live'}"
    )

    cached = cache.get(image_bytes, cache_ns)
    if cached is not None:
        data = cached
    else:
        allowed_parts = ", ".join(sorted(OBJECT_PARTS.get(claim_object, {"unknown"})))
        allowed_issues = ", ".join(sorted(ISSUE_TYPES))
        prompt = prompts.render(
            prompts.IMAGE_ANALYSIS_TEMPLATE,
            claim_object=claim_object,
            claimed_issue=parsed.claimed_issue,
            claimed_part=", ".join(parsed.claimed_parts),
            claim_summary=parsed.summary or "(see claimed part/issue)",
            image_id=image_id,
            allowed_parts=allowed_parts,
            allowed_issues=allowed_issues,
        )
        data = client.generate_json(prompt, [image_bytes], mock_factory=_mock_finding)
        cache.put(image_bytes, cache_ns, data)

    return ImageFinding(
        image_id=image_id,
        rel_path=rel_path,
        object_match=str(data.get("object_match", "unclear")).lower(),
        object_color=str(data.get("object_color", "")).lower(),
        identity_descriptor=data.get("identity_descriptor", ""),
        claimed_part_visible=bool(data.get("claimed_part_visible", False)),
        actual_part=data.get("actual_part", "unknown"),
        claimed_issue_present=str(data.get("claimed_issue_present", "unclear")).lower(),
        actual_issue_type=data.get("actual_issue_type", "unknown"),
        severity=data.get("severity", "unknown"),
        usable_for_review=bool(data.get("usable_for_review", False)),
        looks_non_original=bool(data.get("looks_non_original", False)),
        has_on_image_instruction_text=bool(data.get("has_on_image_instruction_text", False)),
        quality_flags=list(data.get("quality_flags", []) or []),
        notes=data.get("notes", ""),
    )


def analyze_images(
    rel_paths: list[str],
    claim_object: str,
    parsed: ParsedClaim,
    client: GeminiClient,
    cache: AnalysisCache,
) -> list[ImageFinding]:
    return [analyze_image(p, claim_object, parsed, client, cache) for p in rel_paths]
