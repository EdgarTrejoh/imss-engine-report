# Plan De Trabajo

## Estado Actual

El repositorio contiene un motor local IMSS en estabilizacion. El ETL principal sigue en `etl_imss.py`; la logica de normalizacion, transformacion, metricas y agregacion vive en `src/imss_engine/` con pruebas unitarias.

La auditoria ligera operativa esta en `src/imss_engine/light_audit.py`. La auditoria DuckDB profunda opcional esta en `imss_duckdb_exports.py`. El manifest de corrida esta en `src/imss_engine/manifest.py`.

El procesamiento raw tiene una sola ruta productiva. Pandas lee y transforma
por chunks con tipos dimensionales explicitos; DuckDB persiste y consolida los
agregados parciales con uso de disco, publica CSV atomicamente y puede generar
Parquet comprimido. No existe fallback al motor pandas completo.

## Cerrado En Fase 2

- Reglas de negocio IMSS estabilizadas.
- Auditoria DuckDB oficial.
- Idempotencia por corrida completa con staging y replace atomico.
- Manifest JSON de corrida.
- Integracion legacy ETL -> archivo final -> auditoria DuckDB -> manifest.
- Pruebas locales con fixtures pequenos.
- GitHub Actions ligero para ejecutar `pytest` sin datos reales.
- Consolidacion insert-only hacia `data/processed/imss_concentrado.csv`.
- Modos `mes_consulta` y `periodo_consulta`.
- Hash ligero `period_fingerprint_hash`.
- Auditoria ligera por periodo antes de insertar. Este flujo no ejecuta DuckDB automaticamente sobre el concentrado completo.
- Resolucion deterministica de encoding `utf-8-sig`/`latin-1`.
- Motor DuckDB externo a memoria con temporales exclusivos por corrida.
- Equivalencia entre consolidacion de uno y multiples parciales validada con fixtures.
- Salida Parquet Zstandard opcional.
- Enero 2025 procesado y reconciliado: 4,643,036 filas, cero llaves duplicadas.
- DuckDB fijo desde historical batch hasta raw processing; selector operativo retirado.
- Suite completa validada con 207 pruebas.

## Clasificacion De Auditorias

- Auditoria ligera: validacion operativa, rapida, por periodo y obligatoria antes de insertar al concentrado.
- Auditoria DuckDB: auditoria profunda opcional/on-demand para revisar un CSV o concentrado completo. Puede tardar varios minutos y no debe asumirse como paso obligatorio despues de cada carga del concentrado.

## Operativo Actual

- Ejecutar tests: `python -m pytest`.
- Ejecutar auditoria manual: `python scripts/run_audit.py <archivo_csv> --output-dir reports/audits/audit_manual`.
- Ejecutar ETL local: `python scripts/run_etl.py`.
- Configurar `etl.mode` como `mes_consulta` o `periodo_consulta` antes de ejecutar ETL real.
- Ejecutar DuckDB manualmente sobre el concentrado solo cuando se requiera un snapshot completo de auditoria.
- Usar `chunk_size: 100000`, `duckdb_memory_limit: 1GB` y
  `duckdb_threads: 2` para historicos grandes. DuckDB no se selecciona: es el
  unico motor productivo.
- Ejecutar primero `--dry-run` y revisar el manifest antes de cada bloque real.

## Fuera De Alcance Actual

- `full_refresh`.
- `upsert_period`.
- Append mensual.
- API.
- Dashboard.
- Docker.
- Orquestacion productiva.
- Observabilidad avanzada.

## Siguiente Trabajo Sugerido

1. Ejecutar un dry-run acotado para `2025-06-30` a `2025-08-31`.
2. Confirmar que el plan marca los tres periodos esperados y DuckDB como motor.
3. Verificar espacio para raw, parciales DuckDB, CSV y WAL antes de ejecutar.
4. Ejecutar como maximo tres periodos con `stop_on_failure`.
5. Conservar y revisar los manifests de cada periodo y del batch.
