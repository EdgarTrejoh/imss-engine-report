# Checkpoint — IMSS PostgreSQL local load

Fecha: 2026-07-09  
Proyecto: IMSS Engine Report  
Base local: imss_engine_test  
Schema: imss  
Tabla final: imss.imss_hechos_asegurados  

## Dictamen

Carga PostgreSQL local completada y validada.

El concentrado local `data/processed/imss_concentrado.csv` fue enviado a PostgreSQL de forma controlada, periodo por periodo, usando el loader existente.

No se ejecutó carga masiva global.
No se usó DataFrame.
No se modificó el CSV fuente.
No se subieron archivos `data/` ni `outputs/` a Git.

## Estado final PostgreSQL

Periodos finales: 7  
Total filas finales: 26,718,841  
Duplicados por llave analítica: 0  

| Periodo | Filas final | Status control | Run ID |
|---|---:|---|---|
| 2016-01-31 | 3,638,419 | loaded | manual_finalize_20160131 |
| 2016-02-29 | 3,655,343 | loaded | manual_finalize_20160229 |
| 2016-03-31 | 3,652,496 | loaded | manual_finalize_20160331 |
| 2016-04-30 | 3,665,505 | loaded | pg_load_20160430_20260709_155946 |
| 2016-05-31 | 3,683,768 | loaded | pg_load_20160531_20260709_162625 |
| 2016-06-30 | 3,691,605 | loaded | pg_load_20160630_20260709_171721 |
| 2026-01-31 | 4,731,705 | loaded | manual_finalize_20260131 |

## Nuevos manifests PostgreSQL

| Run ID | Run mode | Status |
|---|---|---|
| pg_load_20160430_20260709_155946 | final_manifest | completed |
| pg_load_20160531_20260709_162625 | final_manifest | completed |
| pg_load_20160630_20260709_171721 | final_manifest | completed |

## Validaciones ejecutadas

- `check_postgres_connection.py`: OK
- `check_postgres_schema.py`: OK
- `--summary-reserved-periods`: 7 periodos
- `--summarize-source-periods`: 26,718,841 filas fuente
- `--check-existing`: periodos nuevos antes de carga; `already_exists` después de carga
- `--validate-post-promotion`: passed para 2016-04-30, 2016-05-31 y 2016-06-30
- Validación SQL final:
  - `FINAL_TOTAL_MATCH: True`
  - `DUPLICATE_KEY_GROUPS: 0`
  - Todos los conteos por periodo coinciden con el concentrado

## Incidente controlado

Durante `load-staging` de 2016-06-30 ocurrió una pérdida de conexión.

Diagnóstico posterior:

- `STAGING_COUNT: 0`
- `FINAL_COUNT: 0`
- `PERIOD_CONTROL: pending`
- `RUN_MANIFEST: pending`

No hubo carga parcial. Se reintentó con el mismo `run_id` y el periodo cerró correctamente.

## Estado de cierre

PostgreSQL local queda sincronizado contra el concentrado operativo local para los 7 periodos disponibles.

Siguiente frente sugerido: preparar estrategia controlada para Supabase, separando schema, índices, constraints, carga de datos, validación y rollback.
