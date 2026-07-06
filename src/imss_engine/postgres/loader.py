"""Insert-only PostgreSQL loader skeleton.

This module defines future loader contracts without reading large CSV files or
modifying a database. All operations are dry-run placeholders unless a future
implementation replaces them deliberately.
"""

from __future__ import annotations

import csv
import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PERIOD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_CSV_ENCODINGS = ("utf-8-sig", "latin1")
SOURCE_CSV_DELIMITERS = ("|", ",", ";", "\t")
EXPECTED_SOURCE_COLUMNS = (
    "periodo_informacion",
    "cve_delegacion",
    "cve_subdelegacion",
    "cve_entidad",
    "cve_municipio",
    "tamaño_patron",
    "sexo",
    "rango_edad",
    "rango_ingreso_vsm",
    "rango_ingreso_uma",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "ptpd",
)
PROFILE_DIMENSION_COLUMNS = (
    "periodo_informacion",
    "ptpd",
    "rango_ingreso_vsm",
    "rango_ingreso_uma",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "sexo",
)
PROFILE_NUMERIC_COLUMNS = (
    "ta",
    "ta_sal",
    "masa_sal_ta",
    "asegurados",
    "no_trabajadores",
)
DISTINCT_COUNT_LIMIT = 10000
SAMPLE_VALUES_LIMIT = 10
STAGING_INSERT_COLUMNS = (
    "run_id",
    "periodo_informacion",
    "cve_delegacion",
    "cve_subdelegacion",
    "cve_entidad",
    "cve_municipio",
    "tamaño_patron",
    "sexo",
    "rango_edad",
    "rango_ingreso_vsm",
    "rango_ingreso_uma",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "ptpd",
    "asegurados",
    "no_trabajadores",
    "ta",
    "ta_sal",
    "tpu",
    "tpc",
    "teu",
    "tec",
    "tpu_sal",
    "tpc_sal",
    "teu_sal",
    "tec_sal",
    "masa_sal_ta",
    "masa_sal_tpu",
    "masa_sal_tpc",
    "masa_sal_teu",
    "masa_sal_tec",
    "puestos_permanentes",
    "puestos_eventuales",
    "puestos_urbanos",
    "puestos_campo",
    "masa_sal_permanentes",
    "masa_sal_eventuales",
    "masa_sal_urbanos",
    "masa_sal_campo",
    "sbc_total",
    "sbc_permanentes",
    "sbc_eventuales",
    "sbc_urbanos",
    "sbc_campo",
    "period_fingerprint_hash",
    "source_url",
    "loaded_at",
    "created_at",
)
STAGING_NUMERIC_COLUMNS = {
    "asegurados",
    "no_trabajadores",
    "ta",
    "ta_sal",
    "tpu",
    "tpc",
    "teu",
    "tec",
    "tpu_sal",
    "tpc_sal",
    "teu_sal",
    "tec_sal",
    "masa_sal_ta",
    "masa_sal_tpu",
    "masa_sal_tpc",
    "masa_sal_teu",
    "masa_sal_tec",
    "puestos_permanentes",
    "puestos_eventuales",
    "puestos_urbanos",
    "puestos_campo",
    "masa_sal_permanentes",
    "masa_sal_eventuales",
    "masa_sal_urbanos",
    "masa_sal_campo",
    "sbc_total",
    "sbc_permanentes",
    "sbc_eventuales",
    "sbc_urbanos",
    "sbc_campo",
}
STAGING_SOURCE_ALIASES = {
    "tamaño_patron": ("tamaño_patron", "tamaÃ±o_patron"),
}


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


def _detect_delimiter(header_line: str) -> str:
    counts = {delimiter: header_line.count(delimiter) for delimiter in SOURCE_CSV_DELIMITERS}
    delimiter, count = max(counts.items(), key=lambda item: item[1])
    return delimiter if count > 0 else ","


def check_source_csv(source_path: str | Path, sample_rows: int = 5) -> dict:
    """Inspect a CSV source with bounded reads and no DataFrame loading."""
    path = Path(source_path)
    exists = path.exists()
    is_file = path.is_file() if exists else False
    if not exists:
        raise FileNotFoundError(f"source CSV does not exist: {path}")
    if not is_file:
        raise ValueError(f"source path is not a file: {path}")
    if sample_rows < 0:
        raise ValueError("sample_rows must be greater than or equal to 0")

    last_error: Exception | None = None
    for encoding in SOURCE_CSV_ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                header_line = file.readline()
                if not header_line:
                    delimiter = ","
                    header: list[str] = []
                    sample_rows_read = 0
                else:
                    delimiter = _detect_delimiter(header_line)
                    header = next(csv.reader([header_line], delimiter=delimiter))
                    sample_rows_read = 0
                    reader = csv.reader(file, delimiter=delimiter)
                    for _ in range(sample_rows):
                        try:
                            next(reader)
                        except StopIteration:
                            break
                        sample_rows_read += 1
            break
        except UnicodeDecodeError as error:
            last_error = error
            continue
    else:
        raise UnicodeDecodeError(
            "unknown",
            b"",
            0,
            1,
            f"Could not decode source CSV with supported encodings: {last_error}",
        )

    missing_expected_columns = [
        column for column in EXPECTED_SOURCE_COLUMNS if column not in set(header)
    ]
    return {
        "source_path": str(path),
        "exists": exists,
        "is_file": is_file,
        "file_size_bytes": path.stat().st_size,
        "sample_rows_requested": sample_rows,
        "sample_rows_read": sample_rows_read,
        "header": header,
        "column_count": len(header),
        "delimiter": delimiter,
        "encoding": encoding,
        "missing_expected_columns": missing_expected_columns,
        "reads_full_csv": False,
        "loads_dataframe": False,
    }


def _empty_dimension_profile() -> dict:
    return {
        "non_empty_count": 0,
        "empty_count": 0,
        "distinct_count_limited": 0,
        "sample_values": [],
    }


def _empty_numeric_profile() -> dict:
    return {
        "non_empty_count": 0,
        "empty_count": 0,
        "numeric_parse_errors": 0,
        "min": None,
        "max": None,
        "sum": 0.0,
    }


def profile_source_csv_streaming(source_path: str | Path, max_rows: int | None = 10000) -> dict:
    """Profile a CSV source row by row with bounded memory usage."""
    if max_rows is None:
        raise ValueError("max_rows must be a positive integer; unlimited profiling is not supported")
    if max_rows <= 0:
        raise ValueError("max_rows must be greater than 0")

    source_check = check_source_csv(source_path, sample_rows=0)
    path = Path(source_path)
    header = source_check["header"]
    header_set = set(header)
    delimiter = source_check["delimiter"]
    encoding = source_check["encoding"]

    dimension_profiles = {
        column: _empty_dimension_profile()
        for column in PROFILE_DIMENSION_COLUMNS
        if column in header_set
    }
    numeric_profiles = {
        column: _empty_numeric_profile()
        for column in PROFILE_NUMERIC_COLUMNS
        if column in header_set
    }
    distinct_values = {column: set() for column in dimension_profiles}
    missing_profile_columns = [
        column
        for column in (*PROFILE_DIMENSION_COLUMNS, *PROFILE_NUMERIC_COLUMNS)
        if column not in header_set
    ]

    rows_profiled = 0
    with path.open("r", encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        for row in reader:
            if rows_profiled >= max_rows:
                break
            rows_profiled += 1

            for column, profile in dimension_profiles.items():
                value = (row.get(column) or "").strip()
                if value:
                    profile["non_empty_count"] += 1
                    if len(distinct_values[column]) < DISTINCT_COUNT_LIMIT:
                        distinct_values[column].add(value)
                    if value not in profile["sample_values"] and len(profile["sample_values"]) < SAMPLE_VALUES_LIMIT:
                        profile["sample_values"].append(value)
                else:
                    profile["empty_count"] += 1

            for column, profile in numeric_profiles.items():
                raw_value = (row.get(column) or "").strip()
                if not raw_value:
                    profile["empty_count"] += 1
                    continue
                profile["non_empty_count"] += 1
                try:
                    value = float(raw_value)
                except ValueError:
                    profile["numeric_parse_errors"] += 1
                    continue
                profile["sum"] += value
                profile["min"] = value if profile["min"] is None else min(profile["min"], value)
                profile["max"] = value if profile["max"] is None else max(profile["max"], value)

    for column, values in distinct_values.items():
        dimension_profiles[column]["distinct_count_limited"] = len(values)

    return {
        "source_path": str(path),
        "file_size_bytes": source_check["file_size_bytes"],
        "encoding": encoding,
        "delimiter": delimiter,
        "column_count": source_check["column_count"],
        "rows_profiled": rows_profiled,
        "max_rows": max_rows,
        "reached_max_rows": rows_profiled >= max_rows,
        "reads_full_csv": False,
        "loads_dataframe": False,
        "opens_database_connection": False,
        "missing_expected_columns": source_check["missing_expected_columns"],
        "missing_profile_columns": missing_profile_columns,
        "has_ptpd": "ptpd" in header_set,
        "has_rango_ingreso_vsm": "rango_ingreso_vsm" in header_set,
        "has_rango_ingreso_uma": "rango_ingreso_uma" in header_set,
        "has_sector_economico_4": "sector_economico_4" in header_set,
        "has_ta_sal": "ta_sal" in header_set,
        "has_masa_sal_ta": "masa_sal_ta" in header_set,
        "dimension_profiles": dimension_profiles,
        "numeric_profiles": numeric_profiles,
    }


def summarize_source_csv_periods_streaming(
    source_path: str | Path,
    max_rows: int | None = None,
) -> dict:
    """Summarize source CSV row counts by period with streaming reads."""
    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be greater than 0 when provided")

    source_check = check_source_csv(source_path, sample_rows=0)
    path = Path(source_path)
    header = source_check["header"]
    if "periodo_informacion" not in set(header):
        raise ValueError("source CSV must include periodo_informacion")

    delimiter = source_check["delimiter"]
    encoding = source_check["encoding"]
    rows_by_period: dict[str, int] = {}
    empty_period_rows = 0
    rows_scanned = 0
    stopped_by_limit = False

    with path.open("r", encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        for row in reader:
            rows_scanned += 1
            period = (row.get("periodo_informacion") or "").strip()
            if not period:
                empty_period_rows += 1
            else:
                rows_by_period[period] = rows_by_period.get(period, 0) + 1
            if max_rows is not None and rows_scanned >= max_rows:
                stopped_by_limit = True
                break

    sorted_periods = sorted(rows_by_period)
    return {
        "source_path": str(path),
        "file_size_bytes": source_check["file_size_bytes"],
        "encoding": encoding,
        "delimiter": delimiter,
        "column_count": source_check["column_count"],
        "rows_scanned": rows_scanned,
        "max_rows": max_rows,
        "reached_max_rows": stopped_by_limit,
        "reads_full_csv": max_rows is None,
        "loads_dataframe": False,
        "opens_database_connection": False,
        "empty_period_rows": empty_period_rows,
        "distinct_period_count": len(rows_by_period),
        "sample_periods": sorted_periods[:20],
        "min_period": sorted_periods[0] if sorted_periods else None,
        "max_period": sorted_periods[-1] if sorted_periods else None,
        "rows_by_period": {period: rows_by_period[period] for period in sorted_periods},
    }


def _row_value(row: dict, column: str):
    for source_column in STAGING_SOURCE_ALIASES.get(column, (column,)):
        if source_column in row:
            value = (row.get(source_column) or "").strip()
            return value or None
    return None


def _staging_row_values(row: dict, run_id: str) -> tuple:
    values = []
    for column in STAGING_INSERT_COLUMNS:
        if column == "run_id":
            values.append(run_id)
            continue
        value = _row_value(row, column)
        if column in STAGING_NUMERIC_COLUMNS and value is not None:
            value = value.replace(",", "")
        values.append(value)
    return tuple(values)


def _staging_count(cursor, period: str) -> int:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM imss.imss_staging_asegurados
        WHERE periodo_informacion = %s;
        """,
        (period,),
    )
    return int(cursor.fetchone()[0])


def load_staging_insert_only(
    connection,
    source_path: str | Path,
    period: str,
    batch_size: int = 5000,
    max_rows: int | None = None,
    run_id: str | None = None,
) -> dict:
    """Load one period from a CSV source into staging with insert-only semantics."""
    validate_period(period)
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be greater than 0 when provided")

    source_check = check_source_csv(source_path, sample_rows=0)
    header = source_check["header"]
    if "periodo_informacion" not in set(header):
        raise ValueError("source CSV must include periodo_informacion")

    path = Path(source_path)
    encoding = source_check["encoding"]
    delimiter = source_check["delimiter"]
    effective_run_id = run_id or f"staging_load_{period}"
    committed = False
    rolled_back = False

    try:
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
            staging_row_count_before = _staging_count(cursor, period)

            if not period_control_exists:
                return {
                    "periodo_informacion": period,
                    "source_path": str(path),
                    "file_size_bytes": source_check["file_size_bytes"],
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "batch_size": batch_size,
                    "max_rows": max_rows,
                    "rows_scanned": 0,
                    "rows_matched_period": 0,
                    "rows_inserted_staging": 0,
                    "staging_row_count_before": staging_row_count_before,
                    "staging_row_count_after": staging_row_count_before,
                    "period_control_exists": False,
                    "inserted": False,
                    "reason": "missing_period_control",
                    "committed": False,
                    "rolled_back": False,
                    "touches_staging_table": False,
                    "touches_final_table": False,
                    "writes_period_control_only": False,
                    "writes_run_manifest_only": False,
                    "opens_database_connection": True,
                    "reads_source_csv": False,
                    "reads_full_csv": False,
                    "loads_dataframe": False,
                }

            if staging_row_count_before > 0:
                return {
                    "periodo_informacion": period,
                    "source_path": str(path),
                    "file_size_bytes": source_check["file_size_bytes"],
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "batch_size": batch_size,
                    "max_rows": max_rows,
                    "rows_scanned": 0,
                    "rows_matched_period": 0,
                    "rows_inserted_staging": 0,
                    "staging_row_count_before": staging_row_count_before,
                    "staging_row_count_after": staging_row_count_before,
                    "period_control_exists": True,
                    "inserted": False,
                    "reason": "staging_period_already_exists",
                    "committed": False,
                    "rolled_back": False,
                    "touches_staging_table": False,
                    "touches_final_table": False,
                    "writes_period_control_only": False,
                    "writes_run_manifest_only": False,
                    "opens_database_connection": True,
                    "reads_source_csv": False,
                    "reads_full_csv": False,
                    "loads_dataframe": False,
                }

            quoted_columns = [
                f'"{column}"' if column == "tamaño_patron" else column
                for column in STAGING_INSERT_COLUMNS
            ]
            placeholders = ", ".join(["%s"] * len(STAGING_INSERT_COLUMNS))
            insert_sql = (
                f"INSERT INTO imss.imss_staging_asegurados "
                f"({', '.join(quoted_columns)}) VALUES ({placeholders});"
            )

            rows_scanned = 0
            rows_matched_period = 0
            rows_inserted_staging = 0
            batch = []
            with path.open("r", encoding=encoding, newline="") as file:
                reader = csv.DictReader(file, delimiter=delimiter)
                for row in reader:
                    if max_rows is not None and rows_scanned >= max_rows:
                        break
                    rows_scanned += 1
                    if (row.get("periodo_informacion") or "").strip() != period:
                        continue
                    rows_matched_period += 1
                    batch.append(_staging_row_values(row, effective_run_id))
                    if len(batch) >= batch_size:
                        cursor.executemany(insert_sql, batch)
                        rows_inserted_staging += len(batch)
                        batch = []

                if batch:
                    cursor.executemany(insert_sql, batch)
                    rows_inserted_staging += len(batch)

            staging_row_count_after = _staging_count(cursor, period)
        connection.commit()
        committed = True
    except Exception:
        connection.rollback()
        rolled_back = True
        raise

    return {
        "periodo_informacion": period,
        "source_path": str(path),
        "file_size_bytes": source_check["file_size_bytes"],
        "encoding": encoding,
        "delimiter": delimiter,
        "batch_size": batch_size,
        "max_rows": max_rows,
        "rows_scanned": rows_scanned,
        "rows_matched_period": rows_matched_period,
        "rows_inserted_staging": rows_inserted_staging,
        "staging_row_count_before": staging_row_count_before,
        "staging_row_count_after": staging_row_count_after,
        "period_control_exists": period_control_exists,
        "inserted": rows_inserted_staging > 0,
        "run_id": effective_run_id,
        "committed": committed,
        "rolled_back": rolled_back,
        "touches_staging_table": True,
        "touches_final_table": False,
        "writes_period_control_only": False,
        "writes_run_manifest_only": False,
        "opens_database_connection": True,
        "reads_source_csv": True,
        "reads_full_csv": max_rows is None,
        "loads_dataframe": False,
    }


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
