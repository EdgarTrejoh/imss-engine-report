from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.raw_compare import compare_raw_aggregate_with_concentrado


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare one explicit IMSS raw aggregate against the concentrado CSV without writing it."
    )
    parser.add_argument("--period", required=True, help="Period to compare in YYYY-MM-DD format.")
    parser.add_argument("--aggregate-file", required=True, help="Temporary aggregate CSV to compare.")
    parser.add_argument(
        "--concentrado-file",
        default="data/processed/imss_concentrado.csv",
        help="Read-only concentrado CSV path.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/processing",
        help="Directory for raw compare manifests.",
    )
    args = parser.parse_args()

    manifest, manifest_path = compare_raw_aggregate_with_concentrado(
        args.period,
        aggregate_file=args.aggregate_file,
        concentrado_file=args.concentrado_file,
        output_dir=args.output_dir,
    )
    payload = {
        "manifest_path": str(manifest_path),
        "result": manifest,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if manifest["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
