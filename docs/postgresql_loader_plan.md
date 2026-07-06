# PostgreSQL Loader Plan

## Estado De Esta Rama

Esta rama crea solo un skeleton tecnico para una futura integracion PostgreSQL.

No implementa carga masiva, no abre conexiones automaticamente, no lee el CSV concentrado grande y no modifica ninguna base de datos.

## Componentes Creados

- `src/imss_engine/postgres/config.py`: lectura segura de variables `IMSS_PG_*`.
- `src/imss_engine/postgres/connection.py`: helper futuro para construir conexion cuando exista driver.
- `src/imss_engine/postgres/loader.py`: contratos placeholder para el flujo insert-only.
- `scripts/run_postgres_loader.py`: CLI dry-run que imprime el plan y no toca PostgreSQL.
- `.env.example`: variables esperadas sin secretos reales.

## Variables De Entorno

```text
IMSS_PG_HOST
IMSS_PG_PORT
IMSS_PG_DATABASE
IMSS_PG_USER
IMSS_PG_PASSWORD
```

El skeleton puede importarse sin estas variables. Si faltan, el CLI dry-run solo reporta configuracion incompleta.

## Flujo Futuro Insert-Only

El loader futuro debe seguir este orden:

1. Validar `periodo_informacion`.
2. Verificar si el periodo ya existe en `imss.imss_period_control` y `imss.imss_hechos_asegurados`.
3. Preparar `imss.imss_staging_asegurados`.
4. Validar staging contra reglas IMSS vigentes.
5. Promover staging a `imss.imss_hechos_asegurados` solo si el periodo es nuevo y valido.
6. Registrar resultado en `imss.imss_period_control`.
7. Registrar manifest en `imss.imss_run_manifest`.

La version inicial debe conservar semantica insert-only. Periodos existentes deben resolverse como `already_exists` o conflicto, no sobrescribirse.

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

- carga masiva desde `data/processed/imss_concentrado.csv`;
- lectura del CSV grande;
- `upsert_period`;
- `full_refresh`;
- sobrescritura de periodos;
- API;
- dashboard;
- Docker;
- cloud;
- Supabase;
- BigQuery.

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
