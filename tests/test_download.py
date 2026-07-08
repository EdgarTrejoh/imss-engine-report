import json

import pytest

from src.imss_engine.download import (
    build_raw_file_path,
    build_source_url,
    calculate_sha256,
    download_imss_period,
    validate_period,
    write_download_manifest,
)


class FakeResponse:
    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield from self.chunks


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


def test_validate_period_rejects_invalid_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        validate_period("2016-04")


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


def test_download_writes_raw_and_manifest_without_processed_dir(tmp_path):
    config = tmp_path / "config.yaml"
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "download"
    _write_config(config)

    manifest, manifest_path = download_imss_period(
        "2016-04-30",
        config_path=config,
        raw_root=raw_root,
        manifest_dir=manifest_dir,
        request_get=lambda *args, **kwargs: FakeResponse([b"a|b\n", b"1|2\n"]),
    )

    raw_path = raw_root / "2016" / "asg-2016-04-30.csv"
    assert raw_path.read_bytes() == b"a|b\n1|2\n"
    assert manifest["status"] == "success"
    assert manifest["downloaded"] is True
    assert manifest["raw_file_path"] == str(raw_path)
    assert manifest["file_size_bytes"] == raw_path.stat().st_size
    assert manifest["sha256"] == calculate_sha256(raw_path)
    assert manifest_path.exists()
    assert not (tmp_path / "data" / "processed").exists()


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
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "conflict_existing_raw_hash"
