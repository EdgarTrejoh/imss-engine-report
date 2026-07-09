from pathlib import Path

import pytest

from src.imss_engine.download import calculate_sha256
from src.imss_engine.publish_plan import build_publish_plan


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


def _write_csv(path: Path, rows, columns=COMPARE_COLUMNS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(",".join(columns) + "\n")
        for row in rows:
            file.write(",".join(str(row.get(column, "")) for column in columns) + "\n")
    return path


def _plan(tmp_path, aggregate_rows, concentrado_rows=None, period="2016-06-30", columns=COMPARE_COLUMNS):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", aggregate_rows, columns=columns)
    concentrado = tmp_path / "data" / "processed" / "imss_concentrado.csv"
    if concentrado_rows is not None:
        _write_csv(concentrado, concentrado_rows)
    return build_publish_plan(
        period,
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )


def _assert_dry_run_safety(plan):
    assert plan["would_write"] is False
    assert plan["safety_checks"]["writes_concentrado"] is False
    assert plan["safety_checks"]["writes_data_processed"] is False
    assert plan["safety_checks"]["loads_postgresql"] is False
    assert plan["safety_checks"]["touches_staging_table"] is False
    assert plan["safety_checks"]["touches_final_table"] is False
    assert plan["safety_checks"]["writes_period_control"] is False
    assert plan["safety_checks"]["writes_run_manifest"] is False


def test_publish_plan_already_exists_maps_to_no_op(tmp_path):
    plan, plan_path = _plan(tmp_path, [_row()], [_row()])

    assert plan["status"] == "success"
    assert plan["action"] == "no_op"
    assert plan["comparison_status"] == "already_exists"
    assert plan["aggregate_summary"]["row_count"] == 1
    assert plan["existing_summary"]["row_count"] == 1
    assert plan["compare_manifest_path"]
    assert plan_path.exists()
    assert plan["plan_manifest_path"] == str(plan_path)
    _assert_dry_run_safety(plan)


def test_publish_plan_new_period_maps_to_insert_candidate(tmp_path):
    plan, _ = _plan(tmp_path, [_row()], [_row(period="2016-05-31")])

    assert plan["status"] == "success"
    assert plan["action"] == "insert_candidate"
    assert plan["comparison_status"] == "new_period"
    assert plan["existing_summary"] is None
    _assert_dry_run_safety(plan)


def test_publish_plan_hash_conflict_maps_to_block(tmp_path):
    plan, _ = _plan(tmp_path, [_row()], [_row(values={"ta": "2"})])

    assert plan["status"] == "blocked"
    assert plan["action"] == "block"
    assert plan["comparison_status"] == "conflict_existing_period_hash"
    _assert_dry_run_safety(plan)


def test_publish_plan_row_count_conflict_maps_to_block(tmp_path):
    plan, _ = _plan(tmp_path, [_row()], [_row(), _row(values={"cve_municipio": "002"})])

    assert plan["status"] == "blocked"
    assert plan["action"] == "block"
    assert plan["comparison_status"] == "conflict_existing_period_row_count"
    _assert_dry_run_safety(plan)


def test_publish_plan_missing_concentrado_maps_to_block_without_creating_data_processed(tmp_path):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row()])
    concentrado = tmp_path / "missing" / "imss_concentrado.csv"

    plan, _ = build_publish_plan(
        "2016-06-30",
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )

    assert plan["status"] == "blocked"
    assert plan["action"] == "block"
    assert plan["comparison_status"] == "missing_concentrado"
    assert not (tmp_path / "data" / "processed").exists()
    _assert_dry_run_safety(plan)


def test_publish_plan_invalid_aggregate_maps_to_failed_block(tmp_path):
    columns = tuple(column for column in COMPARE_COLUMNS if column != "ta")
    plan, _ = _plan(tmp_path, [_row()], [_row()], columns=columns)

    assert plan["status"] == "failed"
    assert plan["action"] == "block"
    assert plan["comparison_status"] == "failed"
    assert "ta" in plan["reason"]
    _assert_dry_run_safety(plan)


def test_publish_plan_period_mismatch_maps_to_failed_block(tmp_path):
    plan, _ = _plan(tmp_path, [_row(period="2016-05-31")], [_row()])

    assert plan["status"] == "failed"
    assert plan["action"] == "block"
    assert plan["comparison_status"] == "failed"
    assert "does not match" in plan["reason"]
    _assert_dry_run_safety(plan)


def test_publish_plan_does_not_modify_concentrado(tmp_path):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row()])
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", [_row()])
    before_hash = calculate_sha256(concentrado)

    plan, _ = build_publish_plan(
        "2016-06-30",
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )

    assert calculate_sha256(concentrado) == before_hash
    assert plan["action"] == "no_op"
    _assert_dry_run_safety(plan)


def test_publish_plan_uses_only_explicit_aggregate_file(tmp_path):
    requested = _write_csv(tmp_path / "outputs" / "processing" / "requested.csv", [_row()])
    _write_csv(
        tmp_path / "outputs" / "processing" / "other.csv",
        [_row(values={"ta": "999", "masa_sal_ta": "999.0"})],
    )
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", [_row()])

    plan, _ = build_publish_plan(
        "2016-06-30",
        aggregate_file=requested,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )

    assert plan["aggregate_file"] == str(requested)
    assert plan["aggregate_summary"]["sum_ta"] == 1
    assert plan["action"] == "no_op"
    _assert_dry_run_safety(plan)


def test_publish_plan_contains_minimum_required_fields(tmp_path):
    plan, _ = _plan(tmp_path, [_row()], [_row()])

    for key in (
        "run_id",
        "mode",
        "periodo_informacion",
        "created_at",
        "finished_at",
        "status",
        "action",
        "reason",
        "aggregate_file",
        "concentrado_file",
        "compare_manifest_path",
        "comparison_status",
        "aggregate_summary",
        "existing_summary",
        "safety_checks",
        "would_write",
        "target",
        "error_message",
    ):
        assert key in plan


def test_publish_plan_rejects_data_processed_output_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row()])
    concentrado = _write_csv(tmp_path / "data" / "processed_source" / "imss_concentrado.csv", [_row()])

    with pytest.raises(ValueError, match="data/processed"):
        build_publish_plan(
            "2016-06-30",
            aggregate_file=aggregate,
            concentrado_file=concentrado,
            output_dir="data/processed",
        )

    assert not (tmp_path / "data" / "processed").exists()


def test_publish_plan_rejects_data_processed_child_output_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row()])
    concentrado = _write_csv(tmp_path / "data" / "processed_source" / "imss_concentrado.csv", [_row()])

    with pytest.raises(ValueError, match="data/processed"):
        build_publish_plan(
            "2016-06-30",
            aggregate_file=aggregate,
            concentrado_file=concentrado,
            output_dir=Path("data") / "processed" / "plans",
        )

    assert not (tmp_path / "data" / "processed").exists()
