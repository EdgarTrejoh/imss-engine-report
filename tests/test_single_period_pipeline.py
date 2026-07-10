from pathlib import Path

import pytest

from src.imss_engine.download import build_raw_file_path
from src.imss_engine.single_period_pipeline import (
    PipelineDependencies,
    execute_single_period_pipeline,
    plan_single_period_pipeline,
)


def _write_config(path: Path, *, mode="mes_consulta", period="2016-07-31") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "etl:",
                '  base_url: "http://datos.imss.gob.mx/sites/default/files/asg-{}.csv"',
                "  chunk_size: 400000",
                f'  mode: "{mode}"',
                f'  mes_consulta: "{period}"',
                "  periodo_consulta:",
                "    meses:",
                '      - "2016-07-31"',
                '      - "2016-08-31"',
                "  meses: []",
            ]
        ),
        encoding="utf-8",
    )
    return path


class _Config:
    is_complete = True


class _Connection:
    def __init__(self, calls):
        self.calls = calls
        self.closed = False

    def close(self):
        self.closed = True
        self.calls.append("close")


def _valid_raw(period="2016-07-31"):
    return {
        "periodo_informacion": period,
        "valid": True,
        "status": "success",
        "raw_file_path": f"raw/asg-{period}.csv",
    }


def _processing_success(path="outputs/raw_aggregate.csv"):
    return {
        "status": "success",
        "aggregate_output_path": path,
        "aggregate_rows": 1,
        "raw_processing_uses_dataframe": True,
    }


def _deps(
    calls,
    *,
    existing=False,
    validation_status="passed",
    process_status="success",
    raw_valid=True,
):
    def download(period, **kwargs):
        calls.append("download")
        return {"status": "success", "downloaded": True}, Path("download_manifest.json")

    def validate_raw(period, **kwargs):
        calls.append("validate_raw")
        if not raw_valid:
            return {
                "periodo_informacion": period,
                "valid": False,
                "status": "failed_missing_required_columns",
                "error_message": "bad raw",
            }, Path("raw_validation.json")
        return _valid_raw(period), Path("raw_validation.json")

    def process_raw(period, **kwargs):
        calls.append("process_raw")
        if process_status != "success":
            return {"status": process_status, "error_message": "processing failed"}, Path("processing.json")
        return _processing_success(), Path("processing.json")

    def connect(config):
        calls.append("connect")
        return _Connection(calls)

    def check_existing(connection, period):
        calls.append("check_existing")
        return {"periodo_informacion": period, "exists": existing}

    def register_period_control(connection, period, **kwargs):
        calls.append("register_period_control")
        return {"inserted": True, "recommended_status": "pending_registered"}

    def register_run_manifest(connection, period, run_id, manifest=None):
        calls.append("register_run_manifest")
        return {"inserted": True, "recommended_status": "run_manifest_registered"}

    def load_staging(connection, source_path, period, **kwargs):
        calls.append("load_staging")
        return {"inserted": True, "rows_inserted_staging": 1}

    def promote_staging_final(connection, period, **kwargs):
        calls.append("promote_staging_final")
        return {"inserted": True, "rows_inserted_final": 1}

    def validate_post_promotion(connection, period):
        calls.append("validate_post_promotion")
        return {"validation_status": validation_status}

    def finalize_period_control(connection, period, **kwargs):
        calls.append("finalize_period_control")
        return {"finalized": True, "writes_period_control_only": True}

    def finalize_run_manifest(connection, period, run_id):
        calls.append("finalize_run_manifest")
        return {"finalized": True, "writes_run_manifest_only": True}

    return PipelineDependencies(
        download_period=download,
        validate_raw=validate_raw,
        process_raw=process_raw,
        postgres_config_from_env=lambda: _Config(),
        connect_postgres=connect,
        check_existing=check_existing,
        register_period_control=register_period_control,
        register_run_manifest=register_run_manifest,
        load_staging=load_staging,
        promote_staging_final=promote_staging_final,
        validate_post_promotion=validate_post_promotion,
        finalize_period_control=finalize_period_control,
        finalize_run_manifest=finalize_run_manifest,
    )


def test_dry_run_does_not_call_download_processing_or_postgres(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")

    manifest, manifest_path = plan_single_period_pipeline(
        config_path=config,
        output_dir=tmp_path / "outputs" / "pipeline",
        run_id="dry_run_id",
    )

    assert manifest["status"] == "planned"
    assert manifest["action"] == "dry_run"
    assert manifest["dry_run"] is True
    assert manifest["writes_postgresql"] is False
    assert manifest["writes_concentrado"] is False
    assert manifest["writes_data_processed"] is False
    assert manifest["periodo_informacion"] == "2016-07-31"
    assert manifest_path.exists()


def test_periodo_consulta_without_period_is_blocked_for_single_period(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml", mode="periodo_consulta")

    with pytest.raises(ValueError, match="periodo_consulta"):
        plan_single_period_pipeline(config_path=config, output_dir=tmp_path / "outputs")


def test_execute_with_existing_raw_does_not_download(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-07-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    calls = []

    manifest, _ = execute_single_period_pipeline(
        config_path=config,
        period="2016-07-31",
        raw_root=raw_root,
        output_dir=tmp_path / "outputs" / "pipeline",
        dependencies=_deps(calls),
    )

    assert manifest["status"] == "success"
    assert "download" not in calls
    assert "validate_raw" in calls


def test_execute_with_missing_raw_calls_downloader(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")
    calls = []

    execute_single_period_pipeline(
        config_path=config,
        period="2016-07-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs" / "pipeline",
        dependencies=_deps(calls),
    )

    assert calls[0] == "download"


def test_raw_validation_failure_stops_before_processing_and_postgres(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-07-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    calls = []

    manifest, _ = execute_single_period_pipeline(
        config_path=config,
        period="2016-07-31",
        raw_root=raw_root,
        output_dir=tmp_path / "outputs" / "pipeline",
        dependencies=_deps(calls, raw_valid=False),
    )

    assert manifest["status"] == "failed"
    assert "validate_raw" in calls
    assert "process_raw" not in calls
    assert "connect" not in calls


def test_processing_failure_does_not_open_postgres(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-07-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    calls = []

    manifest, _ = execute_single_period_pipeline(
        config_path=config,
        period="2016-07-31",
        raw_root=raw_root,
        output_dir=tmp_path / "outputs" / "pipeline",
        dependencies=_deps(calls, process_status="failed"),
    )

    assert manifest["status"] == "failed"
    assert "process_raw" in calls
    assert "connect" not in calls


def test_existing_postgres_period_finishes_no_op_without_staging(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-07-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    calls = []

    manifest, _ = execute_single_period_pipeline(
        config_path=config,
        period="2016-07-31",
        raw_root=raw_root,
        output_dir=tmp_path / "outputs" / "pipeline",
        dependencies=_deps(calls, existing=True),
    )

    assert manifest["status"] == "success"
    assert manifest["action"] == "no_op"
    assert "check_existing" in calls
    assert "load_staging" not in calls


def test_new_period_calls_postgres_steps_in_order(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-07-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    calls = []

    manifest, _ = execute_single_period_pipeline(
        config_path=config,
        period="2016-07-31",
        raw_root=raw_root,
        output_dir=tmp_path / "outputs" / "pipeline",
        run_id="pipeline_run",
        dependencies=_deps(calls),
    )

    assert manifest["status"] == "success"
    assert manifest["action"] == "loaded"
    assert calls[calls.index("register_period_control") : calls.index("finalize_run_manifest") + 1] == [
        "register_period_control",
        "register_run_manifest",
        "load_staging",
        "promote_staging_final",
        "validate_post_promotion",
        "finalize_period_control",
        "finalize_run_manifest",
    ]


def test_failed_post_promotion_validation_does_not_finalize(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml")
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-07-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("raw", encoding="utf-8")
    calls = []

    manifest, _ = execute_single_period_pipeline(
        config_path=config,
        period="2016-07-31",
        raw_root=raw_root,
        output_dir=tmp_path / "outputs" / "pipeline",
        dependencies=_deps(calls, validation_status="failed"),
    )

    assert manifest["status"] == "failed"
    assert "validate_post_promotion" in calls
    assert "finalize_period_control" not in calls
    assert "finalize_run_manifest" not in calls


def test_pipeline_does_not_reference_concentrado_or_publish_modules():
    source = Path("src/imss_engine/single_period_pipeline.py").read_text(encoding="utf-8")

    assert "data/processed/imss_concentrado.csv" not in source
    assert "publish_insert" not in source
    assert "publish_plan" not in source
    assert "raw_compare" not in source
    assert "publish_concentrado_insert_only" not in source


def test_execute_processes_only_one_period_from_cli_override(tmp_path):
    config = _write_config(tmp_path / "config" / "config.yaml", mode="periodo_consulta")
    calls = []

    manifest, _ = execute_single_period_pipeline(
        config_path=config,
        period="2016-08-31",
        raw_root=tmp_path / "raw",
        output_dir=tmp_path / "outputs" / "pipeline",
        dependencies=_deps(calls),
    )

    assert manifest["periodo_informacion"] == "2016-08-31"
