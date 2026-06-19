"""
Stage 3 - requirements-aware decision.

Combines the parsed claim, the per-image findings, and the matched
evidence_requirements rule into the final fields:
  evidence_standard_met, valid_image, issue_type, object_part,
  claim_status, supporting_image_ids, severity, justifications.

NOTE: This is intentionally a thin, transparent rule layer over the VLM
findings. In iteration 2 we can optionally add a final "decider" LLM call for
the hard multi-image cases (identity mismatch, etc.). For now it is fully
deterministic so the contract is testable offline.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.claim_parser import ParsedClaim
from pipeline.image_analysis import ImageFinding


@dataclass
class Decision:
    evidence_standard_met: bool
    evidence_standard_met_reason: str
    issue_type: str
    object_part: str
    claim_status: str
    claim_status_justification: str
    supporting_image_ids: str
    valid_image: bool
    severity: str
    risk_flags: list[str]


def match_requirement(
    claim_object: str, parsed: ParsedClaim, requirements: list[dict]
) -> dict | None:
    """Pick the most relevant evidence requirement rule (best-effort)."""
    # Prefer an object-specific rule whose `applies_to` family overlaps the
    # claimed issue; fall back to a general ('all') rule.
    issue = (parsed.claimed_issue or "").lower()
    candidates = [r for r in requirements if r.get("claim_object") == claim_object]
    for r in candidates:
        if any(tok in r.get("applies_to", "").lower() for tok in issue.split("_") if tok):
            return r
    if candidates:
        return candidates[0]
    return next((r for r in requirements if r.get("claim_object") == "all"), None)


def decide(
    claim_object: str,
    parsed: ParsedClaim,
    findings: list[ImageFinding],
    requirements: list[dict],
) -> Decision:
    risk_flags: list[str] = []
    requirement = match_requirement(claim_object, parsed, requirements)

    present = [f for f in findings if not f.missing]
    usable = [f for f in present if f.usable_for_review]

    # Aggregate quality flags as risk flags.
    for f in present:
        risk_flags.extend(f.quality_flags)

    # --- valid_image / evidence_standard_met -------------------------------
    valid_image = len(usable) > 0
    evidence_met = valid_image and any(f.shows_claimed_object for f in usable)

    # --- supporting images -------------------------------------------------
    supporting = [f.image_id for f in usable if f.issue_visible]
    supporting_ids = ";".join(supporting) if supporting else "none"

    # --- issue / part ------------------------------------------------------
    issue_finding = next((f for f in usable if f.issue_visible), None)
    issue_type = issue_finding.issue_type if issue_finding else (
        "none" if evidence_met else "unknown"
    )
    object_part = (
        issue_finding.issue_part if issue_finding
        else (parsed.claimed_parts[0] if parsed.claimed_parts else "unknown")
    )
    severity = issue_finding.severity if issue_finding else "none" if evidence_met else "unknown"

    # --- claim status ------------------------------------------------------
    if not evidence_met:
        claim_status = "not_enough_information"
        reason = (requirement or {}).get(
            "minimum_image_evidence", "Insufficient usable image evidence."
        )
        justification = "The submitted images do not provide enough usable evidence to evaluate the claim."
        if not valid_image:
            risk_flags.append("damage_not_visible")
    elif issue_finding is not None:
        claim_status = "supported"
        reason = "The claimed object/part is visible and the issue can be assessed."
        justification = (
            f"Image {issue_finding.image_id} shows {issue_finding.issue_type} on "
            f"{issue_finding.issue_part}, consistent with the claim."
        )
    else:
        # Object visible, but the claimed issue is not present -> contradicted.
        claim_status = "contradicted"
        reason = "The claimed object/part is visible but the claimed issue is not present."
        justification = "The relevant part is visible and shows no sign of the claimed damage."
        risk_flags.append("damage_not_visible")

    return Decision(
        evidence_standard_met=evidence_met,
        evidence_standard_met_reason=reason,
        issue_type=issue_type,
        object_part=object_part,
        claim_status=claim_status,
        claim_status_justification=justification,
        supporting_image_ids=supporting_ids,
        valid_image=valid_image,
        severity=severity,
        risk_flags=risk_flags,
    )
