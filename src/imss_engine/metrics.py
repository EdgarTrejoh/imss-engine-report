"""Metric calculations for IMSS data."""

from __future__ import annotations

import numpy as np
import pandas as pd


SBC_METRIC_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "sbc_total": (("masa_sal_ta",), ("ta_sal",)),
    "sbc_permanente_urbano": (("masa_sal_tpu",), ("tpu_sal",)),
    "sbc_permanente_campo": (("masa_sal_tpc",), ("tpc_sal",)),
    "sbc_eventual_urbano": (("masa_sal_teu",), ("teu_sal",)),
    "sbc_eventual_campo": (("masa_sal_tec",), ("tec_sal",)),
    "sbc_permanentes": (("masa_sal_tpu", "masa_sal_tpc"), ("tpu_sal", "tpc_sal")),
    "sbc_eventuales": (("masa_sal_teu", "masa_sal_tec"), ("teu_sal", "tec_sal")),
    "sbc_urbanos": (("masa_sal_tpu", "masa_sal_teu"), ("tpu_sal", "teu_sal")),
    "sbc_campo": (("masa_sal_tpc", "masa_sal_tec"), ("tpc_sal", "tec_sal")),
}
DIFFERENCE_METRIC_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "diff_ta_componentes": (("ta",), ("tpu", "tpc", "teu", "tec")),
    "diff_masa_sal_componentes": (
        ("masa_sal_ta",),
        ("masa_sal_tpu", "masa_sal_tpc", "masa_sal_teu", "masa_sal_tec"),
    ),
    "diff_asegurados_ta_no_trabajadores": (("asegurados",), ("ta", "no_trabajadores")),
}


def _sum_columns(frame: pd.DataFrame, columns: tuple[str, ...]):
    result = frame[columns[0]]
    for column in columns[1:]:
        result = result + frame[column]
    return result


def safe_divide(numerator, denominator):
    """Divide while returning NaN for zero or missing denominators."""
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    result = num / den
    return result.where(den.notna() & (den != 0), np.nan)


def calculate_sbc_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SBC only with documented *_sal denominators."""
    out = df.copy()
    for output_column, (numerator_columns, denominator_columns) in SBC_METRIC_SPECS.items():
        out[output_column] = safe_divide(
            _sum_columns(out, numerator_columns),
            _sum_columns(out, denominator_columns),
        )
    return out


def add_validation_differences(df: pd.DataFrame) -> pd.DataFrame:
    """Add non-failing validation differences for official total fields."""
    out = df.copy()
    for output_column, (minuend_columns, subtrahend_columns) in DIFFERENCE_METRIC_SPECS.items():
        out[output_column] = _sum_columns(out, minuend_columns) - _sum_columns(
            out, subtrahend_columns
        )
    return out
