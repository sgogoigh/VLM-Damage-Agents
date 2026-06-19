"""
Stage 3 - staged, claim-grounded decision.

Implements the verification workflow the per-image VLM was prompted for:
  STEP 1  category: does the image show the claimed object?
  STEP 2  part:     is the claimed part visible?
  STEP 3  issue:    is the CLAIMED issue present on the claimed part?

The decision compares the EVIDENCE against the CLAIM, so "some damage is
visible" is no longer enough to mark a claim supported - the visible damage must
match what the customer claimed, or the claim is contradicted.

Fully deterministic so behaviour is reproducible and explainable.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.claim_parser import ParsedClaim
from pipeline.image_analysis import ImageFinding
from schema import OBJECT_PARTS

_SEV_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "unknown": 0}


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
    issue = (parsed.claimed_issue or "").lower()
    candidates = [r for r in requirements if r.get("claim_object") == claim_object]
    for r in candidates:
        if any(tok in r.get("applies_to", "").lower() for tok in issue.split("_") if tok):
            return r
    if candidates:
        return candidates[0]
    return next((r for r in requirements if r.get("claim_object") == "all"), None)


def _most_severe(findings: list[ImageFinding]) -> ImageFinding:
    return max(findings, key=lambda f: _SEV_ORDER.get(f.severity, 0))


def decide(
    claim_object: str,
    parsed: ParsedClaim,
    findings: list[ImageFinding],
    requirements: list[dict],
) -> Decision:
    risk_flags: list[str] = []
    requirement = match_requirement(claim_object, parsed, requirements) or {}
    req_min = requirement.get("minimum_image_evidence", "Sufficient, relevant image evidence is required.")
    claimed_part = parsed.claimed_parts[0] if parsed.claimed_parts else "unknown"
    claimed_issue = parsed.claimed_issue or "unknown"

    present = [f for f in findings if not f.missing]
    usable = [f for f in present if f.usable_for_review]

    # Aggregate quality / authenticity / injection flags (apply to any outcome).
    for f in present:
        risk_flags.extend(f.quality_flags)
        if f.looks_non_original:
            risk_flags.append("non_original_image")
        if f.has_on_image_instruction_text:
            risk_flags.append("text_instruction_present")
    if getattr(parsed, "injection_detected", False):
        risk_flags.append("text_instruction_present")

    def D(**kw) -> Decision:
        base = dict(evidence_standard_met=False, evidence_standard_met_reason="",
                    issue_type="unknown", object_part=claimed_part,
                    claim_status="not_enough_information", claim_status_justification="",
                    supporting_image_ids="none", valid_image=bool(usable),
                    severity="unknown", risk_flags=risk_flags)
        base.update(kw)
        return Decision(**base)

    # ---- No usable evidence at all -> not_enough_information ----------------
    if not usable:
        risk_flags.append("damage_not_visible")
        return D(evidence_standard_met=False, valid_image=False,
                 evidence_standard_met_reason=req_min,
                 claim_status_justification="No usable image evidence was submitted to evaluate the claim.")

    matched = [f for f in usable if f.object_match == "match"]
    mismatched = [f for f in usable if f.object_match == "mismatch"]

    # ---- STEP 1: identity conflict across multiple images -> NEI -----------
    # Only when images explicitly disagree on whether the claimed object is even
    # present (one says match, another mismatch). NOTE: we deliberately do NOT
    # use color/descriptor differences - close-ups vs full shots of the same
    # object legitimately differ and that produced false conflicts.
    identity_conflict = len(usable) >= 2 and bool(matched) and bool(mismatched)
    if identity_conflict:
        risk_flags += ["wrong_object", "claim_mismatch", "manual_review_required"]
        ref = _most_severe(usable)
        return D(evidence_standard_met=False, valid_image=True,
                 issue_type=ref.actual_issue_type, object_part=claimed_part,
                 claim_status="not_enough_information",
                 evidence_standard_met_reason="Images appear to show different objects; identity cannot be confirmed.",
                 claim_status_justification="The submitted images appear to show different objects, so the claim cannot be reliably verified.")

    # ---- STEP 1: wrong object (nothing matches the claimed object) ---------
    if not matched:
        if mismatched:
            risk_flags += ["wrong_object", "claim_mismatch"]
            ref = mismatched[0]
            return D(evidence_standard_met=True, valid_image=True,
                     issue_type=ref.actual_issue_type if ref.actual_issue_type != "unknown" else "unknown",
                     object_part="unknown", claim_status="contradicted",
                     severity=ref.severity if ref.severity != "unknown" else "low",
                     evidence_standard_met_reason="The image is clear but shows a different object than claimed.",
                     claim_status_justification=f"Image {ref.image_id} does not show the claimed {claim_object}, so it does not support the claim.")
        # object can't be confirmed (all unclear)
        risk_flags.append("damage_not_visible")
        return D(evidence_standard_met=False, valid_image=True,
                 claim_status="not_enough_information",
                 evidence_standard_met_reason=req_min,
                 claim_status_justification="The submitted images do not clearly show the claimed object, so the claim cannot be evaluated.")

    valid_parts = OBJECT_PARTS.get(claim_object, set())

    # ---- STEP 2/3: issue presence drives the decision ----------------------
    # If the claimed issue is visibly present, the part is implicitly shown ->
    # supported (don't gate on the VLM's exact part-naming, which is noisy).
    yes = [f for f in matched if f.claimed_issue_present == "yes"]
    if yes:
        ref = _most_severe(yes)
        issue = ref.actual_issue_type if ref.actual_issue_type not in ("none", "unknown") else claimed_issue
        part = claimed_part if claimed_part in valid_parts else (
            ref.actual_part if ref.actual_part in valid_parts else claimed_part)
        valid = not ref.looks_non_original
        return D(evidence_standard_met=True, valid_image=valid,
                 issue_type=issue, object_part=part,
                 claim_status="supported", severity=ref.severity,
                 supporting_image_ids=";".join(f.image_id for f in yes),
                 evidence_standard_met_reason="The claimed part is visible and the claimed issue is confirmed.",
                 claim_status_justification=f"Image {ref.image_id} shows {issue} on the {part}, consistent with the claim.")

    # No confirmation. Is the claimed part at least visible to rule it in/out?
    part_imgs = [f for f in matched if f.claimed_part_visible]
    no = [f for f in part_imgs if f.claimed_issue_present == "no"]

    if no:
        ref = _most_severe(no)
        actual = ref.actual_issue_type
        part = ref.actual_part if ref.actual_part in valid_parts else claimed_part
        risk_flags.append("damage_not_visible" if actual in ("none", "unknown") else "claim_mismatch")
        valid = not ref.looks_non_original
        sev = ref.severity if actual not in ("none", "unknown") else "none"
        return D(evidence_standard_met=True, valid_image=valid,
                 issue_type=actual, object_part=part, claim_status="contradicted",
                 severity=sev, supporting_image_ids=";".join(f.image_id for f in no),
                 evidence_standard_met_reason="The claimed part is visible, so the claim could be evaluated.",
                 claim_status_justification=f"Image {ref.image_id} shows the {claimed_part} but not the claimed {claimed_issue}, so the claim is contradicted.")

    # Part not visible / issue indeterminable -> not enough information.
    risk_flags.append("damage_not_visible")
    return D(evidence_standard_met=False, valid_image=True, object_part=claimed_part,
             claim_status="not_enough_information",
             evidence_standard_met_reason=req_min,
             claim_status_justification=f"The claimed {claimed_part} or issue cannot be clearly assessed from the submitted images.")
