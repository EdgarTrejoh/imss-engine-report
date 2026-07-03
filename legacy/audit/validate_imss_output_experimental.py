from __future__ import annotations

import sys
from pathlib import Path

import duckdb


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("imss_analisis_profundo.csv")

    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    con = duckdb.connect()

    path_sql = str(path.resolve()).replace("\\", "/").replace("'", "''")

    con.execute(
        f"""
        CREATE OR REPLACE VIEW imss AS
        SELECT *
        FROM read_csv_auto(
            '{path_sql}',
            header=true,
            sample_size=-1,
            ignore_errors=false
        )
        """
    )

    columns = [row[0] for row in con.execute("DESCRIBE imss").fetchall()]
    print("\n=== COLUMNAS DETECTADAS ===")
    print(", ".join(columns))

    expected = [
        "periodo_informacion",
        "asegurados",
        "no_trabajadores",
        "ta",
        "ta_sal",
        "tpu",
        "tpc",
        "teu",
        "tec",
        "tpu_sal",
        "tpc_sal",
        "teu_sal",
        "tec_sal",
        "masa_sal_ta",
        "masa_sal_tpu",
        "masa_sal_tpc",
        "masa_sal_teu",
        "masa_sal_tec",
        "rango_ingreso_vsm",
        "rango_ingreso_uma",
        "sector_economico_1",
        "sector_economico_2",
        "sector_economico_4",
        "ptpd",
        "sbc_total",
    ]

    missing = [c for c in expected if c not in columns]
    forbidden = [c for c in columns if c == "sector_economico_3"]

    print("\n=== VALIDACIÓN DE LAYOUT ===")
    print(f"Columnas esperadas faltantes: {missing if missing else 'NINGUNA'}")
    print(f"Columnas prohibidas detectadas: {forbidden if forbidden else 'NINGUNA'}")

    print("\n=== RESUMEN GENERAL ===")
    print(
        con.execute(
            """
            SELECT
                COUNT(*) AS filas,
                COUNT(DISTINCT periodo_informacion) AS periodos,
                MIN(periodo_informacion) AS periodo_min,
                MAX(periodo_informacion) AS periodo_max,
                SUM(TRY_CAST(asegurados AS DOUBLE)) AS asegurados,
                SUM(TRY_CAST(no_trabajadores AS DOUBLE)) AS no_trabajadores,
                SUM(TRY_CAST(ta AS DOUBLE)) AS puestos_trabajo,
                SUM(TRY_CAST(ta_sal AS DOUBLE)) AS puestos_con_salario,
                SUM(TRY_CAST(masa_sal_ta AS DOUBLE)) AS masa_sal_total,
                SUM(TRY_CAST(masa_sal_ta AS DOUBLE))
                    / NULLIF(SUM(TRY_CAST(ta_sal AS DOUBLE)), 0) AS sbc_total_calculado
            FROM imss
            """
        ).df().to_string(index=False)
    )

    print("\n=== RESUMEN POR PERIODO ===")
    print(
        con.execute(
            """
            SELECT
                periodo_informacion,
                COUNT(*) AS filas,
                SUM(TRY_CAST(asegurados AS DOUBLE)) AS asegurados,
                SUM(TRY_CAST(no_trabajadores AS DOUBLE)) AS no_trabajadores,
                SUM(TRY_CAST(ta AS DOUBLE)) AS puestos_trabajo,
                SUM(TRY_CAST(ta_sal AS DOUBLE)) AS puestos_con_salario,
                SUM(TRY_CAST(masa_sal_ta AS DOUBLE)) AS masa_sal_total,
                SUM(TRY_CAST(masa_sal_ta AS DOUBLE))
                    / NULLIF(SUM(TRY_CAST(ta_sal AS DOUBLE)), 0) AS sbc_total_calculado,
                SUM(TRY_CAST(tpu AS DOUBLE) + TRY_CAST(tpc AS DOUBLE)) AS puestos_permanentes,
                SUM(TRY_CAST(teu AS DOUBLE) + TRY_CAST(tec AS DOUBLE)) AS puestos_eventuales,
                SUM(TRY_CAST(tpu AS DOUBLE) + TRY_CAST(tpc AS DOUBLE) + TRY_CAST(teu AS DOUBLE) + TRY_CAST(tec AS DOUBLE)) AS componentes_ta,
                SUM(TRY_CAST(ta AS DOUBLE))
                    - SUM(TRY_CAST(tpu AS DOUBLE) + TRY_CAST(tpc AS DOUBLE) + TRY_CAST(teu AS DOUBLE) + TRY_CAST(tec AS DOUBLE)) AS diff_ta_componentes,
                SUM(TRY_CAST(masa_sal_ta AS DOUBLE))
                    - SUM(
                        TRY_CAST(masa_sal_tpu AS DOUBLE)
                        + TRY_CAST(masa_sal_tpc AS DOUBLE)
                        + TRY_CAST(masa_sal_teu AS DOUBLE)
                        + TRY_CAST(masa_sal_tec AS DOUBLE)
                    ) AS diff_masa_componentes
            FROM imss
            GROUP BY periodo_informacion
            ORDER BY periodo_informacion
            """
        ).df().to_string(index=False)
    )

    print("\n=== VALIDACIÓN SBC FILA A FILA ===")
    print(
        con.execute(
            """
            SELECT
                COUNT(*) AS filas_revisadas,
                SUM(
                    CASE
                        WHEN TRY_CAST(ta_sal AS DOUBLE) = 0
                             AND TRY_CAST(sbc_total AS DOUBLE) IS NOT NULL
                        THEN 1 ELSE 0
                    END
                ) AS filas_con_sbc_y_denominador_cero,
                MAX(
                    ABS(
                        TRY_CAST(sbc_total AS DOUBLE)
                        - (
                            TRY_CAST(masa_sal_ta AS DOUBLE)
                            / NULLIF(TRY_CAST(ta_sal AS DOUBLE), 0)
                        )
                    )
                ) AS max_diff_sbc_total
            FROM imss
            """
        ).df().to_string(index=False)
    )

    group_cols = [
        "periodo_informacion",
        "cve_delegacion",
        "cve_subdelegacion",
        "cve_entidad",
        "cve_municipio",
        "tamaño_patron",
        "sexo",
        "rango_edad",
        "rango_ingreso_vsm",
        "rango_ingreso_uma",
        "sector_economico_1",
        "sector_economico_2",
        "sector_economico_4",
        "ptpd",
    ]

    available_group_cols = [c for c in group_cols if c in columns]
    quoted_group_cols = ", ".join([f'"{c}"' for c in available_group_cols])

    print("\n=== VALIDACIÓN DE DUPLICADOS POR LLAVE ANALÍTICA ===")
    print(
        con.execute(
            f"""
            SELECT
                COUNT(*) AS llaves_duplicadas,
                SUM(cnt - 1) AS filas_excedentes
            FROM (
                SELECT {quoted_group_cols}, COUNT(*) AS cnt
                FROM imss
                GROUP BY {quoted_group_cols}
                HAVING COUNT(*) > 1
            )
            """
        ).df().to_string(index=False)
    )

    if "ptpd" in columns:
        print("\n=== DISTRIBUCIÓN PTPD ===")
        print(
            con.execute(
                """
                SELECT
                    ptpd,
                    COUNT(*) AS filas,
                    SUM(TRY_CAST(ta AS DOUBLE)) AS puestos_trabajo,
                    SUM(TRY_CAST(ta_sal AS DOUBLE)) AS puestos_con_salario
                FROM imss
                GROUP BY ptpd
                ORDER BY ptpd
                """
            ).df().to_string(index=False)
        )
        print("\n=== SBC PLATAFORMAS DIGITALES ===")

    print(
        con.execute(
            """
            SELECT
                periodo_informacion,
                ptpd,
                SUM(TRY_CAST(ta AS DOUBLE)) AS puestos_trabajo,
                SUM(TRY_CAST(ta_sal AS DOUBLE)) AS puestos_con_salario,
                ROUND(
                    SUM(TRY_CAST(masa_sal_ta AS DOUBLE))
                    / NULLIF(SUM(TRY_CAST(ta_sal AS DOUBLE)), 0),
                    1
                ) AS sbc_ptpd
            FROM imss
            WHERE CAST(ptpd AS VARCHAR) = '1'
            GROUP BY periodo_informacion, ptpd
            """
        ).df().to_string(index=False)
    )

    print("\n=== VALIDACIÓN TERMINADA ===")


if __name__ == "__main__":
    main()