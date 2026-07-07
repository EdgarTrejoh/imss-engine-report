# PostgreSQL Loader Plan

## Estado De Esta Rama

Este documento describe el flujo operativo actual y objetivo del loader PostgreSQL IMSS.

El proyecto ya cuenta con modos controlados de inspeccion de CSV, registro de periodo, manifest inicial, carga insert-only a staging, promocion insert-only de staging a final, validacion post-promocion, finalizacion formal de periodo en `period_control` y manifest final de corrida. La etapa de housekeeping auditable sigue documentada como trabajo posterior.

## Componentes Creados

- `src/imss_engine/postgres/config.py`: lectura segura de variables `IMSS_PG_*`.
- `src/imss_engine/postgres/connection.py`: helper para construir conexiones explicitas a PostgreSQL.
- `src/imss_engine/postgres/loader.py`: funciones controladas para checks, registros iniciales, staging y promocion insert-only.
- `scripts/run_postgres_loader.py`: CLI operativo con dry-run por defecto y modos explicitos para cada paso controlado.
- `.env.example`: variables esperadas sin secretos reales.

## Variables De Entorno

```text
IMSS_PG_HOST
IMSS_PG_PORT
IMSS_PG_DATABASE
IMSS_PG_USER
IMSS_PG_PASSWORD
```

Los modulos pueden importarse sin estas variables. Si faltan, el CLI dry-run solo reporta configuracion incompleta; los modos que abren conexion requieren configuracion completa.

## Flujo Operativo Insert-Only

El loader debe conservar este orden operativo:

1. Validar `periodo_informacion`.
2. Verificar si el periodo ya existe en `imss.imss_period_control` y `imss.imss_hechos_asegurados`.
3. Preparar `imss.imss_staging_asegurados`.
4. Validar staging contra reglas IMSS vigentes.
5. Promover staging a `imss.imss_hechos_asegurados` solo si el periodo es nuevo y valido.
6. Registrar resultado en `imss.imss_period_control`.
7. Registrar manifest en `imss.imss_run_manifest`.

Pasos ya implementados como modos controlados: inspeccion de CSV, perfilado streaming, resumen por periodo, chequeo de periodo existente, registro inicial en `period_control`, registro inicial en `run_manifest`, carga insert-only a staging, promocion insert-only a final, validacion post-promocion, finalizacion formal de periodo y manifest final de corrida.

Pasos posteriores: housekeeping auditable del CSV fuente.

La version actual conserva semantica insert-only. Periodos existentes deben resolverse como `already_exists` o conflicto, no sobrescribirse.

## Politica Operativa De Staging Y Final

### Rol De `imss.imss_staging_asegurados`

`imss.imss_staging_asegurados` debe operar como landing normalizado y evidencia tecnica de carga. No es una tabla temporal desechable.

La politica operativa es:

- staging es acumulativa por periodo;
- staging conserva evidencia para conciliacion, auditoria y reproceso controlado;
- staging no se borra automaticamente despues de promover un periodo a final;
- si un periodo ya existe en staging, no se vuelve a cargar automaticamente;
- cualquier reproceso debe tratarse como flujo explicito de correccion, no como overwrite automatico.

### Rol De `imss.imss_hechos_asegurados`

`imss.imss_hechos_asegurados` es la capa final y curada para consulta analitica. Tambien es acumulativa por periodo.

La promocion `staging -> final` debe conservar semantica insert-only:

- solo promueve periodos explicitamente informados;
- si el periodo ya existe en final, la promocion se rechaza;
- no hay overwrite automatico;
- no hay reproceso implicito.

### CSV Fuente Y Housekeeping Posterior

`data/processed/imss_concentrado.csv` no debe limpiarse ni modificarse como parte de `load-staging` ni de `promote-staging-final`.

La depuracion del CSV fuente queda para una etapa posterior de housekeeping auditable. Esa etapa debera conservar evidencia suficiente para defender el linaje:

- archivo original o copia archivada;
- archivo resultante;
- conteos antes y despues;
- periodos excluidos y conservados;
- hashes;
- manifest de la operacion.

El diseno operativo de esa etapa esta documentado en `docs/source_csv_housekeeping_plan.md`. Ese plan es posterior: no implementa limpieza del CSV, no autoriza sobrescrituras sin snapshot y no debe mezclarse con carga a staging ni promocion a final.

## Flujo Operativo Recomendado

El flujo objetivo debe avanzar por pasos verificables:

1. `check-source-csv`.
2. `profile-source-csv`.
3. `summarize-source-periods`.
4. `register-period-control`.
5. `load-staging`.
6. Validar staging.
7. `promote-staging-final`.
8. Validar final.
9. `finalize-period-control`.
10. `finalize-run-manifest`.
11. Ejecutar housekeeping auditable del CSV fuente en una etapa posterior.

Actualmente no todos estos pasos estan implementados como funciones ejecutables. El paso de housekeeping auditable queda como etapa posterior.

## Reglas De Negocio Que Debe Respetar

- No crear `sector_economico_3`.
- Conservar `sector_economico_1`, `sector_economico_2` y `sector_economico_4`.
- Separar `rango_ingreso_vsm` y `rango_ingreso_uma`.
- Incluir `ptpd`; si no existe historicamente, usar `no_disponible` o valor tecnico aprobado, nunca asumir `0`.
- No calcular SBC con `ta`.
- Calcular SBC con denominadores `*_sal`.
- No usar `timestamp` en la llave analitica.

## Fuera De Alcance

Esta rama no implementa:

- limpieza automatica del CSV fuente;
- housekeeping auditable implementado;
- `upsert_period`;
- `full_refresh`;
- sobrescritura de periodos;
- API;
- dashboard;
- Docker;
- cloud;
- Supabase;
- BigQuery.

## Hardening Operativo

El siguiente bloque de trabajo no debe enfocarse en dashboard, API ni cloud. La prioridad debe ser hardening operativo del motor:

- validaciones previas y posteriores a la promocion;
- guardrails para evitar cargas repetidas;
- manifests y hashes;
- estados de periodo y guardrails posteriores;
- validacion post-promocion;
- housekeeping auditable del CSV fuente.

## Comando Dry-Run

```powershell
python scripts/run_postgres_loader.py --period 2026-01-31
```

El comando imprime el plan de pasos futuro, no abre conexion y no lee archivos de datos.

## Chequeo Controlado Del CSV Fuente

Antes de cargar cualquier dato, se puede inspeccionar localmente un CSV fuente de forma acotada:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --check-source-csv --source-csv .\ruta\al\archivo.csv --sample-rows 5
```

Este modo no requiere variables `IMSS_PG_*`, no conecta a PostgreSQL, no carga datos, no lee el CSV completo y no usa pandas. Solo inspecciona el encabezado y una muestra pequena de filas para reportar delimitador, encoding, columnas y columnas esperadas faltantes.

## Perfilado Streaming Del CSV Fuente

El siguiente pre-check perfila el CSV fuente fila por fila con un limite explicito:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --profile-source-csv --source-csv .\data\processed\imss_concentrado.csv --max-rows 10000
```

Este modo no requiere variables `IMSS_PG_*`, no conecta a PostgreSQL, no carga datos, no lee el CSV completo por defecto y no usa pandas. Recorre el archivo con lectura streaming hasta `--max-rows` y reporta layout, columnas criticas, dimensiones clave y metricas numericas basicas antes de cualquier staging.

## Resumen Streaming Por Periodo Del CSV Fuente

Para validar la distribucion de filas por `periodo_informacion` sin cargar datos, se puede ejecutar:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --summarize-source-periods --source-csv .\data\processed\imss_concentrado.csv --max-rows 100000
```

Este modo no requiere variables `IMSS_PG_*`, no conecta a PostgreSQL, no crea tablas, no carga datos, no escribe archivos de salida y no usa pandas. Recorre el CSV fila por fila hasta `--max-rows` y reporta conteos por periodo, periodos distintos, periodos de muestra, minimo, maximo, filas con periodo vacio y si se alcanzo el limite de lectura.

## Chequeo De Periodo Existente

El primer chequeo real del loader es solo de lectura. Permite validar si un periodo ya existe antes de una carga futura:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --period 2026-01-31 --check-existing
```

Este modo abre conexion con las variables `IMSS_PG_*` y ejecuta unicamente `SELECT` sobre:

- `imss.imss_period_control`
- `imss.imss_hechos_asegurados`

El comando no lee el CSV concentrado, no ejecuta DDL, no crea tablas, no carga datos, no modifica PostgreSQL y no imprime la password. Si el periodo aparece en control, lo reporta como `already_exists`; si hay filas finales sin control, lo reporta como conflicto; si no aparece en ninguna tabla, lo reporta como `new_period`.

## Registro Inicial En Period Control

La primera escritura controlada permitida es registrar un periodo nuevo como `pending` en `imss.imss_period_control`:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --period 2026-01-31 --register-period-control --run-id manual_test_20260131
```

Este modo primero ejecuta el chequeo de periodo existente. Si el periodo ya existe en `imss.imss_period_control` o si hay filas en `imss.imss_hechos_asegurados`, no inserta nada y reporta la razon. Si el periodo es nuevo, inserta una sola fila con `status = 'pending'`.

El registro no lee el CSV concentrado, no carga hechos, no usa staging, no ejecuta DDL, no crea tablas, no usa upsert, no usa `ON CONFLICT DO UPDATE` y no sobrescribe periodos existentes.

## Registro Inicial En Run Manifest

Cuando el periodo ya existe en `imss.imss_period_control`, se puede registrar un manifest minimo en `imss.imss_run_manifest`:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --period 2026-01-31 --register-run-manifest --run-id manual_manifest_20260131
```

Este modo valida que el periodo exista previamente en `period_control`. Si falta, no inserta nada y reporta `missing_period_control`. Si existe, inserta una sola fila en `imss.imss_run_manifest` con `run_mode = 'manifest_only'`, `status = 'pending'` y un `manifest_json` seguro.

El registro no lee el CSV concentrado, no carga hechos, no usa staging, no modifica `period_control`, no usa upsert, no usa `ON CONFLICT DO UPDATE` y no sobrescribe manifests existentes.

## Carga Insert-Only A Staging

El primer resguardo controlado del CSV fuente hacia PostgreSQL carga exclusivamente un periodo a `imss.imss_staging_asegurados`:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --load-staging --source-csv .\data\processed\imss_concentrado.csv --period 2026-01-31 --batch-size 5000
```

Este modo requiere que el periodo exista previamente en `imss.imss_period_control` y que no existan filas previas para ese periodo en staging. Lee el CSV por streaming, filtra `periodo_informacion`, inserta por lotes parametrizados y hace commit solo al terminar correctamente.

La carga staging no toca `imss.imss_hechos_asegurados`, no modifica `period_control`, no modifica `run_manifest`, no usa pandas, no carga DataFrame, no usa upsert, no usa `ON CONFLICT DO UPDATE`, no ejecuta `UPDATE`, no ejecuta `DELETE`, no ejecuta `TRUNCATE` y no implementa `full_refresh`.

## Promocion Insert-Only De Staging A Final

Cuando un periodo ya fue cargado y validado en `imss.imss_staging_asegurados`, se puede promover de forma controlada hacia `imss.imss_hechos_asegurados`:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --promote-staging-final --period 2026-01-31 --batch-size 50000
```

Este modo no lee CSV, no usa pandas, no carga DataFrame y no limpia `data/processed/imss_concentrado.csv`. El housekeeping del CSV fuente queda como paso posterior, despues de validar que la tabla final contiene el periodo esperado.

La promocion requiere que:

- el periodo exista en `imss.imss_period_control`;
- existan filas del periodo en `imss.imss_staging_asegurados`;
- no existan filas previas del periodo en `imss.imss_hechos_asegurados`.

La promocion es insert-only. Inserta desde staging hacia final filtrando `periodo_informacion`, no modifica staging, no modifica `period_control`, no modifica `run_manifest`, no usa upsert, no usa `ON CONFLICT DO UPDATE`, no ejecuta `UPDATE`, no ejecuta `DELETE`, no ejecuta `TRUNCATE` y no implementa `full_refresh`.

Tratamiento de `ptpd`: si `staging.ptpd` viene `NULL` o vacio, se mapea a `no_disponible`. Este valor es compatible con la constraint vigente `chk_imss_hechos_ptpd`, que permite `0`, `1`, `no_disponible` y `no_aplica`. No se convierte `ptpd` vacio a `0`.

## Validacion Post-Promocion

Despues de promover un periodo a `imss.imss_hechos_asegurados`, se puede ejecutar una validacion reusable de solo lectura:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --validate-post-promotion --period 2026-01-31
```

Este modo compara `imss.imss_staging_asegurados` contra `imss.imss_hechos_asegurados` para el periodo informado. Revisa existencia en `period_control`, conteos, agregados principales (`ta`, `ta_sal`, `masa_sal_ta`) y el tratamiento de `ptpd` vacio hacia `no_disponible`.

La validacion es prerequisito operativo para un housekeeping auditable del CSV fuente. No modifica PostgreSQL, no modifica el CSV, no actualiza formalmente el estado del periodo, no escribe manifest, no usa pandas y no carga DataFrame.

## Finalizacion Formal De Periodo

Cuando la validacion post-promocion ya paso, se puede cerrar formalmente el periodo en `imss.imss_period_control`:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --finalize-period-control --period 2026-01-31 --run-id manual_finalize_20260131
```

Este modo ejecuta primero `validate-post-promotion`. Si la validacion falla, no actualiza nada. Si el periodo existe en `period_control`, esta en `pending` y la validacion pasa, actualiza unicamente `imss.imss_period_control` con `status = 'loaded'`, `row_count`, `sum_ta`, `sum_ta_sal`, `sum_masa_sal_ta`, `loaded_at`, `error_message = NULL` y `run_id` cuando se informe.

La finalizacion solo permite la transicion `pending -> loaded`. Si el periodo ya esta `loaded`, responde idempotentemente sin volver a actualizar. Si el estado es distinto de `pending` o `loaded`, no actualiza.

Este modo no modifica staging, no modifica final, no modifica el CSV, no escribe manifest, no implementa housekeeping y no calcula fingerprint todavia. Tampoco actualiza `sum_asegurados` ni `sum_no_trabajadores`, porque esas sumas no forman parte de la validacion formal de esta etapa.

## Manifest Final De Corrida

Despues de `finalize-period-control`, se puede cerrar el manifest inicial existente en `imss.imss_run_manifest`:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --finalize-run-manifest --period 2026-01-31 --run-id manual_manifest_20260131
```

Este modo actualiza unicamente `imss.imss_run_manifest` para el `run_id` existente. Cambia `run_mode` a `final_manifest`, cambia `status` de `pending` a `completed`, completa `started_at` si estaba vacio, escribe `finished_at` y reemplaza `manifest_json` con evidencia final de validacion.

La finalizacion del manifest requiere que la validacion post-promocion pase y que `imss.imss_period_control.status = 'loaded'`. Si el manifest ya esta `completed`, responde idempotentemente sin volver a actualizar. Si el manifest tiene un periodo distinto en `manifest_json`, no actualiza.

Este modo no modifica `period_control`, no modifica staging, no modifica final, no modifica el CSV, no implementa housekeeping y no calcula `config_hash_sha256` todavia.

## Smoke Test De Conexion

Cuando exista un entorno local PostgreSQL configurado, se puede validar solo la conectividad con:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_postgres_connection.py
```

El script lee las variables `IMSS_PG_*`, abre una conexion, ejecuta unicamente:

```sql
SELECT current_database(), current_schema();
```

Despues cierra la conexion. No crea tablas, no ejecuta DDL, no lee el CSV concentrado, no carga datos y no imprime la password.

## Smoke Test De Estructura

Cuando el DDL ya fue aplicado en una base PostgreSQL local, se puede validar que existan el schema, tablas, vistas y constraints criticas con:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_postgres_schema.py
```

El script consulta unicamente catalogos de PostgreSQL (`information_schema` y `pg_constraint`). No ejecuta DDL, no crea tablas, no lee el CSV concentrado, no carga datos y no imprime la password.
