import pandas as pd

from src.imss_engine.aggregate import aggregate_imss_chunk
from src.imss_engine.light_audit import audit_light_period


def _aggregated(load_fixture, period="2026-01-31"):
    df = load_fixture("imss_sample_actual.csv")
    df["periodo_informacion"] = period
    return aggregate_imss_chunk(df)


def test_light_audit_accepts_valid_period(load_fixture):
    df = _aggregated(load_fixture)
    result = audit_light_period(df, "2026-01-31", "hash")
    assert result.ok
    assert result.period_fingerprint_hash == "hash"


def test_light_audit_detects_duplicate_analytic_key(load_fixture):
    df = _aggregated(load_fixture)
    duplicated = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    result = audit_light_period(duplicated, "2026-01-31")
    assert result.status == "failed"
    assert any(error.startswith("duplicate_analytic_keys") for error in result.errors)


def test_light_audit_detects_sector_economico_3(load_fixture):
    df = _aggregated(load_fixture)
    df["sector_economico_3"] = "bad"
    result = audit_light_period(df, "2026-01-31")
    assert result.status == "failed"
    assert "forbidden_column:sector_economico_3" in result.errors


def test_light_audit_rejects_wrong_period(load_fixture):
    df = _aggregated(load_fixture, "2026-02-28")
    result = audit_light_period(df, "2026-01-31")
    assert result.status == "failed"
    assert any(error.startswith("unexpected_periods") for error in result.errors)


def test_light_audit_rejects_empty_dataframe():
    result = audit_light_period(pd.DataFrame(), "2026-01-31")
    assert result.status == "failed"
    assert "empty_dataframe" in result.errors
