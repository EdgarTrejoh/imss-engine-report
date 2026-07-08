import json

import pytest
import requests

from src.imss_engine.download import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_READ_TIMEOUT_SECONDS,
    build_raw_file_path,
    build_source_url,
    calculate_sha256,
    download_imss_period,
    validate_period,
    write_download_manifest,
)


class FakeResponse:
    def __init__(self, chunks, status_code=200):
        self.chunks = chunks
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error
        return None

    def iter_content(self, chunk_size):
        yield from self.chunks


class FailingResponse(FakeResponse):
    def iter_content(self, chunk_size):
        yield b"partial"
        raise RuntimeError("stream interrupted")


def _write_config(path):
    path.write_text(
        "\n".join(
            [
                "etl:",
                '  base_url: "http://example.test/asg-{}.csv"',
            ]
        ),
        encoding="utf-8",
    )


def test_validate_period_accepts_real_date():
    assert validate_period("2016-04-30") == "2016-04-30"


def test_validate_period_rejects_invalid_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        validate_period("2016-04")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        validate_period("abcd-01-01")


def test_validate_period_rejects_impossible_date():
    with pytest.raises(ValueError, match="valid date"):
        validate_period("2016-02-31")


def test_build_source_url_uses_configured_pattern():
    assert (
        build_source_url("http://example.test/asg-{}.csv", "2016-04-30")
        == "http://example.test/asg-2016-04-30.csv"
    )


def test_build_raw_file_path_uses_year_partition(tmp_path):
    assert build_raw_file_path("2016-04-30", tmp_path) == tmp_path / "2016" / "asg-2016-04-30.csv"


def test_calculate_sha256_is_stable(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_bytes(b"abc")

    assert calculate_sha256(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_download_defaults_are_stable():
    assert DEFAULT_MAX_ATTEMPTS == 3
    assert DEFAULT_CONNECT_TIMEOUT_SECONDS == 15
    assert DEFAULT_READ_TIMEOUT_SECONDS == 120


def test_download_writes_raw_and_manifest_without_processed_dir(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)

    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse([b"a|b\n", b"1|2\n"])

    manifest, manifest_path = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=fake_get,
    )

    raw_path = raw_root / "2016" / "asg-2016-04-30.csv"
    assert raw_path.read_bytes() == b"a|b\n1|2\n"
    assert manifest["status"] == "success"
    assert manifest["downloaded"] is True
    assert manifest["raw_file_path"] == str(raw_path)
    assert manifest["file_size_bytes"] == raw_path.stat().st_size
    assert manifest["sha256"] == calculate_sha256(raw_path)
    assert manifest["attempts"] == 1
    assert manifest["max_attempts"] == 3
    assert manifest["timeouts"] == {"connect_seconds": 15, "read_seconds": 120}
    assert manifest["retry_errors"] == []
    assert calls[0]["timeout"] == (15, 120)
    assert manifest_path.exists()
    assert not (tmp_path / "data" / "processed").exists()


def test_download_retries_retryable_timeout_then_succeeds(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)
    attempts = []
    sleeps = []

    def fake_get(*args, **kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise requests.Timeout("temporary timeout")
        return FakeResponse([b"ok\n"])

    manifest, _ = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=fake_get,
        sleep_func=lambda seconds: sleeps.append(seconds),
    )

    assert manifest["status"] == "success"
    assert manifest["downloaded"] is True
    assert manifest["attempts"] == 2
    assert len(manifest["retry_errors"]) == 1
    assert manifest["retry_errors"][0]["error_type"] == "Timeout"
    assert manifest["retry_errors"][0]["retryable"] is True
    assert sleeps == [2]


def test_download_retries_retryable_http_503_then_succeeds(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)
    attempts = 0

    def fake_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return FakeResponse([], status_code=503)
        return FakeResponse([b"ok\n"])

    manifest, _ = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=fake_get,
        sleep_func=lambda seconds: None,
    )

    assert manifest["status"] == "success"
    assert manifest["attempts"] == 2
    assert manifest["retry_errors"][0]["status_code"] == 503
    assert manifest["retry_errors"][0]["retryable"] is True


def test_download_fails_after_retryable_errors_are_exhausted(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)

    manifest, _ = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError("offline")),
        sleep_func=lambda seconds: None,
    )

    raw_path = raw_root / "2016" / "asg-2016-04-30.csv"
    partial_path = raw_root / "2016" / "asg-2016-04-30.csv.part"
    assert manifest["status"] == "failed"
    assert manifest["downloaded"] is False
    assert manifest["attempts"] == 3
    assert len(manifest["retry_errors"]) == 3
    assert all(error["retryable"] is True for error in manifest["retry_errors"])
    assert not raw_path.exists()
    assert not partial_path.exists()


def test_download_does_not_retry_http_404(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)
    attempts = 0

    def fake_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        return FakeResponse([], status_code=404)

    manifest, _ = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=fake_get,
        sleep_func=lambda seconds: pytest.fail("404 should not back off"),
    )

    assert attempts == 1
    assert manifest["status"] == "failed"
    assert manifest["attempts"] == 1
    assert manifest["retry_errors"][0]["status_code"] == 404
    assert manifest["retry_errors"][0]["retryable"] is False


def test_existing_raw_with_same_manifest_hash_is_not_downloaded(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)
    raw_path = raw_root / "2016" / "asg-2016-04-30.csv"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"existing")
    sha256 = calculate_sha256(raw_path)
    write_download_manifest(
        {
            "run_id": "download_20260707T000000Z_samehash",
            "periodo_informacion": "2016-04-30",
            "sha256": sha256,
        },
        manifest_dir,
    )

    manifest, _ = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=lambda *args, **kwargs: pytest.fail("download should not run"),
    )

    assert manifest["status"] == "already_exists"
    assert manifest["downloaded"] is False
    assert manifest["sha256"] == sha256
    assert manifest["attempts"] == 0
    assert manifest["retry_errors"] == []


def test_existing_raw_with_different_manifest_hash_is_not_overwritten(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)
    raw_path = raw_root / "2016" / "asg-2016-04-30.csv"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"existing")
    write_download_manifest(
        {
            "run_id": "download_20260707T000000Z_diffhash",
            "periodo_informacion": "2016-04-30",
            "sha256": "0" * 64,
        },
        manifest_dir,
    )

    manifest, manifest_path = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=lambda *args, **kwargs: pytest.fail("download should not run"),
    )

    assert raw_path.read_bytes() == b"existing"
    assert manifest["status"] == "conflict_existing_raw_hash"
    assert manifest["downloaded"] is False
    assert manifest["attempts"] == 0
    assert manifest["retry_errors"] == []
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "conflict_existing_raw_hash"


def test_existing_raw_without_manifest_hash_is_not_downloaded(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)
    raw_path = raw_root / "2016" / "asg-2016-04-30.csv"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"existing")

    manifest, _ = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=lambda *args, **kwargs: pytest.fail("download should not run"),
    )

    assert raw_path.read_bytes() == b"existing"
    assert manifest["status"] == "existing_raw_without_manifest"
    assert manifest["downloaded"] is False
    assert manifest["attempts"] == 0
    assert manifest["retry_errors"] == []


def test_failed_download_removes_partial_and_writes_error_manifest(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)

    manifest, manifest_path = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=lambda *args, **kwargs: FailingResponse([]),
    )

    raw_path = raw_root / "2016" / "asg-2016-04-30.csv"
    partial_path = raw_root / "2016" / "asg-2016-04-30.csv.part"
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert not raw_path.exists()
    assert not partial_path.exists()
    assert manifest["status"] == "failed"
    assert manifest["downloaded"] is False
    assert manifest["partial_file_path"] == str(partial_path)
    assert manifest["partial_file_exists"] is False
    assert manifest["partial_file_removed"] is True
    assert saved_manifest["status"] == "failed"
    assert saved_manifest["partial_file_removed"] is True
