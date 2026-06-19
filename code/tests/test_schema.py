"""Tests for schema.py - coercion + output contract."""
import schema as S


def test_output_columns_exact_order():
    assert S.OUTPUT_COLUMNS == [
        "user_id", "image_paths", "user_claim", "claim_object",
        "evidence_standard_met", "evidence_standard_met_reason", "risk_flags",
        "issue_type", "object_part", "claim_status",
        "claim_status_justification", "supporting_image_ids", "valid_image",
        "severity",
    ]


def test_coerce_issue_type_valid_and_invalid():
    assert S.coerce_issue_type("DENT") == "dent"
    assert S.coerce_issue_type("nonsense") == "unknown"
    assert S.coerce_issue_type(None) == "unknown"


def test_coerce_object_part_respects_object():
    assert S.coerce_object_part("screen", "laptop") == "screen"
    # 'screen' is not a valid car part -> unknown
    assert S.coerce_object_part("screen", "car") == "unknown"
    assert S.coerce_object_part("front_bumper", "car") == "front_bumper"


def test_coerce_claim_status_defaults_to_nei():
    assert S.coerce_claim_status("supported") == "supported"
    assert S.coerce_claim_status("garbage") == "not_enough_information"


def test_coerce_severity():
    assert S.coerce_severity("HIGH") == "high"
    assert S.coerce_severity("") == "unknown"


def test_coerce_risk_flags_dedup_filter_join():
    assert S.coerce_risk_flags([]) == "none"
    assert S.coerce_risk_flags(["none"]) == "none"
    assert S.coerce_risk_flags(["blurry_image", "blurry_image"]) == "blurry_image"
    assert S.coerce_risk_flags(["blurry_image", "bogus", "claim_mismatch"]) == \
        "blurry_image;claim_mismatch"


def test_bool_str():
    assert S.as_bool_str(True) == "true"
    assert S.as_bool_str(False) == "false"


def test_claim_record_image_list():
    rec = S.ClaimRecord("u1", "a/b.jpg;c/d.jpg", "claim", "car")
    assert rec.image_path_list == ["a/b.jpg", "c/d.jpg"]


def test_prediction_row_to_csv_dict_is_schema_valid():
    row = S.PredictionRow(
        user_id="u1", image_paths="x.jpg", user_claim="c", claim_object="laptop",
        evidence_standard_met=True, risk_flags=["blurry_image", "bogus"],
        issue_type="screen_crack", object_part="screen", claim_status="supported",
        valid_image=True, severity="medium",
    )
    d = row.to_csv_dict()
    assert set(d.keys()) == set(S.OUTPUT_COLUMNS)
    assert d["evidence_standard_met"] == "true"
    assert d["issue_type"] == "unknown"          # 'screen_crack' not in vocab
    assert d["object_part"] == "screen"
    assert d["risk_flags"] == "blurry_image"     # 'bogus' filtered out
