"""Metric calculations for IMSS data."""

from __future__ import annotations

import numpy as np
import pandas as pd


def safe_divide(numerator, denominator):
    """Divide while returning NaN for zero or missing denominators."""
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    result = num / den
    return result.where(den.notna() & (den != 0), np.nan)


def calculate_sbc_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SBC only with documented *_sal denominators."""
    out = df.copy()
    out["sbc_total"] = safe_divide(out["masa_sal_ta"], out["ta_sal"])
    out["sbc_permanente_urbano"] = safe_divide(out["masa_sal_tpu"], out["tpu_sal"])
    out["sbc_permanente_campo"] = safe_divide(out["masa_sal_tpc"], out["tpc_sal"])
    out["sbc_eventual_urbano"] = safe_divide(out["masa_sal_teu"], out["teu_sal"])
    out["sbc_eventual_campo"] = safe_divide(out["masa_sal_tec"], out["tec_sal"])
    out["sbc_permanentes"] = safe_divide(
        out["masa_sal_tpu"] + out["masa_sal_tpc"],
        out["tpu_sal"] + out["tpc_sal"],
    )
    out["sbc_eventuales"] = safe_divide(
        out["masa_sal_teu"] + out["masa_sal_tec"],
        out["teu_sal"] + out["tec_sal"],
    )
    out["sbc_urbanos"] = safe_divide(
        out["masa_sal_tpu"] + out["masa_sal_teu"],
        out["tpu_sal"] + out["teu_sal"],
    )
    out["sbc_campo"] = safe_divide(
        out["masa_sal_tpc"] + out["masa_sal_tec"],
        out["tpc_sal"] + out["tec_sal"],
    )
    return out


def add_validation_differences(df: pd.DataFrame) -> pd.DataFrame:
    """Add non-failing validation differences for official total fields."""
    out = df.copy()
    out["diff_ta_componentes"] = out["ta"] - (
        out["tpu"] + out["tpc"] + out["teu"] + out["tec"]
    )
    out["diff_masa_sal_componentes"] = out["masa_sal_ta"] - (
        out["masa_sal_tpu"]
        + out["masa_sal_tpc"]
        + out["masa_sal_teu"]
        + out["masa_sal_tec"]
    )
    out["diff_asegurados_ta_no_trabajadores"] = out["asegurados"] - (
        out["ta"] + out["no_trabajadores"]
    )
    return out
