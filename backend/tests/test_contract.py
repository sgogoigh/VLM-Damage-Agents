"""Output-contract coercion + vocabulary guarantees."""
from __future__ import annotations

from app.core.contract import (
    CLAIM_STATUS,
    ISSUE_TYPES,
    OBJECT_PARTS,
    OUTPUT_COLUMNS,
    RISK_FLAGS,
    SEVERITY,
    ClaimRecord,
    PredictionRow,
    as_bool_str,
    coerce_claim_object,
    coerce_claim_status,
    coerce_issue_type,
    coerce_object_part,
    coerce_risk_flags,
    coerce_severity,
    risk_flags_to_str,
)


def test_output_columns_exact_order():
    assert OUTPUT_COLUMNS == [
        "user_id", "image_paths", "user_claim", "claim_object",
        "evidence_standard_met", "evidence_standard_met_reason", "risk_flags",
        "issue_type", "object_part", "claim_status",
        "claim_status_justification", "supporting_image_ids", "valid_image",
        "severity",
    ]


def test_coerce_out_of_vocab_falls_back():
    assert coerce_claim_status("banana") == "not_enough_information"
    assert coerce_issue_type("explosion") == "unknown"
    assert coerce_severity("catastrophic") == "unknown"
    assert coerce_claim_object("boat") == "unknown"


def test_coerce_valid_values_pass_through():
    assert coerce_claim_status("SUPPORTED") == "supported"
    assert coerce_issue_type(" Dent ") == "dent"
    assert coerce_severity("High") == "high"
    assert coerce_claim_object("Car") == "car"


def test_object_part_is_object_scoped():
    assert coerce_object_part("screen", "laptop") == "screen"
    assert coerce_object_part("screen", "car") == "unknown"   # wrong object
    assert coerce_object_part("front_bumper", "car") == "front_bumper"


def test_coerce_risk_flags_dedupes_and_filters():
    flags = coerce_risk_flags(["blurry_image", "blurry_image", "none", "bogus", "claim_mismatch"])
    assert flags == ["blurry_image", "claim_mismatch"]
    assert risk_flags_to_str([]) == "none"
    assert risk_flags_to_str(["none"]) == "none"


def test_as_bool_str():
    assert as_bool_str(True) == "true"
    assert as_bool_str(False) == "false"


def test_prediction_row_to_csv_dict_is_schema_valid():
    row = PredictionRow(
        user_id="u1", image_paths="images/x/img_1.jpg", user_claim="c",
        claim_object="car", evidence_standard_met=True,
        risk_flags=["blurry_image", "bogus"], issue_type="dent",
        object_part="screen",  # invalid for car -> unknown
        claim_status="supported", severity="high", valid_image=True,
        supporting_image_ids="img_1",
    )
    d = row.to_csv_dict()
    assert set(d.keys()) == set(OUTPUT_COLUMNS)
    assert d["evidence_standard_met"] == "true"
    assert d["risk_flags"] == "blurry_image"          # bogus filtered out
    assert d["object_part"] == "unknown"              # screen invalid for car
    assert d["claim_status"] in CLAIM_STATUS
    assert d["severity"] in SEVERITY


def test_prediction_row_to_api_dict_native_types():
    row = PredictionRow(
        user_id="u1", image_paths="a.jpg;b.jpg", user_claim="c", claim_object="car",
        evidence_standard_met=True, risk_flags=["claim_mismatch"],
        supporting_image_ids="img_1;img_2", valid_image=False,
    )
    d = row.to_api_dict()
    assert d["image_paths"] == ["a.jpg", "b.jpg"]
    assert d["supporting_image_ids"] == ["img_1", "img_2"]
    assert d["risk_flags"] == ["claim_mismatch"]
    assert d["evidence_standard_met"] is True
    assert d["valid_image"] is False


def test_api_dict_supporting_none_becomes_empty_list():
    row = PredictionRow(user_id="u", image_paths="a.jpg", user_claim="c",
                        claim_object="car", supporting_image_ids="none")
    assert row.to_api_dict()["supporting_image_ids"] == []


def test_claim_record_image_path_list():
    rec = ClaimRecord(user_id="u", image_paths=" a.jpg ; b.jpg ;", user_claim="c", claim_object="car")
    assert rec.image_path_list == ["a.jpg", "b.jpg"]


def test_vocab_sets_nonempty():
    assert "supported" in CLAIM_STATUS
    assert "manual_review_required" in RISK_FLAGS
    assert "windshield" in OBJECT_PARTS["car"]
    assert "none" in ISSUE_TYPES
