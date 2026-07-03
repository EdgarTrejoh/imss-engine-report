import pandas as pd

from src.imss_engine.schema import (
    SECTOR_COLUMNS,
    ensure_optional_columns,
    get_missing_required_columns,
    validate_required_columns,
)


def test_sector_economico_3_is_not_part_of_schema():
    assert "sector_economico_3" not in SECTOR_COLUMNS
    assert SECTOR_COLUMNS == (
        "sector_economico_1",
        "sector_economico_2",
        "sector_economico_4",
    )


def test_validate_required_columns_reports_missing_metrics(load_fixture):
    df = load_fixture("imss_sample_actual.csv").drop(columns=["ta_sal"])
    result = validate_required_columns(df)
    assert result["valid"] is False
    assert get_missing_required_columns(df) == ["ta_sal"]


def test_ensure_optional_columns_creates_historical_dimensions_as_null(load_fixture):
    df = load_fixture("imss_sample_missing_ptpd.csv")
    out = ensure_optional_columns(df)
    assert "ptpd" in out.columns
    assert out["ptpd"].isna().all()
