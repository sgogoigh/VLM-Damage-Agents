"""
Stage 3 — chain-structured, deterministic decision.

Consumes the per-image VLM chain (object -> per-part issue -> severity welfare
check) and applies explicit, deterministic rules:

  1. Object check       -> wrong object / identity conflict short-circuits.
  2. Per-part merge      -> a claimed part is CONFIRMED if ANY usable image shows
                           the issue present at a non-exaggerated severity
                           (multi-image OR-merge, per the spec note).
  3. Welfare check       -> issue present but severity EXAGGERATED => contradicted.
  4. History tiebreaker  -> only when the visual signal is ambiguous; never
                           overrides clear evidence (adds manual review).

Every output field is derived from a definite rule/bucket.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.contract import OBJECT_PARTS
from app.core.pipeline.claim_parser import ParsedClaim
from app.core.pipeline.image_analysis import ImageFinding, PartVerdict

_SEV_ORDER = {"none": 0, "unknown": 0, "low": 1, "medium": 2, "high": 3}
_COSMETIC = {"scratch", "stain", "dent"}


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


def match_requirement(claim_object: str, parsed: ParsedClaim, requirements: list[dict]) -> dict | None:
    issue = (parsed.claimed_issue or "").lower()
    candidates = [r for r in requirements if r.get("claim_object") == claim_object]
    for r in candidates:
        if any(tok in r.get("applies_to", "").lower() for tok in issue.split("_") if tok):
            return r
    if candidates:
        return candidates[0]
    return next((r for r in requirements if r.get("claim_object") == "all"), None)


def _calibrate_severity(issue_type: str, raw: str) -> str:
    """Deterministic severity bucket. Cosmetic issues rarely warrant 'high'."""
    if issue_type in ("none", "unknown") or raw in ("none", "unknown", ""):
        return raw or "unknown"
    if issue_type in _COSMETIC and raw == "high":
        return "medium"
    return raw


def decide(
    claim_object: str,
    parsed: ParsedClaim,
    findings: list[ImageFinding],
    requirements: list[dict],
    user_history_risky: bool = False,
) -> Decision:
    risk_flags: list[str] = []
    requirement = match_requirement(claim_object, parsed, requirements) or {}
    req_min = requirement.get("minimum_image_evidence", "Sufficient, relevant image evidence is required.")
    claimed_parts = [p for p in parsed.claimed_parts if p] or ["unknown"]
    claimed_part = claimed_parts[0]
    claimed_issue = parsed.claimed_issue or "unknown"
    valid_parts = OBJECT_PARTS.get(claim_object, set())

    present = [f for f in findings if not f.missing]
    usable = [f for f in present if f.usable_for_review]

    for f in present:
        risk_flags.extend(f.quality_flags)
        if f.looks_non_original:
            risk_flags.append("non_original_image")
        if f.has_on_image_instruction_text:
            risk_flags.append("text_instruction_present")
    if getattr(parsed, "injection_detected", False):
        risk_flags.append("text_instruction_present")

    def D(**kw) -> Decision:
        base = dict(evidence_standard_met=False, evidence_standard_met_reason=req_min,
                    issue_type="unknown", object_part=claimed_part,
                    claim_status="not_enough_information", claim_status_justification="",
                    supporting_image_ids="none", valid_image=bool(usable),
                    severity="unknown", risk_flags=risk_flags)
        base.update(kw)
        return Decision(**base)

    # ---- No usable evidence ----------------------------------------------
    if not usable:
        risk_flags.append("damage_not_visible")
        return D(valid_image=False,
                 claim_status_justification="No usable image evidence was submitted to evaluate the claim.")

    matched = [f for f in usable if f.object_match == "match"]
    mismatched = [f for f in usable if f.object_match == "mismatch"]

    # ---- STEP 1: identity conflict (images disagree on the object) -------
    if len(usable) >= 2 and matched and mismatched:
        risk_flags += ["wrong_object", "claim_mismatch", "manual_review_required"]
        return D(evidence_standard_met=False, valid_image=True,
                 claim_status="not_enough_information",
                 evidence_standard_met_reason="Images appear to show different objects; identity cannot be confirmed.",
                 claim_status_justification="The submitted images appear to show different objects, so the claim cannot be reliably verified.")

    # ---- STEP 1: wrong object --------------------------------------------
    if not matched:
        if mismatched:
            risk_flags += ["wrong_object", "claim_mismatch"]
            ref = mismatched[0]
            return D(evidence_standard_met=True, valid_image=True,
                     object_part="unknown", claim_status="contradicted", severity="low",
                     evidence_standard_met_reason="The image is clear but shows a different object than claimed.",
                     claim_status_justification=f"Image {ref.image_id} does not show the claimed {claim_object}, so it does not support the claim.")
        risk_flags.append("damage_not_visible")
        return D(valid_image=True,
                 claim_status_justification="The submitted images do not clearly show the claimed object, so the claim cannot be evaluated.")

    # ---- STEP 2/3: per-part merge across matched usable images ------------
    confirming: list[tuple[str, ImageFinding, PartVerdict]] = []
    wrong_part: list[tuple[str, ImageFinding, PartVerdict]] = []
    undamaged: list[tuple[str, ImageFinding, PartVerdict]] = []
    any_part_visible = False

    for part in claimed_parts:
        for f in matched:
            v = f.verdict_for(part)
            if not v or not v.visible:
                continue
            any_part_visible = True
            claim_part_unmapped = part not in valid_parts  # parser couldn't pin it
            if v.actual_issue == "none":
                undamaged.append((part, f, v))        # visible & undamaged
            elif v.actual_issue in ("", "unknown"):
                continue                              # ambiguous -> NEI branch
            elif (v.actual_part in ("", "unknown", part) or v.actual_part == claimed_part
                  or claim_part_unmapped):
                confirming.append((part, f, v))
            else:
                wrong_part.append((part, f, v))        # real damage on a different part

    # Welfare check: customer claimed HIGH but a usable image judged it exaggerated.
    exaggeration = parsed.claimed_severity == "high" and any(
        f.severity_vs_claim == "exaggerated" for f in matched)

    if confirming and not exaggeration:
        part, f, v = max(confirming, key=lambda t: _SEV_ORDER.get(t[2].severity, 0))
        issue = v.actual_issue if v.actual_issue not in ("none", "unknown") else claimed_issue
        op = claimed_part if claimed_part in valid_parts else (
            v.actual_part if v.actual_part in valid_parts else claimed_part)
        ids = sorted({cf.image_id for _, cf, _ in confirming})
        return D(evidence_standard_met=True, valid_image=not f.looks_non_original,
                 issue_type=issue, object_part=op, claim_status="supported",
                 severity=_calibrate_severity(issue, v.severity),
                 supporting_image_ids=";".join(ids),
                 evidence_standard_met_reason="The claimed part is visible and the claimed damage is confirmed.",
                 claim_status_justification=f"Image {f.image_id} shows {issue} on the {op}, consistent with the claim.")

    if exaggeration and confirming:
        part, f, v = max(confirming, key=lambda t: _SEV_ORDER.get(t[2].severity, 0))
        op = claimed_part if claimed_part in valid_parts else v.actual_part
        risk_flags.append("claim_mismatch")
        return D(evidence_standard_met=True, valid_image=not f.looks_non_original,
                 issue_type=v.actual_issue, object_part=op, claim_status="contradicted",
                 severity=_calibrate_severity(v.actual_issue, v.severity),
                 supporting_image_ids=";".join(sorted({cf.image_id for _, cf, _ in confirming})),
                 evidence_standard_met_reason="The claimed part is visible, so the claim could be evaluated.",
                 claim_status_justification=f"The visible damage on the {op} is less severe than the claim implies, so the claim is contradicted.")

    if wrong_part:
        part, f, v = wrong_part[0]
        op = v.actual_part if v.actual_part in valid_parts else claimed_part
        risk_flags.append("claim_mismatch")
        return D(evidence_standard_met=True, valid_image=not f.looks_non_original,
                 issue_type=v.actual_issue, object_part=op, claim_status="contradicted",
                 severity=_calibrate_severity(v.actual_issue, v.severity),
                 supporting_image_ids=";".join(sorted({cf.image_id for _, cf, _ in wrong_part})),
                 evidence_standard_met_reason="The claimed part is visible, so the claim could be evaluated.",
                 claim_status_justification=f"Image {f.image_id} shows damage on the {op}, not the claimed {claimed_part}, so the claim is contradicted.")

    if undamaged:
        part, f, v = undamaged[0]
        risk_flags.append("damage_not_visible")
        return D(evidence_standard_met=True, valid_image=not f.looks_non_original,
                 issue_type="none", object_part=claimed_part, claim_status="contradicted",
                 severity="none",
                 supporting_image_ids=";".join(sorted({cf.image_id for _, cf, _ in undamaged})),
                 evidence_standard_met_reason="The claimed part is visible, so the claim could be evaluated.",
                 claim_status_justification=f"The {claimed_part} is visible and undamaged, so the claimed {claimed_issue} is contradicted.")

    # AMBIGUOUS: part visible but damage unclear -> history tiebreaker ------
    if any_part_visible:
        if user_history_risky:
            risk_flags.append("manual_review_required")
        return D(evidence_standard_met=True, valid_image=True, object_part=claimed_part,
                 claim_status="not_enough_information",
                 evidence_standard_met_reason="The claimed part is visible, but the claimed damage cannot be clearly confirmed or ruled out.",
                 claim_status_justification="The claimed part is visible but the claimed damage cannot be clearly confirmed; routed for review.")

    risk_flags.append("damage_not_visible")
    return D(valid_image=True, object_part=claimed_part,
             claim_status_justification=f"The claimed {claimed_part} is not clearly visible in the submitted images, so the claim cannot be evaluated.")
