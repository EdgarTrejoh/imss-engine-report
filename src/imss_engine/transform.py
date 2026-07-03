"""Transformation layer for IMSS data."""

from __future__ import annotations

import pandas as pd

from .schema import CRITICAL_METRIC_COLUMNS


def convert_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert approved metric columns to numeric without touching dimensions."""
    out = df.copy()
    for col in CRITICAL_METRIC_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def add_worker_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add approved worker-position derived metrics."""
    out = df.copy()
    out["puestos_permanentes"] = out["tpu"] + out["tpc"]
    out["puestos_eventuales"] = out["teu"] + out["tec"]
    out["puestos_urbanos"] = out["tpu"] + out["teu"]
    out["puestos_campo"] = out["tpc"] + out["tec"]
    return out


def add_salary_mass_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add approved salary-mass derived metrics."""
    out = df.copy()
    out["masa_sal_permanentes"] = out["masa_sal_tpu"] + out["masa_sal_tpc"]
    out["masa_sal_eventuales"] = out["masa_sal_teu"] + out["masa_sal_tec"]
    out["masa_sal_urbanos"] = out["masa_sal_tpu"] + out["masa_sal_teu"]
    out["masa_sal_campo"] = out["masa_sal_tpc"] + out["masa_sal_tec"]
    return out
