import pandas as pd
import pytest

from src.imss_engine.aggregate import aggregate_imss_chunk
from src.imss_engine.concentrado import (
    build_period_urls,
    calculate_period_fingerprint,
    make_candidate,
    period_fingerprint_hash,
    publish_concentrado_insert_only,
    resolve_configured_periods,
)


def _aggregated(load_fixture, period="2026-01-31"):
    df = load_fixture("imss_sample_actual.csv")
    df["periodo_informacion"] = period
    return aggregate_imss_chunk(df)


def test_mes_consulta_uses_single_configured_month():
    mode, periods = resolve_configured_periods(
        {"mode": "mes_consulta", "mes_consulta": "2026-01-31"}
    )
    assert mode == "mes_consulta"
    assert periods == ["2026-01-31"]


def test_periodo_consulta_uses_explicit_month_list():
    mode, periods = resolve_configured_periods(
        {
            "mode": "periodo_consulta",
            "periodo_consulta": {"meses": ["2026-01-31", "2026-02-28"]},
        }
    )
    assert mode == "periodo_consulta"
    assert periods == ["2026-01-31", "2026-02-28"]


def test_periodo_consulta_rejects_duplicate_months():
    with pytest.raises(ValueError, match="duplicados"):
        resolve_configured_periods(
            {
                "mode": "periodo_consulta",
                "periodo_consulta": {"meses": ["2026-01-31", "2026-01-31"]},
            }
        )


def test_mode_rejects_non_empty_legacy_meses():
    with pytest.raises(ValueError, match="etl.meses es legacy"):
        resolve_configured_periods(
            {
                "mode": "periodo_consulta",
                "periodo_consulta": {"meses": ["2016-01-31"]},
                "meses": ["2026-01-31"],
            }
        )


def test_build_period_urls_preserves_order():
    urls = build_period_urls("http://example/asg-{}.csv", ["2026-02-28", "2026-01-31"])
    assert urls == [
        ("2026-02-28", "http://example/asg-2026-02-28.csv"),
        ("2026-01-31", "http://example/asg-2026-01-31.csv"),
    ]


def test_hash_is_stable_for_same_summary():
    summary = {
        "periodo_informacion": "2026-01-31",
        "row_count": 1,
        "sum_ta": 10,
    }
    assert period_fingerprint_hash(summary) == period_fingerprint_hash(dict(reversed(summary.items())))


def test_hash_changes_when_metric_changes():
    base = {"periodo_informacion": "2026-01-31", "row_count": 1, "sum_ta": 10}
    changed = {**base, "sum_ta": 11}
    assert period_fingerprint_hash(base) != period_fingerprint_hash(changed)


def test_concentrado_is_created_when_missing(tmp_path, load_fixture):
    concentrado = tmp_path / "imss_concentrado.csv"
    df = _aggregated(load_fixture)
    candidate = make_candidate(df, "2026-01-31", "http://example/asg-2026-01-31.csv")

    results, summary = publish_concentrado_insert_only(concentrado, [candidate])

    assert concentrado.exists()
    assert results[0].status == "success_loaded"
    assert summary["concentrado_exists_before"] is False
    assert summary["rows_loaded"] == len(df)


def test_new_period_is_loaded_into_existing_concentrado(tmp_path, load_fixture):
    concentrado = tmp_path / "imss_concentrado.csv"
    old_df = _aggregated(load_fixture, "2026-01-31")
    old_df.to_csv(concentrado, index=False)
    new_df = _aggregated(load_fixture, "2026-02-28")
    candidate = make_candidate(new_df, "2026-02-28", "http://example/asg-2026-02-28.csv")

    results, _ = publish_concentrado_insert_only(concentrado, [candidate])

    loaded = pd.read_csv(concentrado, dtype=str)
    assert results[0].status == "success_loaded"
    assert set(loaded["periodo_informacion"]) == {"2026-01-31", "2026-02-28"}


def test_existing_same_period_is_not_duplicated(tmp_path, load_fixture):
    concentrado = tmp_path / "imss_concentrado.csv"
    df = _aggregated(load_fixture)
    df.to_csv(concentrado, index=False)
    candidate = make_candidate(df, "2026-01-31", "http://example/asg-2026-01-31.csv")

    first_results, _ = publish_concentrado_insert_only(concentrado, [candidate])
    second_results, _ = publish_concentrado_insert_only(concentrado, [candidate])

    loaded = pd.read_csv(concentrado)
    assert first_results[0].status == "already_exists"
    assert second_results[0].status == "already_exists"
    assert len(loaded) == len(df)


def test_existing_period_with_different_row_count_conflicts(tmp_path, load_fixture):
    concentrado = tmp_path / "imss_concentrado.csv"
    df = _aggregated(load_fixture)
    candidate_df = pd.concat([df, df.assign(cve_municipio="999")], ignore_index=True)
    df.to_csv(concentrado, index=False)
    candidate = make_candidate(candidate_df, "2026-01-31", "http://example/asg-2026-01-31.csv")

    results, _ = publish_concentrado_insert_only(concentrado, [candidate])

    assert results[0].status == "conflict_existing_period_row_count"


def test_existing_period_with_same_rows_different_hash_conflicts(tmp_path, load_fixture):
    concentrado = tmp_path / "imss_concentrado.csv"
    existing = _aggregated(load_fixture)
    candidate_df = existing.copy()
    candidate_df.loc[candidate_df.index[0], "ta"] = candidate_df.loc[candidate_df.index[0], "ta"] + 1
    existing.to_csv(concentrado, index=False)
    candidate = make_candidate(candidate_df, "2026-01-31", "http://example/asg-2026-01-31.csv")

    results, _ = publish_concentrado_insert_only(concentrado, [candidate])

    assert results[0].status == "conflict_existing_period_hash"


def test_staging_preserves_original_if_publication_fails(tmp_path, load_fixture):
    concentrado = tmp_path / "imss_concentrado.csv"
    original = _aggregated(load_fixture, "2026-01-31")
    original.to_csv(concentrado, index=False)
    candidate_df = _aggregated(load_fixture, "2026-02-28")
    candidate = make_candidate(candidate_df, "2026-02-28", "http://example/asg-2026-02-28.csv")

    def fail_replace(src, dst):
        raise RuntimeError("replace failed")

    with pytest.raises(RuntimeError, match="replace failed"):
        publish_concentrado_insert_only(concentrado, [candidate], replace_func=fail_replace)

    loaded = pd.read_csv(concentrado)
    assert set(loaded["periodo_informacion"]) == {"2026-01-31"}
