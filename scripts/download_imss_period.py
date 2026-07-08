from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.download import download_imss_period


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download one IMSS raw CSV period with local manifest evidence."
    )
    parser.add_argument("--period", required=True, help="Period to download in YYYY-MM-DD format.")
    parser.add_argument("--config", default=None, help="Optional config YAML path.")
    parser.add_argument(
        "--raw-root",
        default="data/raw/imss/asegurados",
        help="Root directory for raw IMSS asegurados files.",
    )
    parser.add_argument(
        "--manifest-dir",
        default="outputs/audit/download",
        help="Directory for local download manifests.",
    )
    args = parser.parse_args()

    manifest, manifest_path = download_imss_period(
        args.period,
        config_path=args.config,
        raw_root=args.raw_root,
        manifest_dir=args.manifest_dir,
    )
    payload = {
        "manifest_path": str(manifest_path),
        "result": manifest,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if manifest["status"] in {"failed", "conflict_existing_raw_hash", "existing_raw_without_manifest"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
