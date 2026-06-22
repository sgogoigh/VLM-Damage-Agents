"""
CSV reading / writing and image-path resolution for the standalone backend.

- Reads reference data (user history, evidence requirements) and input claims.
- Resolves semicolon-separated image paths against the configured dataset root.
- Writes output.csv with the exact column order from ``contract.OUTPUT_COLUMNS``.

All filesystem locations come from ``Settings`` (env-configurable), so nothing
here is hardcoded to a particular checkout layout.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.config import Settings, get_settings
from app.core.contract import OUTPUT_COLUMNS, ClaimRecord, PredictionRow


def read_claims(csv_path: Path) -> list[ClaimRecord]:
    """Read an input claims CSV (claims.csv or sample_claims.csv)."""
    rows: list[ClaimRecord] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                ClaimRecord(
                    user_id=(r.get("user_id") or "").strip(),
                    image_paths=(r.get("image_paths") or "").strip(),
                    user_claim=(r.get("user_claim") or "").strip(),
                    claim_object=(r.get("claim_object") or "").strip().lower(),
                )
            )
    return rows


def read_sample_with_labels(csv_path: Path) -> list[dict[str, str]]:
    """Read sample_claims.csv keeping the expected-output columns (for eval)."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_user_history(csv_path: Path | None = None) -> dict[str, dict[str, str]]:
    """Return {user_id: history_row}. Missing file -> empty mapping."""
    path = csv_path or get_settings().user_history_csv
    if not Path(path).exists():
        return {}
    history: dict[str, dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            uid = (r.get("user_id") or "").strip()
            if uid:
                history[uid] = r
    return history


def read_evidence_requirements(csv_path: Path | None = None) -> list[dict[str, str]]:
    """Return the list of requirement rules. Missing file -> empty list."""
    path = csv_path or get_settings().evidence_requirements_csv
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resolve_image_path(rel_path: str, settings: Settings | None = None) -> Path:
    """Resolve a CSV image path (e.g. 'images/test/case_001/img_1.jpg')."""
    s = settings or get_settings()
    return (s.images_root / rel_path).resolve()


def image_exists(rel_path: str, settings: Settings | None = None) -> bool:
    return resolve_image_path(rel_path, settings).exists()


def image_id_from_path(rel_path: str) -> str:
    """Image ID is the filename without extension, e.g. 'img_1'."""
    return Path(rel_path).stem


def write_output(rows: list[PredictionRow], out_path: Path) -> None:
    """Write predictions with the exact required header/order (full rewrite)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_dict())


def count_output_rows(out_path: Path) -> int:
    """Number of DATA rows already written (0 if file missing/empty)."""
    out_path = Path(out_path)
    if not out_path.exists():
        return 0
    with open(out_path, newline="", encoding="utf-8") as f:
        n = sum(1 for _ in csv.reader(f))
    return max(0, n - 1)  # minus header


def append_output_row(row: PredictionRow, out_path: Path) -> None:
    """Append one prediction, writing the header first if the file is new.

    Enables incremental + resumable batch runs: a long throttled run can be
    stopped and resumed without losing completed rows.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_path.exists() or out_path.stat().st_size == 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        if new_file:
            writer.writeheader()
        writer.writerow(row.to_csv_dict())
