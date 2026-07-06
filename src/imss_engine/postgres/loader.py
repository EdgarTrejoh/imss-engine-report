"""Insert-only PostgreSQL loader skeleton.

This module defines future loader contracts without reading large CSV files or
modifying a database. All operations are dry-run placeholders unless a future
implementation replaces them deliberately.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PERIOD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class LoaderStepResult:
    """Dry-run result for one future loader step."""

    step: str
    status: str = "planned"
    details: dict[str, Any] = field(default_factory=dict)


def _not_implemented_for_execute(step: str) -> None:
    raise NotImplementedError(
        f"{step} is currently a skeleton placeholder. Only dry-run planning is implemented."
    )


def validate_period(period: str) -> LoaderStepResult:
    """Validate period format for future insert-only loads."""
    if not isinstance(period, str) or not PERIOD_RE.match(period):
        raise ValueError("period must be a string in YYYY-MM-DD format")
    return LoaderStepResult("validate_period", details={"periodo_informacion": period})


def validate_existing_period(period: str, *, dry_run: bool = True) -> LoaderStepResult:
    """Plan the future check for existing period_control/final rows."""
    validate_period(period)
    if not dry_run:
        _not_implemented_for_execute("validate_existing_period")
    return LoaderStepResult(
        "validate_existing_period",
        details={
            "periodo_informacion": period,
            "mode": "insert_only",
            "would_check": [
                "imss.imss_period_control",
                "imss.imss_hechos_asegurados",
            ],
        },
    )


def check_existing_period(connection, period: str) -> dict:
    """Read PostgreSQL to determine whether a period already exists.

    This is the first real loader check and is intentionally read-only. It only
    executes SELECT statements against period control and final facts.
    """
    validate_period(period)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status, row_count
            FROM imss.imss_period_control
            WHERE periodo_informacion = %s;
            """,
            (period,),
        )
        period_control_row = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) AS final_table_row_count
            FROM imss.imss_hechos_asegurados
            WHERE periodo_informacion = %s;
            """,
            (period,),
        )
        final_table_row_count = int(cursor.fetchone()[0])

    period_control_exists = period_control_row is not None
    period_control_status = period_control_row[0] if period_control_exists else None
    period_control_row_count = period_control_row[1] if period_control_exists else None

    if period_control_exists:
        exists = True
        recommended_status = "already_exists"
    elif final_table_row_count > 0:
        exists = True
        recommended_status = "conflict_existing_final_rows_without_control"
    else:
        exists = False
        recommended_status = "new_period"

    return {
        "periodo_informacion": period,
        "period_control_exists": period_control_exists,
        "period_control_status": period_control_status,
        "period_control_row_count": period_control_row_count,
        "final_table_row_count": final_table_row_count,
        "exists": exists,
        "recommended_status": recommended_status,
    }


def register_period_control_pending(
    connection,
    period: str,
    run_id: str | None = None,
    source_url: str | None = None,
) -> dict:
    """Insert a pending period_control row when the period is new.

    This is an explicit write operation for the loader bootstrap. It only
    inserts into ``imss.imss_period_control`` and never overwrites existing
    periods.
    """
    validate_period(period)
    existing = check_existing_period(connection, period)
    if existing["exists"]:
        return {
            "periodo_informacion": period,
            "inserted": False,
            "status": None,
            "recommended_status": existing["recommended_status"],
            "run_id": run_id,
            "source_url": source_url,
            "reason": "period already exists in period_control or final table",
            "period_check": existing,
        }

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO imss.imss_period_control (
                    periodo_informacion,
                    status,
                    row_count,
                    period_fingerprint_hash,
                    sum_asegurados,
                    sum_no_trabajadores,
                    sum_ta,
                    sum_ta_sal,
                    sum_masa_sal_ta,
                    run_id,
                    source_url,
                    error_message
                )
                VALUES (
                    %s,
                    'pending',
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    %s,
                    %s,
                    NULL
                );
                """,
                (period, run_id, source_url),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "periodo_informacion": period,
        "inserted": True,
        "status": "pending",
        "recommended_status": "pending_registered",
        "run_id": run_id,
        "source_url": source_url,
    }


def prepare_staging(period: str, source_path: str | Path | None = None, *, dry_run: bool = True) -> LoaderStepResult:
    """Plan staging preparation without reading the source file."""
    validate_period(period)
    if not dry_run:
        _not_implemented_for_execute("prepare_staging")
    return LoaderStepResult(
        "prepare_staging",
        details={
            "periodo_informacion": period,
            "source_path": str(source_path) if source_path is not None else None,
            "target_table": "imss.imss_staging_asegurados",
            "reads_source_file": False,
        },
    )


def promote_staging_to_final(period: str, *, dry_run: bool = True) -> LoaderStepResult:
    """Plan insert-only promotion from staging to final table."""
    validate_period(period)
    if not dry_run:
        _not_implemented_for_execute("promote_staging_to_final")
    return LoaderStepResult(
        "promote_staging_to_final",
        details={
            "periodo_informacion": period,
            "mode": "insert_only",
            "source_table": "imss.imss_staging_asegurados",
            "target_table": "imss.imss_hechos_asegurados",
            "disallowed": ["upsert_period", "full_refresh"],
        },
    )


def register_period_control(period: str, *, dry_run: bool = True) -> LoaderStepResult:
    """Plan period control registration for an insert-only load."""
    validate_period(period)
    if not dry_run:
        _not_implemented_for_execute("register_period_control")
    return LoaderStepResult(
        "register_period_control",
        details={
            "periodo_informacion": period,
            "target_table": "imss.imss_period_control",
            "future_status": "loaded",
        },
    )


def plan_register_run_manifest(run_id: str | None = None, *, dry_run: bool = True) -> LoaderStepResult:
    """Plan manifest registration in PostgreSQL JSONB."""
    if not dry_run:
        _not_implemented_for_execute("plan_register_run_manifest")
    return LoaderStepResult(
        "register_run_manifest",
        details={
            "run_id": run_id,
            "target_table": "imss.imss_run_manifest",
            "stores_manifest_jsonb": True,
        },
    )


def register_run_manifest(
    connection,
    period: str,
    run_id: str,
    manifest: dict | None = None,
) -> dict:
    """Insert a run manifest row when period_control exists.

    This function writes only to ``imss.imss_run_manifest`` and does not update
    period control, staging or final facts.
    """
    validate_period(period)
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required for run_manifest registration")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM imss.imss_period_control
            WHERE periodo_informacion = %s;
            """,
            (period,),
        )
        period_control_exists = cursor.fetchone() is not None

        cursor.execute(
            """
            SELECT 1
            FROM imss.imss_run_manifest
            WHERE run_id = %s;
            """,
            (run_id,),
        )
        manifest_exists = cursor.fetchone() is not None

    if not period_control_exists:
        return {
            "periodo_informacion": period,
            "run_id": run_id,
            "inserted": False,
            "recommended_status": "missing_period_control",
            "writes_run_manifest_only": False,
            "reason": "period does not exist in imss.imss_period_control",
        }

    if manifest_exists:
        return {
            "periodo_informacion": period,
            "run_id": run_id,
            "inserted": False,
            "recommended_status": "manifest_already_exists",
            "writes_run_manifest_only": False,
            "reason": "run_id already exists in imss.imss_run_manifest",
        }

    manifest_payload = dict(manifest or {})
    manifest_payload.update(
        {
            "periodo_informacion": period,
            "run_id": run_id,
            "mode": "manifest_only",
            "reads_source_csv": False,
            "touches_final_table": False,
            "touches_staging_table": False,
        }
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO imss.imss_run_manifest (
                    run_id,
                    run_mode,
                    status,
                    manifest_json
                )
                VALUES (
                    %s,
                    'manifest_only',
                    'pending',
                    CAST(%s AS jsonb)
                );
                """,
                (run_id, json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True)),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "periodo_informacion": period,
        "run_id": run_id,
        "inserted": True,
        "recommended_status": "run_manifest_registered",
        "writes_run_manifest_only": True,
    }


def plan_insert_only_load(
    period: str,
    *,
    source_path: str | Path | None = None,
    run_id: str | None = None,
) -> list[LoaderStepResult]:
    """Return the planned steps for a future insert-only PostgreSQL load."""
    return [
        validate_period(period),
        validate_existing_period(period),
        prepare_staging(period, source_path),
        promote_staging_to_final(period),
        register_period_control(period),
        plan_register_run_manifest(run_id),
    ]
