"""Dry-run planning for historical IMSS single-period pipeline batches."""

from __future__ import annotations

import calendar
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .download import DEFAULT_RAW_ROOT, build_raw_file_path, now_utc_iso, validate_period
from .postgres.config import PostgresConfig
from .postgres.connection import connect
from .postgres.loader import check_existing_period


DEFAULT_BATCH_OUTPUT_DIR = Path("outputs/pipeline")
PLANNER_ACTIONS = (
    "skip_existing",
    "download_process_load",
    "validate_process_load",
    "blocked_existing_pending",
    "blocked_existing_non_loaded",
    "blocked_partial_final",
    "blocked_inconsistent_state",
)


@dataclass(frozen=True)
class HistoricalBatchPlannerDependencies:
    postgres_config_from_env: Callable = PostgresConfig.from_env
    connect_postgres: Callable = connect
    check_existing: Callable = check_existing_period


def generate_historical_batch_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"historical_batch_{timestamp}_{uuid.uuid4().hex[:8]}"


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


def write_historical_batch_plan(plan: dict, output_dir: str | Path = DEFAULT_BATCH_OUTPUT_DIR) -> Path:
    path = _manifest_path(output_dir, plan["run_id"], plan["start_period"], plan["end_period"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True),
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
        "dry_run": True,
        "config_path": str(config_path),
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
