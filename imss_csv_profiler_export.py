from __future__ import annotations

import logging
import sys
from pathlib import Path
import duckdb
import polars as pl

logging.basicConfig(level=logging.INFO, format='%(message)s')


def human_mb(nbytes: int) -> float:
    return round(nbytes / (1024**2), 2)


def main(csv_path: str) -> None:
    path = Path(csv_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")

    output_dir = path.parent
    base = path.stem

    logging.info(f"\n📂 Analizando: {path.name}")
    logging.info(f"💾 Tamaño: {human_mb(path.stat().st_size)} MB")

    # ======================================================
    # 1) SCHEMA (Lazy scan)
    # ======================================================
    lf = pl.scan_csv(
        str(path),
        infer_schema_length=50_000,
        try_parse_dates=True,
        ignore_errors=True,
    )

    sch = lf.collect_schema()  # evita warning y es más eficiente
    colnames = sch.names()
    dtypes = [str(sch.get(c)) for c in colnames]

    schema_df = pl.DataFrame({"column": colnames, "dtype": dtypes})
    schema_path = output_dir / f"{base}_schema.csv"
    schema_df.write_csv(schema_path)
    logging.info(f"✅ Schema exportado → {schema_path.name}")

    # ======================================================
    # 2) CONTEO DE FILAS (DuckDB)
    # ======================================================
    con = duckdb.connect(database=":memory:")
    con.execute(
        f"""
        CREATE VIEW imss AS
        SELECT * FROM read_csv_auto(
            '{str(path).replace("\\\\", "/")}',
            sample_size=200000,
            ignore_errors=true
        );
        """
    )
    nrows = con.execute("SELECT COUNT(*) FROM imss;").fetchone()[0]
    con.close()

    # ======================================================
    # 3) NULOS POR COLUMNA
    # ======================================================
    nulls_df = (
        lf.select([pl.col(c).null_count().alias(c) for c in colnames])
        .collect()
        .transpose(include_header=True)
        .rename({"column": "column", "column_0": "null_count"})
        .sort("null_count", descending=True)
    )

    nulls_path = output_dir / f"{base}_nulls.csv"
    nulls_df.write_csv(nulls_path)
    logging.info(f"✅ Nulos exportados → {nulls_path.name}")

    # ======================================================
    # 4) RESUMEN GENERAL (forzamos todo a string para evitar crash)
    # ======================================================
    summary_df = pl.DataFrame(
        {
            "metric": [
                "file_name",
                "file_size_mb",
                "total_rows",
                "total_columns",
            ],
            "value": [
                str(path.name),
                str(human_mb(path.stat().st_size)),
                str(nrows),
                str(len(colnames)),
            ],
        }
    )

    summary_path = output_dir / f"{base}_summary.csv"
    summary_df.write_csv(summary_path)
    logging.info(f"✅ Resumen exportado → {summary_path.name}")

    logging.info("\n🎯 LISTO compita.")
    logging.info("Archivos generados:")
    logging.info(f" - {schema_path.name}")
    logging.info(f" - {nulls_path.name}")
    logging.info(f" - {summary_path.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.info("Uso: python imss_csv_profiler_export.py <ruta_al_csv>")
        sys.exit(1)

    main(sys.argv[1])
