"""Planning and controlled execution for historical IMSS single-period batches."""

from __future__ import annotations

import calendar
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import load_config
from .download import DEFAULT_RAW_ROOT, build_raw_file_path, now_utc_iso, validate_period
from .postgres.config import PostgresConfig
from .postgres.connection import connect
from .postgres.loader import check_existing_period
from .single_period_pipeline import execute_single_period_pipeline


DEFAULT_BATCH_OUTPUT_DIR = Path("outputs/pipeline")
HISTORICAL_BATCH_CONFIG_SECTION = "imss_historical_batch"
ELIGIBLE_EXECUTE_ACTIONS = {"download_process_load", "validate_process_load"}
MAX_BATCH_EXECUTE_PERIODS = 3
PLANNER_ACTIONS = (
    "skip_existing",
    "download_process_load",
    "validate_process_load",
    "blocked_existing_pending",
    "blocked_existing_non_loaded",
    "blocked_partial_final",
    "blocked_inconsistent_state",
)
HISTORICAL_BATCH_DEFAULTS = {
    "raw_root": str(DEFAULT_RAW_ROOT),
    "output_dir": str(DEFAULT_BATCH_OUTPUT_DIR),
    "chunk_size": 100000,
    "batch_size": 5000,
    "promotion_batch_size": 50000,
    "duckdb_memory_limit": "1GB",
    "duckdb_threads": 2,
    "stop_on_failure": True,
}


@dataclass(frozen=True)
class HistoricalBatchPlannerDependencies:
    postgres_config_from_env: Callable = PostgresConfig.from_env
    connect_postgres: Callable = connect
    check_existing: Callable = check_existing_period
    execute_single_period: Callable = execute_single_period_pipeline


def generate_historical_batch_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"historical_batch_{timestamp}_{uuid.uuid4().hex[:8]}"


def resolve_historical_batch_config(
    *,
    config_path: str | Path,
    cli_mode: str | None = None,
    cli_start_period: str | None = None,
    cli_end_period: str | None = None,
    cli_max_periods: int | None = None,
    cli_stop_on_failure: bool | None = None,
    cli_raw_root: str | Path | None = None,
    cli_output_dir: str | Path | None = None,
    cli_chunk_size: int | None = None,
    cli_batch_size: int | None = None,
    cli_promotion_batch_size: int | None = None,
    cli_duckdb_memory_limit: str | None = None,
    cli_duckdb_threads: int | None = None,
) -> dict:
    """Resolve historical batch settings with CLI > config > safe defaults."""
    config = load_config(config_path) or {}
    section = config.get(HISTORICAL_BATCH_CONFIG_SECTION)
    if section is None:
        section = {}
    if not isinstance(section, dict):
        raise ValueError(f"{HISTORICAL_BATCH_CONFIG_SECTION} must be a mapping")

    cli_explicit = bool(cli_mode and cli_start_period and cli_end_period)
    if section.get("enabled") is False and not cli_explicit:
        raise ValueError(
            f"{HISTORICAL_BATCH_CONFIG_SECTION}.enabled is false; provide explicit CLI mode and periods to override"
        )

    def resolve(name: str, cli_value, config_name: str | None = None, default=None):
        if cli_value is not None:
            return cli_value, "cli"
        key = config_name or name
        if key in section and section[key] is not None:
            return section[key], "config"
        return default, "default"

    mode, mode_source = resolve("mode", cli_mode)
    start_period, start_source = resolve("start_period", cli_start_period)
    end_period, end_source = resolve("end_period", cli_end_period)
    max_periods, max_source = resolve(
        "max_periods", cli_max_periods, "max_periods_per_run"
    )
    stop_on_failure, stop_source = resolve(
        "stop_on_failure",
        cli_stop_on_failure,
        default=HISTORICAL_BATCH_DEFAULTS["stop_on_failure"],
    )
    raw_root, raw_root_source = resolve(
        "raw_root", cli_raw_root, default=HISTORICAL_BATCH_DEFAULTS["raw_root"]
    )
    output_dir, output_dir_source = resolve(
        "output_dir", cli_output_dir, default=HISTORICAL_BATCH_DEFAULTS["output_dir"]
    )
    chunk_size, chunk_size_source = resolve(
        "chunk_size", cli_chunk_size, default=HISTORICAL_BATCH_DEFAULTS["chunk_size"]
    )
    batch_size, batch_size_source = resolve(
        "batch_size", cli_batch_size, default=HISTORICAL_BATCH_DEFAULTS["batch_size"]
    )
    promotion_batch_size, promotion_source = resolve(
        "promotion_batch_size",
        cli_promotion_batch_size,
        default=HISTORICAL_BATCH_DEFAULTS["promotion_batch_size"],
    )
    legacy_processing_engine = section.get("processing_engine")
    if legacy_processing_engine not in {None, "duckdb"}:
        raise ValueError(
            "imss_historical_batch.processing_engine is retired; only DuckDB is supported."
        )
    duckdb_memory_limit, duckdb_memory_limit_source = resolve(
        "duckdb_memory_limit",
        cli_duckdb_memory_limit,
        default=HISTORICAL_BATCH_DEFAULTS["duckdb_memory_limit"],
    )
    duckdb_threads, duckdb_threads_source = resolve(
        "duckdb_threads",
        cli_duckdb_threads,
        default=HISTORICAL_BATCH_DEFAULTS["duckdb_threads"],
    )

    if mode not in {"dry_run", "execute"}:
        raise ValueError("historical batch mode must be dry_run or execute")
    if not start_period or not end_period:
        raise ValueError("start-period and end-period are required in CLI or imss_historical_batch config")
    start_period = validate_period(str(start_period))
    end_period = validate_period(str(end_period))
    if mode == "execute" and max_periods is None:
        raise ValueError("execute requires --max-periods in CLI or max_periods_per_run in config")
    if max_periods is not None:
        max_periods = int(max_periods)
        if max_periods <= 0:
            raise ValueError("max-periods must be greater than zero")
        if max_periods > MAX_BATCH_EXECUTE_PERIODS:
            raise ValueError(f"max-periods cannot be greater than {MAX_BATCH_EXECUTE_PERIODS}")
    if mode == "execute" and stop_on_failure is not True:
        raise ValueError("execute requires stop_on_failure=true")

    numeric_values = {
        "chunk_size": chunk_size,
        "batch_size": batch_size,
        "promotion_batch_size": promotion_batch_size,
        "duckdb_threads": duckdb_threads,
    }
    for name, value in numeric_values.items():
        numeric_values[name] = int(value)
        if numeric_values[name] <= 0:
            raise ValueError(f"{name} must be greater than zero")

    return {
        "config_path": str(config_path),
        "config_section": HISTORICAL_BATCH_CONFIG_SECTION,
        "enabled": section.get("enabled", True),
        "mode": mode,
        "start_period": start_period,
        "end_period": end_period,
        "max_periods": max_periods,
        "stop_on_failure": stop_on_failure,
        "raw_root": str(raw_root),
        "output_dir": str(output_dir),
        **numeric_values,
        "processing_engine": "duckdb",
        "duckdb_memory_limit": str(duckdb_memory_limit),
        "sources": {
            "mode": mode_source,
            "start_period": start_source,
            "end_period": end_source,
            "max_periods": max_source,
            "stop_on_failure": stop_source,
            "raw_root": raw_root_source,
            "output_dir": output_dir_source,
            "chunk_size": chunk_size_source,
            "batch_size": batch_size_source,
            "promotion_batch_size": promotion_source,
            "processing_engine": "fixed",
            "duckdb_memory_limit": duckdb_memory_limit_source,
            "duckdb_threads": duckdb_threads_source,
        },
    }


def _parse_period_date(period: str) -> datetime:
    validate_period(period)
    return datetime.strptime(period, "%Y-%m-%d")


def _is_month_end(value: datetime) -> bool:
    return value.day == calendar.monthrange(value.year, value.month)[1]


def generate_month_end_periods(start_period: str, end_period: str) -> list[str]:
    """Generate inclusive month-end periods between two explicit month-end dates."""
    start = _parse_period_date(start_period)
    end = _parse_period_date(end_period)
    if start > end:
        raise ValueError("start-period must be less than or equal to end-period")
    if not _is_month_end(start):
        raise ValueError("start-period must be a calendar month-end date")
    if not _is_month_end(end):
        raise ValueError("end-period must be a calendar month-end date")

    periods: list[str] = []
    year = start.year
    month = start.month
    while (year, month) <= (end.year, end.month):
        day = calendar.monthrange(year, month)[1]
        periods.append(f"{year:04d}-{month:02d}-{day:02d}")
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return periods


def _manifest_path(output_dir: str | Path, run_id: str, start_period: str, end_period: str) -> Path:
    return Path(output_dir) / (
        f"historical_batch_plan_{run_id}_{validate_period(start_period)}_{validate_period(end_period)}.json"
    )


def _execute_manifest_path(output_dir: str | Path, run_id: str, start_period: str, end_period: str) -> Path:
    return Path(output_dir) / (
        f"historical_batch_execute_{run_id}_{validate_period(start_period)}_{validate_period(end_period)}.json"
    )


def write_historical_batch_plan(plan: dict, output_dir: str | Path = DEFAULT_BATCH_OUTPUT_DIR) -> Path:
    path = _manifest_path(output_dir, plan["run_id"], plan["start_period"], plan["end_period"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def write_historical_batch_execute_manifest(
    manifest: dict,
    output_dir: str | Path = DEFAULT_BATCH_OUTPUT_DIR,
) -> Path:
    path = _execute_manifest_path(
        output_dir,
        manifest["run_id"],
        manifest["start_period"],
        manifest["end_period"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _empty_summary() -> dict[str, int]:
    return {action: 0 for action in PLANNER_ACTIONS}


def _classify_period(*, raw_exists: bool, postgres_state: dict) -> tuple[str, bool, str]:
    final_count = int(postgres_state.get("final_table_row_count") or 0)
    period_control_exists = bool(postgres_state.get("period_control_exists"))
    period_control_status = postgres_state.get("period_control_status")

    if period_control_exists and period_control_status == "loaded" and final_count > 0:
        return "skip_existing", False, "period_loaded_in_postgresql"
    if period_control_exists and period_control_status == "loaded" and final_count == 0:
        return "blocked_inconsistent_state", True, "period_control_loaded_without_final_rows"
    if period_control_exists and period_control_status == "pending":
        return "blocked_existing_pending", True, "period_control_pending"
    if period_control_exists and period_control_status not in {None, "loaded", "pending"}:
        return "blocked_existing_non_loaded", True, "period_control_status_is_not_loaded"
    if final_count > 0 and period_control_status != "loaded":
        return "blocked_partial_final", True, "final_rows_exist_without_loaded_period_control"
    if period_control_exists and period_control_status is None:
        return "blocked_inconsistent_state", True, "period_control_exists_without_status"
    if not period_control_exists and final_count == 0:
        if raw_exists:
            return "validate_process_load", False, "raw_exists_and_period_not_loaded"
        return "download_process_load", False, "raw_missing_and_period_not_loaded"
    return "blocked_inconsistent_state", True, "ambiguous_postgresql_state"


def _period_plan(period: str, *, raw_root: str | Path, postgres_state: dict) -> dict:
    raw_file_path = build_raw_file_path(period, raw_root)
    raw_exists = raw_file_path.exists()
    action, blocked, reason = _classify_period(raw_exists=raw_exists, postgres_state=postgres_state)
    return {
        "periodo_informacion": period,
        "raw_file_path": str(raw_file_path),
        "raw_exists": raw_exists,
        "postgres_exists": bool(postgres_state.get("exists", False)),
        "final_table_row_count": int(postgres_state.get("final_table_row_count") or 0),
        "period_control_exists": bool(postgres_state.get("period_control_exists", False)),
        "period_control_status": postgres_state.get("period_control_status"),
        "recommended_action": action,
        "blocked": blocked,
        "reason": reason,
        "postgres_check": postgres_state,
    }


def plan_historical_batch(
    *,
    start_period: str,
    end_period: str,
    config_path: str | Path = "config/config.yaml",
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    output_dir: str | Path = DEFAULT_BATCH_OUTPUT_DIR,
    run_id: str | None = None,
    effective_config: dict | None = None,
    dependencies: HistoricalBatchPlannerDependencies = HistoricalBatchPlannerDependencies(),
) -> tuple[dict, Path]:
    """Plan historical single-period pipeline work without downloads, processing or writes."""
    periods = generate_month_end_periods(start_period, end_period)
    effective_run_id = run_id or generate_historical_batch_run_id()
    started_at = now_utc_iso()
    config = dependencies.postgres_config_from_env()
    if not config.is_complete:
        raise ValueError("PostgreSQL config is incomplete. Set IMSS_PG_* variables.")

    connection = dependencies.connect_postgres(config)
    period_plans = []
    try:
        for period in periods:
            postgres_state = dependencies.check_existing(connection, period)
            period_plans.append(
                _period_plan(period, raw_root=raw_root, postgres_state=postgres_state)
            )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    summary = _empty_summary()
    for item in period_plans:
        summary[item["recommended_action"]] += 1

    plan = {
        "run_id": effective_run_id,
        "mode": "historical_batch_planner",
        "batch_mode": (effective_config or {}).get("mode", "dry_run"),
        "dry_run": True,
        "config_path": str(config_path),
        "config_section": HISTORICAL_BATCH_CONFIG_SECTION,
        "effective_config": effective_config,
        "max_periods": (effective_config or {}).get("max_periods"),
        "stop_on_failure": (effective_config or {}).get("stop_on_failure", True),
        "start_period": validate_period(start_period),
        "end_period": validate_period(end_period),
        "period_count": len(periods),
        "status": "planned",
        "summary": summary,
        "periods": period_plans,
        "writes_postgresql": False,
        "writes_concentrado": False,
        "writes_data_processed": False,
        "downloads_raw": False,
        "processes_raw": False,
        "touches_staging_table": False,
        "touches_final_table": False,
        "opens_database_connection": True,
        "started_at": started_at,
        "finished_at": now_utc_iso(),
    }
    manifest_path = write_historical_batch_plan(plan, output_dir)
    return plan, manifest_path


def _selected_periods(plan: dict, max_periods: int) -> tuple[list[dict], list[str]]:
    eligible = [
        period
        for period in plan["periods"]
        if period["recommended_action"] in ELIGIBLE_EXECUTE_ACTIONS and not period["blocked"]
    ]
    selected = eligible[:max_periods]
    not_selected = [period["periodo_informacion"] for period in eligible[max_periods:]]
    return selected, not_selected


def _base_execute_manifest(
    *,
    run_id: str,
    plan: dict,
    plan_manifest_path: str | Path,
    max_periods: int,
    stop_on_failure: bool,
    started_at: str,
    config_path: str | Path,
    effective_config: dict | None,
) -> dict:
    skipped_existing = [
        item["periodo_informacion"]
        for item in plan["periods"]
        if item["recommended_action"] == "skip_existing"
    ]
    blocked = [
        item["periodo_informacion"]
        for item in plan["periods"]
        if item["blocked"] or str(item["recommended_action"]).startswith("blocked_")
    ]
    return {
        "run_id": run_id,
        "mode": "historical_batch_execute",
        "batch_mode": (effective_config or {}).get("mode", "execute"),
        "dry_run": False,
        "config_path": str(config_path),
        "config_section": HISTORICAL_BATCH_CONFIG_SECTION,
        "effective_config": effective_config,
        "status": None,
        "action": None,
        "start_period": plan["start_period"],
        "end_period": plan["end_period"],
        "max_periods": max_periods,
        "stop_on_failure": stop_on_failure,
        "plan_manifest_path": str(plan_manifest_path),
        "planned_period_count": plan["period_count"],
        "eligible_period_count": 0,
        "selected_period_count": 0,
        "skipped_existing_count": len(skipped_existing),
        "blocked_count": len(blocked),
        "executed_period_count": 0,
        "successful_period_count": 0,
        "failed_period_count": 0,
        "skipped_existing_periods": skipped_existing,
        "blocked_periods": blocked,
        "not_selected_periods": [],
        "executions": [],
        "stopped_after_failure": False,
        "error_period": None,
        "error_message": None,
        "writes_postgresql": False,
        "writes_concentrado": False,
        "writes_data_processed": False,
        "downloads_raw": False,
        "processes_raw": False,
        "touches_staging_table": False,
        "touches_final_table": False,
        "started_at": started_at,
        "finished_at": None,
    }


def _final_row_count(single_result: dict) -> int | None:
    validation = (single_result.get("postgres") or {}).get("validate_post_promotion") or {}
    value = validation.get("final_row_count")
    return int(value) if value is not None else None


def execute_historical_batch(
    *,
    start_period: str,
    end_period: str,
    config_path: str | Path = "config/config.yaml",
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    output_dir: str | Path = DEFAULT_BATCH_OUTPUT_DIR,
    run_id: str | None = None,
    max_periods: int,
    stop_on_failure: bool = True,
    chunk_size: int = 100000,
    batch_size: int = 5000,
    promotion_batch_size: int = 50000,
    duckdb_memory_limit: str = "1GB",
    duckdb_threads: int = 2,
    effective_config: dict | None = None,
    dependencies: HistoricalBatchPlannerDependencies = HistoricalBatchPlannerDependencies(),
) -> tuple[dict, Path]:
    """Execute a bounded historical batch by delegating each period to the single-period pipeline."""
    if max_periods <= 0:
        raise ValueError("max-periods must be greater than zero")
    if max_periods > MAX_BATCH_EXECUTE_PERIODS:
        raise ValueError(f"max-periods cannot be greater than {MAX_BATCH_EXECUTE_PERIODS}")
    if not stop_on_failure:
        raise ValueError("execute requires stop-on-failure for PR #42")

    effective_run_id = run_id or generate_historical_batch_run_id()
    plan, plan_manifest_path = plan_historical_batch(
        start_period=start_period,
        end_period=end_period,
        config_path=config_path,
        raw_root=raw_root,
        output_dir=output_dir,
        run_id=f"{effective_run_id}_plan",
        effective_config=effective_config,
        dependencies=dependencies,
    )
    selected, not_selected = _selected_periods(plan, max_periods)
    eligible_count = sum(
        1
        for item in plan["periods"]
        if item["recommended_action"] in ELIGIBLE_EXECUTE_ACTIONS and not item["blocked"]
    )
    manifest = _base_execute_manifest(
        run_id=effective_run_id,
        plan=plan,
        plan_manifest_path=plan_manifest_path,
        max_periods=max_periods,
        stop_on_failure=stop_on_failure,
        started_at=now_utc_iso(),
        config_path=config_path,
        effective_config=effective_config,
    )
    manifest["eligible_period_count"] = eligible_count
    manifest["selected_period_count"] = len(selected)
    manifest["not_selected_periods"] = not_selected

    if not selected:
        manifest["status"] = "success"
        manifest["action"] = "no_op"
        manifest["finished_at"] = now_utc_iso()
        return manifest, write_historical_batch_execute_manifest(manifest, output_dir)

    for item in selected:
        period = item["periodo_informacion"]
        single_result, single_manifest_path = dependencies.execute_single_period(
            config_path=config_path,
            period=period,
            raw_root=raw_root,
            output_dir=output_dir,
            chunk_size=chunk_size,
            batch_size=batch_size,
            promotion_batch_size=promotion_batch_size,
            duckdb_memory_limit=duckdb_memory_limit,
            duckdb_threads=duckdb_threads,
            run_id=f"{effective_run_id}_{period}",
        )
        execution = {
            "periodo_informacion": period,
            "planned_action": item["recommended_action"],
            "execution_status": single_result.get("status"),
            "execution_action": single_result.get("action"),
            "single_period_run_id": single_result.get("run_id"),
            "single_period_manifest_path": str(single_manifest_path),
            "final_row_count": _final_row_count(single_result),
            "error_message": single_result.get("error_message"),
        }
        manifest["executions"].append(execution)
        manifest["executed_period_count"] += 1
        if single_result.get("status") == "success":
            manifest["successful_period_count"] += 1
        else:
            manifest["failed_period_count"] += 1
            manifest["status"] = "failed"
            manifest["action"] = "failed"
            manifest["stopped_after_failure"] = True
            manifest["error_period"] = period
            manifest["error_message"] = single_result.get("error_message") or "single-period pipeline failed"
            break

    manifest["writes_postgresql"] = manifest["executed_period_count"] > 0
    manifest["downloads_raw"] = manifest["executed_period_count"] > 0
    manifest["processes_raw"] = manifest["executed_period_count"] > 0
    manifest["touches_staging_table"] = manifest["successful_period_count"] > 0
    manifest["touches_final_table"] = manifest["successful_period_count"] > 0

    if manifest["status"] is None:
        manifest["status"] = "success"
        manifest["action"] = "executed"
    if manifest["stopped_after_failure"]:
        selected_periods = [item["periodo_informacion"] for item in selected]
        failed_index = selected_periods.index(manifest["error_period"])
        manifest["not_selected_periods"].extend(selected_periods[failed_index + 1 :])

    manifest["finished_at"] = now_utc_iso()
    return manifest, write_historical_batch_execute_manifest(manifest, output_dir)
