"""Guarded append-only publication of IMSS raw aggregates into concentrado CSV."""

from __future__ import annotations

import csv
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .download import calculate_sha256, get_file_size_bytes, now_utc_iso, validate_period
from .raw_compare import compare_raw_aggregate_with_concentrado


DEFAULT_PUBLISH_OUTPUT_DIR = Path("outputs/audit/publish")
DISALLOWED_OUTPUT_DIR = Path("data") / "processed"
SAFETY_WRITE_FLAGS = (
    "writes_concentrado",
    "writes_data_processed",
    "loads_postgresql",
    "touches_staging_table",
    "touches_final_table",
    "writes_period_control",
    "writes_run_manifest",
)


class PublishBlockedError(ValueError):
    """Raised when a controlled guardrail blocks publication."""


def generate_publish_insert_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def _resolve_from_cwd(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve(strict=False)


def _ensure_output_dir_allowed(output_dir: str | Path) -> None:
    candidate = _resolve_from_cwd(output_dir)
    disallowed = _resolve_from_cwd(DISALLOWED_OUTPUT_DIR)
    if candidate == disallowed or disallowed in candidate.parents:
        raise PublishBlockedError("output_dir cannot be data/processed or a child of data/processed")


def _manifest_path(output_dir: str | Path, run_id: str, period: str) -> Path:
    return Path(output_dir) / f"publish_manifest_{run_id}_{validate_period(period)}.json"


def _unknown_manifest_path(output_dir: str | Path, run_id: str) -> Path:
    return Path(output_dir) / f"publish_manifest_{run_id}_unknown.json"


def write_publish_manifest(manifest: dict, output_dir: str | Path = DEFAULT_PUBLISH_OUTPUT_DIR) -> Path:
    _ensure_output_dir_allowed(output_dir)
    period = manifest.get("periodo_informacion")
    path = (
        _manifest_path(output_dir, manifest["run_id"], period)
        if period
        else _unknown_manifest_path(output_dir, manifest["run_id"])
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _base_manifest(
    *,
    run_id: str,
    publish_plan_path: str | Path,
    output_dir: str | Path,
) -> dict:
    return {
        "run_id": run_id,
        "mode": "publish_imss_insert_only",
        "periodo_informacion": None,
        "created_at": now_utc_iso(),
        "finished_at": None,
        "status": None,
        "action": None,
        "reason": None,
        "publish_plan_path": str(publish_plan_path),
        "publish_plan_sha256": None,
        "aggregate_file": None,
        "aggregate_sha256": None,
        "aggregate_file_size_bytes": None,
        "concentrado_file": None,
        "concentrado_sha256_before": None,
        "concentrado_sha256_after": None,
        "concentrado_file_size_before": None,
        "concentrado_file_size_after": None,
        "concentrado_row_count_before": None,
        "concentrado_row_count_after": None,
        "rows_inserted": 0,
        "backup_path": None,
        "backup_sha256": None,
        "backup_file_size_bytes": None,
        "backup_created_at": None,
        "comparison_before": None,
        "comparison_before_manifest_path": None,
        "comparison_after": None,
        "comparison_after_manifest_path": None,
        "validation_status": None,
        "append_only": True,
        "rollback_manual_path": None,
        "writes_concentrado": False,
        "writes_data_processed": False,
        "loads_postgresql": False,
        "touches_staging_table": False,
        "touches_final_table": False,
        "writes_period_control": False,
        "writes_run_manifest": False,
        "columns_validated": False,
        "column_order_match": False,
        "aggregate_periods_detected": [],
        "periods_before": [],
        "periods_after": [],
        "error_message": None,
        "publish_manifest_path": None,
    }


def _finish(
    manifest: dict,
    *,
    status: str,
    action: str,
    validation_status: str,
    reason: str | None = None,
    error_message: str | None = None,
) -> dict:
    manifest["status"] = status
    manifest["action"] = action
    manifest["validation_status"] = validation_status
    manifest["reason"] = reason
    manifest["error_message"] = error_message
    manifest["finished_at"] = now_utc_iso()
    return manifest


def _load_publish_plan(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"publish_plan does not exist: {path}")
    if not path.is_file():
        raise PublishBlockedError(f"publish_plan path is not a file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid publish_plan JSON: {exc}") from exc


def _paths_match(first: str | Path, second: str | Path) -> bool:
    return _resolve_from_cwd(first) == _resolve_from_cwd(second)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PublishBlockedError(message)


def _validate_plan(plan: dict, plan_path: Path, concentrado_file: str | Path | None) -> tuple[str, Path, Path]:
    _require(plan.get("mode") == "plan_imss_publish", "publish_plan mode is not plan_imss_publish")
    _require(plan.get("status") == "success", "publish_plan status is not success")
    _require(plan.get("action") == "insert_candidate", "publish_plan action is not insert_candidate")
    _require(plan.get("would_write") is False, "publish_plan must be dry-run")
    _require(plan.get("comparison_status") == "new_period", "publish_plan is not a new_period candidate")

    period = validate_period(str(plan.get("periodo_informacion", "")))
    aggregate_file = Path(str(plan.get("aggregate_file") or ""))
    _require(aggregate_file.exists(), f"aggregate_file does not exist: {aggregate_file}")
    _require(aggregate_file.is_file(), f"aggregate_file is not a file: {aggregate_file}")

    plan_concentrado = Path(str(plan.get("concentrado_file") or ""))
    target = plan.get("target") or {}
    _require(target.get("type") == "csv_concentrado", "publish_plan target.type is not csv_concentrado")
    _require(target.get("path"), "publish_plan target.path is required")
    _require(_paths_match(target["path"], plan_concentrado), "target.path does not match plan concentrado_file")

    selected_concentrado = Path(concentrado_file) if concentrado_file is not None else plan_concentrado
    _require(_paths_match(selected_concentrado, plan_concentrado), "concentrado path mismatch")
    _require(selected_concentrado.exists(), "concentrado file does not exist; publish will not create it")
    _require(selected_concentrado.is_file(), f"concentrado path is not a file: {selected_concentrado}")

    expected_sha = plan.get("aggregate_sha256")
    expected_size = plan.get("aggregate_file_size_bytes")
    _require(bool(expected_sha), "publish_plan aggregate_sha256 is required")
    _require(expected_size is not None, "publish_plan aggregate_file_size_bytes is required")
    _require(calculate_sha256(aggregate_file) == expected_sha, "aggregate_file sha256 mismatch")
    _require(get_file_size_bytes(aggregate_file) == int(expected_size), "aggregate_file size mismatch")

    safety_checks = plan.get("safety_checks") or {}
    for flag in SAFETY_WRITE_FLAGS:
        _require(safety_checks.get(flag) is False, f"publish_plan safety check is not read-only: {flag}")

    if plan.get("plan_manifest_path"):
        _require(_paths_match(plan["plan_manifest_path"], plan_path), "publish_plan self path mismatch")

    return period, aggregate_file, selected_concentrado


def _read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            return next(reader)
        except StopIteration as exc:
            raise PublishBlockedError(f"CSV file is empty: {path}") from exc


def _scan_csv(path: Path, *, period: str | None = None) -> dict:
    row_count = 0
    periods: set[str] = set()
    header = _read_header(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != header:
            raise PublishBlockedError(f"CSV header mismatch in {path}")
        if "periodo_informacion" not in header:
            raise PublishBlockedError(f"CSV file is missing periodo_informacion column: {path}")
        for row in reader:
            values = [value or "" for value in row.values()]
            if values == header:
                raise PublishBlockedError("aggregate file contains a duplicated header row")
            row_period = str(row.get("periodo_informacion", ""))
            periods.add(row_period)
            if period is not None and row_period != period:
                raise PublishBlockedError(f"aggregate period mismatch: {row_period}")
            row_count += 1
    return {
        "header": header,
        "row_count": row_count,
        "periods": sorted(periods),
    }


def _validate_aggregate_for_append(
    *,
    aggregate_file: Path,
    concentrado_file: Path,
    period: str,
    expected_rows: int,
) -> dict:
    aggregate_scan = _scan_csv(aggregate_file, period=period)
    concentrado_scan = _scan_csv(concentrado_file)
    _require(
        aggregate_scan["header"] == concentrado_scan["header"],
        "aggregate and concentrado columns do not match exactly",
    )
    _require(aggregate_scan["row_count"] == expected_rows, "aggregate row count does not match plan summary")
    _require(aggregate_scan["row_count"] > 0, "aggregate file has no data rows")
    return {
        "columns": aggregate_scan["header"],
        "aggregate_row_count": aggregate_scan["row_count"],
        "aggregate_periods": aggregate_scan["periods"],
        "concentrado_row_count": concentrado_scan["row_count"],
        "concentrado_periods": concentrado_scan["periods"],
    }


def _backup_path(output_dir: str | Path, run_id: str) -> Path:
    return Path(output_dir) / "backups" / f"imss_concentrado_{run_id}_before.csv"


def _create_backup(concentrado_file: Path, output_dir: str | Path, run_id: str) -> dict:
    backup = _backup_path(output_dir, run_id)
    if backup.exists():
        raise PublishBlockedError(f"backup already exists: {backup}")
    backup.parent.mkdir(parents=True, exist_ok=True)
    source_sha = calculate_sha256(concentrado_file)
    source_size = get_file_size_bytes(concentrado_file)
    shutil.copy2(concentrado_file, backup)
    backup_sha = calculate_sha256(backup)
    backup_size = get_file_size_bytes(backup)
    _require(backup_sha == source_sha, "backup hash verification failed")
    _require(backup_size == source_size, "backup size verification failed")
    return {
        "backup_path": backup,
        "backup_sha256": backup_sha,
        "backup_file_size_bytes": backup_size,
        "backup_created_at": now_utc_iso(),
    }


def _append_aggregate_rows(aggregate_file: Path, concentrado_file: Path) -> int:
    rows_written = 0
    with aggregate_file.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        next(reader)
        with concentrado_file.open("a", encoding="utf-8", newline="") as target:
            if concentrado_file.stat().st_size > 0:
                with concentrado_file.open("rb") as existing:
                    existing.seek(-1, 2)
                    if existing.read(1) not in {b"\n", b"\r"}:
                        target.write("\n")
            writer = csv.writer(target, lineterminator="\n")
            for row in reader:
                writer.writerow(row)
                rows_written += 1
    return rows_written


def publish_imss_aggregate_from_plan(
    publish_plan: str | Path,
    *,
    concentrado_file: str | Path | None = None,
    output_dir: str | Path = DEFAULT_PUBLISH_OUTPUT_DIR,
    compare_output_dir: str | Path | None = None,
    compare_func: Callable = compare_raw_aggregate_with_concentrado,
) -> tuple[dict, Path]:
    """Publish one aggregate into concentrado using a guarded append-only flow."""
    _ensure_output_dir_allowed(output_dir)
    run_id = generate_publish_insert_run_id()
    manifest = _base_manifest(run_id=run_id, publish_plan_path=publish_plan, output_dir=output_dir)
    manifest_path: Path | None = None
    compare_dir = compare_output_dir if compare_output_dir is not None else output_dir

    try:
        plan_path = Path(publish_plan)
        plan = _load_publish_plan(plan_path)
        manifest["publish_plan_sha256"] = calculate_sha256(plan_path)
        period, aggregate_file, selected_concentrado = _validate_plan(plan, plan_path, concentrado_file)
        manifest["periodo_informacion"] = period
        manifest["aggregate_file"] = str(aggregate_file)
        manifest["aggregate_sha256"] = calculate_sha256(aggregate_file)
        manifest["aggregate_file_size_bytes"] = get_file_size_bytes(aggregate_file)
        manifest["concentrado_file"] = str(selected_concentrado)

        before_compare, before_compare_path = compare_func(
            period,
            aggregate_file=aggregate_file,
            concentrado_file=selected_concentrado,
            output_dir=compare_dir,
        )
        manifest["comparison_before"] = before_compare
        manifest["comparison_before_manifest_path"] = str(before_compare_path)
        before_status = before_compare.get("comparison_status")

        if before_status == "already_exists":
            manifest["concentrado_sha256_before"] = calculate_sha256(selected_concentrado)
            manifest["concentrado_file_size_before"] = get_file_size_bytes(selected_concentrado)
            scan = _scan_csv(selected_concentrado)
            manifest["concentrado_row_count_before"] = scan["row_count"]
            manifest["concentrado_row_count_after"] = scan["row_count"]
            manifest["periods_before"] = scan["periods"]
            manifest["periods_after"] = scan["periods"]
            _finish(
                manifest,
                status="success",
                action="no_op",
                validation_status="skipped",
                reason="period already exists after fresh comparison",
            )
            manifest_path = write_publish_manifest(manifest, output_dir)
            manifest["publish_manifest_path"] = str(manifest_path)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            return manifest, manifest_path

        if before_status == "failed":
            _finish(
                manifest,
                status="failed",
                action="block",
                validation_status="failed",
                reason="fresh comparison failed before append",
                error_message=before_compare.get("error_message"),
            )
            manifest_path = write_publish_manifest(manifest, output_dir)
            manifest["publish_manifest_path"] = str(manifest_path)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            return manifest, manifest_path

        if before_status != "new_period":
            _finish(
                manifest,
                status="blocked",
                action="block",
                validation_status="blocked",
                reason=f"fresh comparison blocked publication: {before_status}",
                error_message=before_compare.get("error_message"),
            )
            manifest_path = write_publish_manifest(manifest, output_dir)
            manifest["publish_manifest_path"] = str(manifest_path)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            return manifest, manifest_path

        expected_rows = int((plan.get("aggregate_summary") or {}).get("row_count", 0))
        append_validation = _validate_aggregate_for_append(
            aggregate_file=aggregate_file,
            concentrado_file=selected_concentrado,
            period=period,
            expected_rows=expected_rows,
        )
        manifest["columns_validated"] = True
        manifest["column_order_match"] = True
        manifest["aggregate_periods_detected"] = append_validation["aggregate_periods"]
        manifest["periods_before"] = append_validation["concentrado_periods"]
        manifest["concentrado_row_count_before"] = append_validation["concentrado_row_count"]
        manifest["concentrado_sha256_before"] = calculate_sha256(selected_concentrado)
        manifest["concentrado_file_size_before"] = get_file_size_bytes(selected_concentrado)

        backup = _create_backup(selected_concentrado, output_dir, run_id)
        manifest["backup_path"] = str(backup["backup_path"])
        manifest["backup_sha256"] = backup["backup_sha256"]
        manifest["backup_file_size_bytes"] = backup["backup_file_size_bytes"]
        manifest["backup_created_at"] = backup["backup_created_at"]
        manifest["rollback_manual_path"] = str(backup["backup_path"])

        try:
            rows_inserted = _append_aggregate_rows(aggregate_file, selected_concentrado)
        except Exception as exc:
            _finish(
                manifest,
                status="failed",
                action="failed",
                validation_status="failed",
                reason="append failed; backup available",
                error_message=str(exc),
            )
            manifest_path = write_publish_manifest(manifest, output_dir)
            manifest["publish_manifest_path"] = str(manifest_path)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            return manifest, manifest_path

        manifest["rows_inserted"] = rows_inserted
        manifest["writes_concentrado"] = True
        manifest["writes_data_processed"] = True

        after_compare, after_compare_path = compare_func(
            period,
            aggregate_file=aggregate_file,
            concentrado_file=selected_concentrado,
            output_dir=compare_dir,
        )
        manifest["comparison_after"] = after_compare
        manifest["comparison_after_manifest_path"] = str(after_compare_path)
        after_scan = _scan_csv(selected_concentrado)
        manifest["concentrado_row_count_after"] = after_scan["row_count"]
        manifest["periods_after"] = after_scan["periods"]
        manifest["concentrado_sha256_after"] = calculate_sha256(selected_concentrado)
        manifest["concentrado_file_size_after"] = get_file_size_bytes(selected_concentrado)

        validation_errors = []
        if after_compare.get("comparison_status") != "already_exists":
            validation_errors.append("post-publish comparison did not return already_exists")
        if rows_inserted != expected_rows:
            validation_errors.append("rows_inserted does not match expected aggregate row_count")
        if manifest["concentrado_row_count_before"] + rows_inserted != manifest["concentrado_row_count_after"]:
            validation_errors.append("row count after append does not match expected total")
        existing_summary_after = after_compare.get("existing_summary") or {}
        if existing_summary_after.get("row_count") != expected_rows:
            validation_errors.append("post-publish period row_count does not match aggregate")
        if manifest["concentrado_sha256_after"] == manifest["concentrado_sha256_before"]:
            validation_errors.append("concentrado sha256 did not change after append")
        if manifest["concentrado_file_size_after"] <= manifest["concentrado_file_size_before"]:
            validation_errors.append("concentrado file size did not increase after append")
        if not Path(manifest["backup_path"]).exists() or calculate_sha256(manifest["backup_path"]) != manifest["backup_sha256"]:
            validation_errors.append("backup is missing or hash changed")

        if validation_errors:
            _finish(
                manifest,
                status="failed_validation",
                action="inserted_validation_failed",
                validation_status="failed",
                reason="post-publish validation failed",
                error_message="; ".join(validation_errors),
            )
        else:
            _finish(
                manifest,
                status="success",
                action="inserted",
                validation_status="passed",
                reason="aggregate appended and validated successfully",
            )

        manifest_path = write_publish_manifest(manifest, output_dir)
        manifest["publish_manifest_path"] = str(manifest_path)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return manifest, manifest_path
    except PublishBlockedError as exc:
        _finish(
            manifest,
            status="blocked",
            action="block",
            validation_status="blocked",
            reason=str(exc),
            error_message=str(exc),
        )
        manifest_path = write_publish_manifest(manifest, output_dir)
        manifest["publish_manifest_path"] = str(manifest_path)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return manifest, manifest_path
    except Exception as exc:
        _finish(
            manifest,
            status="failed",
            action="block",
            validation_status="failed",
            reason=str(exc),
            error_message=str(exc),
        )
        manifest_path = write_publish_manifest(manifest, output_dir)
        manifest["publish_manifest_path"] = str(manifest_path)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return manifest, manifest_path
