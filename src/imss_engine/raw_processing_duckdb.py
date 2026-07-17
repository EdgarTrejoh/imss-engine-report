"""Disk-backed consolidation for IMSS raw chunk aggregates."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd

from .aggregate import DERIVED_SUM_COLUMNS, get_group_columns
from .metrics import DIFFERENCE_METRIC_SPECS, SBC_METRIC_SPECS
from .schema import CRITICAL_METRIC_COLUMNS


DEFAULT_DUCKDB_MEMORY_LIMIT = "1GB"
DEFAULT_DUCKDB_THREADS = 2

SBC_COLUMNS: tuple[str, ...] = tuple(SBC_METRIC_SPECS)
DIFFERENCE_COLUMNS: tuple[str, ...] = tuple(DIFFERENCE_METRIC_SPECS)


class DuckDBProcessingUnavailableError(RuntimeError):
    """Raised when the optional DuckDB processing engine cannot be imported."""


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''").replace("\\", "/") + "'"


def _safe_divide_sql(numerator: str, denominator: str, alias: str) -> str:
    return (
        f"CASE WHEN ({denominator}) IS NULL OR ({denominator}) = 0 "
        f"THEN NULL ELSE ({numerator}) / ({denominator}) END AS {_quote_identifier(alias)}"
    )


def _sum_sql_columns(columns: tuple[str, ...]) -> str:
    return " + ".join(_quote_identifier(column) for column in columns)


def _final_select_sql(timestamp: str) -> str:
    group_columns = get_group_columns()
    sum_columns = list(CRITICAL_METRIC_COLUMNS) + list(DERIVED_SUM_COLUMNS)
    expressions = [_quote_identifier(column) for column in group_columns]
    expressions.extend(_quote_identifier(column) for column in sum_columns)
    for alias, (numerator_columns, denominator_columns) in SBC_METRIC_SPECS.items():
        expressions.append(
            _safe_divide_sql(
                _sum_sql_columns(numerator_columns),
                _sum_sql_columns(denominator_columns),
                alias,
            )
        )
    for alias, (minuend_columns, subtrahend_columns) in DIFFERENCE_METRIC_SPECS.items():
        expressions.append(
            f"({_sum_sql_columns(minuend_columns)}) - ({_sum_sql_columns(subtrahend_columns)}) "
            f"AS {_quote_identifier(alias)}"
        )
    expressions.extend(
        ["'IMSS' AS \"fuente\"", f"{_quote_literal(timestamp)} AS \"timestamp\""]
    )
    return ",\n".join(expressions)


class DuckDBAggregateStore:
    """Persist partial aggregates and consolidate them with a private DuckDB runtime."""

    def __init__(
        self,
        *,
        temporary_directory: str | Path,
        memory_limit: str = DEFAULT_DUCKDB_MEMORY_LIMIT,
        threads: int = DEFAULT_DUCKDB_THREADS,
    ) -> None:
        try:
            import duckdb
        except ImportError as error:
            raise DuckDBProcessingUnavailableError(
                "DuckDB processing engine is unavailable. Install the duckdb dependency."
            ) from error

        if threads <= 0:
            raise ValueError("duckdb_threads must be greater than zero")
        self._duckdb = duckdb
        self.temporary_directory = Path(temporary_directory)
        self.partial_directory = self.temporary_directory / "partials"
        self.spill_directory = self.temporary_directory / "spill"
        self.database_path = self.temporary_directory / "processing.duckdb"
        self.memory_limit = memory_limit
        self.threads = threads
        self.partial_count = 0
        self.temporary_directory.mkdir(parents=True, exist_ok=False)
        self.partial_directory.mkdir()
        self.spill_directory.mkdir()
        self.connection = duckdb.connect(str(self.database_path))
        self.connection.execute(f"SET memory_limit={_quote_literal(memory_limit)}")
        self.connection.execute(f"SET threads={threads}")
        self.connection.execute(
            f"SET temp_directory={_quote_literal(self.spill_directory)}"
        )

    def persist_partial(self, aggregate: pd.DataFrame) -> Path:
        path = self.partial_directory / f"partial_{self.partial_count:06d}.parquet"
        self.connection.register("partial_frame", aggregate)
        try:
            self.connection.execute(
                f"COPY partial_frame TO {_quote_literal(path)} (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        finally:
            self.connection.unregister("partial_frame")
        self.partial_count += 1
        return path

    def consolidate_to_csv(
        self,
        *,
        plain_csv_path: str | Path,
        timestamp: str,
        parquet_output_path: str | Path | None = None,
        parquet_compression: str = "zstd",
    ) -> dict:
        if self.partial_count == 0:
            raise ValueError("No partial aggregates were persisted.")
        group_columns = get_group_columns()
        sum_columns = list(CRITICAL_METRIC_COLUMNS) + list(DERIVED_SUM_COLUMNS)
        group_sql = ", ".join(_quote_identifier(column) for column in group_columns)
        sum_sql = ", ".join(
            f"SUM({_quote_identifier(column)}) AS {_quote_identifier(column)}"
            for column in sum_columns
        )
        parquet_glob = self.partial_directory / "partial_*.parquet"
        query = f"""
            WITH combined AS (
                SELECT {group_sql}, {sum_sql}
                FROM read_parquet({_quote_literal(parquet_glob)}, union_by_name=true)
                GROUP BY {group_sql}
            )
            SELECT {_final_select_sql(timestamp)}
            FROM combined
        """
        plain_csv_path = Path(plain_csv_path)
        self.connection.execute(f"CREATE OR REPLACE TABLE final_output AS {query}")
        self.connection.execute(
            f"COPY final_output TO {_quote_literal(plain_csv_path)} "
            "(FORMAT CSV, HEADER true, DELIMITER ',', NULL '')"
        )
        if parquet_output_path is not None:
            compression = parquet_compression.upper()
            if compression not in {"ZSTD", "SNAPPY"}:
                raise ValueError("parquet_compression must be zstd or snappy")
            self.connection.execute(
                f"COPY final_output TO {_quote_literal(parquet_output_path)} "
                f"(FORMAT PARQUET, COMPRESSION {compression})"
            )
        summary = self.connection.execute("SELECT COUNT(*) FROM final_output").fetchone()
        return {
            "aggregate_rows": int(summary[0]),
            "columns_output": group_columns
            + sum_columns
            + list(SBC_COLUMNS)
            + list(DIFFERENCE_COLUMNS)
            + ["fuente", "timestamp"],
        }

    def close(self) -> None:
        self.connection.close()

    def cleanup(self) -> None:
        shutil.rmtree(self.temporary_directory)


def publish_utf8_sig_atomically(
    plain_csv_path: str | Path,
    staging_output_path: str | Path,
    final_output_path: str | Path,
) -> None:
    """Add an UTF-8 BOM by streaming, then atomically publish the final CSV."""
    plain_csv_path = Path(plain_csv_path)
    staging_output_path = Path(staging_output_path)
    final_output_path = Path(final_output_path)
    final_output_path.parent.mkdir(parents=True, exist_ok=True)
    with plain_csv_path.open("rb") as source, staging_output_path.open("wb") as target:
        target.write(b"\xef\xbb\xbf")
        shutil.copyfileobj(source, target, length=1024 * 1024)
        target.flush()
        os.fsync(target.fileno())
    os.replace(staging_output_path, final_output_path)
