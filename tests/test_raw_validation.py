import json

import pytest

from src.imss_engine.download import build_raw_file_path, calculate_sha256
from src.imss_engine.raw_encoding import RawEncodingOrSchemaError, resolve_raw_encoding
from src.imss_engine.raw_validation import REQUIRED_RAW_DIMENSION_COLUMNS, validate_imss_raw
from src.imss_engine.schema import CRITICAL_METRIC_COLUMNS


def _write_raw(raw_root, period, header, body="1|2\n", encoding="latin-1"):
    path = build_raw_file_path(period, raw_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{header}\n{body}", encoding=encoding)
    return path


def _valid_header():
    return "|".join(REQUIRED_RAW_DIMENSION_COLUMNS + CRITICAL_METRIC_COLUMNS)


def test_validate_raw_accepts_valid_period_and_file(tmp_path):
    raw_root = tmp_path / "raw"
    manifest_dir = tmp_path / "outputs" / "audit" / "raw_validation"
    raw_path = _write_raw(raw_root, "2016-06-30", _valid_header())

    manifest, manifest_path = validate_imss_raw(
        "2016-06-30",
        raw_root=raw_root,
        manifest_dir=manifest_dir,
    )

    assert manifest["status"] == "success"
    assert manifest["valid"] is True
    assert manifest["raw_file_path"] == str(raw_path)
    assert manifest["file_size_bytes"] == raw_path.stat().st_size
    assert manifest["sha256"] == calculate_sha256(raw_path)
    assert manifest["columns_detected"] == list(REQUIRED_RAW_DIMENSION_COLUMNS + CRITICAL_METRIC_COLUMNS)
    assert manifest["missing_required_columns"] == []
    assert manifest["encoding_requested"] == "auto"
    assert manifest["encoding_detected"] == "latin-1"
    assert manifest["encoding_candidates_tried"] == ["utf-8-sig", "latin-1"]
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["status"] == "success"
    assert not (tmp_path / "data" / "processed").exists()


def test_validate_raw_rejects_invalid_period_format(tmp_path):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        validate_imss_raw("2016-06", raw_root=tmp_path / "raw", manifest_dir=tmp_path / "manifests")


def test_validate_raw_rejects_impossible_period_date(tmp_path):
    with pytest.raises(ValueError, match="valid date"):
        validate_imss_raw("2016-02-31", raw_root=tmp_path / "raw", manifest_dir=tmp_path / "manifests")


def test_validate_raw_reports_missing_raw(tmp_path):
    manifest, _ = validate_imss_raw(
        "2016-06-30",
        raw_root=tmp_path / "raw",
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["status"] == "failed_missing_raw"
    assert manifest["valid"] is False
    assert manifest["raw_exists"] is False


def test_validate_raw_reports_empty_raw(tmp_path):
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-06-30", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"")

    manifest, _ = validate_imss_raw(
        "2016-06-30",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["status"] == "failed_empty_raw"
    assert manifest["valid"] is False
    assert manifest["file_size_bytes"] == 0


def test_validate_raw_reports_invalid_separator(tmp_path):
    raw_root = tmp_path / "raw"
    _write_raw(raw_root, "2016-06-30", ",".join(CRITICAL_METRIC_COLUMNS), body="1,2\n")

    manifest, _ = validate_imss_raw(
        "2016-06-30",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["status"] == "failed_invalid_separator"
    assert manifest["valid"] is False
    assert manifest["columns_detected"] == []


def test_validate_raw_reports_unreadable_encoding(tmp_path):
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2016-06-30", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"\xff\xfe\xfa|bad\n")

    manifest, _ = validate_imss_raw(
        "2016-06-30",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
        encoding="utf-8-sig",
    )

    assert manifest["status"] == "failed_unreadable_raw"
    assert manifest["valid"] is False


def test_validate_raw_reports_missing_required_columns(tmp_path):
    raw_root = tmp_path / "raw"
    partial_header = "|".join(REQUIRED_RAW_DIMENSION_COLUMNS + CRITICAL_METRIC_COLUMNS[:-2])
    _write_raw(raw_root, "2016-06-30", partial_header)

    manifest, _ = validate_imss_raw(
        "2016-06-30",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["status"] == "failed_missing_required_columns"
    assert manifest["valid"] is False
    assert manifest["missing_required_columns"] == list(CRITICAL_METRIC_COLUMNS[-2:])


def test_validate_raw_reports_missing_required_dimension(tmp_path):
    raw_root = tmp_path / "raw"
    columns = [column for column in REQUIRED_RAW_DIMENSION_COLUMNS + CRITICAL_METRIC_COLUMNS if column != "cve_entidad"]
    _write_raw(raw_root, "2016-06-30", "|".join(columns))

    manifest, _ = validate_imss_raw(
        "2016-06-30",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["status"] == "failed_missing_required_columns"
    assert manifest["valid"] is False
    assert "cve_entidad" in manifest["missing_required_columns"]


def test_validate_raw_detects_utf8_bom_without_corrupting_header(tmp_path):
    raw_root = tmp_path / "raw"
    _write_raw(
        raw_root,
        "2025-01-31",
        _valid_header(),
        encoding="utf-8-sig",
    )

    manifest, _ = validate_imss_raw(
        "2025-01-31",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["valid"] is True
    assert manifest["encoding_detected"] == "utf-8-sig"
    assert "cve_delegacion" in manifest["columns_detected"]
    assert "tamaño_patron" in manifest["columns_detected"]


def test_validate_raw_detects_utf8_without_bom_as_utf8_sig(tmp_path):
    raw_root = tmp_path / "raw"
    _write_raw(raw_root, "2025-02-28", _valid_header(), encoding="utf-8")

    manifest, _ = validate_imss_raw(
        "2025-02-28",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["valid"] is True
    assert manifest["encoding_detected"] == "utf-8-sig"


def test_validate_raw_empty_header_fails_explicitly(tmp_path):
    raw_root = tmp_path / "raw"
    raw_path = build_raw_file_path("2025-03-31", raw_root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"\n1|2\n")

    manifest, _ = validate_imss_raw(
        "2025-03-31",
        raw_root=raw_root,
        manifest_dir=tmp_path / "manifests",
    )

    assert manifest["status"] == "failed_empty_header"
    assert manifest["encoding_detected"] is None
    assert manifest["candidate_diagnostics"]


def test_forced_wrong_encoding_does_not_fallback(tmp_path):
    raw_root = tmp_path / "raw"
    raw_path = _write_raw(
        raw_root,
        "2025-04-30",
        _valid_header(),
        encoding="utf-8-sig",
    )

    with pytest.raises(RawEncodingOrSchemaError) as exc:
        resolve_raw_encoding(raw_path, encoding="latin-1")

    assert exc.value.resolution.encoding_candidates_tried == ["latin-1"]
    assert exc.value.resolution.encoding_detected is None


def test_unsupported_forced_encoding_is_rejected(tmp_path):
    raw_root = tmp_path / "raw"
    raw_path = _write_raw(raw_root, "2025-05-31", _valid_header())

    with pytest.raises(ValueError, match="Unsupported raw encoding"):
        resolve_raw_encoding(raw_path, encoding="utf-16")
