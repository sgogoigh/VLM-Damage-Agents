"""
Orchestrator - run the full 4-stage pipeline for one claim and build a
schema-valid PredictionRow.
"""
from __future__ import annotations

from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline.claim_parser import parse_claim
from pipeline.decision import decide
from pipeline.image_analysis import analyze_images
from pipeline.risk import apply_user_history
from schema import ClaimRecord, PredictionRow


def run_pipeline(
    record: ClaimRecord,
    *,
    history: dict[str, dict[str, str]],
    requirements: list[dict],
    client: GeminiClient,
    cache: AnalysisCache,
) -> PredictionRow:
    # Stage 1 - parse the claim
    parsed = parse_claim(record.claim_object, record.user_claim, client)

    # Stage 2 - analyze each image (cached/deduped)
    findings = analyze_images(
        record.image_path_list, record.claim_object, parsed, client, cache
    )

    # Stage 3 - requirements-aware decision
    decision = decide(record.claim_object, parsed, findings, requirements)

    # Stage 4 - user-history risk overlay (context only)
    risk_flags = apply_user_history(
        record.user_id, history, decision.risk_flags, decision.claim_status
    )

    return PredictionRow(
        user_id=record.user_id,
        image_paths=record.image_paths,
        user_claim=record.user_claim,
        claim_object=record.claim_object,
        evidence_standard_met=decision.evidence_standard_met,
        evidence_standard_met_reason=decision.evidence_standard_met_reason,
        risk_flags=risk_flags,
        issue_type=decision.issue_type,
        object_part=decision.object_part,
        claim_status=decision.claim_status,
        claim_status_justification=decision.claim_status_justification,
        supporting_image_ids=decision.supporting_image_ids,
        valid_image=decision.valid_image,
        severity=decision.severity,
    )
