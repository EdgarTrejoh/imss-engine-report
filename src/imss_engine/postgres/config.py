"""Environment-based PostgreSQL configuration.

The module is safe to import without environment variables. Missing values are
represented as ``None`` so scripts can run dry-runs in clean environments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig:
    """Minimal PostgreSQL connection configuration for future loaders."""

    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        """Build config from IMSS_PG_* environment variables."""
        port_value = os.getenv("IMSS_PG_PORT")
        return cls(
            host=os.getenv("IMSS_PG_HOST"),
            port=int(port_value) if port_value else None,
            database=os.getenv("IMSS_PG_DATABASE"),
            user=os.getenv("IMSS_PG_USER"),
            password=os.getenv("IMSS_PG_PASSWORD"),
        )

    @property
    def is_complete(self) -> bool:
        """Return True when all connection fields are present."""
        return all(
            [
                self.host,
                self.port,
                self.database,
                self.user,
                self.password,
            ]
        )

    def masked(self) -> dict:
        """Return a log-safe representation without exposing secrets."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": "***" if self.password else None,
            "is_complete": self.is_complete,
        }
