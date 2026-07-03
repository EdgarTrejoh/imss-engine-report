# imss_duckdb_exports.py
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(message)s")

EXPECTED_COLUMNS = [
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
    "sbc_total",
]

ANALYTIC_KEY_COLUMNS = [
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

TOP_VALUE_COLUMNS = [
    "periodo_informacion",
    "cve_entidad",
    "sexo",
    "rango_edad",
    "rango_ingreso_vsm",
    "rango_ingreso_uma",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "ptpd",
]


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _num(column: str, columns: set[str], default: str = "NULL") -> str:
    if column not in columns:
        return f"CAST({default} AS DOUBLE)"
    return f"TRY_CAST({_quote(column)} AS DOUBLE)"


def _num0(column: str, columns: set[str]) -> str:
    if column not in columns:
        return "CAST(0 AS DOUBLE)"
    return f"COALESCE(TRY_CAST({_quote(column)} AS DOUBLE), 0)"


def _text(column: str, columns: set[str], default: str = "NULL") -> str:
    if column not in columns:
        return f"CAST({default} AS VARCHAR)"
    return f"CAST({_quote(column)} AS VARCHAR)"


def _copy(con: duckdb.DuckDBPyConnection, query: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"""
        COPY (
            {query}
        ) TO '{_sql_path(output_path)}'
        (HEADER, DELIMITER ',');
        """
    )


def _write_layout_report(con: duckdb.DuckDBPyConnection, columns: set[str], output_path: Path) -> None:
    values = []
    for column in EXPECTED_COLUMNS:
        values.append(
            f"('{column}', {str(column in columns).lower()}, false, "
            f"'{('present' if column in columns else 'missing')}')"
        )
    values.append(
        "('sector_economico_3', "
        f"{str('sector_economico_3' in columns).lower()}, true, "
        f"'{('forbidden_present' if 'sector_economico_3' in columns else 'absent_ok')}')"
    )

    _copy(
        con,
        f"""
        SELECT *
        FROM (
            VALUES {", ".join(values)}
        ) AS t(column_name, present, forbidden, status)
        ORDER BY forbidden DESC, column_name
        """,
        output_path,
    )


def run_audit(csv_path: str | Path, output_dir: str | Path = "reports/audits") -> dict[str, Path]:
    path = Path(csv_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    base = path.stem

    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA threads=4;")
    con.execute(
        f"""
        CREATE OR REPLACE VIEW imss AS
        SELECT *
        FROM read_csv_auto(
            '{_sql_path(path)}',
            header=true,
            sample_size=-1,
            ignore_errors=false
        );
        """
    )

    columns = {row[0] for row in con.execute("DESCRIBE imss").fetchall()}
    outputs: dict[str, Path] = {}

    def out(name: str) -> Path:
        output_path = outdir / f"{base}_{name}.csv"
        outputs[name] = output_path
        return output_path

    _write_layout_report(con, columns, out("layout_validation"))

    ta_components = " + ".join(_num0(col, columns) for col in ["tpu", "tpc", "teu", "tec"])
    masa_components = " + ".join(
        _num0(col, columns)
        for col in ["masa_sal_tpu", "masa_sal_tpc", "masa_sal_teu", "masa_sal_tec"]
    )

    _copy(
        con,
        f"""
        SELECT
            COUNT(*) AS filas,
            COUNT(DISTINCT {_text("periodo_informacion", columns)}) AS periodos,
            MIN({_text("periodo_informacion", columns)}) AS periodo_min,
            MAX({_text("periodo_informacion", columns)}) AS periodo_max,
            SUM({_num("asegurados", columns)}) AS asegurados,
            SUM({_num("no_trabajadores", columns)}) AS no_trabajadores,
            SUM({_num("ta", columns)}) AS ta,
            SUM({_num("ta_sal", columns)}) AS ta_sal,
            SUM({_num("masa_sal_ta", columns)}) AS masa_sal_ta,
            SUM({_num("masa_sal_ta", columns)}) / NULLIF(SUM({_num("ta_sal", columns)}), 0) AS sbc_total_calculado
        FROM imss
        """,
        out("summary_general"),
    )

    _copy(
        con,
        f"""
        SELECT
            {_text("periodo_informacion", columns)} AS periodo_informacion,
            COUNT(*) AS filas,
            SUM({_num("asegurados", columns)}) AS asegurados,
            SUM({_num("no_trabajadores", columns)}) AS no_trabajadores,
            SUM({_num("ta", columns)}) AS ta,
            SUM({_num("ta_sal", columns)}) AS ta_sal,
            SUM({_num("masa_sal_ta", columns)}) AS masa_sal_ta,
            SUM({_num("masa_sal_ta", columns)}) / NULLIF(SUM({_num("ta_sal", columns)}), 0) AS sbc_total_calculado
        FROM imss
        GROUP BY 1
        ORDER BY 1
        """,
        out("summary_by_period"),
    )

    _copy(
        con,
        f"""
        SELECT
            {_text("periodo_informacion", columns)} AS periodo_informacion,
            SUM({_num0("tpu", columns)} + {_num0("tpc", columns)}) AS puestos_permanentes,
            SUM({_num0("teu", columns)} + {_num0("tec", columns)}) AS puestos_eventuales,
            SUM({_num0("tpu", columns)} + {_num0("teu", columns)}) AS puestos_urbanos,
            SUM({_num0("tpc", columns)} + {_num0("tec", columns)}) AS puestos_campo,
            SUM({_num("ta", columns)}) - SUM({ta_components}) AS diff_ta_componentes
        FROM imss
        GROUP BY 1
        ORDER BY 1
        """,
        out("job_composition_by_period"),
    )

    _copy(
        con,
        f"""
        SELECT
            {_text("periodo_informacion", columns)} AS periodo_informacion,
            SUM({_num0("masa_sal_tpu", columns)} + {_num0("masa_sal_tpc", columns)}) AS masa_sal_permanentes,
            SUM({_num0("masa_sal_teu", columns)} + {_num0("masa_sal_tec", columns)}) AS masa_sal_eventuales,
            SUM({_num0("masa_sal_tpu", columns)} + {_num0("masa_sal_teu", columns)}) AS masa_sal_urbanos,
            SUM({_num0("masa_sal_tpc", columns)} + {_num0("masa_sal_tec", columns)}) AS masa_sal_campo,
            SUM({_num("masa_sal_ta", columns)}) - SUM({masa_components}) AS diff_masa_sal_componentes
        FROM imss
        GROUP BY 1
        ORDER BY 1
        """,
        out("salary_composition_by_period"),
    )

    _copy(
        con,
        f"""
        SELECT
            COUNT(*) AS filas_revisadas,
            SUM(
                CASE
                    WHEN {_num0("ta_sal", columns)} = 0
                         AND {_num("sbc_total", columns)} IS NOT NULL
                    THEN 1 ELSE 0
                END
            ) AS filas_con_sbc_y_denominador_cero,
            MAX(ABS({_num("sbc_total", columns)} - ({_num("masa_sal_ta", columns)} / NULLIF({_num("ta_sal", columns)}, 0)))) AS max_diff_sbc_total,
            SUM({_num("masa_sal_ta", columns)}) / NULLIF(SUM({_num("ta_sal", columns)}), 0) AS sbc_total_calculado
        FROM imss
        """,
        out("sbc_validation"),
    )

    missing_key_columns = [column for column in ANALYTIC_KEY_COLUMNS if column not in columns]
    if missing_key_columns:
        missing = ", ".join(missing_key_columns).replace("'", "''")
        _copy(
            con,
            f"""
            SELECT
                'skipped_missing_key_columns' AS status,
                '{missing}' AS missing_key_columns,
                CAST(NULL AS BIGINT) AS llaves_duplicadas,
                CAST(NULL AS BIGINT) AS filas_excedentes
            """,
            out("duplicate_keys"),
        )
    else:
        key_sql = ", ".join(_quote(column) for column in ANALYTIC_KEY_COLUMNS)
        _copy(
            con,
            f"""
            SELECT
                'ok' AS status,
                '' AS missing_key_columns,
                COUNT(*) AS llaves_duplicadas,
                SUM(cnt - 1) AS filas_excedentes
            FROM (
                SELECT {key_sql}, COUNT(*) AS cnt
                FROM imss
                GROUP BY {key_sql}
                HAVING COUNT(*) > 1
            )
            """,
            out("duplicate_keys"),
        )

    _copy(
        con,
        f"""
        SELECT
            {_text("ptpd", columns)} AS ptpd,
            COUNT(*) AS filas,
            SUM({_num("ta", columns)}) AS puestos,
            SUM({_num("ta_sal", columns)}) AS puestos_con_salario,
            SUM({_num("masa_sal_ta", columns)}) AS masa_sal_ta
        FROM imss
        GROUP BY 1
        ORDER BY 1
        """,
        out("ptpd_distribution"),
    )

    _copy(
        con,
        f"""
        SELECT
            {_text("periodo_informacion", columns)} AS periodo_informacion,
            SUM({_num("ta", columns)}) AS puestos_ptpd_1,
            SUM({_num("ta_sal", columns)}) AS puestos_con_salario_ptpd_1,
            SUM({_num("masa_sal_ta", columns)}) AS masa_sal_ta_ptpd_1,
            SUM({_num("masa_sal_ta", columns)}) / NULLIF(SUM({_num("ta_sal", columns)}), 0) AS sbc_plataformas
        FROM imss
        WHERE {_text("ptpd", columns, "''")} = '1'
        GROUP BY 1
        ORDER BY 1
        """,
        out("ptpd_sbc_by_period"),
    )

    for column in TOP_VALUE_COLUMNS:
        if column not in columns:
            continue
        _copy(
            con,
            f"""
            SELECT
                '{column}' AS column_name,
                {_quote(column)} AS value,
                COUNT(*) AS filas,
                SUM({_num("ta", columns)}) AS ta
            FROM imss
            GROUP BY 1, 2
            ORDER BY filas DESC
            LIMIT 50
            """,
            out(f"top_{column}"),
        )

    con.close()
    logging.info("Auditoria DuckDB exportada en: %s", outdir)
    return outputs


def main(csv_path: str, output_dir: str = "reports/audits") -> dict[str, Path]:
    return run_audit(csv_path, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit a Phase 2 IMSS CSV with DuckDB.")
    parser.add_argument("input_csv")
    parser.add_argument("--output-dir", default="reports/audits")
    args = parser.parse_args()
    main(args.input_csv, args.output_dir)
