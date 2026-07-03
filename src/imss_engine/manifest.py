"""Run manifest helpers for local IMSS pipeline traceability."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def generate_run_id() -> str:
    """Generate a unique local run identifier."""
    return uuid4().hex


def now_utc_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def calculate_sha256(path: str | Path) -> str:
    """Calculate a SHA256 hash for a local file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_file_size_bytes(path: str | Path) -> int:
    """Return local file size in bytes."""
    return Path(path).stat().st_size


def create_manifest_base(
    *,
    config_path: str | Path,
    output_file: str | Path,
    configured_periods: list[dict] | None = None,
    audit_output_dir: str | Path | None = None,
) -> dict:
    """Create the base manifest structure for one pipeline run."""
    config = Path(config_path)
    return {
        "run_id": generate_run_id(),
        "started_at": now_utc_iso(),
        "finished_at": None,
        "status": "running",
        "config_path": str(config),
        "config_hash_sha256": calculate_sha256(config) if config.exists() else None,
        "output_file": str(output_file),
        "output_file_hash_sha256": None,
        "output_file_size_bytes": None,
        "audit_output_dir": str(audit_output_dir) if audit_output_dir is not None else None,
        "audit_status": "not_run",
        "audit_files": [],
        "audit_error": None,
        "configured_periods": configured_periods or [],
        "periods": [],
        "error": None,
    }


def add_period_result(manifest: dict, period_result: dict) -> dict:
    """Append one period result to a manifest."""
    manifest.setdefault("periods", []).append(period_result)
    return manifest


def finalize_manifest_success(
    manifest: dict,
    output_file: str | Path,
    audit_dir: str | Path | None = None,
) -> dict:
    """Mark a manifest as successful and attach final output metadata."""
    output = Path(output_file)
    manifest["finished_at"] = now_utc_iso()
    manifest["status"] = "success"
    manifest["output_file"] = str(output)
    manifest["output_file_hash_sha256"] = calculate_sha256(output) if output.exists() else None
    manifest["output_file_size_bytes"] = get_file_size_bytes(output) if output.exists() else None
    if audit_dir is not None:
        manifest["audit_output_dir"] = str(audit_dir)
    manifest["error"] = None
    return manifest


def set_audit_success(
    manifest: dict,
    audit_output_dir: str | Path,
    audit_files: list[str | Path] | None = None,
) -> dict:
    """Attach successful audit metadata to a manifest."""
    audit_dir = Path(audit_output_dir)
    manifest["audit_output_dir"] = str(audit_dir)
    manifest["audit_status"] = "success"
    manifest["audit_files"] = [str(path) for path in (audit_files or [])]
    manifest["audit_error"] = None
    return manifest


def set_audit_failure(
    manifest: dict,
    audit_output_dir: str | Path,
    error: Exception | str,
) -> dict:
    """Attach failed audit metadata to a manifest."""
    manifest["audit_output_dir"] = str(audit_output_dir)
    manifest["audit_status"] = "failed"
    manifest["audit_error"] = str(error)
    return manifest


def finalize_manifest_failure(
    manifest: dict,
    error: Exception | str,
    *,
    preserve_output_metadata: bool = False,
) -> dict:
    """Mark a manifest as failed without inventing final output metadata."""
    manifest["finished_at"] = now_utc_iso()
    manifest["status"] = "failed"
    manifest["error"] = str(error)
    if not preserve_output_metadata:
        manifest["output_file_hash_sha256"] = None
        manifest["output_file_size_bytes"] = None
    return manifest


def write_manifest(manifest: dict, output_dir: str | Path = "reports/manifests") -> Path:
    """Write a manifest JSON file and return its path."""
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"manifest_{manifest['run_id']}.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
