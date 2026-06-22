"""CSV I/O + image path resolution."""
from __future__ import annotations

from app.core.contract import OUTPUT_COLUMNS, PredictionRow
from app.core.data_io import (
    append_output_row,
    count_output_rows,
    image_id_from_path,
    read_claims,
    read_evidence_requirements,
    read_user_history,
    resolve_image_path,
    write_output,
)


def test_image_id_from_path():
    assert image_id_from_path("images/test/case_001/img_1.jpg") == "img_1"
    assert image_id_from_path("foo/bar/photo.PNG") == "photo"


def test_resolve_image_path_under_dataset(settings):
    p = resolve_image_path("images/sample/case_001/img_1.jpg", settings)
    assert str(p).endswith("img_1.jpg")
    assert "dataset" in str(p).replace("\\", "/")


def test_read_user_history_and_requirements(settings, dataset_available):
    if not dataset_available:
        return
    hist = read_user_history(settings.user_history_csv)
    assert isinstance(hist, dict) and len(hist) > 0
    reqs = read_evidence_requirements(settings.evidence_requirements_csv)
    assert isinstance(reqs, list) and len(reqs) > 0
    assert "claim_object" in reqs[0]


def test_missing_reference_files_return_empty(tmp_path):
    assert read_user_history(tmp_path / "nope.csv") == {}
    assert read_evidence_requirements(tmp_path / "nope.csv") == []


def test_read_claims_parses_rows(settings, dataset_available):
    if not dataset_available:
        return
    claims = read_claims(settings.sample_claims_csv)
    assert len(claims) > 0
    assert claims[0].user_id
    assert claims[0].claim_object in {"car", "laptop", "package"}


def test_write_count_append_roundtrip(tmp_path):
    out = tmp_path / "output.csv"
    row = PredictionRow(user_id="u1", image_paths="a.jpg", user_claim="c", claim_object="car")

    write_output([], out)                 # header only
    assert count_output_rows(out) == 0

    append_output_row(row, out)
    append_output_row(row, out)
    assert count_output_rows(out) == 2

    # Header present and exactly the contract columns, quoted.
    header = out.read_text(encoding="utf-8").splitlines()[0]
    for col in OUTPUT_COLUMNS:
        assert col in header


def test_count_rows_missing_file(tmp_path):
    assert count_output_rows(tmp_path / "absent.csv") == 0
