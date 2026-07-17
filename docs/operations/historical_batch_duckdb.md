# Historical batch IMSS con DuckDB

Esta es la guia operativa vigente para planear y ejecutar periodos historicos
IMSS. Los documentos bajo `docs/continuidad` y `docs/checkpoints` son evidencia
historica y pueden conservar valores predeterminados anteriores.

## Arquitectura productiva

```text
raw CSV
→ resolucion de encoding por encabezado y esquema
→ pandas.read_csv por chunks con RAW_DIMENSION_DTYPES
→ transformaciones Python compartidas
→ agregados parciales Parquet por corrida
→ consolidacion externa con DuckDB
→ salida final atomica
→ staging y promocion PostgreSQL
```

DuckDB es el unico motor productivo de consolidacion. Pandas permanece como
lector y transformador por chunks. No existe una ruta que acumule todos los
agregados parciales en memoria.

No utilice `--processing-engine` ni agregue `processing_engine` a la
configuracion. El manifest registra `processing_engine: duckdb` como hecho de
ejecucion. Un valor heredado `processing_engine: pandas` se rechaza.

## Configuracion

```yaml
imss_historical_batch:
  enabled: true
  mode: "dry_run"
  start_period: "2025-06-30"
  end_period: "2025-08-31"
  max_periods_per_run: 3
  stop_on_failure: true
  raw_root: "data/raw/imss/asegurados"
  output_dir: "outputs/pipeline"
  chunk_size: 100000
  duckdb_memory_limit: "1GB"
  duckdb_threads: 2
  batch_size: 5000
  promotion_batch_size: 50000
```

La clave YAML vigente es `max_periods_per_run`. El resolver la expone como
`max_periods` dentro de `effective_config`; no son dos opciones distintas.

## Dry-run

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --config .\config\config.yaml `
  --dry-run `
  --start-period 2025-06-30 `
  --end-period 2025-08-31
```

El dry-run normal abre una conexion PostgreSQL de lectura para consultar el
estado de cada periodo. No descarga raws, no procesa archivos y no escribe en
staging, final, `period_control` ni `run_manifest`.

Antes de ejecutar, revise en el manifest:

- `status: planned`;
- `processing_engine: duckdb`;
- `sources.processing_engine: fixed`;
- `writes_postgresql: false`;
- periodos y `recommended_action` esperados;
- ausencia de periodos bloqueados o estados inconsistentes.

## Ejecucion de un bloque

Ejecute solo despues de aprobar el dry-run:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --config .\config\config.yaml `
  --execute `
  --start-period 2025-06-30 `
  --end-period 2025-08-31 `
  --max-periods 3 `
  --stop-on-failure
```

El limite operativo es tres periodos por corrida. Cada periodo delega al
single-period pipeline y conserva sus propios manifests y temporales. Una falla
detiene la seleccion restante.

## Controles posteriores

Confirme para cada periodo:

- `encoding_detected` igual al usado por `pandas.read_csv`;
- `processing_engine: duckdb`;
- conteos raw, staging y final;
- cero duplicados por llave analitica;
- sumas de control y SBC validos;
- cero sufijos `.0` generados en codigos dimensionales;
- temporales limpiados;
- `period_control` y `run_manifest` finalizados;
- periodos no seleccionados sin cambios.

## Procesamiento raw local sin PostgreSQL

```powershell
.\.venv\Scripts\python.exe .\scripts\process_imss_raw.py `
  --period 2025-06-30 `
  --chunk-size 100000 `
  --duckdb-memory-limit 1GB `
  --duckdb-threads 2 `
  --write-parquet `
  --parquet-compression zstd
```

Este comando genera artefactos locales y no carga PostgreSQL.

## Fallos y recursos

- DuckDB es una dependencia obligatoria; su ausencia produce un error
  controlado y no activa un fallback pandas.
- Reserve espacio para el raw, parciales Parquet, spill de DuckDB, CSV temporal
  y salida final.
- La publicacion CSV es atomica: archivo temporal, validacion y reemplazo.
- Por defecto los temporales se limpian. Use
  `--preserve-temporary-on-failure` solo para diagnostico.
- No elimine manifests de corridas anteriores: son evidencia operativa.
