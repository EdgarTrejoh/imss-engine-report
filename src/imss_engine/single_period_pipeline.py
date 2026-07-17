"""Single-period IMSS raw-to-PostgreSQL pipeline orchestration."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import load_config
from .download import (
    DEFAULT_RAW_ROOT,
    build_raw_file_path,
    build_source_url,
    download_imss_period,
    now_utc_iso,
    read_etl_config,
    validate_period,
)
from .postgres.config import PostgresConfig
from .postgres.connection import connect
from .postgres.loader import (
    check_existing_period,
    finalize_period_control_loaded,
    finalize_run_manifest,
    load_staging_insert_only,
    promote_staging_to_final_insert_only,
    register_period_control_pending,
    register_run_manifest,
    validate_post_promotion_period,
)
from .raw_processing import DEFAULT_CHUNK_SIZE, process_imss_raw_period
from .raw_validation import validate_imss_raw


DEFAULT_PIPELINE_OUTPUT_DIR = Path("outputs/pipeline")


class SinglePeriodPipelineError(RuntimeError):
    """Raised when a critical pipeline step fails."""


def generate_pipeline_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"single_period_{timestamp}_{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class PipelineDependencies:
    download_period: Callable = download_imss_period
    validate_raw: Callable = validate_imss_raw
    process_raw: Callable = process_imss_raw_period
    postgres_config_from_env: Callable = PostgresConfig.from_env
    connect_postgres: Callable = connect
    check_existing: Callable = check_existing_period
    register_period_control: Callable = register_period_control_pending
    register_run_manifest: Callable = register_run_manifest
    load_staging: Callable = load_staging_insert_only
    promote_staging_final: Callable = promote_staging_to_final_insert_only
    validate_post_promotion: Callable = validate_post_promotion_period
    finalize_period_control: Callable = finalize_period_control_loaded
    finalize_run_manifest: Callable = finalize_run_manifest


def _manifest_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"single_period_pipeline_{run_id}_{validate_period(period)}.json"


def write_pipeline_manifest(manifest: dict, output_dir: str | Path = DEFAULT_PIPELINE_OUTPUT_DIR) -> Path:
    path = _manifest_path(output_dir, manifest["run_id"], manifest["periodo_informacion"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _resolve_period(config_path: str | Path, period_override: str | None) -> str:
    if period_override:
        return validate_period(period_override)

    config = load_config(config_path)
    etl_config = config.get("etl", {})
    mode = etl_config.get("mode")
    if mode == "mes_consulta":
        return validate_period(str(etl_config.get("mes_consulta", "")))
    if mode == "periodo_consulta":
        raise ValueError(
            "config mode periodo_consulta is multi-period capable; pass --period for this single-period pipeline"
        )
    raise ValueError("Unable to resolve a single period. Use --period or etl.mode=mes_consulta.")


def _source_url(config_path: str | Path, period: str) -> str:
    etl_config, _ = read_etl_config(config_path)
    return build_source_url(etl_config["base_url"], period)


def _base_manifest(
    *,
    run_id: str,
    period: str,
    dry_run: bool,
    config_path: str | Path,
    raw_file_path: str | Path,
    raw_exists_before: bool,
    source_url: str | None,
    started_at: str,
) -> dict:
    return {
        "run_id": run_id,
        "mode": "single_period_pipeline",
        "periodo_informacion": period,
        "dry_run": dry_run,
        "status": None,
        "action": None,
        "config_path": str(config_path),
        "source_url": source_url,
        "raw_file_path": str(raw_file_path),
        "raw_exists_before": raw_exists_before,
        "aggregate_output_path": None,
        "steps": [],
        "download": None,
        "raw_validation": None,
        "raw_processing": None,
        "encoding_requested": None,
        "encoding_detected": None,
        "encoding_candidates_tried": [],
        "postgres": {
            "check_existing": None,
            "register_period_control": None,
            "register_run_manifest": None,
            "load_staging": None,
            "promote_staging_final": None,
            "validate_post_promotion": None,
            "finalize_period_control": None,
            "finalize_run_manifest": None,
        },
        "writes_postgresql": False,
        "writes_concentrado": False,
        "writes_data_processed": False,
        "raw_processing_uses_dataframe": True,
        "postgres_loader_uses_dataframe": False,
        "started_at": started_at,
        "finished_at": None,
        "error_message": None,
    }


def _record_step(manifest: dict, name: str, status: str, result: Any = None) -> None:
    manifest["steps"].append({"step": name, "status": status, "result": result})


def _finish(manifest: dict, *, status: str, action: str, error_message: str | None = None) -> dict:
    manifest["status"] = status
    manifest["action"] = action
    manifest["error_message"] = error_message
    manifest["finished_at"] = now_utc_iso()
    return manifest


def plan_single_period_pipeline(
    *,
    config_path: str | Path = "config/config.yaml",
    period: str | None = None,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    output_dir: str | Path = DEFAULT_PIPELINE_OUTPUT_DIR,
    run_id: str | None = None,
) -> tuple[dict, Path]:
    """Build a dry-run manifest without downloading, processing or opening PostgreSQL."""
    resolved_period = _resolve_period(config_path, period)
    effective_run_id = run_id or generate_pipeline_run_id()
    raw_file_path = build_raw_file_path(resolved_period, raw_root)
    source_url = _source_url(config_path, resolved_period)
    manifest = _base_manifest(
        run_id=effective_run_id,
        period=resolved_period,
        dry_run=True,
        config_path=config_path,
        raw_file_path=raw_file_path,
        raw_exists_before=raw_file_path.exists(),
        source_url=source_url,
        started_at=now_utc_iso(),
    )
    _record_step(
        manifest,
        "dry_run_plan",
        "planned",
        {
            "would_download_if_raw_missing": not raw_file_path.exists(),
            "would_validate_raw": True,
            "would_process_raw": True,
            "would_open_postgresql": True,
            "would_write_postgresql": True,
            "would_write_concentrado": False,
            "would_write_data_processed": False,
        },
    )
    _finish(manifest, status="planned", action="dry_run")
    manifest_path = write_pipeline_manifest(manifest, output_dir)
    return manifest, manifest_path


def execute_single_period_pipeline(
    *,
    config_path: str | Path = "config/config.yaml",
    period: str | None = None,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    output_dir: str | Path = DEFAULT_PIPELINE_OUTPUT_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    batch_size: int = 5000,
    promotion_batch_size: int = 50000,
    duckdb_memory_limit: str = "1GB",
    duckdb_threads: int = 2,
    preserve_temporary_on_failure: bool = False,
    run_id: str | None = None,
    dependencies: PipelineDependencies = PipelineDependencies(),
) -> tuple[dict, Path]:
    """Execute one explicit IMSS raw-to-PostgreSQL period pipeline."""
    resolved_period = _resolve_period(config_path, period)
    effective_run_id = run_id or generate_pipeline_run_id()
    raw_file_path = build_raw_file_path(resolved_period, raw_root)
    source_url = _source_url(config_path, resolved_period)
    manifest = _base_manifest(
        run_id=effective_run_id,
        period=resolved_period,
        dry_run=False,
        config_path=config_path,
        raw_file_path=raw_file_path,
        raw_exists_before=raw_file_path.exists(),
        source_url=source_url,
        started_at=now_utc_iso(),
    )

    try:
        if raw_file_path.exists():
            _record_step(manifest, "download", "skipped", {"reason": "raw_already_exists"})
        else:
            download_result, download_manifest_path = dependencies.download_period(
                resolved_period,
                config_path=config_path,
                raw_root=raw_root,
            )
            manifest["download"] = {
                "manifest_path": str(download_manifest_path),
                "result": download_result,
            }
            _record_step(manifest, "download", download_result.get("status"), manifest["download"])
            if download_result.get("status") not in {"success", "already_exists"}:
                raise SinglePeriodPipelineError(
                    download_result.get("error_message") or f"download failed: {download_result.get('status')}"
                )

        raw_validation, raw_validation_manifest_path = dependencies.validate_raw(
            resolved_period,
            raw_root=raw_root,
        )
        manifest["raw_validation"] = {
            "manifest_path": str(raw_validation_manifest_path),
            "result": raw_validation,
        }
        manifest["encoding_requested"] = raw_validation.get("encoding_requested")
        manifest["encoding_detected"] = raw_validation.get("encoding_detected")
        manifest["encoding_candidates_tried"] = raw_validation.get("encoding_candidates_tried", [])
        _record_step(manifest, "raw_validation", raw_validation.get("status"), manifest["raw_validation"])
        if not raw_validation.get("valid"):
            raise SinglePeriodPipelineError(
                raw_validation.get("error_message") or f"raw validation failed: {raw_validation.get('status')}"
            )

        processing_result, processing_manifest_path = dependencies.process_raw(
            resolved_period,
            raw_root=raw_root,
            output_dir=output_dir,
            chunk_size=chunk_size,
            encoding=raw_validation["encoding_detected"],
            validation_result=raw_validation,
            validation_manifest_path=raw_validation_manifest_path,
            duckdb_memory_limit=duckdb_memory_limit,
            duckdb_threads=duckdb_threads,
            preserve_temporary_on_failure=preserve_temporary_on_failure,
        )
        manifest["raw_processing"] = {
            "manifest_path": str(processing_manifest_path),
            "result": processing_result,
        }
        manifest["aggregate_output_path"] = processing_result.get("aggregate_output_path")
        _record_step(manifest, "raw_processing", processing_result.get("status"), manifest["raw_processing"])
        if processing_result.get("status") != "success":
            raise SinglePeriodPipelineError(
                processing_result.get("error_message") or f"processing failed: {processing_result.get('status')}"
            )

        config = dependencies.postgres_config_from_env()
        if not config.is_complete:
            raise SinglePeriodPipelineError("PostgreSQL config is incomplete. Set IMSS_PG_* variables.")

        connection = dependencies.connect_postgres(config)
        try:
            existing = dependencies.check_existing(connection, resolved_period)
            manifest["postgres"]["check_existing"] = existing
            _record_step(manifest, "postgres.check_existing", "success", existing)
            if existing.get("exists"):
                _finish(manifest, status="success", action="no_op")
                return manifest, write_pipeline_manifest(manifest, output_dir)

            period_control = dependencies.register_period_control(
                connection,
                resolved_period,
                run_id=effective_run_id,
                source_url=source_url,
            )
            manifest["postgres"]["register_period_control"] = period_control
            manifest["writes_postgresql"] = manifest["writes_postgresql"] or bool(period_control.get("inserted"))
            _record_step(manifest, "postgres.register_period_control", period_control.get("recommended_status"), period_control)
            if not period_control.get("inserted"):
                raise SinglePeriodPipelineError(period_control.get("reason") or "period_control was not inserted")

            run_manifest = dependencies.register_run_manifest(
                connection,
                resolved_period,
                effective_run_id,
                manifest={
                    "pipeline_run_id": effective_run_id,
                    "source_url": source_url,
                    "raw_file_path": str(raw_file_path),
                    "aggregate_output_path": manifest["aggregate_output_path"],
                },
            )
            manifest["postgres"]["register_run_manifest"] = run_manifest
            manifest["writes_postgresql"] = manifest["writes_postgresql"] or bool(run_manifest.get("inserted"))
            _record_step(manifest, "postgres.register_run_manifest", run_manifest.get("recommended_status"), run_manifest)
            if not run_manifest.get("inserted"):
                raise SinglePeriodPipelineError(run_manifest.get("reason") or "run_manifest was not inserted")

            load_result = dependencies.load_staging(
                connection,
                manifest["aggregate_output_path"],
                resolved_period,
                batch_size=batch_size,
                run_id=effective_run_id,
            )
            manifest["postgres"]["load_staging"] = load_result
            manifest["writes_postgresql"] = manifest["writes_postgresql"] or bool(load_result.get("inserted"))
            _record_step(manifest, "postgres.load_staging", "inserted" if load_result.get("inserted") else "not_inserted", load_result)
            if not load_result.get("inserted"):
                raise SinglePeriodPipelineError(load_result.get("reason") or "staging load did not insert rows")

            promotion = dependencies.promote_staging_final(
                connection,
                resolved_period,
                run_id=effective_run_id,
                batch_size=promotion_batch_size,
            )
            manifest["postgres"]["promote_staging_final"] = promotion
            manifest["writes_postgresql"] = manifest["writes_postgresql"] or bool(promotion.get("inserted"))
            _record_step(manifest, "postgres.promote_staging_final", "inserted" if promotion.get("inserted") else "not_inserted", promotion)
            if not promotion.get("inserted"):
                raise SinglePeriodPipelineError(promotion.get("reason") or "promotion did not insert rows")

            validation = dependencies.validate_post_promotion(connection, resolved_period)
            manifest["postgres"]["validate_post_promotion"] = validation
            _record_step(manifest, "postgres.validate_post_promotion", validation.get("validation_status"), validation)
            if validation.get("validation_status") != "passed":
                raise SinglePeriodPipelineError("post-promotion validation failed")

            finalized_period = dependencies.finalize_period_control(
                connection,
                resolved_period,
                run_id=effective_run_id,
            )
            manifest["postgres"]["finalize_period_control"] = finalized_period
            manifest["writes_postgresql"] = manifest["writes_postgresql"] or bool(
                finalized_period.get("writes_period_control_only")
            )
            _record_step(
                manifest,
                "postgres.finalize_period_control",
                "finalized" if finalized_period.get("finalized") else "not_finalized",
                finalized_period,
            )
            if not finalized_period.get("finalized"):
                raise SinglePeriodPipelineError(finalized_period.get("reason") or "period_control was not finalized")

            finalized_manifest = dependencies.finalize_run_manifest(
                connection,
                resolved_period,
                effective_run_id,
            )
            manifest["postgres"]["finalize_run_manifest"] = finalized_manifest
            manifest["writes_postgresql"] = manifest["writes_postgresql"] or bool(
                finalized_manifest.get("writes_run_manifest_only")
            )
            _record_step(
                manifest,
                "postgres.finalize_run_manifest",
                "finalized" if finalized_manifest.get("finalized") else "not_finalized",
                finalized_manifest,
            )
            if not finalized_manifest.get("finalized"):
                raise SinglePeriodPipelineError(finalized_manifest.get("reason") or "run_manifest was not finalized")
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()

        _finish(manifest, status="success", action="loaded")
        return manifest, write_pipeline_manifest(manifest, output_dir)
    except Exception as error:
        _finish(manifest, status="failed", action="failed", error_message=str(error))
        return manifest, write_pipeline_manifest(manifest, output_dir)
