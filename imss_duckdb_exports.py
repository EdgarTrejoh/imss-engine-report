# imss_duckdb_exports.py
from __future__ import annotations

import logging
import sys
from pathlib import Path
import duckdb

logging.basicConfig(level=logging.INFO, format='%(message)s')

def main(csv_path: str):
    path = Path(csv_path).expanduser().resolve()
    outdir = path.parent
    base = path.stem

    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA threads=4;")  # súbele si tienes más núcleos

    con.execute(f"""
        CREATE VIEW imss AS
        SELECT *
        FROM read_csv_auto('{str(path).replace("\\\\","/")}', sample_size=200000, ignore_errors=true);
    """)

    # 1) Rango de fechas
    con.execute(f"""
        COPY (
            SELECT MIN(periodo_informacion) AS min_periodo,
                   MAX(periodo_informacion) AS max_periodo
            FROM imss
        ) TO '{str(outdir / (base + "_date_range.csv")).replace("\\\\","/")}'
        (HEADER, DELIMITER ',');
    """)

    # 2) Top values (ejemplos)
    for col in ["cve_entidad", "sexo", "sector_economico_1", "rango_edad", "rango_uma"]:
        con.execute(f"""
            COPY (
                SELECT {col} AS value, COUNT(*) AS n
                FROM imss
                GROUP BY 1
                ORDER BY n DESC
                LIMIT 50
            ) TO '{str(outdir / (base + f"_top_{col}.csv")).replace("\\\\","/")}'
            (HEADER, DELIMITER ',');
        """)

    # 3) Duplicados por llave lógica
    con.execute(f"""
        COPY (
            SELECT
                periodo_informacion, cve_entidad, sexo, rango_edad, rango_uma, sector_economico_1,
                COUNT(*) AS n
            FROM imss
            GROUP BY 1,2,3,4,5,6
            HAVING COUNT(*) > 1
            ORDER BY n DESC
        ) TO '{str(outdir / (base + "_duplicates_key.csv")).replace("\\\\","/")}'
        (HEADER, DELIMITER ',');
    """)

    # 4) Stats numéricos (min/max/avg + conteo de negativos)
    con.execute(f"""
        COPY (
            SELECT
              'total_asegurados' AS metric,
              MIN(total_asegurados) AS min_v,
              MAX(total_asegurados) AS max_v,
              AVG(total_asegurados) AS avg_v,
              SUM(CASE WHEN total_asegurados < 0 THEN 1 ELSE 0 END) AS negatives
            FROM imss
            UNION ALL
            SELECT 'masa_salarial_total', MIN(masa_salarial_total), MAX(masa_salarial_total), AVG(masa_salarial_total),
                   SUM(CASE WHEN masa_salarial_total < 0 THEN 1 ELSE 0 END)
            FROM imss
        ) TO '{str(outdir / (base + "_numeric_stats.csv")).replace("\\\\","/")}'
        (HEADER, DELIMITER ',');
    """)

    con.close()
    logging.info("✅ Exportaciones listas en:", outdir)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.info("Uso: python imss_duckdb_exports.py <ruta_al_csv>")
        raise SystemExit(1)
    main(sys.argv[1])
