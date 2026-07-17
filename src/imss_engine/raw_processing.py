"""Raw-only IMSS processing into temporary aggregate outputs."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .aggregate import aggregate_imss_chunk
from .download import (
    DEFAULT_RAW_ROOT,
    calculate_sha256,
    get_file_size_bytes,
    now_utc_iso,
    validate_period,
)
from .dimension_normalization import (
    BLANK_TO_NA_COLUMNS,
    INTEGER_CODE_COLUMNS,
    RAW_DIMENSION_DTYPES,
    SECTOR_DECIMAL_TO_INTEGER_COLUMNS,
    normalize_imss_dimension_values,
    normalize_raw_integer_codes,
)
from .raw_encoding import DEFAULT_RAW_ENCODING, DEFAULT_RAW_SEPARATOR
from .raw_validation import validate_imss_raw
from .raw_processing_duckdb import (
    DEFAULT_DUCKDB_MEMORY_LIMIT,
    DEFAULT_DUCKDB_THREADS,
    DuckDBAggregateStore,
    publish_utf8_sig_atomically,
)


DEFAULT_PROCESSING_OUTPUT_DIR = Path("outputs/processing")
DEFAULT_CHUNK_SIZE = 100000
PRODUCTIVE_PROCESSING_ENGINE = "duckdb"


def generate_raw_processing_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def _aggregate_output_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"raw_aggregate_{run_id}_{validate_period(period)}.csv"


def _manifest_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"raw_processing_manifest_{run_id}_{validate_period(period)}.json"


def _parquet_output_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"raw_aggregate_{run_id}_{validate_period(period)}.parquet"


def write_raw_processing_manifest(manifest: dict, output_dir: str | Path = DEFAULT_PROCESSING_OUTPUT_DIR) -> Path:
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
        "encoding_requested": None,
        "encoding_detected": None,
        "encoding_candidates_tried": [],
        "chunk_size": chunk_size,
        "processing_engine": None,
        "memory_limit": None,
        "duckdb_threads": None,
        "temporary_directory": None,
        "temporary_files_cleaned": None,
        "failure_stage": None,
        "chunks_processed": 0,
        "rows_read": 0,
        "aggregate_rows": 0,
        "aggregate_output_path": str(aggregate_output_path),
        "aggregate_file_size_bytes": None,
        "aggregate_sha256": None,
        "parquet_output_path": None,
        "parquet_file_size_bytes": None,
        "parquet_sha256": None,
        "parquet_compression": None,
        "columns_output": [],
        "dimension_normalization": {
            "applied": False,
            "blank_to_na_columns": list(BLANK_TO_NA_COLUMNS),
            "sector_decimal_to_integer_columns": list(SECTOR_DECIMAL_TO_INTEGER_COLUMNS),
        },
        "raw_integer_code_normalization": {
            "columns": list(INTEGER_CODE_COLUMNS),
            "normalized_values_by_column": {
                column: 0 for column in INTEGER_CODE_COLUMNS
            },
        },
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


def _remove_empty_temporary_parent(temporary_directory: Path) -> None:
    parent = temporary_directory.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


def process_imss_raw_period(
    period: str,
    *,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    output_dir: str | Path = DEFAULT_PROCESSING_OUTPUT_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    encoding: str = DEFAULT_RAW_ENCODING,
    separator: str = DEFAULT_RAW_SEPARATOR,
    validation_result: dict | None = None,
    validation_manifest_path: str | Path | None = None,
    processing_engine: str | None = None,
    duckdb_memory_limit: str = DEFAULT_DUCKDB_MEMORY_LIMIT,
    duckdb_threads: int = DEFAULT_DUCKDB_THREADS,
    preserve_temporary_on_failure: bool = False,
    write_parquet: bool = False,
    parquet_compression: str = "zstd",
) -> tuple[dict, Path]:
    """Validate and process one explicit raw IMSS period into a temporary aggregate CSV."""
    period = validate_period(period)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if processing_engine not in {None, PRODUCTIVE_PROCESSING_ENGINE}:
        raise ValueError(
            "processing_engine is no longer configurable; the only productive engine is 'duckdb'."
        )

    run_id = generate_raw_processing_run_id()
    if validation_result is None:
        raw_validation, resolved_validation_manifest_path = validate_imss_raw(
            period,
            raw_root=raw_root,
            encoding=encoding,
            separator=separator,
        )
    else:
        raw_validation = validation_result
        resolved_validation_manifest_path = validation_manifest_path
    aggregate_output_path = _aggregate_output_path(output_dir, run_id, period)
    parquet_output_path = _parquet_output_path(output_dir, run_id, period)
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
        "manifest_path": str(resolved_validation_manifest_path) if resolved_validation_manifest_path else None,
    }
    manifest["encoding_requested"] = raw_validation.get("encoding_requested", encoding)
    manifest["encoding_detected"] = raw_validation.get("encoding_detected")
    manifest["encoding_candidates_tried"] = raw_validation.get("encoding_candidates_tried", [])
    manifest["raw_file_size_bytes"] = raw_validation.get("file_size_bytes")
    manifest["raw_sha256"] = raw_validation.get("sha256")
    manifest["processing_engine"] = PRODUCTIVE_PROCESSING_ENGINE
    manifest["memory_limit"] = duckdb_memory_limit
    manifest["duckdb_threads"] = duckdb_threads
    if write_parquet:
        manifest["parquet_output_path"] = str(parquet_output_path)
        manifest["parquet_compression"] = parquet_compression.lower()

    if not raw_validation["valid"]:
        manifest["aggregate_output_path"] = None
        _finish(
            manifest,
            status="failed_raw_validation",
            error_message=raw_validation.get("error_message") or raw_validation["status"],
        )
        return manifest, write_raw_processing_manifest(manifest, output_dir)

    raw_file_path = Path(raw_validation["raw_file_path"])
    encoding_detected = raw_validation.get("encoding_detected")
    if not encoding_detected:
        manifest["aggregate_output_path"] = None
        _finish(
            manifest,
            status="failed_raw_validation",
            error_message="Validated raw input does not include encoding_detected.",
        )
        return manifest, write_raw_processing_manifest(manifest, output_dir)
    duckdb_store: DuckDBAggregateStore | None = None
    temporary_directory = Path(output_dir) / ".tmp" / run_id
    plain_csv_path = temporary_directory / "aggregate_plain.csv"
    staged_output_path = Path(str(aggregate_output_path) + ".tmp")
    try:
        manifest["failure_stage"] = "initialize_duckdb"
        duckdb_store = DuckDBAggregateStore(
            temporary_directory=temporary_directory,
            memory_limit=duckdb_memory_limit,
            threads=duckdb_threads,
        )
        manifest["temporary_directory"] = str(Path(".tmp") / run_id)
        chunks = pd.read_csv(
            raw_file_path,
            sep=separator,
            encoding=encoding_detected,
            chunksize=chunk_size,
            low_memory=False,
            dtype=RAW_DIMENSION_DTYPES,
        )
        for chunk in chunks:
            manifest["failure_stage"] = "transform_chunk"
            manifest["chunks_processed"] += 1
            manifest["rows_read"] += len(chunk)
            chunk["periodo_informacion"] = period
            chunk, normalization_counts = normalize_raw_integer_codes(chunk)
            for column, count in normalization_counts.items():
                manifest["raw_integer_code_normalization"][
                    "normalized_values_by_column"
                ][column] += count
            partial = aggregate_imss_chunk(chunk)
            partial = normalize_imss_dimension_values(partial)
            manifest["failure_stage"] = "persist_partial"
            duckdb_store.persist_partial(partial)

        if manifest["chunks_processed"] == 0:
            raise ValueError("Raw file did not produce any chunks to process.")

        output_timestamp = now_utc_iso()
        manifest["failure_stage"] = "consolidate_duckdb"
        summary = duckdb_store.consolidate_to_csv(
            plain_csv_path=plain_csv_path,
            timestamp=output_timestamp,
            parquet_output_path=parquet_output_path if write_parquet else None,
            parquet_compression=parquet_compression,
        )
        manifest["failure_stage"] = "publish_output"
        publish_utf8_sig_atomically(
            plain_csv_path,
            staged_output_path,
            aggregate_output_path,
        )
        manifest["aggregate_rows"] = summary["aggregate_rows"]
        manifest["columns_output"] = summary["columns_output"]
        manifest["dimension_normalization"]["applied"] = True

        manifest["aggregate_file_size_bytes"] = get_file_size_bytes(aggregate_output_path)
        manifest["aggregate_sha256"] = calculate_sha256(aggregate_output_path)
        if write_parquet:
            manifest["parquet_file_size_bytes"] = get_file_size_bytes(parquet_output_path)
            manifest["parquet_sha256"] = calculate_sha256(parquet_output_path)
        manifest["failure_stage"] = None
        if duckdb_store is not None:
            duckdb_store.close()
            duckdb_store.cleanup()
            _remove_empty_temporary_parent(temporary_directory)
            duckdb_store = None
            manifest["temporary_files_cleaned"] = True
        _finish(manifest, status="success")
        return manifest, write_raw_processing_manifest(manifest, output_dir)
    except Exception as error:
        if duckdb_store is not None:
            duckdb_store.close()
            if preserve_temporary_on_failure:
                manifest["temporary_files_cleaned"] = False
            else:
                duckdb_store.cleanup()
                _remove_empty_temporary_parent(temporary_directory)
                manifest["temporary_files_cleaned"] = True
            duckdb_store = None
        elif temporary_directory.exists() and not preserve_temporary_on_failure:
            shutil.rmtree(temporary_directory)
            _remove_empty_temporary_parent(temporary_directory)
            manifest["temporary_files_cleaned"] = True
        elif temporary_directory.exists():
            manifest["temporary_files_cleaned"] = False
        if staged_output_path.exists():
            staged_output_path.unlink()
        if aggregate_output_path.exists():
            aggregate_output_path.unlink()
        if parquet_output_path.exists():
            parquet_output_path.unlink()
        manifest["aggregate_output_path"] = None
        _finish(manifest, status="failed", error_message=str(error))
        return manifest, write_raw_processing_manifest(manifest, output_dir)
