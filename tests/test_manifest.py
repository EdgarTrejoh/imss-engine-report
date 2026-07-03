from __future__ import annotations

import json

from src.imss_engine.manifest import (
    calculate_sha256,
    create_manifest_base,
    finalize_manifest_failure,
    finalize_manifest_success,
    generate_run_id,
    get_file_size_bytes,
    set_audit_failure,
    set_audit_success,
    write_manifest,
)


def test_generate_run_id_produces_non_empty_value():
    assert generate_run_id()


def test_calculate_sha256_is_stable_for_small_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"hello\n")

    assert calculate_sha256(path) == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
    assert get_file_size_bytes(path) == 6


def test_write_manifest_writes_valid_json(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("etl: {}\n", encoding="utf-8")
    manifest = create_manifest_base(config_path=config, output_file=tmp_path / "output.csv")

    path = write_manifest(manifest, tmp_path / "manifests")

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["run_id"] == manifest["run_id"]
    assert loaded["status"] == "running"
    assert loaded["audit_status"] == "not_run"
    assert loaded["audit_files"] == []


def test_success_manifest_includes_output_hash_and_size(tmp_path):
    config = tmp_path / "config.yaml"
    output = tmp_path / "output.csv"
    config.write_text("etl: {}\n", encoding="utf-8")
    output.write_text("periodo,ta\n2026-01-31,1\n", encoding="utf-8")

    manifest = create_manifest_base(config_path=config, output_file=output)
    finalize_manifest_success(manifest, output)

    assert manifest["status"] == "success"
    assert manifest["output_file"] == str(output)
    assert manifest["output_file_hash_sha256"] == calculate_sha256(output)
    assert manifest["output_file_size_bytes"] == output.stat().st_size


def test_failure_manifest_does_not_invent_missing_output_hash(tmp_path):
    config = tmp_path / "config.yaml"
    output = tmp_path / "missing.csv"
    config.write_text("etl: {}\n", encoding="utf-8")

    manifest = create_manifest_base(config_path=config, output_file=output)
    finalize_manifest_failure(manifest, RuntimeError("boom"))

    assert manifest["status"] == "failed"
    assert manifest["error"] == "boom"
    assert manifest["output_file_hash_sha256"] is None
    assert manifest["output_file_size_bytes"] is None


def test_manifest_records_audit_success(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("etl: {}\n", encoding="utf-8")
    manifest = create_manifest_base(config_path=config, output_file=tmp_path / "output.csv")

    set_audit_success(manifest, tmp_path / "audits" / manifest["run_id"], ["summary_general.csv"])

    assert manifest["audit_status"] == "success"
    assert manifest["audit_files"] == ["summary_general.csv"]
    assert manifest["audit_error"] is None


def test_manifest_records_audit_failure(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("etl: {}\n", encoding="utf-8")
    manifest = create_manifest_base(config_path=config, output_file=tmp_path / "output.csv")

    set_audit_failure(manifest, tmp_path / "audits" / manifest["run_id"], "audit boom")

    assert manifest["audit_status"] == "failed"
    assert manifest["audit_error"] == "audit boom"
