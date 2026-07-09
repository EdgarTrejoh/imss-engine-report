import json
from pathlib import Path

import pytest

from src.imss_engine.download import calculate_sha256, get_file_size_bytes
from src.imss_engine.publish_insert import publish_imss_aggregate_from_plan
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


def _write_csv(path: Path, rows, columns=COMPARE_COLUMNS, *, final_newline=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    ending = "\n" if final_newline else ""
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(",".join(columns) + "\n")
        for index, row in enumerate(rows):
            line_end = "\n" if index < len(rows) - 1 else ending
            file.write(",".join(str(row.get(column, "")) for column in columns) + line_end)
    return path


def _make_insert_candidate_plan(tmp_path, *, aggregate_rows=None, concentrado_rows=None):
    aggregate_rows = aggregate_rows if aggregate_rows is not None else [_row()]
    concentrado_rows = concentrado_rows if concentrado_rows is not None else [_row(period="2016-05-31")]
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", aggregate_rows)
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", concentrado_rows)
    plan, plan_path = build_publish_plan(
        "2016-06-30",
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )
    assert plan["action"] == "insert_candidate"
    return plan, plan_path, aggregate, concentrado


def _publish(plan_path, concentrado, tmp_path, **kwargs):
    return publish_imss_aggregate_from_plan(
        plan_path,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "audit" / "publish",
        **kwargs,
    )


def _read_lines(path: Path):
    return path.read_text(encoding="utf-8-sig").splitlines()


def test_valid_plan_with_fresh_new_period_inserts_append_only(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    before_hash = calculate_sha256(concentrado)

    result, manifest_path = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "success"
    assert result["action"] == "inserted"
    assert result["validation_status"] == "passed"
    assert result["rows_inserted"] == 1
    assert result["comparison_before"]["comparison_status"] == "new_period"
    assert result["comparison_after"]["comparison_status"] == "already_exists"
    assert result["append_only"] is True
    assert result["loads_postgresql"] is False
    assert result["writes_concentrado"] is True
    assert result["writes_data_processed"] is True
    assert calculate_sha256(concentrado) != before_hash
    assert Path(result["backup_path"]).exists()
    assert calculate_sha256(result["backup_path"]) == result["backup_sha256"]
    assert manifest_path.exists()


def test_fresh_already_exists_is_idempotent_no_op_without_backup(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    _write_csv(concentrado, [_row(period="2016-05-31"), _row()])
    before_hash = calculate_sha256(concentrado)

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "success"
    assert result["action"] == "no_op"
    assert result["validation_status"] == "skipped"
    assert result["backup_path"] is None
    assert result["rows_inserted"] == 0
    assert calculate_sha256(concentrado) == before_hash


def test_plan_action_no_op_is_blocked(tmp_path):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row()])
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", [_row()])
    plan, plan_path = build_publish_plan(
        "2016-06-30",
        aggregate_file=aggregate,
        concentrado_file=concentrado,
        output_dir=tmp_path / "outputs" / "processing",
    )
    assert plan["action"] == "no_op"

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert result["action"] == "block"
    assert "insert_candidate" in result["reason"]


def test_plan_status_blocked_is_blocked(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["status"] = "blocked"
    plan["action"] = "block"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "status is not success" in result["reason"]


def test_invalid_plan_json_fails(tmp_path):
    plan_path = tmp_path / "outputs" / "processing" / "bad_plan.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("{not json", encoding="utf-8")

    result, _ = publish_imss_aggregate_from_plan(
        plan_path,
        output_dir=tmp_path / "outputs" / "audit" / "publish",
    )

    assert result["status"] == "failed"
    assert result["action"] == "block"
    assert "invalid publish_plan JSON" in result["error_message"]


def test_aggregate_hash_mismatch_blocks_without_backup(tmp_path):
    _, plan_path, aggregate, concentrado = _make_insert_candidate_plan(tmp_path)
    _write_csv(aggregate, [_row(values={"ta": "9"})])

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "sha256 mismatch" in result["reason"]
    assert result["backup_path"] is None


def test_aggregate_size_mismatch_blocks_without_backup(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["aggregate_file_size_bytes"] = int(plan["aggregate_file_size_bytes"]) + 1
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "size mismatch" in result["reason"]
    assert result["backup_path"] is None


def test_missing_concentrado_blocks(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    concentrado.unlink()

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "does not exist" in result["reason"]


def test_incompatible_columns_block_before_backup(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    bad_columns = tuple(column for column in COMPARE_COLUMNS if column != "ptpd")
    _write_csv(concentrado, [_row(period="2016-05-31")], columns=bad_columns)

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "columns do not match" in result["reason"]
    assert result["backup_path"] is None


def test_aggregate_with_different_period_fails_before_append(tmp_path):
    aggregate = _write_csv(tmp_path / "outputs" / "processing" / "aggregate.csv", [_row(period="2016-05-31")])
    concentrado = _write_csv(tmp_path / "data" / "processed" / "imss_concentrado.csv", [_row(period="2016-04-30")])
    plan = {
        "mode": "plan_imss_publish",
        "periodo_informacion": "2016-06-30",
        "status": "success",
        "action": "insert_candidate",
        "would_write": False,
        "comparison_status": "new_period",
        "aggregate_file": str(aggregate),
        "aggregate_sha256": calculate_sha256(aggregate),
        "aggregate_file_size_bytes": get_file_size_bytes(aggregate),
        "concentrado_file": str(concentrado),
        "target": {"type": "csv_concentrado", "path": str(concentrado)},
        "safety_checks": {
            "writes_concentrado": False,
            "writes_data_processed": False,
            "loads_postgresql": False,
            "touches_staging_table": False,
            "touches_final_table": False,
            "writes_period_control": False,
            "writes_run_manifest": False,
        },
    }
    plan_path = tmp_path / "outputs" / "processing" / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "failed"
    assert result["action"] == "block"
    assert "does not match" in result["error_message"]
    assert result["rows_inserted"] == 0


def test_fresh_conflict_hash_blocks(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    _write_csv(concentrado, [_row(values={"ta": "9"})])

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "conflict_existing_period_hash" in result["reason"]
    assert result["backup_path"] is None


def test_fresh_conflict_row_count_blocks(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    _write_csv(concentrado, [_row(), _row(values={"cve_municipio": "999"})])

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "conflict_existing_period_row_count" in result["reason"]
    assert result["backup_path"] is None


def test_backup_does_not_replace_existing_backup(tmp_path, monkeypatch):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    monkeypatch.setattr("src.imss_engine.publish_insert.generate_publish_insert_run_id", lambda: "fixed_run")
    existing = tmp_path / "outputs" / "audit" / "publish" / "backups" / "imss_concentrado_fixed_run_before.csv"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("existing", encoding="utf-8")

    result, _ = _publish(plan_path, concentrado, tmp_path)

    assert result["status"] == "blocked"
    assert "backup already exists" in result["reason"]
    assert existing.read_text(encoding="utf-8") == "existing"


def test_append_does_not_duplicate_header_and_handles_missing_trailing_newline(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path, concentrado_rows=[_row(period="2016-05-31")])
    _write_csv(concentrado, [_row(period="2016-05-31")], final_newline=False)

    result, _ = _publish(plan_path, concentrado, tmp_path)

    lines = _read_lines(concentrado)
    assert result["status"] == "success"
    assert lines.count(",".join(COMPARE_COLUMNS)) == 1
    assert len(lines) == 3


def test_post_compare_failure_reports_failed_validation_with_backup(tmp_path):
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)
    calls = []

    def compare_stub(period, *, aggregate_file, concentrado_file, output_dir):
        calls.append(period)
        status = "new_period" if len(calls) == 1 else "failed"
        return (
            {
                "comparison_status": status,
                "status": "success" if status == "new_period" else "failed",
                "error_message": "forced post failure" if status == "failed" else None,
                "aggregate_summary": {"row_count": 1, "fingerprint_sha256": "a"},
                "existing_summary": None,
            },
            Path(output_dir) / f"compare_{len(calls)}.json",
        )

    result, _ = _publish(plan_path, concentrado, tmp_path, compare_func=compare_stub)

    assert result["status"] == "failed_validation"
    assert result["action"] == "inserted_validation_failed"
    assert Path(result["backup_path"]).exists()
    assert result["rollback_manual_path"] == result["backup_path"]


def test_cli_returns_parseable_json_for_controlled_error(tmp_path):
    plan_path = tmp_path / "missing.json"
    output_dir = tmp_path / "outputs" / "audit" / "publish"
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/publish_imss_aggregate.py",
            "--publish-plan",
            str(plan_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode != 0
    assert payload["status"] == "failed"
    assert payload["action"] == "block"
    assert payload["result"]["loads_postgresql"] is False


def test_publish_rejects_data_processed_compare_output_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)

    result, _ = _publish(
        plan_path,
        concentrado,
        tmp_path,
        compare_output_dir=Path("data") / "processed",
    )

    assert result["status"] == "blocked"
    assert result["action"] == "block"
    assert "data/processed" in result["error_message"]
    assert not (tmp_path / "data" / "processed" / "raw_compare_manifest.json").exists()


def test_publish_rejects_data_processed_compare_output_dir_child(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, plan_path, _, concentrado = _make_insert_candidate_plan(tmp_path)

    result, _ = _publish(
        plan_path,
        concentrado,
        tmp_path,
        compare_output_dir=Path("data") / "processed" / "compare",
    )

    assert result["status"] == "blocked"
    assert result["action"] == "block"
    assert "data/processed" in result["error_message"]
    assert not (tmp_path / "data" / "processed" / "compare").exists()


def test_cli_returns_parseable_json_for_disallowed_output_dir(tmp_path):
    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "publish_imss_aggregate.py"),
            "--publish-plan",
            "missing.json",
            "--output-dir",
            "data/processed",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode != 0
    assert payload == {
        "status": "blocked",
        "action": "block",
        "publish_manifest_path": None,
        "result": {
            "status": "blocked",
            "action": "block",
            "validation_status": "blocked",
            "would_write": False,
            "error_message": "output_dir cannot be data/processed or a child of data/processed",
        },
    }
    assert not (tmp_path / "data" / "processed").exists()
