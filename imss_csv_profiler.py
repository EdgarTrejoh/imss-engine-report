import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
"""
imss_csv_profiler.py
Perfilado rápido para CSV grande (1GB+), sin explotar RAM.

Uso:
  python imss_csv_profiler.py "C:/ruta/imss_analisis_profundo.csv"
"""

from __future__ import annotations

import sys
from pathlib import Path
import duckdb
import polars as pl


def human_mb(nbytes: int) -> str:
    return f"{nbytes / (1024**2):,.1f} MB"


def main(csv_path: str) -> None:
    path = Path(csv_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")

    logging.info("=" * 80)
    logging.info(f"Archivo: {path.name}")
    logging.info(f"Ruta:    {path}")
    logging.info(f"Tamaño:  {human_mb(path.stat().st_size)}")
    logging.info("=" * 80)

    # ------------------------------------------------------------------
    # 1) SCHEMA + muestra (Polars en modo Lazy: casi cero RAM)
    # ------------------------------------------------------------------
    logging.info("\n[1/5] Leyendo schema (muestra) con Polars...")
    lf = pl.scan_csv(
        str(path),
        infer_schema_length=50_000,  # aumenta si tu CSV trae tipos raros al inicio
        try_parse_dates=True,
        ignore_errors=True,
    )

    schema = lf.schema
    logging.info("\nColumnas detectadas (nombre : tipo):")
    for k, v in schema.items():
        logging.info(f" - {k}: {v}")

    # Muestra rápida
    logging.info("\nMuestra (primeras 5 filas):")
    logging.info(lf.head(5).collect())

    # ------------------------------------------------------------------
    # 2) Conteo de filas SIN cargar todo (DuckDB)
    # ------------------------------------------------------------------
    logging.info("\n[2/5] Contando filas con DuckDB (sin cargar todo a memoria)...")
    con = duckdb.connect(database=":memory:")
    # read_csv_auto infiere tipos; SAMPLE_SIZE ayuda con archivos grandes
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
    logging.info(f"Filas totales: {nrows:,}")

    # ------------------------------------------------------------------
    # 3) Nulos por columna (rápido y útil)
    # ------------------------------------------------------------------
    logging.info("\n[3/5] Nulos por columna (Polars Lazy)...")
    nulls = (
        lf.select(
            [
                pl.col(c).null_count().alias(c)
                for c in lf.columns
            ]
        )
        .collect()
        .to_dict(as_series=False))
    # nulls es dict {col: [count]}
    null_list = sorted(((k, v[0]) for k, v in nulls.items()), key=lambda x: x[1], reverse=True)
    logging.info("Top 15 columnas con más nulos:")
    for k, v in null_list[:15]:
        logging.info(f" - {k}: {v:,}")

    # ------------------------------------------------------------------
    # 4) Chequeos típicos para tu dataset IMSS
    #    (ajusta nombres si difieren)
    # ------------------------------------------------------------------
    logging.info("\n[4/5] Chequeos típicos (si existen estas columnas)...")

    cols = set(lf.columns)
    candidate_keys = ["periodo_informacion", "cve_entidad", "sexo", "rango_edad", "rango_uma", "sector_economico_1"]

    present_keys = [c for c in candidate_keys if c in cols]
    if present_keys:
        logging.info(f"Posible llave compuesta detectada: {present_keys}")
        # duplicados por llave (esto sí puede tardar, pero sigue siendo streaming/lazy)
        dup = (
            lf.group_by(present_keys)
              .len()
              .filter(pl.col("len") > 1)
              .select(pl.sum("len").alias("rows_in_duplicate_groups"), pl.count().alias("duplicate_groups"))
              .collect()
        )
        logging.info("Duplicados (aprox):")
        logging.info(dup)
    else:
        logging.info("No encontré columnas típicas de llave. (No pasa nada, solo ajusta nombres).")

    # Rango de fechas
    for datecol in ["periodo_informacion", "Periodo", "fecha", "timestamp"]:
        if datecol in cols:
            logging.info(f"\nRango para {datecol}:")
            rng = lf.select(pl.col(datecol).min().alias("min"), pl.col(datecol).max().alias("max")).collect()
            logging.info(rng)

    # ------------------------------------------------------------------
    # 5) Mini reporte de “qué hay dentro” (conteos útiles)
    # ------------------------------------------------------------------
    logging.info("\n[5/5] Conteos rápidos (top categorías) ...")
    for cat in ["cve_entidad", "sexo", "sector_economico_1", "rango_edad", "rango_uma"]:
        if cat in cols:
            top = (
                lf.group_by(cat)
                  .len()
                  .sort("len", descending=True)
                  .head(10)
                  .collect()
            )
            logging.info(f"\nTop 10 de {cat}:")
            logging.info(top)

    logging.info("\nListo. Si quieres, ahora hacemos consultas SQL con DuckDB.")
    logging.info("Ejemplo:")
    logging.info("  SELECT periodo_informacion, SUM(total_asegurados) FROM imss GROUP BY 1 ORDER BY 1;")

    con.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.info("Uso: python imss_csv_profiler.py <ruta_al_csv>")
        sys.exit(1)
    main(sys.argv[1])
