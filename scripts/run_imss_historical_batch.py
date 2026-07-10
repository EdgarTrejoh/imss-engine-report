from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.historical_batch_planner import plan_historical_batch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan historical IMSS single-period pipeline work in dry-run mode."
    )
    parser.add_argument("--config", default="config/config.yaml", help="Config YAML path.")
    parser.add_argument("--start-period", required=True, help="Inclusive month-end start period.")
    parser.add_argument("--end-period", required=True, help="Inclusive month-end end period.")
    parser.add_argument("--dry-run", action="store_true", help="Generate a dry-run batch plan.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Reserved for a future PR. Execution is not implemented in PR #41.",
    )
    parser.add_argument(
        "--raw-root",
        default="data/raw/imss/asegurados",
        help="Root directory for raw IMSS asegurados files.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/pipeline",
        help="Directory for historical batch plan manifests.",
    )
    parser.add_argument("--run-id", default=None, help="Optional explicit run_id.")
    args = parser.parse_args()

    if args.execute:
        print("Historical batch execute is out of scope for PR #41. Use --dry-run only.", file=sys.stderr)
        raise SystemExit(2)
    if not args.dry_run:
        print("--dry-run is required. Historical batch execution is not implemented.", file=sys.stderr)
        raise SystemExit(2)

    try:
        plan, manifest_path = plan_historical_batch(
            config_path=args.config,
            start_period=args.start_period,
            end_period=args.end_period,
            raw_root=args.raw_root,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    except Exception as error:
        payload = {
            "status": "failed",
            "action": "historical_batch_plan",
            "manifest_path": None,
            "summary": None,
            "periods": [],
            "error_message": str(error),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from error

    payload = {
        "status": plan["status"],
        "action": "historical_batch_plan",
        "manifest_path": str(manifest_path),
        "summary": plan["summary"],
        "periods": plan["periods"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
