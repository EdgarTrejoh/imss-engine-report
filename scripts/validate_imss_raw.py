from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.raw_validation import validate_imss_raw


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate one downloaded IMSS raw CSV period without processing data."
    )
    parser.add_argument("--period", required=True, help="Period to validate in YYYY-MM-DD format.")
    parser.add_argument(
        "--raw-root",
        default="data/raw/imss/asegurados",
        help="Root directory for raw IMSS asegurados files.",
    )
    parser.add_argument(
        "--manifest-dir",
        default="outputs/audit/raw_validation",
        help="Directory for local raw validation manifests.",
    )
    parser.add_argument(
        "--encoding",
        choices=("auto", "latin-1", "utf-8-sig"),
        default="auto",
        help="Raw encoding resolution mode.",
    )
    parser.add_argument("--separator", default="|", help="Expected raw file separator.")
    args = parser.parse_args()

    manifest, manifest_path = validate_imss_raw(
        args.period,
        raw_root=args.raw_root,
        manifest_dir=args.manifest_dir,
        encoding=args.encoding,
        separator=args.separator,
    )
    payload = {
        "manifest_path": str(manifest_path),
        "result": manifest,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if not manifest["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
