"""Dry-run publish planning for IMSS raw aggregate outputs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .download import now_utc_iso, validate_period
from .raw_compare import (
    DEFAULT_COMPARE_OUTPUT_DIR,
    DEFAULT_CONCENTRADO_FILE,
    compare_raw_aggregate_with_concentrado,
)


DEFAULT_PUBLISH_PLAN_OUTPUT_DIR = DEFAULT_COMPARE_OUTPUT_DIR
DISALLOWED_OUTPUT_DIR = Path("data") / "processed"

ACTION_BY_COMPARISON_STATUS: dict[str, tuple[str, str, str]] = {
    "already_exists": (
        "success",
        "no_op",
        "Period already exists in concentrado and matches functionally.",
    ),
    "new_period": (
        "success",
        "insert_candidate",
        "Period does not exist in concentrado; dry-run only.",
    ),
    "conflict_existing_period_hash": (
        "blocked",
        "block",
        "Existing period fingerprint differs from aggregate fingerprint.",
    ),
    "conflict_existing_period_row_count": (
        "blocked",
        "block",
        "Existing period row count differs from aggregate row count.",
    ),
    "missing_concentrado": (
        "blocked",
        "block",
        "Concentrado file does not exist; dry-run will not create it.",
    ),
    "failed": (
        "failed",
        "block",
        "Comparison failed; publish planning is blocked.",
    ),
}


def generate_publish_plan_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def _plan_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"publish_plan_{run_id}_{validate_period(period)}.json"


def _resolve_from_cwd(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve(strict=False)


def _ensure_output_dir_allowed(output_dir: str | Path) -> None:
    candidate = _resolve_from_cwd(output_dir)
    disallowed = _resolve_from_cwd(DISALLOWED_OUTPUT_DIR)
    if candidate == disallowed or disallowed in candidate.parents:
        raise ValueError("output_dir cannot be data/processed or a child of data/processed")


def write_publish_plan(plan: dict, output_dir: str | Path = DEFAULT_PUBLISH_PLAN_OUTPUT_DIR) -> Path:
    _ensure_output_dir_allowed(output_dir)
    path = _plan_path(output_dir, plan["run_id"], plan["periodo_informacion"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _safety_checks(compare_result: dict, *, period_explicit: bool, aggregate_file_explicit: bool) -> dict:
    return {
        "period_explicit": period_explicit,
        "aggregate_file_explicit": aggregate_file_explicit,
        "concentrado_file_explicit_or_default": True,
        "writes_concentrado": bool(compare_result.get("writes_concentrado", False)),
        "writes_data_processed": bool(compare_result.get("writes_data_processed", False)),
        "loads_postgresql": bool(compare_result.get("loads_postgresql", False)),
        "touches_staging_table": bool(compare_result.get("touches_staging_table", False)),
        "touches_final_table": bool(compare_result.get("touches_final_table", False)),
        "writes_period_control": bool(compare_result.get("writes_period_control", False)),
        "writes_run_manifest": bool(compare_result.get("writes_run_manifest", False)),
    }


def build_publish_plan(
    period: str,
    *,
    aggregate_file: str | Path,
    concentrado_file: str | Path = DEFAULT_CONCENTRADO_FILE,
    output_dir: str | Path = DEFAULT_PUBLISH_PLAN_OUTPUT_DIR,
) -> tuple[dict, Path]:
    """Build a dry-run publish plan from the existing read-only comparison result."""
    period = validate_period(period)
    _ensure_output_dir_allowed(output_dir)
    run_id = generate_publish_plan_run_id()
    created_at = now_utc_iso()
    compare_result, compare_manifest_path = compare_raw_aggregate_with_concentrado(
        period,
        aggregate_file=aggregate_file,
        concentrado_file=concentrado_file,
        output_dir=output_dir,
    )
    comparison_status = str(compare_result.get("comparison_status") or "failed")
    status, action, default_reason = ACTION_BY_COMPARISON_STATUS.get(
        comparison_status,
        ACTION_BY_COMPARISON_STATUS["failed"],
    )
    reason = compare_result.get("error_message") or default_reason
    safety_checks = _safety_checks(
        compare_result,
        period_explicit=True,
        aggregate_file_explicit=True,
    )
    plan = {
        "run_id": run_id,
        "mode": "plan_imss_publish",
        "periodo_informacion": period,
        "created_at": created_at,
        "finished_at": now_utc_iso(),
        "status": status,
        "action": action,
        "reason": reason,
        "aggregate_file": str(aggregate_file),
        "aggregate_sha256": compare_result.get("aggregate_sha256"),
        "aggregate_file_size_bytes": compare_result.get("aggregate_file_size_bytes"),
        "concentrado_file": str(concentrado_file),
        "compare_manifest_path": str(compare_manifest_path),
        "comparison_status": comparison_status,
        "aggregate_summary": compare_result.get("aggregate_summary"),
        "existing_summary": compare_result.get("existing_summary"),
        "safety_checks": safety_checks,
        "would_write": False,
        "target": {
            "type": "csv_concentrado",
            "path": str(concentrado_file),
        },
        "error_message": compare_result.get("error_message") if status == "failed" else None,
    }
    plan_path = write_publish_plan(plan, output_dir)
    plan["plan_manifest_path"] = str(plan_path)
    # Rewrite once with the self-reference included.
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return plan, plan_path
