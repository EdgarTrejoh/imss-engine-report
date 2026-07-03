"""Schema definitions and validation helpers for IMSS asegurados data."""

from __future__ import annotations

from typing import Any

import pandas as pd


CRITICAL_METRIC_COLUMNS: tuple[str, ...] = (
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
)

EXPECTED_DIMENSION_COLUMNS: tuple[str, ...] = (
    "cve_delegacion",
    "cve_subdelegacion",
    "cve_entidad",
    "cve_municipio",
    "tamaño_patron",
    "sexo",
    "rango_edad",
    "rango_salarial",
    "rango_uma",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "ptpd",
)

OPTIONAL_HISTORICAL_COLUMNS: tuple[str, ...] = EXPECTED_DIMENSION_COLUMNS

SECTOR_COLUMNS: tuple[str, ...] = (
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
)


def get_missing_required_columns(df: pd.DataFrame) -> list[str]:
    """Return critical metric columns missing from a raw IMSS DataFrame."""
    return [col for col in CRITICAL_METRIC_COLUMNS if col not in df.columns]


def validate_required_columns(df: pd.DataFrame) -> dict[str, Any]:
    """Validate critical metric columns needed for approved calculations."""
    missing = get_missing_required_columns(df)
    return {
        "valid": not missing,
        "missing_required_columns": missing,
    }


def ensure_optional_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Create missing historical dimensions as null without inferring meaning."""
    out = df.copy()
    for col in OPTIONAL_HISTORICAL_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    return out
