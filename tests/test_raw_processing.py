import json
from pathlib import Path

import pandas as pd
import pytest
import duckdb

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


def _write_raw(raw_root, period, rows, columns=REQUIRED_RAW_COLUMNS, encoding="latin-1"):
    path = build_raw_file_path(period, raw_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as file:
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
    assert manifest["processing_engine"] == "duckdb"
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


def test_process_raw_utf8_bom_uses_detected_encoding(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs"
    _write_raw(raw_root, "2025-01-31", [_sample_row()], encoding="utf-8-sig")

    manifest, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    assert manifest["status"] == "success"
    assert manifest["encoding_requested"] == "auto"
    assert manifest["encoding_detected"] == "utf-8-sig"


def test_process_raw_forced_latin1_preserves_historical_behavior(tmp_path):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs"
    _write_raw(raw_root, "2016-06-30", [_sample_row()], encoding="latin-1")

    manifest, _ = process_imss_raw_period(
        "2016-06-30",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
        encoding="latin-1",
    )

    assert manifest["status"] == "success"
    assert manifest["encoding_requested"] == "latin-1"
    assert manifest["encoding_detected"] == "latin-1"
    assert manifest["encoding_candidates_tried"] == ["latin-1"]


def test_process_raw_uses_validation_encoding_for_chunk_reader(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs"
    _write_raw(raw_root, "2025-01-31", [_sample_row()], encoding="utf-8-sig")
    real_read_csv = pd.read_csv
    encodings = []

    def tracking_read_csv(*args, **kwargs):
        encodings.append(kwargs.get("encoding"))
        return real_read_csv(*args, **kwargs)

    monkeypatch.setattr("src.imss_engine.raw_processing.pd.read_csv", tracking_read_csv)

    manifest, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=output_dir,
        chunk_size=1,
    )

    assert manifest["status"] == "success"
    assert encodings == [manifest["encoding_detected"]]


def _read_comparable_output(path):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    frame = frame.drop(columns=["timestamp"])
    sort_columns = [
        "periodo_informacion",
        "cve_delegacion",
        "cve_subdelegacion",
        "cve_entidad",
        "cve_municipio",
        "tamaño_patron",
        "sexo",
        "rango_edad",
        "rango_ingreso_vsm",
        "rango_ingreso_uma",
        "sector_economico_1",
        "sector_economico_2",
        "sector_economico_4",
        "ptpd",
    ]
    return frame.sort_values(sort_columns, kind="stable").reset_index(drop=True)


@pytest.mark.parametrize("encoding", ["latin-1", "utf-8-sig"])
def test_duckdb_external_consolidation_is_equivalent_across_chunking_and_encodings(tmp_path, encoding):
    raw_root = tmp_path / "raw"
    rows = [
        _sample_row(
            {
                "cve_municipio": "",
                "tamaño_patron": "",
                "sector_economico_1": "1.0",
                "ta": "2",
                "ta_sal": "2",
                "tpu": "1",
                "teu": "1",
                "tpu_sal": "1",
                "teu_sal": "1",
                "masa_sal_ta": "20",
                "masa_sal_tpu": "10",
                "masa_sal_teu": "10",
            }
        ),
        _sample_row(
            {
                "cve_municipio": "",
                "tamaño_patron": "",
                "sector_economico_1": "1.0",
                "ta": "3",
                "ta_sal": "3",
                "tpu": "2",
                "teu": "1",
                "tpu_sal": "2",
                "teu_sal": "1",
                "masa_sal_ta": "45",
                "masa_sal_tpu": "30",
                "masa_sal_teu": "15",
            }
        ),
        _sample_row(
            {
                "cve_entidad": "10",
                "tamaño_patron": "S2",
                "ta": "0",
                "ta_sal": "0",
                "tpu": "0",
                "tpu_sal": "0",
                "masa_sal_ta": "0",
                "masa_sal_tpu": "0",
            }
        ),
    ]
    _write_raw(raw_root, "2025-01-31", rows, encoding=encoding)

    reference_manifest, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=tmp_path / "single_chunk_reference",
        chunk_size=len(rows),
        duckdb_memory_limit="256MB",
        duckdb_threads=1,
    )
    duckdb_manifest, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=tmp_path / "duckdb",
        chunk_size=1,
        duckdb_memory_limit="256MB",
        duckdb_threads=1,
        write_parquet=True,
        parquet_compression="zstd",
    )

    assert reference_manifest["status"] == duckdb_manifest["status"] == "success"
    assert reference_manifest["columns_output"] == duckdb_manifest["columns_output"]
    reference_output = _read_comparable_output(reference_manifest["aggregate_output_path"])
    duckdb_output = _read_comparable_output(duckdb_manifest["aggregate_output_path"])
    pd.testing.assert_frame_equal(reference_output, duckdb_output, check_dtype=False)
    csv_path = Path(duckdb_manifest["aggregate_output_path"]).as_posix()
    parquet_path = Path(duckdb_manifest["parquet_output_path"]).as_posix()
    parquet_difference_count = duckdb.sql(
        f"""
        SELECT COUNT(*) FROM (
            SELECT * EXCLUDE (timestamp)
            FROM read_csv_auto('{csv_path}', header=true)
            EXCEPT ALL
            SELECT * EXCLUDE (timestamp)
            FROM read_parquet('{parquet_path}')
        )
        """
    ).fetchone()[0]
    assert parquet_difference_count == 0
    assert duckdb_manifest["parquet_compression"] == "zstd"
    assert duckdb_manifest["parquet_file_size_bytes"] > 0
    assert duckdb_manifest["encoding_detected"] == (
        "utf-8-sig" if encoding == "utf-8-sig" else "latin-1"
    )
    assert duckdb_manifest["temporary_files_cleaned"] is True
    assert not (tmp_path / "duckdb" / ".tmp").exists()


def test_duckdb_result_is_independent_of_chunk_size(tmp_path):
    raw_root = tmp_path / "raw"
    rows = [
        _sample_row({"ta": str(index + 1), "ta_sal": str(index + 1), "masa_sal_ta": str((index + 1) * 10)})
        for index in range(6)
    ]
    _write_raw(raw_root, "2025-01-31", rows, encoding="utf-8-sig")

    first, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=tmp_path / "chunk1",
        chunk_size=1,
        duckdb_memory_limit="256MB",
        duckdb_threads=1,
    )
    second, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=tmp_path / "chunk4",
        chunk_size=4,
        duckdb_memory_limit="256MB",
        duckdb_threads=1,
    )

    pd.testing.assert_frame_equal(
        _read_comparable_output(first["aggregate_output_path"]),
        _read_comparable_output(second["aggregate_output_path"]),
        check_dtype=False,
    )
    assert first["chunks_processed"] == 6
    assert second["chunks_processed"] == 2


def test_retired_pandas_engine_is_rejected_before_processing(tmp_path):
    with pytest.raises(ValueError, match="only productive engine is 'duckdb'"):
        process_imss_raw_period(
            "2025-01-31",
            raw_root=tmp_path / "raw",
            output_dir=tmp_path / "outputs",
            processing_engine="pandas",
        )


def test_duckdb_failure_keeps_requested_temporaries_and_no_partial_output(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    output_dir = tmp_path / "outputs"
    _write_raw(raw_root, "2025-01-31", [_sample_row()], encoding="utf-8-sig")

    def fail_persist(self, aggregate):
        raise RuntimeError("controlled persistence failure")

    monkeypatch.setattr(
        "src.imss_engine.raw_processing.DuckDBAggregateStore.persist_partial",
        fail_persist,
    )

    manifest, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=output_dir,
        preserve_temporary_on_failure=True,
    )

    assert manifest["status"] == "failed"
    assert manifest["failure_stage"] == "persist_partial"
    assert manifest["temporary_files_cleaned"] is False
    assert manifest["aggregate_output_path"] is None
    assert list((output_dir / ".tmp").iterdir())


def test_duckdb_runs_use_distinct_temporary_directories(tmp_path):
    raw_root = tmp_path / "raw"
    _write_raw(raw_root, "2025-01-31", [_sample_row()], encoding="utf-8-sig")

    first, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=tmp_path / "first",
    )
    second, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=tmp_path / "second",
    )

    assert first["run_id"] != second["run_id"]
    assert first["temporary_directory"] != second["temporary_directory"]


def test_dimension_dtypes_prevent_chunk_float_suffix_with_final_null(
    tmp_path,
):
    raw_root = tmp_path / "raw"
    rows = [
        _sample_row({"cve_entidad": "9", "cve_subdelegacion": "1"}),
        _sample_row({"cve_entidad": "9", "cve_subdelegacion": "6"}),
        _sample_row({"cve_entidad": "1", "cve_subdelegacion": "11"}),
        _sample_row({"cve_entidad": "9", "cve_subdelegacion": "54"}),
        _sample_row({"cve_entidad": "", "cve_subdelegacion": ""}),
    ]
    _write_raw(raw_root, "2025-01-31", rows, encoding="utf-8-sig")

    manifest, _ = process_imss_raw_period(
        "2025-01-31",
        raw_root=raw_root,
        output_dir=tmp_path / "duckdb",
        chunk_size=3,
        duckdb_memory_limit="256MB",
        duckdb_threads=1,
    )

    output = pd.read_csv(
        manifest["aggregate_output_path"],
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    assert manifest["status"] == "success"
    assert set(output["cve_entidad"]) == {"", "1", "9"}
    assert {"1", "6", "11", "54", ""} == set(output["cve_subdelegacion"])
    assert not output["cve_entidad"].str.endswith(".0").any()
    assert not output["cve_subdelegacion"].str.endswith(".0").any()
    assert manifest["raw_integer_code_normalization"]["normalized_values_by_column"][
        "cve_entidad"
    ] == 0
    assert manifest["raw_integer_code_normalization"]["normalized_values_by_column"][
        "cve_subdelegacion"
    ] == 0


@pytest.mark.parametrize("period", ["2025-02-28", "2025-03-31"])
def test_dimension_dtype_fix_does_not_mutate_other_period_raw_files(tmp_path, period):
    raw_root = tmp_path / "raw"
    raw_path = _write_raw(
        raw_root,
        period,
        [_sample_row({"cve_entidad": "9", "cve_subdelegacion": "54"})],
        encoding="utf-8-sig",
    )
    raw_hash_before = calculate_sha256(raw_path)

    manifest, _ = process_imss_raw_period(
        period,
        raw_root=raw_root,
        output_dir=tmp_path / "outputs",
        duckdb_memory_limit="256MB",
        duckdb_threads=1,
    )

    assert manifest["status"] == "success"
    assert calculate_sha256(raw_path) == raw_hash_before
    assert manifest["raw_integer_code_normalization"]["normalized_values_by_column"][
        "cve_entidad"
    ] == 0
