"""Read-only comparison of temporary raw aggregates against the concentrado."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .aggregate import get_group_columns
from .concentrado import calculate_period_fingerprint
from .download import calculate_sha256, get_file_size_bytes, now_utc_iso, validate_period


DEFAULT_CONCENTRADO_FILE = Path("data/processed/imss_concentrado.csv")
DEFAULT_COMPARE_OUTPUT_DIR = Path("outputs/processing")
FINGERPRINT_NUMERIC_COLUMNS: tuple[str, ...] = (
    "asegurados",
    "no_trabajadores",
    "ta",
    "ta_sal",
    "masa_sal_ta",
    "tpu",
    "tpc",
    "teu",
    "tec",
)
REQUIRED_COMPARE_COLUMNS: tuple[str, ...] = (
    "periodo_informacion",
    *FINGERPRINT_NUMERIC_COLUMNS,
)


def generate_raw_compare_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def _manifest_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"raw_compare_manifest_{run_id}_{validate_period(period)}.json"


def write_raw_compare_manifest(manifest: dict, output_dir: str | Path = DEFAULT_COMPARE_OUTPUT_DIR) -> Path:
    path = _manifest_path(output_dir, manifest["run_id"], manifest["periodo_informacion"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _base_manifest(
    *,
    run_id: str,
    period: str,
    aggregate_file: str | Path,
    concentrado_file: str | Path,
    started_at: str,
) -> dict:
    concentrado_path = Path(concentrado_file)
    return {
        "run_id": run_id,
        "mode": "compare_imss_raw_aggregate",
        "periodo_informacion": period,
        "aggregate_file_path": str(aggregate_file),
        "aggregate_file_size_bytes": None,
        "aggregate_sha256": None,
        "concentrado_file_path": str(concentrado_path),
        "concentrado_exists": concentrado_path.exists(),
        "aggregate_summary": None,
        "existing_summary": None,
        "comparison_status": None,
        "status": None,
        "error_message": None,
        "writes_concentrado": False,
        "writes_data_processed": False,
        "loads_postgresql": False,
        "touches_staging_table": False,
        "touches_final_table": False,
        "writes_period_control": False,
        "writes_run_manifest": False,
        "started_at": started_at,
        "finished_at": None,
    }


def _finish(
    manifest: dict,
    *,
    comparison_status: str,
    status: str,
    error_message: str | None = None,
) -> dict:
    manifest["comparison_status"] = comparison_status
    manifest["status"] = status
    manifest["error_message"] = error_message
    manifest["finished_at"] = now_utc_iso()
    return manifest


def _summary_with_hash(df: pd.DataFrame, period: str) -> dict:
    summary, fingerprint = calculate_period_fingerprint(df, period)
    return {
        **summary,
        "fingerprint_sha256": fingerprint,
    }


def _validate_aggregate_file(path: Path, period: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Aggregate file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Aggregate path is not a file: {path}")
    if path.stat().st_size == 0:
        raise ValueError("Aggregate file is empty.")

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in REQUIRED_COMPARE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Aggregate file is missing required columns: {', '.join(missing)}")

    periods = sorted(str(value) for value in df["periodo_informacion"].astype("string").dropna().unique())
    if len(periods) > 1:
        raise ValueError("aggregate contains multiple periods")
    if periods != [period]:
        found = ", ".join(periods) if periods else "<empty>"
        raise ValueError(f"aggregate period does not match requested period: {found}")

    missing_key_columns = [column for column in get_group_columns() if column not in df.columns]
    if missing_key_columns:
        raise ValueError(
            "Aggregate file is missing analytic key columns: " + ", ".join(missing_key_columns)
        )
    return df


def _read_existing_period(concentrado_file: Path, period: str) -> pd.DataFrame:
    if not concentrado_file.exists():
        return pd.DataFrame()
    chunks = pd.read_csv(concentrado_file, dtype=str, keep_default_na=False, chunksize=100000)
    matches = []
    for chunk in chunks:
        if "periodo_informacion" not in chunk.columns:
            raise ValueError("Concentrado file is missing periodo_informacion column.")
        period_chunk = chunk[chunk["periodo_informacion"].astype("string") == period].copy()
        if not period_chunk.empty:
            matches.append(period_chunk)
    if not matches:
        return pd.DataFrame()
    return pd.concat(matches, ignore_index=True)


def compare_raw_aggregate_with_concentrado(
    period: str,
    *,
    aggregate_file: str | Path,
    concentrado_file: str | Path = DEFAULT_CONCENTRADO_FILE,
    output_dir: str | Path = DEFAULT_COMPARE_OUTPUT_DIR,
) -> tuple[dict, Path]:
    """Compare one explicit temporary aggregate against the concentrado without writing either."""
    period = validate_period(period)
    aggregate_path = Path(aggregate_file)
    concentrado_path = Path(concentrado_file)
    manifest = _base_manifest(
        run_id=generate_raw_compare_run_id(),
        period=period,
        aggregate_file=aggregate_path,
        concentrado_file=concentrado_path,
        started_at=now_utc_iso(),
    )

    try:
        aggregate_df = _validate_aggregate_file(aggregate_path, period)
        manifest["aggregate_file_size_bytes"] = get_file_size_bytes(aggregate_path)
        manifest["aggregate_sha256"] = calculate_sha256(aggregate_path)
        manifest["aggregate_summary"] = _summary_with_hash(aggregate_df, period)

        if not concentrado_path.exists():
            _finish(
                manifest,
                comparison_status="missing_concentrado",
                status="warning",
                error_message="Concentrado file does not exist.",
            )
            return manifest, write_raw_compare_manifest(manifest, output_dir)

        existing_df = _read_existing_period(concentrado_path, period)
        if existing_df.empty:
            _finish(manifest, comparison_status="new_period", status="success")
            return manifest, write_raw_compare_manifest(manifest, output_dir)

        manifest["existing_summary"] = _summary_with_hash(existing_df, period)
        if manifest["existing_summary"]["row_count"] != manifest["aggregate_summary"]["row_count"]:
            _finish(
                manifest,
                comparison_status="conflict_existing_period_row_count",
                status="conflict",
                error_message="Existing period row count differs from aggregate row count.",
            )
            return manifest, write_raw_compare_manifest(manifest, output_dir)

        if (
            manifest["existing_summary"]["fingerprint_sha256"]
            != manifest["aggregate_summary"]["fingerprint_sha256"]
        ):
            _finish(
                manifest,
                comparison_status="conflict_existing_period_hash",
                status="conflict",
                error_message="Existing period fingerprint differs from aggregate fingerprint.",
            )
            return manifest, write_raw_compare_manifest(manifest, output_dir)

        _finish(manifest, comparison_status="already_exists", status="success")
        return manifest, write_raw_compare_manifest(manifest, output_dir)
    except Exception as error:
        _finish(manifest, comparison_status="failed", status="failed", error_message=str(error))
        return manifest, write_raw_compare_manifest(manifest, output_dir)
