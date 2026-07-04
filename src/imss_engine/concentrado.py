"""Insert-only IMSS concentrado workflow helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from .aggregate import get_group_columns
from .light_audit import audit_light_period
from .schema import CRITICAL_METRIC_COLUMNS


PERIOD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

PERIOD_STATUSES = {
    "success_loaded",
    "already_exists",
    "conflict_existing_period_row_count",
    "conflict_existing_period_hash",
    "failed_download",
    "failed_processing",
    "failed_audit",
    "skipped",
}

RUN_STATUSES = {
    "success",
    "success_no_changes",
    "completed_with_warnings",
    "failed",
}


@dataclass(frozen=True)
class PeriodCandidate:
    periodo_informacion: str
    source_url: str
    dataframe: pd.DataFrame
    period_fingerprint_hash: str
    row_count: int


@dataclass(frozen=True)
class PeriodResult:
    periodo_informacion: str
    source_url: str
    status: str
    rows_processed: int | None = None
    rows_existing_in_concentrado: int | None = None
    rows_loaded: int = 0
    period_fingerprint_hash: str | None = None
    audit_status: str | None = None
    error: str | None = None

    def to_manifest(self) -> dict:
        return asdict(self)


def validate_period_string(period: str, field_name: str) -> str:
    if not isinstance(period, str) or not PERIOD_RE.match(period):
        raise ValueError(f"{field_name} debe ser un string YYYY-MM-DD")
    return period


def resolve_configured_periods(etl_config: dict) -> tuple[str, list[str]]:
    """Resolve new mode-based configuration into an ordered period list."""
    mode = etl_config.get("mode")
    legacy_months = etl_config.get("meses")
    if mode in {"mes_consulta", "periodo_consulta"} and legacy_months:
        raise ValueError(
            "etl.meses es legacy y debe estar vacio cuando etl.mode esta activo. "
            "Usa etl.mes_consulta o etl.periodo_consulta.meses."
        )

    if mode == "mes_consulta":
        period = validate_period_string(etl_config.get("mes_consulta"), "etl.mes_consulta")
        return mode, [period]

    if mode == "periodo_consulta":
        months = etl_config.get("periodo_consulta", {}).get("meses")
        if not isinstance(months, list) or not months:
            raise ValueError("etl.periodo_consulta.meses debe ser una lista explicita no vacia")
        validated = [
            validate_period_string(period, f"etl.periodo_consulta.meses[{index}]")
            for index, period in enumerate(months)
        ]
        duplicates = sorted({period for period in validated if validated.count(period) > 1})
        if duplicates:
            raise ValueError(f"etl.periodo_consulta.meses contiene duplicados: {', '.join(duplicates)}")
        return mode, validated

    if mode is None and etl_config.get("meses"):
        legacy_months = etl_config["meses"]
        if not isinstance(legacy_months, list) or not legacy_months:
            raise ValueError("etl.meses legacy debe ser una lista no vacia")
        return "legacy_meses", [validate_period_string(period, "etl.meses") for period in legacy_months]

    raise ValueError("etl.mode debe ser 'mes_consulta' o 'periodo_consulta'")


def build_period_urls(base_url: str, periods: Iterable[str]) -> list[tuple[str, str]]:
    return [(period, base_url.format(period)) for period in periods]


def _json_number(value) -> int | float | None:
    if pd.isna(value):
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def period_fingerprint_summary(df: pd.DataFrame, period: str) -> dict:
    """Build a stable, low-cost functional summary for one period."""
    period_df = df[df["periodo_informacion"].astype("string") == period].copy()
    numeric = {}
    for column in (
        "asegurados",
        "no_trabajadores",
        "ta",
        "ta_sal",
        "masa_sal_ta",
        "tpu",
        "tpc",
        "teu",
        "tec",
    ):
        numeric[f"sum_{column}"] = _json_number(pd.to_numeric(period_df[column], errors="coerce").sum())

    group_columns = [column for column in get_group_columns() if column in period_df.columns]
    distinct_keys = int(period_df[group_columns].drop_duplicates().shape[0]) if group_columns else None

    return {
        "periodo_informacion": period,
        "row_count": int(len(period_df)),
        **numeric,
        "distinct_analytic_keys": distinct_keys,
    }


def period_fingerprint_hash(summary: dict) -> str:
    payload = json.dumps(summary, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def calculate_period_fingerprint(df: pd.DataFrame, period: str) -> tuple[dict, str]:
    summary = period_fingerprint_summary(df, period)
    return summary, period_fingerprint_hash(summary)


def make_candidate(df: pd.DataFrame, period: str, source_url: str) -> PeriodCandidate:
    period_df = df[df["periodo_informacion"].astype("string") == period].copy()
    _, fingerprint = calculate_period_fingerprint(period_df, period)
    return PeriodCandidate(
        periodo_informacion=period,
        source_url=source_url,
        dataframe=period_df,
        period_fingerprint_hash=fingerprint,
        row_count=len(period_df),
    )


def read_concentrado(path: str | Path) -> pd.DataFrame:
    concentrado = Path(path)
    if not concentrado.exists():
        return pd.DataFrame()
    return pd.read_csv(concentrado, dtype=str, keep_default_na=False)


def compare_candidate_with_existing(
    candidate: PeriodCandidate,
    existing_df: pd.DataFrame,
) -> PeriodResult | None:
    if existing_df.empty or "periodo_informacion" not in existing_df.columns:
        return None

    existing_period = existing_df[
        existing_df["periodo_informacion"].astype("string") == candidate.periodo_informacion
    ].copy()
    if existing_period.empty:
        return None

    existing_rows = len(existing_period)
    if existing_rows != candidate.row_count:
        return PeriodResult(
            periodo_informacion=candidate.periodo_informacion,
            source_url=candidate.source_url,
            status="conflict_existing_period_row_count",
            rows_processed=candidate.row_count,
            rows_existing_in_concentrado=existing_rows,
            rows_loaded=0,
            period_fingerprint_hash=candidate.period_fingerprint_hash,
            audit_status="success",
        )

    _, existing_hash = calculate_period_fingerprint(existing_period, candidate.periodo_informacion)
    if existing_hash != candidate.period_fingerprint_hash:
        return PeriodResult(
            periodo_informacion=candidate.periodo_informacion,
            source_url=candidate.source_url,
            status="conflict_existing_period_hash",
            rows_processed=candidate.row_count,
            rows_existing_in_concentrado=existing_rows,
            rows_loaded=0,
            period_fingerprint_hash=candidate.period_fingerprint_hash,
            audit_status="success",
        )

    return PeriodResult(
        periodo_informacion=candidate.periodo_informacion,
        source_url=candidate.source_url,
        status="already_exists",
        rows_processed=candidate.row_count,
        rows_existing_in_concentrado=existing_rows,
        rows_loaded=0,
        period_fingerprint_hash=candidate.period_fingerprint_hash,
        audit_status="success",
    )


def classify_run_status(results: list[PeriodResult]) -> str:
    loaded = [result for result in results if result.status == "success_loaded"]
    unchanged = [result for result in results if result.status == "already_exists"]
    warnings = [
        result
        for result in results
        if result.status not in {"success_loaded", "already_exists"}
    ]
    if loaded and not warnings and not unchanged:
        return "success"
    if not loaded and unchanged and not warnings:
        return "success_no_changes"
    if loaded or unchanged:
        return "completed_with_warnings" if warnings else "success"
    return "failed"


def publish_concentrado_insert_only(
    concentrado_file: str | Path,
    candidates: list[PeriodCandidate],
    *,
    replace_func: Callable[[Path, Path], None] | None = None,
) -> tuple[list[PeriodResult], dict]:
    """Insert only non-existing periods into the official concentrado CSV."""
    concentrado = Path(concentrado_file)
    existing_df = read_concentrado(concentrado)
    rows_before = 0 if existing_df.empty else len(existing_df)
    exists_before = concentrado.exists()
    results: list[PeriodResult] = []
    to_load: list[pd.DataFrame] = []

    for candidate in candidates:
        audit = audit_light_period(
            candidate.dataframe,
            candidate.periodo_informacion,
            candidate.period_fingerprint_hash,
        )
        if not audit.ok:
            results.append(
                PeriodResult(
                    periodo_informacion=candidate.periodo_informacion,
                    source_url=candidate.source_url,
                    status="failed_audit",
                    rows_processed=candidate.row_count,
                    period_fingerprint_hash=candidate.period_fingerprint_hash,
                    audit_status=audit.status,
                    error=";".join(audit.errors),
                )
            )
            continue

        existing_result = compare_candidate_with_existing(candidate, existing_df)
        if existing_result is not None:
            results.append(existing_result)
            continue

        to_load.append(candidate.dataframe)
        results.append(
            PeriodResult(
                periodo_informacion=candidate.periodo_informacion,
                source_url=candidate.source_url,
                status="success_loaded",
                rows_processed=candidate.row_count,
                rows_existing_in_concentrado=0,
                rows_loaded=candidate.row_count,
                period_fingerprint_hash=candidate.period_fingerprint_hash,
                audit_status="success",
            )
        )

    if to_load:
        final_df = pd.concat([existing_df, *to_load], ignore_index=True) if not existing_df.empty else pd.concat(to_load, ignore_index=True)
        tmp = concentrado.with_suffix(concentrado.suffix + ".tmp")
        concentrado.parent.mkdir(parents=True, exist_ok=True)
        final_df.to_csv(tmp, index=False, encoding="utf-8-sig")
        try:
            (replace_func or os.replace)(tmp, concentrado)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise
    rows_after = len(read_concentrado(concentrado)) if concentrado.exists() else rows_before
    summary = {
        "concentrado_file": str(concentrado),
        "concentrado_exists_before": exists_before,
        "concentrado_rows_before": rows_before,
        "concentrado_rows_after": rows_after,
        "periods_loaded": [r.periodo_informacion for r in results if r.status == "success_loaded"],
        "periods_existing": [r.periodo_informacion for r in results if r.status == "already_exists"],
        "periods_conflict": [
            r.periodo_informacion
            for r in results
            if r.status in {"conflict_existing_period_row_count", "conflict_existing_period_hash"}
        ],
        "periods_failed": [
            r.periodo_informacion
            for r in results
            if r.status.startswith("failed_")
        ],
        "rows_loaded": sum(r.rows_loaded for r in results),
        "rows_not_loaded": sum((r.rows_processed or 0) - r.rows_loaded for r in results),
        "status": classify_run_status(results),
    }
    return results, summary
