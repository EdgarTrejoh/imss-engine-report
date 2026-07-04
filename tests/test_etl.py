import pandas as pd
import sys
from pathlib import Path
import importlib
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Importing etl_imss must not trigger downloads or pipeline execution.
import etl_imss
from etl_imss import get_temp_output_path, periodo_from_url, run_concentrado_workflow
from src.imss_engine.manifest import create_manifest_base
from src.imss_engine.audit import normalizar_serie
from src.imss_engine.aggregate import aggregate_imss_chunk

def test_periodo_from_url():
    """Prueba que el extractor de periodo por URL funcione correctamente"""
    url_valida = "http://datos.imss.gob.mx/sites/default/files/asg-2021-09-30.csv"
    assert periodo_from_url(url_valida) == "2021-09-30"
    
    url_invalida = "http://datos.imss.gob.mx/sites/default/files/asg-sin-fecha.csv"
    assert periodo_from_url(url_invalida) == "0000-00-00"

def test_normalizar_serie():
    """Prueba la normalización de strings de auditoría"""
    datos = pd.Series(["  espacios ", "texto", "", "NAN", "NONE", "Ok  "])
    resultado = normalizar_serie(datos)
    
    assert resultado.iloc[0] == "ESPACIOS"
    assert resultado.iloc[1] == "TEXTO"
    assert pd.isna(resultado.iloc[2])
    assert pd.isna(resultado.iloc[3])
    assert pd.isna(resultado.iloc[4])
    assert resultado.iloc[5] == "OK"


def test_importing_etl_imss_does_not_call_network(monkeypatch):
    def fail_get(*args, **kwargs):
        raise AssertionError("Importing etl_imss must not call network")

    monkeypatch.setattr(etl_imss.requests, "get", fail_get)
    importlib.reload(etl_imss)


def test_run_urls_with_staging_replaces_final_only_after_success(tmp_path, monkeypatch):
    final_output = tmp_path / "imss_output.csv"

    def fake_procesar_url(url, first_file):
        mode = "w" if first_file else "a"
        header = "periodo,ta\n" if first_file else ""
        with Path(etl_imss.OUTPUT_FILE).open(mode, encoding="utf-8") as file:
            file.write(f"{header}{periodo_from_url(url)},1\n")
        return True

    monkeypatch.setattr(etl_imss, "procesar_url", fake_procesar_url)

    etl_imss.run_urls_with_staging(
        [
            "http://example.local/asg-2026-01-31.csv",
            "http://example.local/asg-2026-05-31.csv",
        ],
        final_output,
    )

    assert final_output.read_text(encoding="utf-8") == (
        "periodo,ta\n"
        "2026-01-31,1\n"
        "2026-05-31,1\n"
    )
    assert not get_temp_output_path(final_output).exists()


def test_run_urls_with_staging_keeps_existing_final_when_period_fails(tmp_path, monkeypatch):
    final_output = tmp_path / "imss_output.csv"
    final_output.write_text("old final\n", encoding="utf-8")

    def fake_procesar_url(url, first_file):
        with Path(etl_imss.OUTPUT_FILE).open("w", encoding="utf-8") as file:
            file.write("partial tmp\n")
        raise RuntimeError("simulated period failure")

    monkeypatch.setattr(etl_imss, "procesar_url", fake_procesar_url)

    try:
        etl_imss.run_urls_with_staging(["http://example.local/asg-2026-01-31.csv"], final_output)
    except RuntimeError as exc:
        assert "simulated period failure" in str(exc)
    else:
        raise AssertionError("Expected staging run to fail")

    assert final_output.read_text(encoding="utf-8") == "old final\n"
    assert not get_temp_output_path(final_output).exists()


def test_run_urls_with_staging_writes_success_manifest(tmp_path, monkeypatch):
    final_output = tmp_path / "imss_output.csv"
    config = tmp_path / "config.yaml"
    manifest_dir = tmp_path / "manifests"
    audit_base_dir = tmp_path / "audits"
    config.write_text("etl: {}\n", encoding="utf-8")
    manifest = create_manifest_base(
        config_path=config,
        output_file=final_output,
        configured_periods=[
            {
                "periodo_informacion": "2026-01-31",
                "source_url": "http://example.local/asg-2026-01-31.csv",
            }
        ],
    )

    def fake_procesar_url(url, first_file):
        with Path(etl_imss.OUTPUT_FILE).open("w", encoding="utf-8") as file:
            file.write("periodo,ta\n2026-01-31,1\n")
        return {
            "periodo_informacion": periodo_from_url(url),
            "source_url": url,
            "status": "success",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00",
            "rows_read": 1,
            "rows_processed": 1,
            "columns_detected": ["periodo", "ta"],
            "error": None,
        }

    monkeypatch.setattr(etl_imss, "procesar_url", fake_procesar_url)

    def fake_audit_runner(csv_path, output_dir):
        audit_file = Path(output_dir) / "summary_general.csv"
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        audit_file.write_text("metric,value\nfilas,1\n", encoding="utf-8")
        return {"summary_general": audit_file}

    etl_imss.run_urls_with_staging(
        ["http://example.local/asg-2026-01-31.csv"],
        final_output,
        manifest=manifest,
        manifest_output_dir=manifest_dir,
        audit_runner=fake_audit_runner,
        audit_base_dir=audit_base_dir,
    )

    manifest_files = list(manifest_dir.glob("manifest_*.json"))
    assert len(manifest_files) == 1
    loaded = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    assert loaded["status"] == "success"
    assert loaded["output_file_hash_sha256"]
    assert loaded["output_file_size_bytes"] == final_output.stat().st_size
    assert loaded["periods"][0]["rows_read"] == 1
    assert loaded["audit_status"] == "success"
    assert loaded["audit_output_dir"] == str(audit_base_dir / loaded["run_id"])
    assert loaded["audit_files"] == ["summary_general.csv"]


def test_run_urls_with_staging_writes_failed_manifest_and_preserves_final(tmp_path, monkeypatch):
    final_output = tmp_path / "imss_output.csv"
    config = tmp_path / "config.yaml"
    manifest_dir = tmp_path / "manifests"
    final_output.write_text("old final\n", encoding="utf-8")
    config.write_text("etl: {}\n", encoding="utf-8")
    manifest = create_manifest_base(config_path=config, output_file=final_output)

    def fake_procesar_url(url, first_file):
        with Path(etl_imss.OUTPUT_FILE).open("w", encoding="utf-8") as file:
            file.write("partial tmp\n")
        raise RuntimeError("simulated manifest failure")

    monkeypatch.setattr(etl_imss, "procesar_url", fake_procesar_url)

    try:
        etl_imss.run_urls_with_staging(
            ["http://example.local/asg-2026-01-31.csv"],
            final_output,
            manifest=manifest,
            manifest_output_dir=manifest_dir,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected staging run to fail")

    manifest_files = list(manifest_dir.glob("manifest_*.json"))
    assert len(manifest_files) == 1
    loaded = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    assert loaded["status"] == "failed"
    assert "simulated manifest failure" in loaded["error"]
    assert loaded["periods"][0]["status"] == "failed"
    assert loaded["output_file_hash_sha256"] is None
    assert loaded["output_file_size_bytes"] is None
    assert loaded["audit_status"] == "not_run"
    assert final_output.read_text(encoding="utf-8") == "old final\n"


def test_run_urls_with_staging_writes_failed_manifest_when_audit_fails(tmp_path, monkeypatch):
    final_output = tmp_path / "imss_output.csv"
    config = tmp_path / "config.yaml"
    manifest_dir = tmp_path / "manifests"
    audit_base_dir = tmp_path / "audits"
    config.write_text("etl: {}\n", encoding="utf-8")
    manifest = create_manifest_base(config_path=config, output_file=final_output)

    def fake_procesar_url(url, first_file):
        with Path(etl_imss.OUTPUT_FILE).open("w", encoding="utf-8") as file:
            file.write("periodo,ta\n2026-01-31,1\n")
        return {
            "periodo_informacion": periodo_from_url(url),
            "source_url": url,
            "status": "success",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00",
            "rows_read": 1,
            "rows_processed": 1,
            "columns_detected": ["periodo", "ta"],
            "error": None,
        }

    def fake_audit_runner(csv_path, output_dir):
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(etl_imss, "procesar_url", fake_procesar_url)

    try:
        etl_imss.run_urls_with_staging(
            ["http://example.local/asg-2026-01-31.csv"],
            final_output,
            manifest=manifest,
            manifest_output_dir=manifest_dir,
            audit_runner=fake_audit_runner,
            audit_base_dir=audit_base_dir,
        )
    except RuntimeError as exc:
        assert "simulated audit failure" in str(exc)
    else:
        raise AssertionError("Expected audit failure to propagate")

    manifest_files = list(manifest_dir.glob("manifest_*.json"))
    assert len(manifest_files) == 1
    loaded = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    assert final_output.exists()
    assert loaded["status"] == "failed"
    assert loaded["audit_status"] == "failed"
    assert loaded["audit_output_dir"] == str(audit_base_dir / loaded["run_id"])
    assert "simulated audit failure" in loaded["audit_error"]
    assert loaded["output_file_hash_sha256"]
    assert loaded["output_file_size_bytes"] == final_output.stat().st_size


def test_periodo_consulta_continues_after_one_period_failure(tmp_path, load_fixture):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("etl: {}\n", encoding="utf-8")
    concentrado = tmp_path / "imss_concentrado.csv"
    manifest_dir = tmp_path / "manifests"
    etl_config = {
        "base_url": "http://example.local/asg-{}.csv",
        "mode": "periodo_consulta",
        "periodo_consulta": {"meses": ["2026-01-31", "2026-02-28"]},
        "concentrado_file": str(concentrado),
    }

    def fake_processor(url):
        period = periodo_from_url(url)
        if period == "2026-02-28":
            raise RuntimeError("simulated processing failure")
        df = load_fixture("imss_sample_actual.csv")
        df["periodo_informacion"] = period
        return aggregate_imss_chunk(df)

    manifest = run_concentrado_workflow(
        etl_config,
        config_path,
        process_period_func=fake_processor,
        manifest_output_dir=manifest_dir,
    )

    assert manifest["status"] == "completed_with_warnings"
    assert manifest["periods_loaded"] == ["2026-01-31"]
    assert manifest["periods_failed"] == ["2026-02-28"]
    assert concentrado.exists()
    assert list(manifest_dir.glob("manifest_*.json"))


def test_mes_consulta_workflow_processes_only_configured_month(tmp_path, load_fixture):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("etl: {}\n", encoding="utf-8")
    concentrado = tmp_path / "imss_concentrado.csv"
    etl_config = {
        "base_url": "http://example.local/asg-{}.csv",
        "mode": "mes_consulta",
        "mes_consulta": "2026-05-31",
        "concentrado_file": str(concentrado),
    }
    seen_urls = []

    def fake_processor(url):
        seen_urls.append(url)
        period = periodo_from_url(url)
        df = load_fixture("imss_sample_actual.csv")
        df["periodo_informacion"] = period
        return aggregate_imss_chunk(df)

    manifest = run_concentrado_workflow(
        etl_config,
        config_path,
        process_period_func=fake_processor,
        manifest_output_dir=tmp_path / "manifests",
    )

    assert seen_urls == ["http://example.local/asg-2026-05-31.csv"]
    assert manifest["run_mode"] == "mes_consulta"
    assert manifest["periods_loaded"] == ["2026-05-31"]
    assert concentrado.exists()
