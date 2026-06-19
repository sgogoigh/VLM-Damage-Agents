"""
Optional final "decider" LLM pass (text-only).

Takes the parsed claim + per-image findings + the matched evidence requirement
and produces the holistic, vocabulary-mapped decision - including cross-image
consistency reasoning that the independent per-image analysis cannot do.

Cached by a hash of its full text input so re-runs are free. Falls back to the
deterministic `decision.decide` when disabled or in mock mode (handled by the
orchestrator).
"""
from __future__ import annotations

import json

import config
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline import prompts
from pipeline.claim_parser import ParsedClaim
from pipeline.decision import Decision, match_requirement
from pipeline.image_analysis import ImageFinding
from schema import ISSUE_TYPES, OBJECT_PARTS


def _findings_payload(findings: list[ImageFinding]) -> list[dict]:
    out = []
    for f in findings:
        if f.missing:
            out.append({"image_id": f.image_id, "missing": True})
            continue
        out.append({
            "image_id": f.image_id,
            "object_match": f.object_match,
            "object_color": f.object_color,
            "identity_descriptor": f.identity_descriptor,
            "claimed_part_visible": f.claimed_part_visible,
            "actual_part": f.actual_part,
            "claimed_issue_present": f.claimed_issue_present,
            "actual_issue_type": f.actual_issue_type,
            "severity": f.severity,
            "usable_for_review": f.usable_for_review,
            "looks_non_original": f.looks_non_original,
            "has_on_image_instruction_text": f.has_on_image_instruction_text,
            "quality_flags": f.quality_flags,
            "notes": f.notes,
        })
    return out


def run_decider(
    claim_object: str,
    parsed: ParsedClaim,
    findings: list[ImageFinding],
    requirements: list[dict],
    client: GeminiClient,
    cache: AnalysisCache,
) -> Decision:
    requirement = match_requirement(claim_object, parsed, requirements) or {}
    findings_json = json.dumps(_findings_payload(findings), ensure_ascii=False)

    prompt = prompts.render(
        prompts.DECIDER_TEMPLATE,
        claim_object=claim_object,
        claimed_parts=", ".join(parsed.claimed_parts),
        claimed_issue=parsed.claimed_issue,
        claim_summary=parsed.summary,
        injection_detected=str(parsed.injection_detected).lower(),
        requirement_text=requirement.get("minimum_image_evidence", ""),
        findings_json=findings_json,
        allowed_issues=", ".join(sorted(ISSUE_TYPES)),
        allowed_parts=", ".join(sorted(OBJECT_PARTS.get(claim_object, {"unknown"}))),
    )

    cache_ns = f"{prompts.DECIDER_VERSION}|{config.GEMINI_MODEL}"
    key_bytes = prompt.encode("utf-8")
    data = cache.get(key_bytes, cache_ns)
    if data is None:
        data = client.generate_json(prompt)
        cache.put(key_bytes, cache_ns, data)

    supporting = data.get("supporting_image_ids") or []
    if isinstance(supporting, str):
        supporting = [supporting]
    supporting_ids = ";".join(s for s in supporting if s and s != "none") or "none"

    risk_flags = list(data.get("risk_flags", []) or [])
    if parsed.injection_detected and "text_instruction_present" not in risk_flags:
        risk_flags.append("text_instruction_present")

    return Decision(
        evidence_standard_met=bool(data.get("evidence_standard_met", False)),
        evidence_standard_met_reason=data.get("evidence_standard_met_reason", ""),
        issue_type=data.get("issue_type", "unknown"),
        object_part=data.get("object_part", "unknown"),
        claim_status=data.get("claim_status", "not_enough_information"),
        claim_status_justification=data.get("claim_status_justification", ""),
        supporting_image_ids=supporting_ids,
        valid_image=bool(data.get("valid_image", False)),
        severity=data.get("severity", "unknown"),
        risk_flags=risk_flags,
    )
