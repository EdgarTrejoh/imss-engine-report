import numpy as np
import pandas as pd

from src.imss_engine.metrics import (
    add_validation_differences,
    calculate_sbc_metrics,
    safe_divide,
)
from src.imss_engine.transform import convert_numeric_columns


def test_safe_divide_returns_nan_for_zero_denominator():
    result = safe_divide(pd.Series([10]), pd.Series([0]))
    assert np.isnan(result.iloc[0])


def test_sbc_uses_sal_denominators_not_ta(load_fixture):
    df = convert_numeric_columns(load_fixture("imss_sample_actual.csv"))
    out = calculate_sbc_metrics(df)
    assert out.loc[0, "sbc_total"] == 100
    assert out.loc[0, "sbc_permanentes"] == 100
    assert out.loc[0, "sbc_eventuales"] == 100
    assert out.loc[0, "sbc_total"] != out.loc[0, "masa_sal_ta"] / out.loc[0, "ta"]


def test_sbc_zero_denominators_are_nan(load_fixture):
    df = convert_numeric_columns(load_fixture("imss_sample_zero_denominator.csv"))
    out = calculate_sbc_metrics(df)
    assert np.isnan(out.loc[0, "sbc_total"])
    assert np.isnan(out.loc[0, "sbc_permanentes"])
    assert np.isnan(out.loc[0, "sbc_eventuales"])


def test_validation_differences_are_warnings_not_replacements(load_fixture):
    df = convert_numeric_columns(load_fixture("imss_sample_actual.csv"))
    out = add_validation_differences(df)
    assert out.loc[0, "diff_ta_componentes"] == 0
    assert out.loc[0, "diff_masa_sal_componentes"] == 0
    assert out.loc[0, "diff_asegurados_ta_no_trabajadores"] == 0
