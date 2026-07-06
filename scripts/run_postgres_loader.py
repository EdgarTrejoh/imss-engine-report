from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.postgres.config import PostgresConfig
from src.imss_engine.postgres.connection import (
    PostgresDriverMissingError,
    connect,
)
from src.imss_engine.postgres.loader import check_existing_period, plan_insert_only_load
from src.imss_engine.postgres.loader import register_period_control_pending


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
    parser.add_argument("--source-url", default=None, help="Optional source URL metadata.")
    parser.add_argument(
        "--check-existing",
        action="store_true",
        help="Run a read-only PostgreSQL check for an existing period.",
    )
    parser.add_argument(
        "--register-period-control",
        action="store_true",
        help="Insert a pending period_control row when the period is new.",
    )
    args = parser.parse_args()

    if args.check_existing and args.register_period_control:
        print(
            "Use either --check-existing or --register-period-control, not both.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    config = PostgresConfig.from_env()
    if args.check_existing or args.register_period_control:
        if not config.is_complete:
            print(
                "PostgreSQL config is incomplete. Set IMSS_PG_HOST, IMSS_PG_PORT, "
                "IMSS_PG_DATABASE, IMSS_PG_USER and IMSS_PG_PASSWORD.",
                file=sys.stderr,
            )
            print(f"Config detected: {config.masked()}", file=sys.stderr)
            raise SystemExit(2)

        connection = None
        try:
            connection = connect(config)
            result = (
                register_period_control_pending(
                    connection,
                    args.period,
                    run_id=args.run_id,
                    source_url=args.source_url,
                )
                if args.register_period_control
                else check_existing_period(connection, args.period)
            )
        except PostgresDriverMissingError as error:
            print(f"PostgreSQL driver missing: {error}", file=sys.stderr)
            raise SystemExit(2) from error
        except Exception as error:
            print(f"PostgreSQL period check failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error
        finally:
            if connection is not None:
                connection.close()

        payload = {
            "mode": "register_period_control" if args.register_period_control else "check_existing",
            "opens_database_connection": True,
            "writes_period_control_only": bool(args.register_period_control),
            "touches_final_table": False,
            "touches_staging_table": False,
            "reads_source_csv": False,
            "postgres_config": config.masked(),
            "result": result,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

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
