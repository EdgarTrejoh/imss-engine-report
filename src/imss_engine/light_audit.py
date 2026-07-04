"""Lightweight period audit for the IMSS concentrado workflow."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .aggregate import get_group_columns
from .schema import CRITICAL_METRIC_COLUMNS


REQUIRED_LIGHT_AUDIT_COLUMNS: tuple[str, ...] = (
    "periodo_informacion",
    *get_group_columns(),
    *CRITICAL_METRIC_COLUMNS,
    "rango_ingreso_vsm",
    "rango_ingreso_uma",
    "ptpd",
)


@dataclass(frozen=True)
class LightAuditResult:
    status: str
    errors: list[str]
    period_fingerprint_hash: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"


def audit_light_period(
    df: pd.DataFrame,
    expected_period: str,
    fingerprint_hash: str | None = None,
) -> LightAuditResult:
    """Run local, cheap checks over one aggregated IMSS period."""
    errors: list[str] = []

    if df.empty:
        errors.append("empty_dataframe")
        return LightAuditResult("failed", errors, fingerprint_hash)

    missing = [column for column in REQUIRED_LIGHT_AUDIT_COLUMNS if column not in df.columns]
    if missing:
        errors.append(f"missing_columns:{','.join(missing)}")

    if "sector_economico_3" in df.columns:
        errors.append("forbidden_column:sector_economico_3")

    if "periodo_informacion" in df.columns:
        periods = set(df["periodo_informacion"].astype("string").dropna().unique())
        if periods != {expected_period}:
            errors.append(f"unexpected_periods:{','.join(sorted(periods))}")

    group_columns = get_group_columns()
    present_group_columns = [column for column in group_columns if column in df.columns]
    if len(present_group_columns) == len(group_columns):
        duplicate_count = int(df.duplicated(subset=group_columns, keep=False).sum())
        if duplicate_count:
            errors.append(f"duplicate_analytic_keys:{duplicate_count}")

    sbc_columns = [column for column in df.columns if column.startswith("sbc_")]
    for column in sbc_columns:
        values = pd.to_numeric(df[column], errors="coerce")
        if np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).any():
            errors.append(f"infinite_sbc:{column}")

    return LightAuditResult("failed" if errors else "success", errors, fingerprint_hash)
