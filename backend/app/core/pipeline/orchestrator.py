"""
Orchestrator — run the full chain for one claim and build a schema-valid
PredictionRow.

  Stage 1  parse claim  (object, parts, issue, severity, multi_part)
  Stage 2  per-image VLM chain (object -> per-part issue -> severity welfare)
  Stage 3  deterministic decision (merge + welfare + history tiebreaker)
  Stage 4  user-history risk overlay (context flags only; never flips status)
"""
from __future__ import annotations

from app.core.cache import AnalysisCache
from app.core.contract import ClaimRecord, PredictionRow
from app.core.llm.base import BaseLLMClient
from app.core.pipeline.claim_parser import parse_claim
from app.core.pipeline.decision import decide
from app.core.pipeline.image_analysis import analyze_images
from app.core.pipeline.risk import apply_user_history


def _history_risky(history_row: dict | None) -> bool:
    if not history_row:
        return False
    hist = (history_row.get("history_flags", "") or "").strip().lower()
    return "user_history_risk" in hist or "manual_review_required" in hist


def run_pipeline(
    record: ClaimRecord,
    *,
    history: dict[str, dict[str, str]],
    requirements: list[dict],
    client: BaseLLMClient,
    cache: AnalysisCache,
) -> PredictionRow:
    parsed = parse_claim(record.claim_object, record.user_claim, client, cache)

    findings = analyze_images(
        record.image_path_list, record.claim_object, parsed, client, cache
    )

    decision = decide(record.claim_object, parsed, findings, requirements,
                      user_history_risky=_history_risky(history.get(record.user_id)))

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
