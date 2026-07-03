import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yaml

from imss_duckdb_exports import run_audit as run_duckdb_audit
from src.imss_engine.aggregate import (
    DERIVED_SUM_COLUMNS,
    aggregate_imss_chunk,
    get_group_columns,
)
from src.imss_engine.metrics import add_validation_differences, calculate_sbc_metrics
from src.imss_engine.manifest import (
    add_period_result,
    create_manifest_base,
    finalize_manifest_failure,
    finalize_manifest_success,
    now_utc_iso,
    set_audit_failure,
    set_audit_success,
    write_manifest,
)
from src.imss_engine.schema import CRITICAL_METRIC_COLUMNS


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

OUTPUT_FILE = None
CHUNK_SIZE = None
COL_PERIODO = "periodo_informacion"


def periodo_from_url(url):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", url)
    if not m:
        return "0000-00-00"
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def combinar_agregados(df):
    """Combina chunks agregados sin usar timestamp como llave analitica."""
    sum_columns = list(CRITICAL_METRIC_COLUMNS) + list(DERIVED_SUM_COLUMNS)
    combinado = (
        df.groupby(get_group_columns(), as_index=False, dropna=False)[sum_columns]
        .sum(min_count=1)
    )
    combinado = calculate_sbc_metrics(combinado)
    combinado = add_validation_differences(combinado)
    return combinado


def get_temp_output_path(final_output: Path) -> Path:
    """Return the per-run staging path for an output file."""
    return final_output.with_suffix(final_output.suffix + ".tmp")


def replace_output_atomically(tmp_output: Path, final_output: Path) -> None:
    """Atomically replace final output after a complete successful run."""
    final_output.parent.mkdir(parents=True, exist_ok=True)
    os.replace(tmp_output, final_output)


def cleanup_temp_output(tmp_output: Path) -> None:
    """Remove a stale or failed per-run staging output if it exists."""
    if tmp_output.exists():
        tmp_output.unlink()


def _audit_file_list(audit_outputs, audit_output_dir):
    audit_dir = Path(audit_output_dir)
    if isinstance(audit_outputs, dict):
        paths = audit_outputs.values()
    elif audit_outputs is None:
        paths = audit_dir.glob("*")
    else:
        paths = audit_outputs
    files = []
    for path in paths:
        audit_file = Path(path)
        try:
            files.append(str(audit_file.relative_to(audit_dir)))
        except ValueError:
            files.append(audit_file.name)
    return files


def run_urls_with_staging(
    urls,
    final_output,
    manifest=None,
    manifest_output_dir="reports/manifests",
    audit_runner=run_duckdb_audit,
    audit_base_dir="reports/audits",
):
    """Process all URLs into a temporary file and publish only on full success."""
    global OUTPUT_FILE

    final_output = Path(final_output)
    tmp_output = get_temp_output_path(final_output)
    cleanup_temp_output(tmp_output)
    tmp_output.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE = tmp_output

    first = True
    final_published = False
    try:
        for url in urls:
            period_result = None
            period_started_at = now_utc_iso()
            try:
                processed = procesar_url(url, first_file=first)
                if not processed:
                    raise RuntimeError(f"No se pudo procesar el periodo: {periodo_from_url(url)}")
                period_result = (
                    processed
                    if isinstance(processed, dict)
                    else {
                        "periodo_informacion": periodo_from_url(url),
                        "source_url": url,
                        "status": "success",
                        "started_at": period_started_at,
                        "finished_at": now_utc_iso(),
                        "rows_read": None,
                        "rows_processed": None,
                        "columns_detected": [],
                        "error": None,
                    }
                )
            except Exception as period_error:
                if manifest is not None:
                    add_period_result(
                        manifest,
                        {
                            "periodo_informacion": periodo_from_url(url),
                            "source_url": url,
                            "status": "failed",
                            "started_at": period_started_at,
                            "finished_at": now_utc_iso(),
                            "rows_read": None,
                            "rows_processed": None,
                            "columns_detected": [],
                            "error": str(period_error),
                        },
                    )
                raise

            if not period_result:
                raise RuntimeError(f"No se pudo procesar el periodo: {periodo_from_url(url)}")
            if manifest is not None:
                add_period_result(manifest, period_result)
            first = False

        replace_output_atomically(tmp_output, final_output)
        final_published = True
        OUTPUT_FILE = final_output
        if manifest is not None:
            finalize_manifest_success(manifest, final_output)
            audit_output_dir = Path(audit_base_dir) / manifest["run_id"]
            try:
                audit_outputs = audit_runner(final_output, audit_output_dir)
                set_audit_success(
                    manifest,
                    audit_output_dir,
                    _audit_file_list(audit_outputs, audit_output_dir),
                )
            except Exception as audit_error:
                set_audit_failure(manifest, audit_output_dir, audit_error)
                raise
            finalize_manifest_success(manifest, final_output, audit_dir=audit_output_dir)
            write_manifest(manifest, manifest_output_dir)
    except Exception as error:
        cleanup_temp_output(tmp_output)
        OUTPUT_FILE = final_output
        if manifest is not None:
            finalize_manifest_failure(
                manifest,
                error,
                preserve_output_metadata=final_published,
            )
            write_manifest(manifest, manifest_output_dir)
        raise


def procesar_url(url, first_file):
    if OUTPUT_FILE is None or CHUNK_SIZE is None:
        raise RuntimeError("Config no cargada. Ejecuta main() antes de procesar URLs.")

    periodo = periodo_from_url(url)
    period_started_at = now_utc_iso()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    temp_file = f"temp_{periodo}.csv"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    logging.info(f"Iniciando: {periodo}")

    try:
        logging.info("Descargando archivo desde el IMSS...")
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(temp_file, "wb") as f:
                for chunk_dl in r.iter_content(chunk_size=8192):
                    f.write(chunk_dl)

        chunks = pd.read_csv(
            temp_file,
            sep="|",
            encoding="latin-1",
            chunksize=CHUNK_SIZE,
            low_memory=False,
            keep_default_na=False,
        )

        agg_global = None
        rows_read = 0
        columns_detected = []
        for i, chunk in enumerate(chunks, start=1):
            logging.info(f"Procesando bloque {i}...")
            rows_read += len(chunk)
            for column in chunk.columns:
                if column not in columns_detected:
                    columns_detected.append(column)
            chunk[COL_PERIODO] = periodo
            agg_chunk = aggregate_imss_chunk(chunk)

            if agg_global is None:
                agg_global = agg_chunk
            else:
                agg_global = pd.concat([agg_global, agg_chunk], ignore_index=True)
                agg_global = combinar_agregados(agg_global)

        agg_global["fuente"] = "IMSS"
        agg_global["timestamp"] = timestamp
        mode = "w" if first_file else "a"
        agg_global.to_csv(OUTPUT_FILE, mode=mode, header=first_file, index=False, encoding="utf-8-sig")

        logging.info(f"{periodo} finalizado. Eliminando temporal...")
        os.remove(temp_file)
        time.sleep(3)
        return {
            "periodo_informacion": periodo,
            "source_url": url,
            "status": "success",
            "started_at": period_started_at,
            "finished_at": now_utc_iso(),
            "rows_read": rows_read,
            "rows_processed": len(agg_global),
            "columns_detected": columns_detected,
            "error": None,
        }

    except Exception as e:
        logging.error(f"Error en {periodo}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise


def main():
    global OUTPUT_FILE, CHUNK_SIZE

    config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)["etl"]

    urls = [config["base_url"].format(mes) for mes in config["meses"]]
    final_output = Path(config["output_file"])
    CHUNK_SIZE = config["chunk_size"]

    configured_periods = [
        {
            "periodo_informacion": periodo_from_url(url),
            "source_url": url,
        }
        for url in urls
    ]
    manifest = create_manifest_base(
        config_path=config_path,
        output_file=final_output,
        configured_periods=configured_periods,
    )

    run_urls_with_staging(urls, final_output, manifest=manifest)

    logging.info(f"PROCESO COMPLETO: {final_output}")


if __name__ == "__main__":
    main()
