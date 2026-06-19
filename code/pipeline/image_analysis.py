"""
Stage 2 - per-image VLM analysis.

Each image is analyzed independently (problem_statement REQ_GENERAL_MULTI_IMAGE),
cached by content hash, and deduped so the same image is never analyzed twice.
In MOCK_MODE a neutral, deterministic finding is returned (no API call).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import config
from data_io import image_id_from_path, resolve_image_path
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline import prompts
from pipeline.claim_parser import ParsedClaim
from schema import ISSUE_TYPES, OBJECT_PARTS


@dataclass
class ImageFinding:
    image_id: str
    rel_path: str
    shows_claimed_object: bool = False
    object_seen: str = "unclear"
    identity_descriptor: str = ""
    visible_part: str = "unknown"
    issue_visible: bool = False
    issue_type: str = "unknown"
    issue_part: str = "unknown"
    severity: str = "unknown"
    usable_for_review: bool = False
    looks_non_original: bool = False
    has_on_image_instruction_text: bool = False
    quality_flags: list[str] = field(default_factory=list)
    notes: str = ""
    missing: bool = False  # image file not found on disk


def _mock_finding(_prompt: str, _imgs) -> dict:
    # Neutral placeholder: scaffolding must not pretend to "see" anything.
    return {
        "shows_claimed_object": False,
        "object_seen": "unclear",
        "identity_descriptor": "",
        "visible_part": "unknown",
        "issue_visible": False,
        "issue_type": "unknown",
        "issue_part": "unknown",
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
    image_id = image_id_from_path(rel_path)
    abs_path: Path = resolve_image_path(rel_path)

    if not abs_path.exists():
        return ImageFinding(image_id=image_id, rel_path=rel_path, missing=True,
                            notes="image file not found")

    image_bytes = abs_path.read_bytes()

    # Cache namespace includes prompt version + model + mode so that mock
    # placeholders never collide with live results (and switching models or
    # editing the prompt correctly invalidates prior analyses).
    cache_ns = (
        f"{prompts.IMAGE_ANALYSIS_VERSION}|{config.GEMINI_MODEL}|"
        f"{'mock' if client.mock else 'live'}"
    )

    # Cache lookup (skip the call entirely on a hit).
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
            image_id=image_id,
            allowed_parts=allowed_parts,
            allowed_issues=allowed_issues,
        )
        data = client.generate_json(prompt, [image_bytes], mock_factory=_mock_finding)
        cache.put(image_bytes, cache_ns, data)

    return ImageFinding(
        image_id=image_id,
        rel_path=rel_path,
        shows_claimed_object=bool(data.get("shows_claimed_object", False)),
        object_seen=data.get("object_seen", "unclear"),
        identity_descriptor=data.get("identity_descriptor", ""),
        visible_part=data.get("visible_part", "unknown"),
        issue_visible=bool(data.get("issue_visible", False)),
        issue_type=data.get("issue_type", "unknown"),
        issue_part=data.get("issue_part", "unknown"),
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
