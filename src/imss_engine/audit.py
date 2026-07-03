"""Audit helpers for IMSS outputs."""

from __future__ import annotations

import pandas as pd


def normalizar_serie(serie: pd.Series) -> pd.Series:
    """Normalize text values for audit comparisons."""
    return (
        serie.astype("string")
        .str.strip()
        .str.upper()
        .replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
    )
