from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.publish_plan import build_publish_plan


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a dry-run IMSS publish plan from one explicit raw aggregate."
    )
    parser.add_argument("--period", required=True, help="Period to plan in YYYY-MM-DD format.")
    parser.add_argument("--aggregate-file", required=True, help="Temporary aggregate CSV to evaluate.")
    parser.add_argument(
        "--concentrado-file",
        default="data/processed/imss_concentrado.csv",
        help="Read-only concentrado CSV path.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/processing",
        help="Directory for publish plan and comparison manifests.",
    )
    args = parser.parse_args()

    plan, plan_path = build_publish_plan(
        args.period,
        aggregate_file=args.aggregate_file,
        concentrado_file=args.concentrado_file,
        output_dir=args.output_dir,
    )
    payload = {
        "status": plan["status"],
        "publish_plan_path": str(plan_path),
        "result": plan,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if plan["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
