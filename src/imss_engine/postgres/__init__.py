"""PostgreSQL integration skeleton for the IMSS engine.

This package intentionally does not open database connections or load data at
import time. The first implementation phase only defines configuration,
connection and insert-only loader contracts.
"""

from .config import PostgresConfig

__all__ = ["PostgresConfig"]
