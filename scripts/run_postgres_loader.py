from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.postgres.config import PostgresConfig
from src.imss_engine.postgres.loader import plan_insert_only_load


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run skeleton for the future IMSS PostgreSQL insert-only loader."
    )
    parser.add_argument("--period", required=True, help="Period to plan, in YYYY-MM-DD format.")
    parser.add_argument(
        "--source-csv",
        default=None,
        help="Future source CSV path. The skeleton does not read this file.",
    )
    parser.add_argument("--run-id", default=None, help="Optional future run_id.")
    args = parser.parse_args()

    config = PostgresConfig.from_env()
    plan = plan_insert_only_load(args.period, source_path=args.source_csv, run_id=args.run_id)

    payload = {
        "mode": "dry_run",
        "opens_database_connection": False,
        "reads_source_csv": False,
        "postgres_config": config.masked(),
        "planned_steps": [asdict(step) for step in plan],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
