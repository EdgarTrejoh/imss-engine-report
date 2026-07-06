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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a safe PostgreSQL connection smoke test for the IMSS engine."
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
            cursor.execute("SELECT current_database(), current_schema();")
            database, schema = cursor.fetchone()
        print(
            "PostgreSQL connection OK: "
            f"database={database!r}, schema={schema!r}, user={config.user!r}, host={config.host!r}"
        )
        return 0
    except PostgresDriverMissingError as error:
        print(f"PostgreSQL driver missing: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"PostgreSQL connection failed: {error}", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
