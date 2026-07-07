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
from src.imss_engine.postgres.loader import (
    check_housekeeping_eligibility,
    check_existing_period,
    check_source_csv,
    finalize_period_control_loaded,
    finalize_run_manifest,
    load_staging_insert_only,
    plan_insert_only_load,
    promote_staging_to_final_insert_only,
    profile_source_csv_streaming,
    register_period_control_pending,
    register_run_manifest,
    summarize_reserved_periods,
    summarize_source_csv_periods_streaming,
    validate_post_promotion_period,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Operational CLI for the IMSS PostgreSQL insert-only loader."
    )
    parser.add_argument("--period", help="Period to plan, in YYYY-MM-DD format.")
    parser.add_argument(
        "--source-csv",
        default=None,
        help="Source CSV path for explicit CSV modes. Dry-run does not read this file.",
    )
    parser.add_argument("--sample-rows", type=int, default=5, help="Rows to sample for source CSV checks.")
    parser.add_argument("--batch-size", type=int, default=5000, help="Batch size for staging loads.")
    parser.add_argument("--run-id", default=None, help="Optional future run_id.")
    parser.add_argument("--source-url", default=None, help="Optional source URL metadata.")
    parser.add_argument(
        "--check-source-csv",
        action="store_true",
        help="Inspect a CSV header and bounded sample without connecting to PostgreSQL.",
    )
    parser.add_argument(
        "--profile-source-csv",
        action="store_true",
        help="Profile a CSV with streaming reads and bounded row count.",
    )
    parser.add_argument(
        "--summarize-source-periods",
        action="store_true",
        help="Summarize CSV row counts by periodo_informacion with streaming reads.",
    )
    parser.add_argument("--max-rows", type=int, default=None, help="Maximum rows to scan in streaming CSV modes.")
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
    parser.add_argument(
        "--register-run-manifest",
        action="store_true",
        help="Insert a run_manifest row when period_control exists.",
    )
    parser.add_argument(
        "--load-staging",
        action="store_true",
        help="Load one period into imss.imss_staging_asegurados using insert-only batches.",
    )
    parser.add_argument(
        "--promote-staging-final",
        action="store_true",
        help="Promote one staged period into imss.imss_hechos_asegurados using insert-only batches.",
    )
    parser.add_argument(
        "--validate-post-promotion",
        action="store_true",
        help="Validate staging and final consistency for one promoted period with read-only checks.",
    )
    parser.add_argument(
        "--finalize-period-control",
        action="store_true",
        help="Mark a validated pending period as loaded in imss.imss_period_control.",
    )
    parser.add_argument(
        "--finalize-run-manifest",
        action="store_true",
        help="Mark an existing pending run manifest as completed.",
    )
    parser.add_argument(
        "--check-housekeeping-eligibility",
        action="store_true",
        help="Run a read-only eligibility check for future source CSV housekeeping.",
    )
    parser.add_argument(
        "--summary-reserved-periods",
        action="store_true",
        help="Return a compact read-only summary of periods preserved in final facts.",
    )
    args = parser.parse_args()

    write_or_check_flags = [
        args.check_source_csv,
        args.profile_source_csv,
        args.summarize_source_periods,
        args.check_existing,
        args.register_period_control,
        args.register_run_manifest,
        args.load_staging,
        args.promote_staging_final,
        args.validate_post_promotion,
        args.finalize_period_control,
        args.finalize_run_manifest,
        args.check_housekeeping_eligibility,
        args.summary_reserved_periods,
    ]
    if sum(bool(flag) for flag in write_or_check_flags) > 1:
        print(
            "Use only one of --check-source-csv, --profile-source-csv, "
            "--summarize-source-periods, --check-existing, --register-period-control, "
            "--register-run-manifest, --load-staging, --promote-staging-final, "
            "--validate-post-promotion, --finalize-period-control or "
            "--finalize-run-manifest, --check-housekeeping-eligibility or "
            "--summary-reserved-periods.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if args.check_source_csv:
        if not args.source_csv:
            print("--check-source-csv requires --source-csv.", file=sys.stderr)
            raise SystemExit(2)
        try:
            result = check_source_csv(args.source_csv, sample_rows=args.sample_rows)
        except Exception as error:
            print(f"Source CSV check failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        payload = {
            "mode": "check_source_csv",
            "opens_database_connection": False,
            "reads_source_csv": True,
            "reads_full_csv": False,
            "loads_dataframe": False,
            "writes_period_control_only": False,
            "writes_run_manifest_only": False,
            "touches_final_table": False,
            "touches_staging_table": False,
            "result": result,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.profile_source_csv:
        if not args.source_csv:
            print("--profile-source-csv requires --source-csv.", file=sys.stderr)
            raise SystemExit(2)
        try:
            result = profile_source_csv_streaming(
                args.source_csv,
                max_rows=args.max_rows if args.max_rows is not None else 10000,
            )
        except Exception as error:
            print(f"Source CSV profile failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        payload = {
            "mode": "profile_source_csv",
            "opens_database_connection": False,
            "reads_source_csv": True,
            "reads_full_csv": False,
            "loads_dataframe": False,
            "writes_period_control_only": False,
            "writes_run_manifest_only": False,
            "touches_final_table": False,
            "touches_staging_table": False,
            "result": result,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.summarize_source_periods:
        if not args.source_csv:
            print("--summarize-source-periods requires --source-csv.", file=sys.stderr)
            raise SystemExit(2)
        try:
            result = summarize_source_csv_periods_streaming(args.source_csv, max_rows=args.max_rows)
        except Exception as error:
            print(f"Source period summary failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        payload = {
            "mode": "summarize_source_periods",
            "opens_database_connection": False,
            "reads_source_csv": True,
            "reads_full_csv": result["reads_full_csv"],
            "loads_dataframe": False,
            "writes_period_control_only": False,
            "writes_run_manifest_only": False,
            "touches_final_table": False,
            "touches_staging_table": False,
            "result": result,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.check_housekeeping_eligibility and not args.source_csv:
        print("--check-housekeeping-eligibility requires --source-csv.", file=sys.stderr)
        raise SystemExit(2)

    if not args.period and not args.check_housekeeping_eligibility and not args.summary_reserved_periods:
        print(
            "--period is required unless --check-source-csv, --profile-source-csv "
            "--summarize-source-periods, --check-housekeeping-eligibility or "
            "--summary-reserved-periods is used.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if args.register_run_manifest and not args.run_id:
        print("--register-run-manifest requires --run-id.", file=sys.stderr)
        raise SystemExit(2)

    if args.finalize_run_manifest and not args.run_id:
        print("--finalize-run-manifest requires --run-id.", file=sys.stderr)
        raise SystemExit(2)

    if args.load_staging and not args.source_csv:
        print("--load-staging requires --source-csv.", file=sys.stderr)
        raise SystemExit(2)

    config = PostgresConfig.from_env()
    if (
        args.check_existing
        or args.register_period_control
        or args.register_run_manifest
        or args.load_staging
        or args.promote_staging_final
        or args.validate_post_promotion
        or args.finalize_period_control
        or args.finalize_run_manifest
        or args.check_housekeeping_eligibility
        or args.summary_reserved_periods
    ):
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
            if args.register_period_control:
                result = register_period_control_pending(
                    connection,
                    args.period,
                    run_id=args.run_id,
                    source_url=args.source_url,
                )
            elif args.register_run_manifest:
                result = register_run_manifest(connection, args.period, args.run_id)
            elif args.load_staging:
                result = load_staging_insert_only(
                    connection,
                    args.source_csv,
                    args.period,
                    batch_size=args.batch_size,
                    max_rows=args.max_rows,
                    run_id=args.run_id,
                )
            elif args.promote_staging_final:
                result = promote_staging_to_final_insert_only(
                    connection,
                    args.period,
                    run_id=args.run_id,
                    batch_size=args.batch_size,
                )
            elif args.validate_post_promotion:
                result = validate_post_promotion_period(connection, args.period)
            elif args.finalize_period_control:
                result = finalize_period_control_loaded(
                    connection,
                    args.period,
                    run_id=args.run_id,
                )
            elif args.finalize_run_manifest:
                result = finalize_run_manifest(
                    connection,
                    args.period,
                    args.run_id,
                )
            elif args.check_housekeeping_eligibility:
                result = check_housekeeping_eligibility(
                    connection,
                    args.source_csv,
                    period=args.period,
                )
            elif args.summary_reserved_periods:
                result = summarize_reserved_periods(connection, period=args.period)
            else:
                result = check_existing_period(connection, args.period)
        except PostgresDriverMissingError as error:
            print(f"PostgreSQL driver missing: {error}", file=sys.stderr)
            raise SystemExit(2) from error
        except Exception as error:
            print(f"PostgreSQL loader operation failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error
        finally:
            if connection is not None:
                connection.close()

        uses_result_flags = (
            args.load_staging
            or args.promote_staging_final
            or args.validate_post_promotion
            or args.finalize_period_control
            or args.finalize_run_manifest
            or args.check_housekeeping_eligibility
            or args.summary_reserved_periods
        )
        payload = {
            "mode": (
                "summary_reserved_periods"
                if args.summary_reserved_periods
                else "check_housekeeping_eligibility"
                if args.check_housekeeping_eligibility
                else "register_run_manifest"
                if args.register_run_manifest
                else "promote_staging_final"
                if args.promote_staging_final
                else "validate_post_promotion"
                if args.validate_post_promotion
                else "finalize_period_control"
                if args.finalize_period_control
                else "finalize_run_manifest"
                if args.finalize_run_manifest
                else "load_staging"
                if args.load_staging
                else "register_period_control"
                if args.register_period_control
                else "check_existing"
            ),
            "opens_database_connection": (
                result["opens_database_connection"] if uses_result_flags else True
            ),
            "writes_period_control_only": (
                result["writes_period_control_only"]
                if uses_result_flags
                else bool(args.register_period_control)
            ),
            "writes_run_manifest_only": (
                result["writes_run_manifest_only"]
                if uses_result_flags
                else bool(args.register_run_manifest)
            ),
            "touches_staging_table": (
                result["touches_staging_table"] if uses_result_flags else False
            ),
            "touches_final_table": (
                result["touches_final_table"] if uses_result_flags else False
            ),
            "reads_source_csv": (
                result["reads_source_csv"] if uses_result_flags else False
            ),
            "reads_full_csv": (
                result["reads_full_csv"] if uses_result_flags else False
            ),
            "loads_dataframe": (
                result["loads_dataframe"] if uses_result_flags else False
            ),
            "writes_source_csv": (
                result.get("writes_source_csv", False) if uses_result_flags else False
            ),
            "archives_source_csv": (
                result.get("archives_source_csv", False) if uses_result_flags else False
            ),
            "creates_output_csv": (
                result.get("creates_output_csv", False) if uses_result_flags else False
            ),
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
