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
RAW_DIMENSION_DTYPES: dict[str, str] = {
    "cve_delegacion": "string",
    "cve_subdelegacion": "string",
    "cve_entidad": "string",
    "cve_municipio": "string",
    "sector_economico_1": "string",
    "sector_economico_2": "string",
    "sector_economico_4": "string",
    "tamaño_patron": "string",
    "sexo": "string",
    "rango_edad": "string",
    "rango_salarial": "string",
    "rango_uma": "string",
    "ptpd": "string",
}
INTEGER_CODE_COLUMNS: tuple[str, ...] = (
    "cve_delegacion",
    "cve_subdelegacion",
    "cve_entidad",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
)
_INTEGER_DECIMAL_RE = re.compile(r"^(-?\d+)\.0+$")
_POSITIVE_INTEGER_DECIMAL_RE = re.compile(r"^([0-9]+)\.0$")


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


def normalize_raw_integer_codes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Remove a defensive trailing .0 only from approved integer code dimensions."""
    out = df.copy()
    counts: dict[str, int] = {}
    for column in INTEGER_CODE_COLUMNS:
        if column not in out.columns:
            counts[column] = 0
            continue
        values = out[column].astype("string")
        matches = values.str.match(_POSITIVE_INTEGER_DECIMAL_RE, na=False)
        counts[column] = int(matches.sum())
        out[column] = values.str.replace(
            _POSITIVE_INTEGER_DECIMAL_RE,
            lambda match: match.group(1),
            regex=True,
        )
    return out, counts
