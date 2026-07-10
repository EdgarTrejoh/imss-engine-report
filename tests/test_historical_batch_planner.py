import json
from pathlib import Path

import pytest

from scripts import run_imss_historical_batch
from src.imss_engine.download import build_raw_file_path
from src.imss_engine.historical_batch_planner import (
    HistoricalBatchPlannerDependencies,
    generate_month_end_periods,
    plan_historical_batch,
)


class _Config:
    is_complete = True


class _Connection:
    def __init__(self, calls):
        self.calls = calls

    def close(self):
        self.calls.append("close")


def _pg_state(
    *,
    exists=False,
    final_table_row_count=0,
    period_control_exists=False,
    period_control_status=None,
):
    return {
        "periodo_informacion": "2016-08-31",
        "exists": exists,
        "final_table_row_count": final_table_row_count,
        "period_control_exists": period_control_exists,
        "period_control_status": period_control_status,
        "period_control_row_count": None,
        "recommended_status": "new_period",
    }


def _deps(calls, states):
    def connect(config):
        calls.append("connect")
        return _Connection(calls)

    def check_existing(connection, period):
        calls.append(f"check_existing:{period}")
        state = dict(states.get(period, _pg_state()))
        state["periodo_informacion"] = period
        return state

    return HistoricalBatchPlannerDependencies(
        postgres_config_from_env=lambda: _Config(),
        connect_postgres=connect,
        check_existing=check_existing,
    )


def test_generates_month_end_periods_between_start_and_end():
    assert generate_month_end_periods("2016-08-31", "2016-12-31") == [
        "2016-08-31",
        "2016-09-30",
        "2016-10-31",
        "2016-11-30",
        "2016-12-31",
    ]


def test_rejects_start_period_after_end_period():
    with pytest.raises(ValueError, match="start-period"):
        generate_month_end_periods("2016-12-31", "2016-08-31")


def test_rejects_non_month_end_period():
    with pytest.raises(ValueError, match="month-end"):
        generate_month_end_periods("2016-08-30", "2016-12-31")


def test_loaded_period_maps_to_skip_existing(tmp_path):
    calls = []
    plan, _ = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        dependencies=_deps(
            calls,
            {
                "2016-08-31": _pg_state(
                    exists=True,
                    final_table_row_count=10,
                    period_control_exists=True,
                    period_control_status="loaded",
                )
            },
        ),
    )

    assert plan["periods"][0]["recommended_action"] == "skip_existing"
    assert plan["periods"][0]["blocked"] is False
    assert plan["summary"]["skip_existing"] == 1


def test_raw_missing_and_postgres_missing_maps_to_download_process_load(tmp_path):
    calls = []
    plan, _ = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        dependencies=_deps(calls, {"2016-08-31": _pg_state()}),
    )

    assert plan["periods"][0]["raw_exists"] is False
    assert plan["periods"][0]["recommended_action"] == "download_process_load"
    assert plan["summary"]["download_process_load"] == 1


def test_raw_exists_and_postgres_missing_maps_to_validate_process_load(tmp_path):
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-08-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    calls = []

    plan, _ = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=raw_root,
        output_dir=tmp_path / "outputs",
        dependencies=_deps(calls, {"2016-08-31": _pg_state()}),
    )

    assert plan["periods"][0]["raw_exists"] is True
    assert plan["periods"][0]["recommended_action"] == "validate_process_load"
    assert plan["summary"]["validate_process_load"] == 1


def test_pending_period_control_blocks(tmp_path):
    calls = []
    plan, _ = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        dependencies=_deps(
            calls,
            {
                "2016-08-31": _pg_state(
                    exists=True,
                    period_control_exists=True,
                    period_control_status="pending",
                )
            },
        ),
    )

    assert plan["periods"][0]["recommended_action"] == "blocked_existing_pending"
    assert plan["periods"][0]["blocked"] is True


def test_non_loaded_period_control_blocks(tmp_path):
    calls = []
    plan, _ = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        dependencies=_deps(
            calls,
            {
                "2016-08-31": _pg_state(
                    exists=True,
                    period_control_exists=True,
                    period_control_status="failed_load",
                )
            },
        ),
    )

    assert plan["periods"][0]["recommended_action"] == "blocked_existing_non_loaded"
    assert plan["periods"][0]["blocked"] is True


def test_partial_final_blocks(tmp_path):
    calls = []
    plan, _ = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        dependencies=_deps(
            calls,
            {
                "2016-08-31": _pg_state(
                    exists=True,
                    final_table_row_count=5,
                    period_control_exists=False,
                )
            },
        ),
    )

    assert plan["periods"][0]["recommended_action"] == "blocked_partial_final"
    assert plan["periods"][0]["blocked"] is True


def test_ambiguous_state_blocks(tmp_path):
    calls = []
    plan, _ = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        dependencies=_deps(
            calls,
            {
                "2016-08-31": _pg_state(
                    exists=True,
                    final_table_row_count=0,
                    period_control_exists=True,
                    period_control_status="loaded",
                )
            },
        ),
    )

    assert plan["periods"][0]["recommended_action"] == "blocked_inconsistent_state"
    assert plan["periods"][0]["blocked"] is True


def test_manifest_contains_read_only_flags_and_writes_file(tmp_path):
    calls = []
    plan, manifest_path = plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-09-30",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        run_id="batch_test",
        dependencies=_deps(calls, {}),
    )

    assert plan["status"] == "planned"
    assert plan["dry_run"] is True
    assert plan["writes_postgresql"] is False
    assert plan["writes_concentrado"] is False
    assert plan["writes_data_processed"] is False
    assert plan["downloads_raw"] is False
    assert plan["processes_raw"] is False
    assert plan["touches_staging_table"] is False
    assert plan["touches_final_table"] is False
    assert plan["opens_database_connection"] is True
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["period_count"] == 2


def test_dry_run_does_not_call_download_process_or_load_staging(tmp_path):
    calls = []
    plan_historical_batch(
        start_period="2016-08-31",
        end_period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs",
        dependencies=_deps(calls, {}),
    )

    assert calls == ["connect", "check_existing:2016-08-31", "close"]


def test_source_does_not_reference_concentrado_or_publish_modules():
    source = Path("src/imss_engine/historical_batch_planner.py").read_text(encoding="utf-8")

    assert "data/processed/imss_concentrado.csv" not in source
    assert "publish_insert" not in source
    assert "publish_plan" not in source
    assert "raw_compare" not in source


def test_cli_rejects_execute(capsys, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_imss_historical_batch.py",
            "--start-period",
            "2016-08-31",
            "--end-period",
            "2016-12-31",
            "--execute",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        run_imss_historical_batch.main()

    assert exc.value.code == 2
    assert "out of scope" in capsys.readouterr().err


def test_cli_prints_valid_json(capsys, monkeypatch, tmp_path):
    def fake_plan(**kwargs):
        return (
            {
                "status": "planned",
                "summary": {"download_process_load": 1},
                "periods": [{"periodo_informacion": "2016-08-31"}],
            },
            tmp_path / "outputs" / "historical_batch_plan.json",
        )

    monkeypatch.setattr(run_imss_historical_batch, "plan_historical_batch", fake_plan)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_imss_historical_batch.py",
            "--start-period",
            "2016-08-31",
            "--end-period",
            "2016-08-31",
            "--dry-run",
        ],
    )

    run_imss_historical_batch.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "planned"
    assert payload["action"] == "historical_batch_plan"
    assert payload["periods"] == [{"periodo_informacion": "2016-08-31"}]
