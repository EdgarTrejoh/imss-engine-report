"""PostgreSQL connection helpers.

No connection is opened at import time. The optional driver dependency will be
required only when a future caller explicitly asks to connect.
"""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from typing import Any

from .config import PostgresConfig


class PostgresDriverMissingError(RuntimeError):
    """Raised when no supported PostgreSQL driver is installed."""


def get_available_driver() -> str | None:
    """Return the first supported installed driver name, if any."""
    if find_spec("psycopg") is not None:
        return "psycopg"
    if find_spec("psycopg2") is not None:
        return "psycopg2"
    return None


def build_connection_kwargs(config: PostgresConfig) -> dict[str, Any]:
    """Convert a PostgresConfig into common driver keyword arguments."""
    return {
        "host": config.host,
        "port": config.port,
        "dbname": config.database,
        "user": config.user,
        "password": config.password,
    }


def connect(config: PostgresConfig | None = None):
    """Create a PostgreSQL connection for future loader implementations.

    This function is intentionally unused by the current skeleton CLI. Calling
    it requires a complete config and an installed supported driver.
    """
    pg_config = config or PostgresConfig.from_env()
    if not pg_config.is_complete:
        raise ValueError("PostgreSQL config is incomplete. Set IMSS_PG_* variables.")

    driver = get_available_driver()
    if driver is None:
        raise PostgresDriverMissingError(
            "No PostgreSQL driver installed. Future implementation can use psycopg or psycopg2."
        )

    module = import_module(driver)
    return module.connect(**build_connection_kwargs(pg_config))
