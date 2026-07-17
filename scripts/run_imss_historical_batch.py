from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.historical_batch_planner import (
    execute_historical_batch,
    plan_historical_batch,
    resolve_historical_batch_config,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan or execute bounded historical IMSS single-period pipeline work."
    )
    parser.add_argument("--config", default="config/config.yaml", help="Config YAML path.")
    parser.add_argument("--start-period", default=None, help="Inclusive month-end start period.")
    parser.add_argument("--end-period", default=None, help="Inclusive month-end end period.")
    parser.add_argument("--dry-run", action="store_true", help="Generate a dry-run batch plan.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute a bounded historical batch by delegating to the single-period pipeline.",
    )
    parser.add_argument("--max-periods", type=int, default=None, help="Maximum periods to execute. Required for --execute.")
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        default=None,
        help="Stop after the first failed period. Required behavior for PR #42.",
    )
    parser.add_argument(
        "--raw-root",
        default=None,
        help="Root directory for raw IMSS asegurados files.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for historical batch plan manifests.",
    )
    parser.add_argument("--run-id", default=None, help="Optional explicit run_id.")
    parser.add_argument("--chunk-size", type=int, default=None, help="Raw CSV processing chunk size.")
    parser.add_argument("--batch-size", type=int, default=None, help="PostgreSQL staging batch size.")
    parser.add_argument(
        "--promotion-batch-size",
        type=int,
        default=None,
        help="PostgreSQL staging-to-final promotion batch size.",
    )
    parser.add_argument("--duckdb-memory-limit", default=None)
    parser.add_argument("--duckdb-threads", type=int, default=None)
    args = parser.parse_args()

    try:
        if args.dry_run and args.execute:
            raise ValueError("Use at most one of --dry-run or --execute; config may supply mode.")
        cli_mode = "dry_run" if args.dry_run else "execute" if args.execute else None
        effective = resolve_historical_batch_config(
            config_path=args.config,
            cli_mode=cli_mode,
            cli_start_period=args.start_period,
            cli_end_period=args.end_period,
            cli_max_periods=args.max_periods,
            cli_stop_on_failure=args.stop_on_failure,
            cli_raw_root=args.raw_root,
            cli_output_dir=args.output_dir,
            cli_chunk_size=args.chunk_size,
            cli_batch_size=args.batch_size,
            cli_promotion_batch_size=args.promotion_batch_size,
            cli_duckdb_memory_limit=args.duckdb_memory_limit,
            cli_duckdb_threads=args.duckdb_threads,
        )
        if effective["mode"] == "dry_run":
            result, manifest_path = plan_historical_batch(
                config_path=args.config,
                start_period=effective["start_period"],
                end_period=effective["end_period"],
                raw_root=effective["raw_root"],
                output_dir=effective["output_dir"],
                run_id=args.run_id,
                effective_config=effective,
            )
            action = "historical_batch_plan"
        else:
            result, manifest_path = execute_historical_batch(
                config_path=args.config,
                start_period=effective["start_period"],
                end_period=effective["end_period"],
                raw_root=effective["raw_root"],
                output_dir=effective["output_dir"],
                run_id=args.run_id,
                max_periods=effective["max_periods"],
                stop_on_failure=effective["stop_on_failure"],
                chunk_size=effective["chunk_size"],
                batch_size=effective["batch_size"],
                promotion_batch_size=effective["promotion_batch_size"],
                duckdb_memory_limit=effective["duckdb_memory_limit"],
                duckdb_threads=effective["duckdb_threads"],
                effective_config=effective,
            )
            action = result["action"]
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    except Exception as error:
        payload = {
            "status": "failed",
            "action": "failed",
            "manifest_path": None,
            "summary": None,
            "periods": [],
            "error_message": str(error),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from error

    payload = {
        "status": result["status"],
        "action": action,
        "manifest_path": str(manifest_path),
        "summary": result.get("summary"),
        "periods": result.get("periods"),
        "effective_config": result.get("effective_config"),
        "result": result,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
