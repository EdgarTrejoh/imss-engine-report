# Checkpoint operativo - PR #43 historical batch execute

Fecha: 2026-07-10  
Proyecto: IMSS Engine Report  
Repositorio: `EdgarTrejoh/imss-engine-report`

## 1. Resumen ejecutivo

Despues del merge de PR #42, `feat: add IMSS historical batch execute limit`, se ejecuto exitosamente la primera corrida batch historica real controlada.

El rango planeado fue de `2016-08-31` a `2016-12-31`. La ejecucion aplico `max-periods=3`, cargo exactamente los primeros tres periodos elegibles y dejo los dos restantes fuera de la corrida.

PostgreSQL local paso de 8 a 11 periodos resguardados. El dry-run posterior clasifico los tres periodos recien cargados como `skip_existing`, confirmando el comportamiento esperado del planner despues de la carga.

## 2. Alcance y antecedentes

El flujo utilizado fue construido y validado mediante:

- PR #39: single-period pipeline.
- PR #40: checkpoint de ejecucion real single-period para `2016-07-31`.
- PR #41: historical batch planner dry-run.
- PR #42: historical batch execute limitado a un maximo de tres periodos.

La ejecucion batch reutilizo el single-period pipeline para cada periodo seleccionado. No implemento una ruta de carga paralela ni dependio del concentrado CSV historico.

## 3. Estado Git previo

Comandos ejecutados:

```powershell
git switch main
git pull origin main
git status --short --branch
```

Estado observado:

```text
## main...origin/main
 M config/config.yaml
```

`main` estaba actualizado contra `origin/main`. La modificacion de `config/config.yaml` era local y preexistente. No se hizo commit ni se abrio una rama antes de la ejecucion operativa.

## 4. Validaciones PostgreSQL previas

Conexion:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_postgres_connection.py
```

Resultado:

```text
PostgreSQL connection OK:
- database: imss_engine_test
- schema: public
- user: postgres
- host: localhost
```

Schema:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_postgres_schema.py
```

| Validacion | Resultado |
|---|---:|
| schema `imss` | present |
| tables found | 13 / expected 13 |
| views found | 5 / expected 5 |
| critical constraints found | 4 / expected 4 |
| schema validation | OK |

## 5. Estado PostgreSQL antes del batch

Comando:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --summary-reserved-periods
```

Resultado previo: `period_count = 8`.

| Periodo | Filas |
|---|---:|
| `2016-01-31` | 3,638,419 |
| `2016-02-29` | 3,655,343 |
| `2016-03-31` | 3,652,496 |
| `2016-04-30` | 3,665,505 |
| `2016-05-31` | 3,683,768 |
| `2016-06-30` | 3,691,605 |
| `2016-07-31` | 3,714,707 |
| `2026-01-31` | 4,731,705 |

## 6. Dry-run previo

Comando:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --start-period 2016-08-31 `
  --end-period 2016-12-31 `
  --dry-run
```

Resultado:

| Campo | Valor |
|---|---:|
| `status` | `planned` |
| `action` | `historical_batch_plan` |
| `period_count` | `5` |
| `download_process_load` | `5` |
| `skip_existing` | `0` |
| `validate_process_load` | `0` |
| total de estados bloqueados | `0` |
| `writes_postgresql` | `false` |
| `downloads_raw` | `false` |
| `processes_raw` | `false` |
| `touches_staging_table` | `false` |
| `touches_final_table` | `false` |

Los cinco periodos fueron clasificados como `download_process_load`:

- `2016-08-31`
- `2016-09-30`
- `2016-10-31`
- `2016-11-30`
- `2016-12-31`

Manifest local:

```text
outputs\pipeline\historical_batch_plan_historical_batch_20260710T183204Z_3b4f7f01_2016-08-31_2016-12-31.json
```

## 7. Execute batch real controlado

Comando:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --start-period 2016-08-31 `
  --end-period 2016-12-31 `
  --execute `
  --max-periods 3 `
  --stop-on-failure
```

Resultado general:

| Campo | Valor |
|---|---:|
| `status` | `success` |
| `action` | `executed` |
| `mode` | `historical_batch_execute` |
| `run_id` | `historical_batch_20260710T183237Z_dda09839` |
| `max_periods` | `3` |
| `planned_period_count` | `5` |
| `eligible_period_count` | `5` |
| `selected_period_count` | `3` |
| `executed_period_count` | `3` |
| `successful_period_count` | `3` |
| `failed_period_count` | `0` |
| `stopped_after_failure` | `false` |
| `blocked_count` | `0` |
| `skipped_existing_count` | `0` |
| `writes_postgresql` | `true` |
| `writes_concentrado` | `false` |
| `writes_data_processed` | `false` |
| `downloads_raw` | `true` |
| `processes_raw` | `true` |
| `touches_staging_table` | `true` |
| `touches_final_table` | `true` |

Manifests locales:

```text
outputs\pipeline\historical_batch_execute_historical_batch_20260710T183237Z_dda09839_2016-08-31_2016-12-31.json
outputs\pipeline\historical_batch_plan_historical_batch_20260710T183237Z_dda09839_plan_2016-08-31_2016-12-31.json
```

## 8. Periodos ejecutados y limite aplicado

El batch ejecuto exactamente:

- `2016-08-31`
- `2016-09-30`
- `2016-10-31`

No ejecuto:

- `2016-11-30`
- `2016-12-31`

Ambos quedaron pendientes exclusivamente por el limite operativo `max_periods=3`; no fueron clasificados como bloqueados.

## 9. Resultados por periodo

| Periodo | Accion planeada | Estado | Accion | Filas finales |
|---|---|---|---|---:|
| `2016-08-31` | `download_process_load` | `success` | `loaded` | 3,728,258 |
| `2016-09-30` | `download_process_load` | `success` | `loaded` | 3,725,336 |
| `2016-10-31` | `download_process_load` | `success` | `loaded` | 3,740,962 |

Referencias de ejecución single-period:

| Periodo | Run ID | Manifest local |
|---|---|---|
| `2016-08-31` | `historical_batch_20260710T183237Z_dda09839_2016-08-31` | `outputs\pipeline\single_period_pipeline_historical_batch_20260710T183237Z_dda09839_2016-08-31_2016-08-31.json` |
| `2016-09-30` | `historical_batch_20260710T183237Z_dda09839_2016-09-30` | `outputs\pipeline\single_period_pipeline_historical_batch_20260710T183237Z_dda09839_2016-09-30_2016-09-30.json` |
| `2016-10-31` | `historical_batch_20260710T183237Z_dda09839_2016-10-31` | `outputs\pipeline\single_period_pipeline_historical_batch_20260710T183237Z_dda09839_2016-10-31_2016-10-31.json` |

## 10. Estado PostgreSQL posterior

Comando:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --summary-reserved-periods
```

Resultado posterior: `period_count = 11`.

| Periodo | Filas |
|---|---:|
| `2016-01-31` | 3,638,419 |
| `2016-02-29` | 3,655,343 |
| `2016-03-31` | 3,652,496 |
| `2016-04-30` | 3,665,505 |
| `2016-05-31` | 3,683,768 |
| `2016-06-30` | 3,691,605 |
| `2016-07-31` | 3,714,707 |
| `2016-08-31` | 3,728,258 |
| `2016-09-30` | 3,725,336 |
| `2016-10-31` | 3,740,962 |
| `2026-01-31` | 4,731,705 |

Metricas de los nuevos periodos:

| Periodo | Asegurados `SUM(ta)` | Trabajadores con SBC `SUM(ta_sal)` | Masa salarial `SUM(masa_sal_ta)` | SBC promedio |
|---|---:|---:|---:|---:|
| `2016-08-31` | 18,466,227 | 18,326,176 | 5,879,995,921.79 | 320.8523110216774083 |
| `2016-09-30` | 18,626,402 | 18,483,108 | 5,851,136,187 | 316.5666827786755344 |
| `2016-10-31` | 18,797,954 | 18,652,053 | 5,880,350,473.09 | 315.2655888920109759 |

## 11. Dry-run posterior e idempotencia operativa

Comando:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --start-period 2016-08-31 `
  --end-period 2016-12-31 `
  --dry-run
```

Resultado:

| Campo | Valor |
|---|---:|
| `status` | `planned` |
| `download_process_load` | `2` |
| `skip_existing` | `3` |
| `validate_process_load` | `0` |
| total de estados bloqueados | `0` |
| `writes_postgresql` | `false` |
| `downloads_raw` | `false` |
| `processes_raw` | `false` |

Clasificacion posterior:

| Periodo | Accion recomendada |
|---|---|
| `2016-08-31` | `skip_existing` |
| `2016-09-30` | `skip_existing` |
| `2016-10-31` | `skip_existing` |
| `2016-11-30` | `download_process_load` |
| `2016-12-31` | `download_process_load` |

Manifest local:

```text
outputs\pipeline\historical_batch_plan_historical_batch_20260710T195433Z_88f4980b_2016-08-31_2016-12-31.json
```

El resultado confirma que los periodos cargados fueron reconocidos posteriormente como existentes y no se recomendaron para una nueva ejecución.

## 12. Evidencia local

Los manifests citados viven en `outputs/pipeline/`. La carpeta `outputs/` está ignorada por Git y funciona como evidencia operativa local; sus archivos no forman parte de este PR documental.

## 13. Confirmaciones de no afectacion

- No se uso `data/processed/imss_concentrado.csv`.
- No se reconstruyo el concentrado gigante.
- No se uso `publish_insert.py`.
- No se uso `publish_plan.py`.
- No se uso `raw_compare.py` como paso operativo.
- No se ejecuto Supabase.
- No se ejecuto housekeeping automatico.
- No se ejecutaron mas de tres periodos.
- No se hizo commit durante la ejecucion operativa.
- `config/config.yaml` permanecio como modificacion local preexistente y queda fuera de este PR.

## 14. Dictamen operativo

PR #42 quedo validado con una ejecucion batch historica real y controlada. El sistema demostro que puede:

- planear un rango mensual historico;
- seleccionar exclusivamente periodos elegibles;
- limitar la corrida a un maximo de tres periodos;
- reutilizar el single-period pipeline para cada carga;
- dejar sin ejecutar los periodos que exceden el limite;
- llevar PostgreSQL de 8 a 11 periodos resguardados;
- reconocer los periodos recien cargados como `skip_existing` en el dry-run posterior.

Los periodos `2016-11-30` y `2016-12-31` permanecen como candidatos para una corrida posterior controlada.
