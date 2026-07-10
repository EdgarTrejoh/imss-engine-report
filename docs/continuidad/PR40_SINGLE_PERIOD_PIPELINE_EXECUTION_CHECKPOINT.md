# Checkpoint operativo — PR #40 single-period pipeline execute

Fecha: 2026-07-10  
Proyecto: IMSS Engine Report  
Repositorio: `EdgarTrejoh/imss-engine-report`

## 1. Resumen ejecutivo

Después del merge de PR #39, `feat: add IMSS single-period pipeline orchestrator`, se ejecutó exitosamente el nuevo orquestador single-period para el periodo `2016-07-31`.

El flujo validado fue:

```text
raw mensual
-> validacion raw
-> aggregate mensual en outputs/pipeline
-> PostgreSQL staging
-> PostgreSQL final
-> validacion post-promotion
-> finalizacion de period_control
-> finalizacion de run_manifest
```

El resultado confirma que el flujo operativo nuevo puede cargar un periodo nuevo a PostgreSQL sin depender de `data/processed/imss_concentrado.csv`.

## 2. Alcance

Este checkpoint documenta el primer `--execute` real exitoso del orquestador single-period.

Alcance confirmado:

- PostgreSQL local: `imss_engine_test`.
- Schema: `imss`.
- Periodo cargado: `2016-07-31`.
- Origen operativo: raw mensual descargado desde IMSS.
- Agregado temporal: `outputs/pipeline/`.
- Destino final: `imss.imss_hechos_asegurados`.

Fuera de alcance confirmado:

- No se usó `data/processed/imss_concentrado.csv`.
- No se usó `publish_insert.py`.
- No se usó `publish_plan.py`.
- No se usó `raw_compare.py`.
- No se ejecutó Supabase.
- No se ejecutó batch histórico.
- No se ejecutó housekeeping automático.

## 3. Precheck PostgreSQL

Comando ejecutado:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --check-existing --period 2016-07-31
```

Resultado antes del execute:

| Campo | Valor |
|---|---:|
| `exists` | `false` |
| `final_table_row_count` | `0` |
| `period_control_exists` | `false` |
| `period_control_status` | `null` |
| `recommended_status` | `new_period` |
| `opens_database_connection` | `true` |
| `reads_source_csv` | `false` |
| `reads_full_csv` | `false` |
| `touches_final_table` | `false` |
| `touches_staging_table` | `false` |

Configuracion PostgreSQL observada:

| Campo | Valor |
|---|---|
| database | `imss_engine_test` |
| host | `localhost` |
| user | `postgres` |

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

Resultado:

| Validacion | Resultado |
|---|---:|
| schema `imss` | present |
| tables found | 13 / expected 13 |
| views found | 5 / expected 5 |
| critical constraints found | 4 / expected 4 |
| schema validation | OK |

## 5. Execute real del orquestador

Comando ejecutado:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_single_period_pipeline.py `
  --period 2016-07-31 `
  --execute
```

Resultado general:

| Campo | Valor |
|---|---|
| `status` | `success` |
| `action` | `loaded` |
| `periodo_informacion` | `2016-07-31` |
| `run_id` | `single_period_20260710T164911Z_d7e03bc2` |
| `manifest_path` | `outputs\pipeline\single_period_pipeline_single_period_20260710T164911Z_d7e03bc2_2016-07-31.json` |
| `writes_postgresql` | `true` |
| `writes_concentrado` | `false` |
| `writes_data_processed` | `false` |
| `postgres_loader_uses_dataframe` | `false` |
| `raw_processing_uses_dataframe` | `true` |

## 6. Descarga raw

| Campo | Valor |
|---|---|
| `status` | `success` |
| `downloaded` | `true` |
| `raw_file_path` | `data\raw\imss\asegurados\2016\asg-2016-07-31.csv` |
| `file_size_bytes` | `293324802` |
| `sha256` | `5f0c3c81f182750525e776cf3785c01ecd0b11dd92b6a3df51657e305d655695` |
| `source_url` | `http://datos.imss.gob.mx/sites/default/files/asg-2016-07-31.csv` |
| `attempts` | `1` |

## 7. Validacion raw

| Campo | Valor |
|---|---|
| `status` | `success` |
| `valid` | `true` |
| `encoding` | `latin-1` |
| `separator` | `|` |
| `missing_required_columns` | `[]` |
| `raw_file_size_bytes` | `293324802` |
| `sha256` | `5f0c3c81f182750525e776cf3785c01ecd0b11dd92b6a3df51657e305d655695` |

## 8. Procesamiento raw a aggregate mensual

| Campo | Valor |
|---|---:|
| `status` | `success` |
| `rows_read` | `3714707` |
| `chunks_processed` | `10` |
| `chunk_size` | `400000` |
| `aggregate_rows` | `3714707` |
| `aggregate_file_size_bytes` | `767148622` |
| `aggregate_sha256` | `fe35754424301b5cb3a7d6a9be897fbd729e0a7f894beb7480fe09d57899288d` |
| `writes_data_processed` | `false` |
| `loads_postgresql` | `false` |

Aggregate temporal:

```text
outputs\pipeline\raw_aggregate_20260710T165007Z_b3be4bf1_2016-07-31.csv
```

## 9. Carga a PostgreSQL staging

Fuente:

```text
outputs\pipeline\raw_aggregate_20260710T165007Z_b3be4bf1_2016-07-31.csv
```

| Campo | Valor |
|---|---:|
| `rows_inserted_staging` | `3714707` |
| `rows_matched_period` | `3714707` |
| `rows_scanned` | `3714707` |
| `staging_row_count_before` | `0` |
| `staging_row_count_after` | `3714707` |
| `committed` | `true` |
| `rolled_back` | `false` |
| `touches_staging_table` | `true` |
| `touches_final_table` | `false` |
| `loads_dataframe` | `false` |

## 10. Promocion staging a final

| Campo | Valor |
|---|---:|
| `rows_inserted_final` | `3714707` |
| `final_row_count_before` | `0` |
| `final_row_count_after` | `3714707` |
| `committed` | `true` |
| `rolled_back` | `false` |
| `ptpd_empty_rows_in_staging` | `3714707` |
| `ptpd_mapped_to` | `no_disponible` |
| `touches_final_table` | `true` |

## 11. Validacion post-promotion

| Check | Resultado |
|---|---|
| `validation_status` | `passed` |
| `failed_checks` | `[]` |
| `final_row_count` | `3714707` |
| `staging_row_count` | `3714707` |
| `row_count_match` | `true` |
| `final_sum_ta` | `18348131` |
| `staging_sum_ta` | `18348131` |
| `sum_ta_match` | `true` |
| `final_sum_ta_sal` | `18210531` |
| `staging_sum_ta_sal` | `18210531` |
| `sum_ta_sal_match` | `true` |
| `final_sum_masa_sal_ta` | `5859521732.95` |
| `staging_sum_masa_sal_ta` | `5859521732.95` |
| `sum_masa_sal_ta_match` | `true` |
| `ptpd_empty_to_no_disponible_match` | `true` |

## 12. Finalizacion de controles PostgreSQL

`period_control`:

| Campo | Valor |
|---|---|
| `finalized` | `true` |
| `status_before` | `pending` |
| `status_after` | `loaded` |
| `row_count` | `3714707` |
| `validation_status` | `passed` |

`run_manifest`:

| Campo | Valor |
|---|---|
| `finalized` | `true` |
| `status_before` | `pending` |
| `status_after` | `completed` |
| `run_mode_before` | `manifest_only` |
| `run_mode_after` | `final_manifest` |
| `period_control_status` | `loaded` |
| `row_count` | `3714707` |
| `validation_status` | `passed` |

## 13. Check-existing posterior

Comando ejecutado:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --check-existing --period 2016-07-31
```

Resultado posterior:

| Campo | Valor |
|---|---:|
| `exists` | `true` |
| `final_table_row_count` | `3714707` |
| `period_control_exists` | `true` |
| `period_control_row_count` | `3714707` |
| `period_control_status` | `loaded` |
| `recommended_status` | `already_exists` |

## 14. Summary posterior

Comando ejecutado:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --summary-reserved-periods
```

Resultado:

```text
period_count: 8
```

Periodos cargados:

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

Cifras para `2016-07-31`:

| Metrica | Valor |
|---|---:|
| `asegurados_total_sum_ta` | 18,348,131 |
| `trabajadores_con_sbc_sum_ta_sal` | 18,210,531 |
| `masa_salarial_sum_masa_sal_ta` | 5,859,521,732.95 |
| `sbc_promedio` | 321.7655615286561386 |

## 15. Confirmaciones de no dependencia

La ejecucion validada no dependio de:

- `data/processed/imss_concentrado.csv`;
- `publish_insert.py`;
- `publish_plan.py`;
- `raw_compare.py`;
- Supabase;
- batch historico;
- housekeeping automatico.

## 16. Dictamen

El PR #39 quedo validado con una ejecucion real controlada.

El nuevo flujo operativo single-period ya puede incorporar un periodo mensual nuevo a PostgreSQL local desde raw mensual trazable, generando aggregate temporal en `outputs/pipeline/`, cargando staging, promoviendo a final y cerrando controles PostgreSQL sin reconstruir ni depender del concentrado CSV operativo.

La fuente operativa para continuidad queda orientada a:

```text
raw mensual -> aggregate mensual -> PostgreSQL
```

no a:

```text
data/processed/imss_concentrado.csv -> PostgreSQL
```
