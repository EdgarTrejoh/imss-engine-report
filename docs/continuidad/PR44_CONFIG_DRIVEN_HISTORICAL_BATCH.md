# PR #44 - Historical batch dirigido por configuracion

El runner `scripts/run_imss_historical_batch.py` usa la seccion YAML `imss_historical_batch` para resolver el rango, modo y limites del batch historico.

La prioridad es:

```text
CLI > imss_historical_batch > default seguro
```

Ejemplo de configuracion:

```yaml
imss_historical_batch:
  enabled: true
  mode: dry_run
  start_period: "2017-01-31"
  end_period: "2017-12-31"
  max_periods_per_run: 3
  stop_on_failure: true
  raw_root: data/raw/imss/asegurados
  output_dir: outputs/pipeline
  chunk_size: 100000
  duckdb_memory_limit: 1GB
  duckdb_threads: 2
  batch_size: 5000
  promotion_batch_size: 50000
```

Dry-run explicito:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --config .\config\config.yaml `
  --dry-run `
  --start-period 2025-06-30 `
  --end-period 2025-08-31
```

Los flags CLI pueden reemplazar valores individuales. Un modo `execute` siempre exige `max_periods <= 3` y `stop_on_failure: true`. Si `enabled` es `false`, solo se permite continuar cuando modo, periodo inicial y periodo final se proporcionan explicitamente por CLI.

El resultado y el manifest incluyen `effective_config` con los valores efectivos y la fuente de cada parametro. El runner no modifica el archivo YAML, no usa `data/processed/imss_concentrado.csv` y conserva los guardrails de PR #42.

DuckDB es una propiedad fija del flujo, no una seleccion configurable:

```text
run_imss_historical_batch.py
→ execute_historical_batch
→ execute_single_period_pipeline
→ process_imss_raw_period
```

El manifest registra `processing_engine: duckdb` con fuente `fixed`. El CLI ya
no expone `--processing-engine`; una configuracion heredada con valor `pandas`
falla explicitamente. Las pruebas verifican que la ausencia de esa clave no
active una ruta pandas.

La guia operativa vigente se encuentra en
`docs/operations/historical_batch_duckdb.md`.
