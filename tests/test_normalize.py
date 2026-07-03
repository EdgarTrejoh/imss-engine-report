import pandas as pd

from src.imss_engine.normalize import (
    ensure_ptpd_column,
    ensure_sector_columns,
    normalize_dimensions,
    normalize_income_ranges,
)


def test_income_ranges_are_not_renamed_or_mixed(load_fixture):
    df = load_fixture("imss_sample_actual.csv")
    out = normalize_income_ranges(df)
    assert "rango_salarial" in out.columns
    assert "rango_uma" in out.columns
    assert out.loc[0, "rango_ingreso_vsm"] == "W1"
    assert out.loc[0, "rango_ingreso_uma"] == "U1"


def test_missing_rango_uma_creates_null_uma_income_range(load_fixture):
    df = load_fixture("imss_sample_legacy_vsm_only.csv")
    out = normalize_dimensions(df)
    assert out.loc[0, "rango_ingreso_vsm"] == "W2"
    assert pd.isna(out.loc[0, "rango_ingreso_uma"])


def test_ptpd_missing_is_null_not_zero(load_fixture):
    df = load_fixture("imss_sample_missing_ptpd.csv")
    out = ensure_ptpd_column(df)
    assert out["ptpd"].isna().all()
    assert not (out["ptpd"] == 0).any()


def test_sectors_preserve_layout_without_sector_3(load_fixture):
    df = load_fixture("imss_sample_sector_layout.csv")
    out = ensure_sector_columns(df)
    assert "sector_economico_3" not in out.columns
    assert out.loc[0, "sector_economico_1"] == "5"
    assert out.loc[0, "sector_economico_2"] == "05"
    assert out.loc[0, "sector_economico_4"] == "0501"
    assert out.loc[0, "sector_economico_2_2pos"] == "05"
    assert out.loc[0, "sector_economico_4_4_pos"] == "0501"
