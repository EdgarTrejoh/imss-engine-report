import json

import pytest

from src.imss_engine.download import calculate_sha256
from src.imss_engine.raw_compare import compare_raw_aggregate_with_concentrado


COMPARE_COLUMNS = (
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
    "asegurados",
    "no_trabajadores",
    "ta",
    "ta_sal",
    "masa_sal_ta",
    "tpu",
    "tpc",
    "teu",
    "tec",
)


def _row(period="2016-06-30", values=None):
    row = {
        "periodo_informacion": period,
        "cve_delegacion": "01",
        "cve_subdelegacion": "001",
        "cve_entidad": "09",
        "cve_municipio": "001",
        "tamaño_patron": "S1",
        "sexo": "M",
        "rango_edad": "20-24",
        "rango_ingreso_vsm": "W1",
        "rango_ingreso_uma": "",
        "sector_economico_1": "1",
        "sector_economico_2": "11",
        "sector_economico_4": "1111",
        "ptpd": "",
        "asegurados": "1",
        "no_trabajadores": "1",
        "ta": "1",
        "ta_sal": "1",
        "masa_sal_ta": "10.0",
        "tpu": "1",
        "tpc": "0",
        "teu": "0",
        "tec": "0",
    }
    if values:
        row.update(values)
    return row


def _write_csv(path, rows, columns=COMPARE_COLUMNS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(",".join(columns) + "\n")
        for row in rows:
            file.write(",".join(str(row.get(column, "")) for column in columns) + "\n")
    return path


def _compare(tmp_path, aggregate_rows, concentrado_rows=None, period="2016-06-30"):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", aggregate_rows)
    concentrado = tmp_path / "data" / "processed" / "imss_concentrado.csv"
    if concentrado_rows is not None:
        _write_csv(concentrado, concentrado_rows)
    output_dir = tmp_path / "outputs" / "processing"
    return compare_raw_aggregate_with_concentrado(
        period,
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=output_dir,
    )


def test_compare_reports_already_exists(tmp_path):
    rows = [_row()]

    manifest, manifest_path = _compare(tmp_path, rows, rows)

    assert manifest["status"] == "success"
    assert manifest["comparison_status"] == "already_exists"
    assert manifest["aggregate_summary"]["row_count"] == 1
    assert manifest["existing_summary"]["row_count"] == 1
    assert (
        manifest["aggregate_summary"]["fingerprint_sha256"]
        == manifest["existing_summary"]["fingerprint_sha256"]
    )
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["comparison_status"] == "already_exists"


def test_compare_reports_new_period(tmp_path):
    manifest, _ = _compare(tmp_path, [_row()], [_row(period="2016-05-31")])

    assert manifest["status"] == "success"
    assert manifest["comparison_status"] == "new_period"
    assert manifest["existing_summary"] is None


def test_compare_reports_conflict_row_count(tmp_path):
    manifest, _ = _compare(tmp_path, [_row()], [_row(), _row(values={"cve_municipio": "002"})])

    assert manifest["status"] == "conflict"
    assert manifest["comparison_status"] == "conflict_existing_period_row_count"


def test_compare_reports_conflict_hash(tmp_path):
    manifest, _ = _compare(tmp_path, [_row()], [_row(values={"ta": "2"})])

    assert manifest["status"] == "conflict"
    assert manifest["comparison_status"] == "conflict_existing_period_hash"
    assert (
        manifest["aggregate_summary"]["fingerprint_sha256"]
        != manifest["existing_summary"]["fingerprint_sha256"]
    )


def test_compare_reports_missing_concentrado_without_creating_data_processed(tmp_path):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row()])
    concentrado = tmp_path / "missing" / "imss_concentrado.csv"

    manifest, _ = compare_raw_aggregate_with_concentrado(
        "2016-06-30",
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )

    assert manifest["status"] == "warning"
    assert manifest["comparison_status"] == "missing_concentrado"
    assert manifest["concentrado_exists"] is False
    assert not (tmp_path / "data" / "processed").exists()


@pytest.mark.parametrize(
    ("columns", "rows", "message"),
    [
        (tuple(column for column in COMPARE_COLUMNS if column != "periodo_informacion"), [_row()], "periodo_informacion"),
        (COMPARE_COLUMNS, [_row(period="2016-05-31")], "does not match"),
        (COMPARE_COLUMNS, [_row(), _row(period="2016-05-31")], "multiple periods"),
        (tuple(column for column in COMPARE_COLUMNS if column != "ta"), [_row()], "ta"),
    ],
)
def test_compare_reports_invalid_aggregate(tmp_path, columns, rows, message):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", rows, columns=columns)
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", [_row()])

    manifest, _ = compare_raw_aggregate_with_concentrado(
        "2016-06-30",
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )

    assert manifest["status"] == "failed"
    assert manifest["comparison_status"] == "failed"
    assert message in manifest["error_message"]


def test_compare_does_not_modify_concentrado(tmp_path):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row()])
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", [_row()])
    before_hash = calculate_sha256(concentrado)

    manifest, _ = compare_raw_aggregate_with_concentrado(
        "2016-06-30",
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )

    assert manifest["comparison_status"] == "already_exists"
    assert calculate_sha256(concentrado) == before_hash
    assert manifest["writes_concentrado"] is False
    assert manifest["writes_data_processed"] is False
    assert manifest["loads_postgresql"] is False
    assert manifest["touches_staging_table"] is False
    assert manifest["touches_final_table"] is False
    assert manifest["writes_period_control"] is False
    assert manifest["writes_run_manifest"] is False


def test_compare_uses_only_explicit_aggregate_file(tmp_path):
    requested = _write_csv(tmp_path / "outputs" / "processing" / "requested.csv", [_row()])
    _write_csv(
        tmp_path / "outputs" / "processing" / "other.csv",
        [_row(values={"ta": "999", "masa_sal_ta": "999.0"})],
    )
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", [_row()])

    manifest, _ = compare_raw_aggregate_with_concentrado(
        "2016-06-30",
        aggregate_file=requested,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )

    assert manifest["comparison_status"] == "already_exists"
    assert manifest["aggregate_file_path"] == str(requested)
    assert manifest["aggregate_summary"]["sum_ta"] == 1
