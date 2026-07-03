import pandas as pd

from src.imss_engine.aggregate import aggregate_imss_chunk, get_group_columns


def test_group_columns_exclude_timestamp_and_include_sector_layout():
    group_cols = get_group_columns()
    assert "timestamp" not in group_cols
    assert "sector_economico_1" in group_cols
    assert "sector_economico_2" in group_cols
    assert "sector_economico_4" in group_cols
    assert "sector_economico_3" not in group_cols
    assert "ptpd" in group_cols


def test_aggregate_preserves_metrics_and_calculates_sbc(load_fixture):
    df = load_fixture("imss_sample_actual.csv")
    df["periodo_informacion"] = "2021-09-30"
    out = aggregate_imss_chunk(df)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["asegurados"] == 18
    assert row["no_trabajadores"] == 3
    assert row["ta"] == 15
    assert row["puestos_permanentes"] == 8
    assert row["puestos_eventuales"] == 7
    assert row["masa_sal_permanentes"] == 800
    assert row["masa_sal_eventuales"] == 400
    assert row["sbc_total"] == 100
    assert "sector_economico_3" not in out.columns


def test_aggregate_missing_ptpd_keeps_null_group(load_fixture):
    df = load_fixture("imss_sample_missing_ptpd.csv")
    df["periodo_informacion"] = "2021-09-30"
    out = aggregate_imss_chunk(df)
    assert "ptpd" in out.columns
    assert pd.isna(out.loc[0, "ptpd"])
