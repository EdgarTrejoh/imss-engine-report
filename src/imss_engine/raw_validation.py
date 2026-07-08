"""Initial validation for downloaded IMSS raw CSV files."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .download import (
    DEFAULT_RAW_ROOT,
    build_raw_file_path,
    calculate_sha256,
    get_file_size_bytes,
    now_utc_iso,
    validate_period,
)
from .schema import CRITICAL_METRIC_COLUMNS


DEFAULT_RAW_VALIDATION_MANIFEST_DIR = Path("outputs/audit/raw_validation")
DEFAULT_RAW_ENCODING = "latin-1"
DEFAULT_RAW_SEPARATOR = "|"
REQUIRED_RAW_DIMENSION_COLUMNS: tuple[str, ...] = (
    "cve_delegacion",
    "cve_subdelegacion",
    "cve_entidad",
    "cve_municipio",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "tamaño_patron",
    "sexo",
    "rango_edad",
    "rango_salarial",
)
REQUIRED_RAW_COLUMNS: tuple[str, ...] = REQUIRED_RAW_DIMENSION_COLUMNS + CRITICAL_METRIC_COLUMNS


def generate_raw_validation_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def _manifest_path(manifest_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(manifest_dir) / f"raw_validation_{run_id}_{validate_period(period)}.json"


def write_raw_validation_manifest(
    manifest: dict,
    manifest_dir: str | Path = DEFAULT_RAW_VALIDATION_MANIFEST_DIR,
) -> Path:
    output_dir = Path(manifest_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(output_dir, manifest["run_id"], manifest["periodo_informacion"])
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _base_manifest(
    *,
    run_id: str,
    period: str,
    raw_file_path: Path,
    encoding: str,
    separator: str,
    started_at: str,
) -> dict:
    return {
        "run_id": run_id,
        "mode": "validate_imss_raw",
        "periodo_informacion": period,
        "raw_file_path": str(raw_file_path),
        "raw_exists": raw_file_path.exists(),
        "file_size_bytes": None,
        "sha256": None,
        "encoding": encoding,
        "separator": separator,
        "columns_detected": [],
        "missing_required_columns": [],
        "valid": False,
        "status": None,
        "error_message": None,
        "started_at": started_at,
        "finished_at": None,
    }


def _finish(manifest: dict, *, status: str, valid: bool, error_message: str | None = None) -> dict:
    manifest["status"] = status
    manifest["valid"] = valid
    manifest["error_message"] = error_message
    manifest["finished_at"] = now_utc_iso()
    return manifest


def _read_header(path: Path, encoding: str) -> str:
    with path.open("r", encoding=encoding, newline="") as file:
        return file.readline()


def validate_imss_raw(
    period: str,
    *,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    manifest_dir: str | Path = DEFAULT_RAW_VALIDATION_MANIFEST_DIR,
    encoding: str = DEFAULT_RAW_ENCODING,
    separator: str = DEFAULT_RAW_SEPARATOR,
) -> tuple[dict, Path]:
    """Validate one downloaded raw IMSS CSV using only file metadata and header."""
    period = validate_period(period)
    raw_file_path = build_raw_file_path(period, raw_root)
    manifest = _base_manifest(
        run_id=generate_raw_validation_run_id(),
        period=period,
        raw_file_path=raw_file_path,
        encoding=encoding,
        separator=separator,
        started_at=now_utc_iso(),
    )

    if not raw_file_path.exists():
        _finish(manifest, status="failed_missing_raw", valid=False, error_message="Raw file does not exist.")
        return manifest, write_raw_validation_manifest(manifest, manifest_dir)

    manifest["file_size_bytes"] = get_file_size_bytes(raw_file_path)
    if manifest["file_size_bytes"] == 0:
        _finish(manifest, status="failed_empty_raw", valid=False, error_message="Raw file is empty.")
        return manifest, write_raw_validation_manifest(manifest, manifest_dir)

    try:
        manifest["sha256"] = calculate_sha256(raw_file_path)
        header_line = _read_header(raw_file_path, encoding)
    except UnicodeError as error:
        _finish(
            manifest,
            status="failed_unreadable_raw",
            valid=False,
            error_message=f"Raw file is not readable with encoding {encoding}: {error}",
        )
        return manifest, write_raw_validation_manifest(manifest, manifest_dir)
    except OSError as error:
        _finish(
            manifest,
            status="failed_unreadable_raw",
            valid=False,
            error_message=f"Raw file could not be read: {error}",
        )
        return manifest, write_raw_validation_manifest(manifest, manifest_dir)

    if separator not in header_line:
        _finish(
            manifest,
            status="failed_invalid_separator",
            valid=False,
            error_message=f"Raw header does not contain expected separator {separator!r}.",
        )
        return manifest, write_raw_validation_manifest(manifest, manifest_dir)

    columns = [column.strip().lstrip("\ufeff") for column in header_line.rstrip("\r\n").split(separator)]
    manifest["columns_detected"] = columns
    missing_required_columns = [column for column in REQUIRED_RAW_COLUMNS if column not in columns]
    manifest["missing_required_columns"] = missing_required_columns
    if missing_required_columns:
        _finish(
            manifest,
            status="failed_missing_required_columns",
            valid=False,
            error_message="Raw header is missing required IMSS metric columns.",
        )
        return manifest, write_raw_validation_manifest(manifest, manifest_dir)

    _finish(manifest, status="success", valid=True)
    return manifest, write_raw_validation_manifest(manifest, manifest_dir)
