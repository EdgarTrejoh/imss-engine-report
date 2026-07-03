"""Normalization helpers for IMSS raw data."""

from __future__ import annotations

import pandas as pd

from .schema import SECTOR_COLUMNS, ensure_optional_columns


def _as_string_preserving_nulls(series: pd.Series) -> pd.Series:
    return series.astype("string").replace({"": pd.NA})


def normalize_income_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """Keep VSM and UMA ranges separate; never rename one into the other."""
    out = df.copy()
    out["rango_ingreso_vsm"] = (
        _as_string_preserving_nulls(out["rango_salarial"])
        if "rango_salarial" in out.columns
        else pd.NA
    )
    out["rango_ingreso_uma"] = (
        _as_string_preserving_nulls(out["rango_uma"])
        if "rango_uma" in out.columns
        else pd.NA
    )
    return out


def ensure_sector_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Preserve documented sector levels 1, 2 and 4 as strings."""
    out = df.copy()
    for col in SECTOR_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
        out[col] = _as_string_preserving_nulls(out[col])

    out["sector_economico_2_2pos"] = out["sector_economico_2"].str.slice(0, 2)
    out["sector_economico_4_4_pos"] = out["sector_economico_4"].str.slice(0, 4)
    return out


def ensure_ptpd_column(df: pd.DataFrame) -> pd.DataFrame:
    """Create ptpd as null when absent; do not assume historical zeros."""
    out = df.copy()
    if "ptpd" not in out.columns:
        out["ptpd"] = pd.NA
    else:
        out["ptpd"] = _as_string_preserving_nulls(out["ptpd"])
    return out


def normalize_dimensions(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize documented dimensions without imputing business meaning."""
    out = ensure_optional_columns(df)
    dimension_cols = (
        "periodo_informacion",
        "cve_delegacion",
        "cve_subdelegacion",
        "cve_entidad",
        "cve_municipio",
        "tamaño_patron",
        "sexo",
        "rango_edad",
    )
    for col in dimension_cols:
        if col in out.columns:
            out[col] = _as_string_preserving_nulls(out[col])
    out = normalize_income_ranges(out)
    out = ensure_sector_columns(out)
    out = ensure_ptpd_column(out)
    return out
