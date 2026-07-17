from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.single_period_pipeline import (
    execute_single_period_pipeline,
    plan_single_period_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the IMSS single-period raw-to-PostgreSQL pipeline."
    )
    parser.add_argument("--config", default="config/config.yaml", help="Config YAML path.")
    parser.add_argument("--period", default=None, help="Period to run in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Plan one period without side effects.")
    parser.add_argument("--execute", action="store_true", help="Execute one period pipeline.")
    parser.add_argument(
        "--raw-root",
        default="data/raw/imss/asegurados",
        help="Root directory for raw IMSS asegurados files.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/pipeline",
        help="Directory for pipeline manifests and aggregate outputs.",
    )
    parser.add_argument("--batch-size", type=int, default=5000, help="PostgreSQL staging batch size.")
    parser.add_argument(
        "--promotion-batch-size",
        type=int,
        default=50000,
        help="PostgreSQL staging-to-final promotion batch size.",
    )
    parser.add_argument("--chunk-size", type=int, default=100000, help="Raw CSV processing chunk size.")
    parser.add_argument("--duckdb-memory-limit", default="1GB")
    parser.add_argument("--duckdb-threads", type=int, default=2)
    parser.add_argument("--preserve-temporary-on-failure", action="store_true")
    parser.add_argument("--run-id", default=None, help="Optional explicit run_id.")
    args = parser.parse_args()

    if args.dry_run == args.execute:
        print("Use exactly one of --dry-run or --execute.", file=sys.stderr)
        raise SystemExit(2)

    try:
        if args.dry_run:
            result, manifest_path = plan_single_period_pipeline(
                config_path=args.config,
                period=args.period,
                raw_root=args.raw_root,
                output_dir=args.output_dir,
                run_id=args.run_id,
            )
        else:
            result, manifest_path = execute_single_period_pipeline(
                config_path=args.config,
                period=args.period,
                raw_root=args.raw_root,
                output_dir=args.output_dir,
                chunk_size=args.chunk_size,
                batch_size=args.batch_size,
                promotion_batch_size=args.promotion_batch_size,
                run_id=args.run_id,
                duckdb_memory_limit=args.duckdb_memory_limit,
                duckdb_threads=args.duckdb_threads,
                preserve_temporary_on_failure=args.preserve_temporary_on_failure,
            )
    except Exception as error:
        payload = {
            "status": "failed",
            "action": "failed",
            "manifest_path": None,
            "result": {
                "status": "failed",
                "action": "failed",
                "error_message": str(error),
                "writes_postgresql": False,
                "writes_concentrado": False,
                "writes_data_processed": False,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from error

    payload = {
        "status": result["status"],
        "action": result["action"],
        "manifest_path": str(manifest_path),
        "result": result,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
