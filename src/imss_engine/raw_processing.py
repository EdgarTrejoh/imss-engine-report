"""Raw-only IMSS processing into temporary aggregate outputs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .aggregate import DERIVED_SUM_COLUMNS, aggregate_imss_chunk, get_group_columns
from .download import (
    DEFAULT_RAW_ROOT,
    calculate_sha256,
    get_file_size_bytes,
    now_utc_iso,
    validate_period,
)
from .metrics import add_validation_differences, calculate_sbc_metrics
from .raw_validation import DEFAULT_RAW_ENCODING, DEFAULT_RAW_SEPARATOR, validate_imss_raw
from .schema import CRITICAL_METRIC_COLUMNS


DEFAULT_PROCESSING_OUTPUT_DIR = Path("outputs/processing")
DEFAULT_CHUNK_SIZE = 400000


def generate_raw_processing_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def _aggregate_output_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"raw_aggregate_{run_id}_{validate_period(period)}.csv"


def _manifest_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"raw_processing_manifest_{run_id}_{validate_period(period)}.json"


def write_raw_processing_manifest(manifest: dict, output_dir: str | Path = DEFAULT_PROCESSING_OUTPUT_DIR) -> Path:
    path = _manifest_path(output_dir, manifest["run_id"], manifest["periodo_informacion"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _combine_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    sum_columns = list(CRITICAL_METRIC_COLUMNS) + list(DERIVED_SUM_COLUMNS)
    combined = df.groupby(get_group_columns(), as_index=False, dropna=False)[sum_columns].sum(min_count=1)
    combined = calculate_sbc_metrics(combined)
    combined = add_validation_differences(combined)
    return combined


def _base_manifest(
    *,
    run_id: str,
    period: str,
    raw_file_path: str | Path,
    chunk_size: int,
    aggregate_output_path: str | Path,
    started_at: str,
) -> dict:
    return {
        "run_id": run_id,
        "mode": "process_imss_raw",
        "periodo_informacion": period,
        "raw_file_path": str(raw_file_path),
        "raw_file_size_bytes": None,
        "raw_sha256": None,
        "raw_validation": None,
        "chunk_size": chunk_size,
        "chunks_processed": 0,
        "rows_read": 0,
        "aggregate_rows": 0,
        "aggregate_output_path": str(aggregate_output_path),
        "aggregate_file_size_bytes": None,
        "aggregate_sha256": None,
        "columns_output": [],
        "status": None,
        "error_message": None,
        "started_at": started_at,
        "finished_at": None,
        "reads_source_csv": True,
        "writes_data_processed": False,
        "loads_postgresql": False,
        "touches_staging_table": False,
        "touches_final_table": False,
        "writes_period_control": False,
        "writes_run_manifest": False,
    }


def _finish(manifest: dict, *, status: str, error_message: str | None = None) -> dict:
    manifest["status"] = status
    manifest["error_message"] = error_message
    manifest["finished_at"] = now_utc_iso()
    return manifest


def process_imss_raw_period(
    period: str,
    *,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    output_dir: str | Path = DEFAULT_PROCESSING_OUTPUT_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    encoding: str = DEFAULT_RAW_ENCODING,
    separator: str = DEFAULT_RAW_SEPARATOR,
) -> tuple[dict, Path]:
    """Validate and process one explicit raw IMSS period into a temporary aggregate CSV."""
    period = validate_period(period)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    run_id = generate_raw_processing_run_id()
    raw_validation, raw_validation_manifest_path = validate_imss_raw(
        period,
        raw_root=raw_root,
        encoding=encoding,
        separator=separator,
    )
    aggregate_output_path = _aggregate_output_path(output_dir, run_id, period)
    manifest = _base_manifest(
        run_id=run_id,
        period=period,
        raw_file_path=raw_validation["raw_file_path"],
        chunk_size=chunk_size,
        aggregate_output_path=aggregate_output_path,
        started_at=now_utc_iso(),
    )
    manifest["raw_validation"] = {
        "valid": raw_validation["valid"],
        "status": raw_validation["status"],
        "manifest_path": str(raw_validation_manifest_path),
    }
    manifest["raw_file_size_bytes"] = raw_validation.get("file_size_bytes")
    manifest["raw_sha256"] = raw_validation.get("sha256")

    if not raw_validation["valid"]:
        manifest["aggregate_output_path"] = None
        _finish(
            manifest,
            status="failed_raw_validation",
            error_message=raw_validation.get("error_message") or raw_validation["status"],
        )
        return manifest, write_raw_processing_manifest(manifest, output_dir)

    raw_file_path = Path(raw_validation["raw_file_path"])
    aggregated_chunks: list[pd.DataFrame] = []
    try:
        chunks = pd.read_csv(
            raw_file_path,
            sep=separator,
            encoding=encoding,
            chunksize=chunk_size,
            low_memory=False,
        )
        for chunk in chunks:
            manifest["chunks_processed"] += 1
            manifest["rows_read"] += len(chunk)
            chunk["periodo_informacion"] = period
            aggregated_chunks.append(aggregate_imss_chunk(chunk))

        if not aggregated_chunks:
            raise ValueError("Raw file did not produce any chunks to process.")

        aggregate_df = _combine_aggregates(pd.concat(aggregated_chunks, ignore_index=True))
        aggregate_df["fuente"] = "IMSS"
        aggregate_df["timestamp"] = now_utc_iso()

        aggregate_output_path.parent.mkdir(parents=True, exist_ok=True)
        aggregate_df.to_csv(aggregate_output_path, index=False, encoding="utf-8-sig")
        manifest["aggregate_rows"] = len(aggregate_df)
        manifest["aggregate_file_size_bytes"] = get_file_size_bytes(aggregate_output_path)
        manifest["aggregate_sha256"] = calculate_sha256(aggregate_output_path)
        manifest["columns_output"] = list(aggregate_df.columns)
        _finish(manifest, status="success")
        return manifest, write_raw_processing_manifest(manifest, output_dir)
    except Exception as error:
        if aggregate_output_path.exists():
            aggregate_output_path.unlink()
        manifest["aggregate_output_path"] = None
        _finish(manifest, status="failed", error_message=str(error))
        return manifest, write_raw_processing_manifest(manifest, output_dir)
