from src.imss_engine.transform import (
    add_salary_mass_metrics,
    add_worker_metrics,
    convert_numeric_columns,
)


def test_worker_metrics_are_calculated_from_documented_components(load_fixture):
    df = convert_numeric_columns(load_fixture("imss_sample_actual.csv"))
    out = add_worker_metrics(df)
    assert out.loc[0, "puestos_permanentes"] == 5
    assert out.loc[0, "puestos_eventuales"] == 5
    assert out.loc[0, "puestos_urbanos"] == 7
    assert out.loc[0, "puestos_campo"] == 3


def test_salary_mass_metrics_are_calculated_from_documented_components(load_fixture):
    df = convert_numeric_columns(load_fixture("imss_sample_actual.csv"))
    out = add_salary_mass_metrics(df)
    assert out.loc[0, "masa_sal_permanentes"] == 500
    assert out.loc[0, "masa_sal_eventuales"] == 300
    assert out.loc[0, "masa_sal_urbanos"] == 600
    assert out.loc[0, "masa_sal_campo"] == 200
