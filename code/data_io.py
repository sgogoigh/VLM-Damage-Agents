"""
CSV reading / writing and image path resolution.

- Reads claims, sample claims, user history, and evidence requirements.
- Resolves semicolon-separated image paths against the dataset root.
- Writes output.csv with the exact column order from schema.OUTPUT_COLUMNS.
"""
from __future__ import annotations

import csv
from pathlib import Path

from code import config
from code.schema import OUTPUT_COLUMNS, ClaimRecord, PredictionRow


def read_claims(csv_path: Path) -> list[ClaimRecord]:
    """Read an input claims CSV (claims.csv or sample_claims.csv)."""
    rows: list[ClaimRecord] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                ClaimRecord(
                    user_id=r.get("user_id", "").strip(),
                    image_paths=r.get("image_paths", "").strip(),
                    user_claim=r.get("user_claim", "").strip(),
                    claim_object=r.get("claim_object", "").strip().lower(),
                )
            )
    return rows


def read_sample_with_labels(csv_path: Path) -> list[dict[str, str]]:
    """Read sample_claims.csv keeping the expected-output columns for eval."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_user_history(csv_path: Path = config.USER_HISTORY_CSV) -> dict[str, dict[str, str]]:
    """user_id -> history row."""
    history: dict[str, dict[str, str]] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            uid = r.get("user_id", "").strip()
            if uid:
                history[uid] = r
    return history


def read_evidence_requirements(
    csv_path: Path = config.EVIDENCE_REQUIREMENTS_CSV,
) -> list[dict[str, str]]:
    """List of requirement rules (requirement_id, claim_object, applies_to, ...)."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resolve_image_path(rel_path: str) -> Path:
    """Resolve a CSV image path (e.g. 'images/test/case_001/img_1.jpg')."""
    return (config.IMAGES_ROOT / rel_path).resolve()


def image_id_from_path(rel_path: str) -> str:
    """Image ID is the filename without extension, e.g. 'img_1'."""
    return Path(rel_path).stem


def write_output(rows: list[PredictionRow], out_path: Path) -> None:
    """Write predictions with the exact required header/order (full rewrite)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_dict())


def count_output_rows(out_path: Path) -> int:
    """Number of DATA rows already written (0 if file missing/empty)."""
    if not out_path.exists():
        return 0
    with open(out_path, newline="", encoding="utf-8") as f:
        n = sum(1 for _ in csv.reader(f))
    return max(0, n - 1)  # minus header


def append_output_row(row: PredictionRow, out_path: Path) -> None:
    """Append one prediction, writing the header first if the file is new.

    Enables incremental + resumable runs: a long throttled run can be stopped
    and resumed without losing completed rows.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists() or out_path.stat().st_size == 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        if new_file:
            writer.writeheader()
        writer.writerow(row.to_csv_dict())
