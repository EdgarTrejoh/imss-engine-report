# Checkpoint DuckDB y enero de 2025 — 2026-07-16

> Documento historico. Conserva el estado observado el 2026-07-16. Para la
> configuracion y los comandos vigentes consulte
> `docs/operations/historical_batch_duckdb.md`. `processing_engine` ya no es
> configurable y DuckDB es el unico motor productivo.

## Estado

La correccion de encoding y el procesamiento externo a memoria quedaron
validados. La suite local termina con:

```text
200 passed
0 failed
```

## Encoding

El raw `asg-2025-01-31.csv` es UTF-8 con BOM. La resolucion automatica detecta
`utf-8-sig` mediante el encabezado y el esquema requerido. El mismo valor se
propaga a `pandas.read_csv`; no existe una segunda deteccion.

## Procesamiento local

```text
run_id: 20260716T180420Z_a4c002c9
motor: duckdb
memoria: 1GB
hilos: 2
chunk_size: 100000
chunks: 47
filas raw: 4,643,036
filas salida: 4,643,036
```

El raw contiene 4,643,036 llaves analiticas unicas, cero grupos duplicados y
maximo un registro por llave. La ausencia de reduccion es correcta: el archivo
fuente ya esta al nivel final de granularidad.

## Reconciliacion

- Llaves unicas en salida: 4,643,036.
- Duplicados en salida: 0.
- Metricas enteras: igualdad exacta.
- Diferencia maxima de masa salarial: 0.0013523101806640625 sobre totales de
  miles de millones, atribuible al orden de suma de punto flotante.
- SBC total no finito: 0.
- `tamaño_patron` vacio o nulo en salida: 0.

Reporte:

```text
outputs/processing/duckdb_2025_01/
reconciliation_20260716T180420Z_a4c002c9_2025-01-31.json
```

## Artefactos

```text
CSV:     1,141,523,858 bytes
Parquet:   199,727,061 bytes
Parquet compression: ZSTD
```

CSV y Parquet contienen 4,643,036 filas. El CSV conserva compatibilidad; el
Parquet es el artefacto recomendado para analisis historico.

## PostgreSQL

El pre-check de enero de 2025 encontro:

```text
period_control: 0
staging: 0
final: 0
```

El intento de carga a staging fue bloqueado antes de leer filas:

```text
reason: missing_period_control
rows_inserted_staging: 0
committed: false
```

No se modificaron staging, period_control ni la tabla final. El siguiente paso
requiere autorizacion explicita para registrar enero con estado `pending`,
cargar staging y detenerse antes de promocion.

## Configuracion historical batch

```yaml
chunk_size: 100000
duckdb_memory_limit: "1GB"
duckdb_threads: 2
```

La indicacion original de no ejecutar el historical batch hasta validar staging
corresponde al momento de este checkpoint y no constituye la instruccion
operativa vigente.
