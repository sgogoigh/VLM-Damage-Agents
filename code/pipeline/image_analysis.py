"""
Stage 2 - per-image VLM analysis (claim-grounded chain).

Each image is analyzed independently against the specific claim and answers the
chain: STEP 1 object check -> STEP 2 per-part issue check -> STEP 3 severity
welfare check -> STEP 4 usability/authenticity. Cached by content hash; in
MOCK_MODE a neutral, deterministic finding is returned (no API call).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from code.data_io import image_id_from_path, resolve_image_path
from code.llm.cache import AnalysisCache
from code.llm.gemini_client import GeminiClient
from code.pipeline.claim_parser import ParsedClaim
from code.schema import ISSUE_TYPES, OBJECT_PARTS


@dataclass
class PartVerdict:
    part: str
    visible: bool = False
    issue_present: str = "unclear"   # yes | no | unclear
    actual_issue: str = "unknown"
    actual_part: str = "unknown"
    severity: str = "unknown"


@dataclass
class ImageFinding:
    image_id: str
    rel_path: str
    object_match: str = "unclear"            # match | mismatch | unclear
    object_color: str = ""
    identity_descriptor: str = ""
    parts: list[PartVerdict] = field(default_factory=list)
    severity_vs_claim: str = "unclear"       # reasonable | exaggerated | understated | unclear
    usable_for_review: bool = False
    looks_non_original: bool = False
    has_on_image_instruction_text: bool = False
    quality_flags: list[str] = field(default_factory=list)
    notes: str = ""
    missing: bool = False

    def verdict_for(self, part: str) -> PartVerdict | None:
        for v in self.parts:
            if v.part == part:
                return v
        return self.parts[0] if self.parts else None


def _coerce_parts(raw: list, claimed_parts: list[str]) -> list[PartVerdict]:
    out: list[PartVerdict] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        out.append(PartVerdict(
            part=str(item.get("part", "unknown")).strip().lower().replace(" ", "_"),
            visible=bool(item.get("visible", False)),
            issue_present=str(item.get("issue_present", "unclear")).strip().lower(),
            actual_issue=str(item.get("actual_issue", "unknown")).strip().lower(),
            actual_part=str(item.get("actual_part", "unknown")).strip().lower().replace(" ", "_"),
            severity=str(item.get("severity", "unknown")).strip().lower(),
        ))
    if not out:  # ensure at least the claimed parts are represented
        out = [PartVerdict(part=p) for p in (claimed_parts or ["unknown"])]
    return out


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
    # Namespace the cache by the ACTUAL client model (not a hardcoded Gemini
    # model) so Gemini and Claude analyses never collide. For the default Gemini
    # client this is the same string as before, so existing cache stays valid.
    cache_ns = (
        f"{prompts.IMAGE_ANALYSIS_VERSION}|{client.model}|"
        f"{'mock' if client.mock else 'live'}"
    )

    def _mock(_prompt: str, _imgs) -> dict:
        return {
            "object_match": "unclear", "object_color": "", "identity_descriptor": "",
            "parts": [{"part": p, "visible": False, "issue_present": "unclear",
                       "actual_issue": "unknown", "severity": "unknown"}
                      for p in (parsed.claimed_parts or ["unknown"])],
            "severity_vs_claim": "unclear", "usable_for_review": False,
            "looks_non_original": False, "has_on_image_instruction_text": False,
            "quality_flags": [], "notes": "(mock) no live VLM analysis performed",
        }

    cached = cache.get(image_bytes, cache_ns)
    if cached is not None:
        data = cached
    else:
        prompt = prompts.render(
            prompts.IMAGE_ANALYSIS_TEMPLATE,
            claim_object=claim_object,
            claimed_parts=", ".join(parsed.claimed_parts),
            claimed_issue=parsed.claimed_issue,
            claimed_severity=parsed.claimed_severity,
            claim_summary=parsed.summary or "(see claimed part/issue)",
            image_id=image_id,
            allowed_parts=", ".join(sorted(OBJECT_PARTS.get(claim_object, {"unknown"}))),
            allowed_issues=", ".join(sorted(ISSUE_TYPES)),
        )
        data = client.generate_json(prompt, [image_bytes], mock_factory=_mock)
        cache.put(image_bytes, cache_ns, data)

    return ImageFinding(
        image_id=image_id,
        rel_path=rel_path,
        object_match=str(data.get("object_match", "unclear")).lower(),
        object_color=str(data.get("object_color", "")).lower(),
        identity_descriptor=data.get("identity_descriptor", ""),
        parts=_coerce_parts(data.get("parts"), parsed.claimed_parts),
        severity_vs_claim=str(data.get("severity_vs_claim", "unclear")).lower(),
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
