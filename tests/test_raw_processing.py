import json
from pathlib import Path

import pandas as pd

from src.imss_engine.download import build_raw_file_path, calculate_sha256
from src.imss_engine.raw_processing import process_imss_raw_period
from src.imss_engine.raw_validation import DEFAULT_RAW_VALIDATION_MANIFEST_DIR, REQUIRED_RAW_COLUMNS


def _sample_row(values=None):
    row = {
        "cve_delegacion": "01",
        "cve_subdelegacion": "001",
        "cve_entidad": "09",
        "cve_municipio": "001",
        "sector_economico_1": "1",
        "sector_economico_2": "11",
        "sector_economico_4": "1111",
        "tamaño_patron": "S1",
        "sexo": "M",
        "rango_edad": "20-24",
        "rango_salarial": "W1",
        "asegurados": "1",
        "no_trabajadores": "1",
        "ta": "1",
        "ta_sal": "1",
        "tpu": "1",
        "tpc": "0",
        "teu": "0",
        "tec": "0",
        "tpu_sal": "1",
        "tpc_sal": "0",
        "teu_sal": "0",
        "tec_sal": "0",
        "masa_sal_ta": "10.0",
        "masa_sal_tpu": "10.0",
        "masa_sal_tpc": "0",
        "masa_sal_teu": "0",
        "masa_sal_tec": "0",
    }
    if values:
        row.update(values)
    return row


def _write_raw(raw_root, period, rows, columns=REQUIRED_RAW_COLUMNS):
    path = build_raw_file_path(period, raw_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="latin-1", newline="") as file:
        file.write("|".join(columns) + "\n")
        for row in rows:
            file.write("|".join(str(row.get(column, "")) for column in columns) + "\n")
    return path


def test_process_raw_success_writes_temporary_aggregate_and_manifest(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs" / "processing"
    rows = [_sample_row(), _sample_row({"ta": "2", "ta_sal": "2", "masa_sal_ta": "20.0"})]
    raw_path = _write_raw(raw_root, "2016-06-30", rows)

    manifest, manifest_path = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    aggregate_path = output_dir / f"raw_aggregate_{manifest['run_id']}_2016-06-30.csv"
    aggregate_df = pd.read_csv(aggregate_path)
    assert manifest["status"] == "success"
    assert manifest["raw_file_path"] == str(raw_path)
    assert manifest["raw_file_size_bytes"] == raw_path.stat().st_size
    assert manifest["raw_sha256"] == calculate_sha256(raw_path)
    assert manifest["raw_validation"]["valid"] is True
    assert manifest["raw_validation"]["manifest_path"]
    assert "outputs/audit/raw_validation" in manifest["raw_validation"]["manifest_path"].replace("\\", "/")
    assert manifest["chunks_processed"] == 2
    assert manifest["rows_read"] == 2
    assert manifest["aggregate_rows"] > 0
    assert manifest["aggregate_output_path"] == str(aggregate_path)
    assert manifest["aggregate_sha256"] == calculate_sha256(aggregate_path)
    assert "periodo_informacion" in aggregate_df.columns
    assert set(aggregate_df["periodo_informacion"]) == {"2016-06-30"}
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "success"
    assert not (tmp_path / "data" / "processed").exists()


def test_process_raw_recombines_same_analytic_key_across_chunks(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs" / "processing"
    rows = [
        _sample_row({"ta": "2", "ta_sal": "2", "asegurados": "2", "masa_sal_ta": "20.0"}),
        _sample_row({"ta": "3", "ta_sal": "3", "asegurados": "3", "masa_sal_ta": "30.0"}),
    ]
    _write_raw(raw_root, "2016-06-30", rows)

    manifest, _ = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    aggregate_df = pd.read_csv(manifest["aggregate_output_path"])
    assert manifest["status"] == "success"
    assert manifest["chunks_processed"] == 2
    assert len(aggregate_df) == 1
    assert aggregate_df.loc[0, "periodo_informacion"] == "2016-06-30"
    assert aggregate_df.loc[0, "ta"] == 5
    assert aggregate_df.loc[0, "ta_sal"] == 5
    assert aggregate_df.loc[0, "asegurados"] == 5
    assert aggregate_df.loc[0, "masa_sal_ta"] == 50.0


def test_process_raw_writes_compatible_dimension_values(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs" / "processing"
    rows = [
        _sample_row(
            {
                "cve_municipio": "",
                "tamaño_patron": "",
                "rango_edad": "",
                "rango_salarial": "",
                "sector_economico_1": "1.0",
                "sector_economico_2": "11.0",
                "sector_economico_4": "1101.0",
            }
        )
    ]
    _write_raw(raw_root, "2016-06-30", rows)

    manifest, _ = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    aggregate_df = pd.read_csv(manifest["aggregate_output_path"], dtype=str, keep_default_na=False)
    assert manifest["dimension_normalization"]["applied"] is True
    assert aggregate_df.loc[0, "cve_municipio"] == "NA"
    assert aggregate_df.loc[0, "tamaño_patron"] == "NA"
    assert aggregate_df.loc[0, "rango_edad"] == "NA"
    assert aggregate_df.loc[0, "rango_ingreso_vsm"] == "NA"
    assert aggregate_df.loc[0, "sector_economico_1"] == "1"
    assert aggregate_df.loc[0, "sector_economico_2"] == "11"
    assert aggregate_df.loc[0, "sector_economico_4"] == "1101"


def test_process_raw_only_processes_requested_period(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs" / "processing"
    _write_raw(raw_root, "2016-05-31", [_sample_row({"cve_entidad": "05"})])
    _write_raw(raw_root, "2016-06-30", [_sample_row({"cve_entidad": "06"})])

    manifest, _ = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    aggregate_files = sorted(output_dir.glob("raw_aggregate_*.csv"))
    aggregate_df = pd.read_csv(aggregate_files[0])
    assert len(aggregate_files) == 1
    assert not (output_dir / "raw_validation").exists()
    assert "2016-06-30" in aggregate_files[0].name
    assert "2016-05-31" not in aggregate_files[0].name
    assert set(aggregate_df["periodo_informacion"]) == {"2016-06-30"}
    assert manifest["periodo_informacion"] == "2016-06-30"


def test_process_raw_invalid_validation_does_not_write_aggregate(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs" / "processing"
    columns = tuple(column for column in REQUIRED_RAW_COLUMNS if column != "cve_entidad")
    _write_raw(raw_root, "2016-06-30", [_sample_row()], columns=columns)

    manifest, manifest_path = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    assert manifest["status"] == "failed_raw_validation"
    assert manifest["raw_validation"]["valid"] is False
    assert manifest["aggregate_output_path"] is None
    assert not list(output_dir.glob("raw_aggregate_*.csv"))
    assert manifest_path.exists()


def test_process_raw_missing_file_does_not_write_aggregate(tmp_path):
    output_dir = tmp_path / "outputs" / "processing"

    manifest, _ = process_imss_raw_period(
        "2016-06-30",
        raw_root=tmp_path / "raw",
        output_dir=output_dir,
        chunk_size=1,
    )

    assert manifest["status"] == "failed_raw_validation"
    assert manifest["raw_validation"]["status"] == "failed_missing_raw"
    assert manifest["aggregate_output_path"] is None
    assert not list(output_dir.glob("raw_aggregate_*.csv"))


def test_process_raw_manifest_contains_metadata_hashes_and_no_side_effect_flags(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs" / "processing"
    _write_raw(raw_root, "2016-06-30", [_sample_row()])

    manifest, _ = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    assert manifest["raw_file_path"]
    assert manifest["raw_sha256"]
    assert manifest["raw_file_size_bytes"] > 0
    assert manifest["raw_validation"]["manifest_path"]
    assert manifest["aggregate_output_path"]
    assert manifest["aggregate_sha256"]
    assert manifest["writes_data_processed"] is False
    assert manifest["loads_postgresql"] is False
    assert manifest["touches_staging_table"] is False
    assert manifest["touches_final_table"] is False
    assert manifest["writes_period_control"] is False
    assert manifest["writes_run_manifest"] is False


def test_process_raw_uses_default_raw_validation_manifest_location(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs" / "processing"
    raw_validation_dir = tmp_path / "outputs" / "audit" / "raw_validation"
    _write_raw(raw_root, "2016-06-30", [_sample_row()])
    monkeypatch.chdir(tmp_path)

    manifest, _ = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    validation_manifest_path = Path(manifest["raw_validation"]["manifest_path"])
    assert validation_manifest_path.parent == DEFAULT_RAW_VALIDATION_MANIFEST_DIR
    assert (raw_validation_dir / validation_manifest_path.name).exists()
    assert not (output_dir / "raw_validation").exists()
