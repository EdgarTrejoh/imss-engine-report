from __future__ import annotations

import pandas as pd

from imss_duckdb_exports import EXPECTED_COLUMNS, run_audit


def test_duckdb_audit_exports_phase_2_reports(tmp_path):
    input_csv = tmp_path / "imss_phase2_sample.csv"
    output_dir = tmp_path / "audits"

    row = {column: "1" for column in EXPECTED_COLUMNS}
    row.update(
        {
            "periodo_informacion": "2024-01-31",
            "tamaño_patron": "A",
            "sexo": "1",
            "rango_edad": "E1",
            "rango_ingreso_vsm": "W1",
            "rango_ingreso_uma": "U1",
            "sector_economico_1": "1",
            "sector_economico_2": "11",
            "sector_economico_4": "1101",
            "ptpd": "1",
            "asegurados": 12,
            "no_trabajadores": 2,
            "ta": 10,
            "ta_sal": 8,
            "tpu": 4,
            "tpc": 1,
            "teu": 3,
            "tec": 2,
            "masa_sal_ta": 800,
            "sbc_total": 100,
        }
    )
    pd.DataFrame([row]).to_csv(input_csv, index=False)

    outputs = run_audit(input_csv, output_dir)

    assert outputs["layout_validation"].exists()
    assert outputs["summary_general"].exists()
    assert outputs["duplicate_keys"].exists()
    assert outputs["ptpd_sbc_by_period"].exists()

    layout = pd.read_csv(outputs["layout_validation"])
    forbidden = layout.loc[layout["column_name"] == "sector_economico_3"].iloc[0]
    assert forbidden["status"] == "absent_ok"

    summary = pd.read_csv(outputs["summary_general"])
    assert summary.loc[0, "sbc_total_calculado"] == 100
