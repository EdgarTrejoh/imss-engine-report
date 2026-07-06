from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.postgres.config import PostgresConfig
from src.imss_engine.postgres.connection import (
    PostgresDriverMissingError,
    connect,
)


EXPECTED_TABLES = {
    "cat_entidad_municipio",
    "cat_genero",
    "cat_ptpd",
    "cat_rango_edad",
    "cat_rango_ingreso_uma",
    "cat_rango_ingreso_vsm",
    "cat_sector_economico_1",
    "cat_sector_economico_2",
    "cat_sector_economico_4",
    "imss_hechos_asegurados",
    "imss_period_control",
    "imss_run_manifest",
    "imss_staging_asegurados",
}

EXPECTED_VIEWS = {
    "vw_empleo_mensual_entidad",
    "vw_empleo_sector_1",
    "vw_empleo_sector_4",
    "vw_period_control",
    "vw_sbc_entidad_genero",
}

EXPECTED_CONSTRAINTS = {
    "chk_cat_ptpd_codigo",
    "chk_imss_hechos_ptpd",
    "chk_imss_period_control_status",
    "uq_imss_hechos_asegurados_analytic_key",
}


def _fetch_names(cursor, query: str) -> set[str]:
    cursor.execute(query)
    return {row[0] for row in cursor.fetchall()}


def _missing(expected: set[str], found: set[str]) -> list[str]:
    return sorted(expected - found)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate expected IMSS PostgreSQL schema objects with read-only catalog queries."
    )
    parser.parse_args()

    config = PostgresConfig.from_env()
    if not config.is_complete:
        print(
            "PostgreSQL config is incomplete. Set IMSS_PG_HOST, IMSS_PG_PORT, "
            "IMSS_PG_DATABASE, IMSS_PG_USER and IMSS_PG_PASSWORD.",
            file=sys.stderr,
        )
        print(f"Config detected: {config.masked()}", file=sys.stderr)
        return 2

    connection = None
    try:
        connection = connect(config)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name = 'imss';
                """
            )
            schema_exists = cursor.fetchone() is not None

            tables = _fetch_names(
                cursor,
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'imss'
                  AND table_type = 'BASE TABLE';
                """,
            )
            views = _fetch_names(
                cursor,
                """
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'imss';
                """,
            )
            constraints = _fetch_names(
                cursor,
                """
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE nsp.nspname = 'imss';
                """,
            )

        errors: list[str] = []
        if not schema_exists:
            errors.append("missing schema: imss")

        for table in _missing(EXPECTED_TABLES, tables):
            errors.append(f"missing table: imss.{table}")

        for view in _missing(EXPECTED_VIEWS, views):
            errors.append(f"missing view: imss.{view}")

        for constraint in _missing(EXPECTED_CONSTRAINTS, constraints):
            errors.append(f"missing constraint: {constraint}")

        print("PostgreSQL IMSS schema smoke test")
        print(f"schema imss: {'present' if schema_exists else 'missing'}")
        print(f"tables found: {len(tables)} / expected {len(EXPECTED_TABLES)}")
        print(f"views found: {len(views)} / expected {len(EXPECTED_VIEWS)}")
        print(f"critical constraints found: {len(EXPECTED_CONSTRAINTS - set(_missing(EXPECTED_CONSTRAINTS, constraints)))} / expected {len(EXPECTED_CONSTRAINTS)}")
        print(f"database host: {config.host!r}, database: {config.database!r}, user: {config.user!r}")

        if errors:
            print("Schema validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1

        print("Schema validation OK.")
        return 0
    except PostgresDriverMissingError as error:
        print(f"PostgreSQL driver missing: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"PostgreSQL schema check failed: {error}", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
