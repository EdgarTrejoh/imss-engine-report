import pandas as pd

from src.imss_engine.dimension_normalization import normalize_imss_dimension_values


def test_normalize_blank_dimension_values_to_na_only_for_selected_columns():
    df = pd.DataFrame(
        {
            "cve_municipio": ["", " "],
            "tamaño_patron": ["", "S1"],
            "rango_edad": [" ", "20-24"],
            "rango_ingreso_vsm": ["", "W1"],
            "ptpd": ["", "1"],
            "rango_ingreso_uma": ["", "U1"],
        }
    )

    out = normalize_imss_dimension_values(df)

    assert out["cve_municipio"].tolist() == ["NA", "NA"]
    assert out["tamaño_patron"].tolist() == ["NA", "S1"]
    assert out["rango_edad"].tolist() == ["NA", "20-24"]
    assert out["rango_ingreso_vsm"].tolist() == ["NA", "W1"]
    assert out["ptpd"].tolist() == ["", "1"]
    assert out["rango_ingreso_uma"].tolist() == ["", "U1"]


def test_normalize_sector_decimal_strings_to_integer_strings():
    df = pd.DataFrame(
        {
            "sector_economico_1": ["1.0", "1", "", "NA", "1.5", " 2.0 "],
            "sector_economico_2": ["11.0", "11", "", "NA", "11.5", " 22.0 "],
            "sector_economico_4": ["1101.0", "1101", "", "NA", "1101.5", " 2202.0 "],
        }
    )

    out = normalize_imss_dimension_values(df)

    assert out["sector_economico_1"].tolist() == ["1", "1", "", "NA", "1.5", "2"]
    assert out["sector_economico_2"].tolist() == ["11", "11", "", "NA", "11.5", "22"]
    assert out["sector_economico_4"].tolist() == ["1101", "1101", "", "NA", "1101.5", "2202"]


def test_normalize_dimension_values_does_not_change_metric_columns_or_row_count():
    df = pd.DataFrame(
        {
            "cve_municipio": ["", "001"],
            "sector_economico_1": ["1.0", "2.0"],
            "asegurados": [1, 2],
            "no_trabajadores": [3, 4],
            "ta": [5, 6],
            "ta_sal": [7, 8],
            "masa_sal_ta": [9.5, 10.5],
            "tpu": [11, 12],
            "tpc": [13, 14],
            "teu": [15, 16],
            "tec": [17, 18],
        }
    )

    out = normalize_imss_dimension_values(df)

    assert len(out) == len(df)
    for column in (
        "asegurados",
        "no_trabajadores",
        "ta",
        "ta_sal",
        "masa_sal_ta",
        "tpu",
        "tpc",
        "teu",
        "tec",
    ):
        assert out[column].tolist() == df[column].tolist()
        assert out[column].sum() == df[column].sum()
