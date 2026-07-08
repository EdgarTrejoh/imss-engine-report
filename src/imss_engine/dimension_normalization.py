"""Compatibility normalization for IMSS analytical dimension values."""

from __future__ import annotations

import re

import pandas as pd


BLANK_TO_NA_COLUMNS: tuple[str, ...] = (
    "cve_municipio",
    "tamaño_patron",
    "rango_edad",
    "rango_ingreso_vsm",
)
SECTOR_DECIMAL_TO_INTEGER_COLUMNS: tuple[str, ...] = (
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
)
_INTEGER_DECIMAL_RE = re.compile(r"^(-?\d+)\.0+$")


def _normalize_blank_to_na(value) -> str:
    if pd.isna(value):
        return "NA"
    text = str(value).strip()
    return "NA" if text == "" else text


def _normalize_sector_code(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text in {"", "NA"}:
        return text
    match = _INTEGER_DECIMAL_RE.match(text)
    if match:
        return match.group(1)
    return text


def normalize_imss_dimension_values(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with selected IMSS dimension values normalized for concentrado compatibility."""
    out = df.copy()
    for column in BLANK_TO_NA_COLUMNS:
        if column in out.columns:
            out[column] = out[column].map(_normalize_blank_to_na)
    for column in SECTOR_DECIMAL_TO_INTEGER_COLUMNS:
        if column in out.columns:
            out[column] = out[column].map(_normalize_sector_code)
    return out
