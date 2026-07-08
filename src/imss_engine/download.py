"""Controlled IMSS raw CSV downloader with local manifest evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

import requests
import yaml


PERIOD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEFAULT_CONFIG_PATHS = (Path("config/config.yaml"), Path("config.yaml"))
DEFAULT_RAW_ROOT = Path("data/raw/imss/asegurados")
DEFAULT_MANIFEST_DIR = Path("outputs/audit/download")


def validate_period(period: str) -> str:
    """Validate and return a YYYY-MM-DD IMSS period string."""
    if not isinstance(period, str) or not PERIOD_RE.match(period):
        raise ValueError("period must be a string in YYYY-MM-DD format")
    return period


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def generate_run_id() -> str:
    return f"download_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"


def read_etl_config(config_path: str | Path | None = None) -> tuple[dict, Path]:
    """Read the ETL config from config/config.yaml or fallback config.yaml."""
    paths = (Path(config_path),) if config_path is not None else DEFAULT_CONFIG_PATHS
    for path in paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                config = yaml.safe_load(file) or {}
            return config["etl"], path
    searched = ", ".join(str(path) for path in paths)
    raise FileNotFoundError(f"No config file found. Searched: {searched}")


def build_source_url(base_url: str, period: str) -> str:
    validate_period(period)
    return base_url.format(period)


def build_raw_file_path(period: str, raw_root: str | Path = DEFAULT_RAW_ROOT) -> Path:
    validate_period(period)
    year = period[:4]
    return Path(raw_root) / year / f"asg-{period}.csv"


def calculate_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_file_size_bytes(path: str | Path) -> int:
    return Path(path).stat().st_size


def _manifest_path(manifest_dir: str | Path, run_id: str, period: str) -> Path:
    safe_period = validate_period(period)
    return Path(manifest_dir) / f"{run_id}_{safe_period}.json"


def write_download_manifest(
    manifest: dict,
    manifest_dir: str | Path = DEFAULT_MANIFEST_DIR,
) -> Path:
    output_dir = Path(manifest_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path(output_dir, manifest["run_id"], manifest["periodo_informacion"])
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _candidate_manifest_paths(manifest_dir: str | Path, period: str) -> list[Path]:
    validate_period(period)
    directory = Path(manifest_dir)
    if not directory.exists():
        return []
    return sorted(
        directory.glob(f"download_*_{period}.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def latest_manifest_sha256(manifest_dir: str | Path, period: str) -> str | None:
    for path in _candidate_manifest_paths(manifest_dir, period):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        sha256 = payload.get("sha256")
        if sha256:
            return str(sha256)
    return None


def create_download_manifest_base(
    *,
    run_id: str,
    period: str,
    source_url: str,
    raw_file_path: str | Path,
    file_exists_before: bool,
    started_at: str,
) -> dict:
    return {
        "run_id": run_id,
        "mode": "download_imss_period",
        "periodo_informacion": period,
        "source_url": source_url,
        "raw_file_path": str(raw_file_path),
        "file_exists_before": file_exists_before,
        "downloaded": False,
        "file_size_bytes": None,
        "sha256": None,
        "status": None,
        "error_message": None,
        "started_at": started_at,
        "finished_at": None,
    }


def _iter_response_content(response, chunk_size: int) -> Iterator[bytes]:
    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:
            yield chunk


def _download_to_partial(
    *,
    source_url: str,
    partial_path: Path,
    request_get: Callable = requests.get,
    chunk_size: int = 1024 * 1024,
) -> None:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    with request_get(source_url, headers=headers, stream=True) as response:
        response.raise_for_status()
        with partial_path.open("wb") as file:
            for chunk in _iter_response_content(response, chunk_size):
                file.write(chunk)


def download_imss_period(
    period: str,
    *,
    config_path: str | Path | None = None,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    manifest_dir: str | Path = DEFAULT_MANIFEST_DIR,
    request_get: Callable = requests.get,
    expected_sha256: str | None = None,
) -> tuple[dict, Path]:
    """Download one IMSS period as raw CSV and write a local manifest."""
    period = validate_period(period)
    etl_config, resolved_config_path = read_etl_config(config_path)
    source_url = build_source_url(etl_config["base_url"], period)
    raw_file_path = build_raw_file_path(period, raw_root)
    file_exists_before = raw_file_path.exists()
    started_at = now_utc_iso()
    run_id = generate_run_id()
    manifest = create_download_manifest_base(
        run_id=run_id,
        period=period,
        source_url=source_url,
        raw_file_path=raw_file_path,
        file_exists_before=file_exists_before,
        started_at=started_at,
    )
    manifest["config_path"] = str(resolved_config_path)

    try:
        if raw_file_path.exists():
            current_hash = calculate_sha256(raw_file_path)
            known_hash = expected_sha256 or latest_manifest_sha256(manifest_dir, period)
            manifest["file_size_bytes"] = get_file_size_bytes(raw_file_path)
            manifest["sha256"] = current_hash
            if known_hash and current_hash == known_hash:
                manifest["status"] = "already_exists"
                manifest["error_message"] = None
            elif known_hash and current_hash != known_hash:
                manifest["status"] = "conflict_existing_raw_hash"
                manifest["error_message"] = "Existing raw file hash differs from manifest hash; not overwritten."
            else:
                manifest["status"] = "existing_raw_without_manifest"
                manifest["error_message"] = "Existing raw file has no prior manifest hash; not overwritten."
            manifest["finished_at"] = now_utc_iso()
            return manifest, write_download_manifest(manifest, manifest_dir)

        raw_file_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = raw_file_path.with_suffix(raw_file_path.suffix + ".part")
        if partial_path.exists():
            raise FileExistsError(f"Partial download already exists: {partial_path}")

        _download_to_partial(
            source_url=source_url,
            partial_path=partial_path,
            request_get=request_get,
        )
        os.replace(partial_path, raw_file_path)
        manifest["downloaded"] = True
        manifest["file_size_bytes"] = get_file_size_bytes(raw_file_path)
        manifest["sha256"] = calculate_sha256(raw_file_path)
        manifest["status"] = "success"
        manifest["finished_at"] = now_utc_iso()
        return manifest, write_download_manifest(manifest, manifest_dir)
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error_message"] = str(error)
        manifest["finished_at"] = now_utc_iso()
        return manifest, write_download_manifest(manifest, manifest_dir)


def download_sources() -> None:
    """Legacy placeholder retained for import compatibility."""
    raise NotImplementedError("Use scripts/download_imss_period.py for controlled raw downloads.")
