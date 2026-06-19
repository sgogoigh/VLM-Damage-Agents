"""Tests for data_io.py - CSV I/O + image path resolution."""
import csv

import config
import data_io as IO
from schema import OUTPUT_COLUMNS, PredictionRow


def test_read_claims_count_and_fields():
    claims = IO.read_claims(config.CLAIMS_CSV)
    assert len(claims) == 44
    first = claims[0]
    assert first.claim_object in {"car", "laptop", "package"}
    assert first.image_path_list  # non-empty


def test_read_sample_has_labels():
    rows = IO.read_sample_with_labels(config.SAMPLE_CLAIMS_CSV)
    assert len(rows) == 20
    assert "claim_status" in rows[0]


def test_read_user_history_keyed():
    hist = IO.read_user_history()
    assert len(hist) == 47
    assert "user_001" in hist
    assert hist["user_001"]["history_flags"] == "none"


def test_read_evidence_requirements():
    reqs = IO.read_evidence_requirements()
    assert len(reqs) == 11
    assert any(r["claim_object"] == "car" for r in reqs)


def test_image_id_from_path():
    assert IO.image_id_from_path("images/test/case_001/img_2.jpg") == "img_2"


def test_resolve_image_path_exists():
    p = IO.resolve_image_path("images/test/case_001/img_1.jpg")
    assert p.exists()


def test_write_output_roundtrip(tmp_path):
    rows = [PredictionRow(user_id="u1", image_paths="x.jpg", user_claim="c",
                          claim_object="car", claim_status="supported")]
    out = tmp_path / "out.csv"
    IO.write_output(rows, out)
    with open(out, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        data = next(reader)
    assert header == OUTPUT_COLUMNS              # exact order preserved
    assert data[0] == "u1"
    # QUOTE_ALL: raw text contains quotes around fields
    assert out.read_text(encoding="utf-8").startswith('"user_id"')
