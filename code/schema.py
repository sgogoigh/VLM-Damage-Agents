"""
Output contract: exact column order and closed allowed-value lists.

Source of truth: problem_statement.md ("Required output", "Allowed values").
Every value the pipeline emits is coerced to the closest allowed value before
being written, so output.csv can never contain an out-of-vocabulary token.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Exact output column order (problem_statement.md). DO NOT reorder.
# ---------------------------------------------------------------------------
OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

INPUT_COLUMNS = ["user_id", "image_paths", "user_claim", "claim_object"]

# ---------------------------------------------------------------------------
# Closed allowed-value vocabularies
# ---------------------------------------------------------------------------
CLAIM_OBJECTS = {"car", "laptop", "package"}

CLAIM_STATUS = {"supported", "contradicted", "not_enough_information"}

ISSUE_TYPES = {
    "dent", "scratch", "crack", "glass_shatter", "broken_part", "missing_part",
    "torn_packaging", "crushed_packaging", "water_damage", "stain", "none",
    "unknown",
}

OBJECT_PARTS = {
    "car": {
        "front_bumper", "rear_bumper", "door", "hood", "windshield",
        "side_mirror", "headlight", "taillight", "fender", "quarter_panel",
        "body", "unknown",
    },
    "laptop": {
        "screen", "keyboard", "trackpad", "hinge", "lid", "corner", "port",
        "base", "body", "unknown",
    },
    "package": {
        "box", "package_corner", "package_side", "seal", "label", "contents",
        "item", "unknown",
    },
}

RISK_FLAGS = {
    "none", "blurry_image", "cropped_or_obstructed", "low_light_or_glare",
    "wrong_angle", "wrong_object", "wrong_object_part", "damage_not_visible",
    "claim_mismatch", "possible_manipulation", "non_original_image",
    "text_instruction_present", "user_history_risk", "manual_review_required",
}

SEVERITY = {"none", "low", "medium", "high", "unknown"}


# ---------------------------------------------------------------------------
# Coercion helpers - guarantee schema-valid output
# ---------------------------------------------------------------------------
def coerce_issue_type(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in ISSUE_TYPES else "unknown"


def coerce_object_part(value: str | None, claim_object: str) -> str:
    v = (value or "").strip().lower()
    allowed = OBJECT_PARTS.get(claim_object, set())
    return v if v in allowed else "unknown"


def coerce_claim_status(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in CLAIM_STATUS else "not_enough_information"


def coerce_severity(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in SEVERITY else "unknown"


def coerce_risk_flags(values: list[str] | None) -> str:
    """Filter to allowed flags, dedupe, and join with ';'. 'none' if empty."""
    if not values:
        return "none"
    seen: list[str] = []
    for raw in values:
        v = (raw or "").strip().lower()
        if v and v != "none" and v in RISK_FLAGS and v not in seen:
            seen.append(v)
    return ";".join(seen) if seen else "none"


def as_bool_str(value: bool) -> str:
    """Output uses lowercase 'true'/'false' (see sample_claims.csv)."""
    return "true" if value else "false"


@dataclass
class ClaimRecord:
    """One input row from claims.csv / sample_claims.csv."""

    user_id: str
    image_paths: str
    user_claim: str
    claim_object: str

    @property
    def image_path_list(self) -> list[str]:
        return [p.strip() for p in self.image_paths.split(";") if p.strip()]


@dataclass
class PredictionRow:
    """One output row. Field names mirror OUTPUT_COLUMNS exactly."""

    user_id: str
    image_paths: str
    user_claim: str
    claim_object: str
    evidence_standard_met: bool = False
    evidence_standard_met_reason: str = ""
    risk_flags: list[str] = field(default_factory=list)
    issue_type: str = "unknown"
    object_part: str = "unknown"
    claim_status: str = "not_enough_information"
    claim_status_justification: str = ""
    supporting_image_ids: str = "none"
    valid_image: bool = False
    severity: str = "unknown"

    def to_csv_dict(self) -> dict[str, str]:
        """Coerce every field to a schema-valid string for CSV writing."""
        return {
            "user_id": self.user_id,
            "image_paths": self.image_paths,
            "user_claim": self.user_claim,
            "claim_object": self.claim_object,
            "evidence_standard_met": as_bool_str(self.evidence_standard_met),
            "evidence_standard_met_reason": self.evidence_standard_met_reason.strip(),
            "risk_flags": coerce_risk_flags(self.risk_flags),
            "issue_type": coerce_issue_type(self.issue_type),
            "object_part": coerce_object_part(self.object_part, self.claim_object),
            "claim_status": coerce_claim_status(self.claim_status),
            "claim_status_justification": self.claim_status_justification.strip(),
            "supporting_image_ids": self.supporting_image_ids or "none",
            "valid_image": as_bool_str(self.valid_image),
            "severity": coerce_severity(self.severity),
        }
