# Checkpoint tecnico - IMSS bulk publish controlado

Fecha: 2026-07-09

## 1. Resumen ejecutivo

El concentrado local `data/processed/imss_concentrado.csv` quedo sincronizado con todos los raw disponibles en `data/raw/imss/asegurados` al cierre de la operacion documentada.

La publicacion se realizo con el flujo append-only agregado en PR #35, usando planes de publicacion previos, comparacion funcional antes/despues, backup local y validacion de idempotencia.

Este checkpoint documenta evidencia operativa local. No versiona `data/processed/`, `data/raw/` ni `outputs/`.

## 2. Alcance

Alcance operativo documentado:

- Concentrado CSV local: `data/processed/imss_concentrado.csv`.
- Publicacion append-only desde agregados temporales previamente validados.
- Backup local antes de cada append real.
- Comparacion funcional read-only antes y despues de publicar.
- Manifests locales de publicacion e idempotencia.

Fuera de este alcance:

- PostgreSQL.
- Staging PostgreSQL.
- Tabla final PostgreSQL.
- `period_control`.
- `run_manifest`.
- ETL historico en `etl_imss.py`.
- Versionado de `data/processed/`.
- Versionado de `outputs/`.

## 3. Estado antes de la operacion

Snapshot before:

```text
outputs\audit\snapshots\snapshot_before_bulk_publish_20260709T192307Z.json
```

| Elemento | Valor |
| --- | --- |
| Concentrado rows | 19,369,568 |
| Periodos en concentrado | `2016-01-31`, `2016-02-29`, `2016-03-31`, `2016-06-30`, `2026-01-31` |
| Raw disponibles | `2016-02-29`, `2016-03-31`, `2016-04-30`, `2016-05-31`, `2016-06-30` |
| Raw no presentes en concentrado | `2016-04-30`, `2016-05-31` |
| Raw sin agregado temporal | `2016-04-30`, `2016-05-31` |

Antes de esta operacion, `2016-06-30` ya habia sido publicado y validado con PR #35.

## 4. Operaciones ejecutadas

| Periodo | Operacion | Filas | Plan | Manifest | Resultado |
| --- | --- | ---: | --- | --- | --- |
| `2016-06-30` | Publicacion previa validada | 3,691,605 | `outputs\processing\publish_plan_20260709T163931Z_7c543de3_2016-06-30.json` | `outputs\audit\publish\publish_manifest_20260709T173848Z_9b61633b_2016-06-30.json` | `success / inserted / passed` |
| `2016-04-30` | Procesamiento y publicacion faltante | 3,665,505 | `outputs\processing\publish_plan_20260709T193552Z_34cbe34a_2016-04-30.json` | `outputs\audit\publish\publish_manifest_20260709T193830Z_e28efa23_2016-04-30.json` | `success / inserted / passed` |
| `2016-05-31` | Procesamiento y publicacion faltante | 3,683,768 | No especificado en este checkpoint | `outputs\audit\publish\publish_manifest_20260709T201045Z_310aff8c_2016-05-31.json` | `success / inserted / passed` |

### Detalle 2016-04-30

```text
validate: success / valid true
process: success
aggregate_rows: 3,665,505
aggregate_output_path: outputs\processing\raw_aggregate_20260709T193311Z_2d7799e7_2016-04-30.csv
publish_plan: outputs\processing\publish_plan_20260709T193552Z_34cbe34a_2016-04-30.json
publish_manifest: outputs\audit\publish\publish_manifest_20260709T193830Z_e28efa23_2016-04-30.json
backup: outputs\audit\publish\backups\imss_concentrado_20260709T193830Z_e28efa23_before.csv
```

### Detalle 2016-05-31

```text
status: success
action: inserted
validation_status: passed
rows_inserted: 3,683,768
comparison_before: new_period
comparison_after: already_exists
publish_manifest: outputs\audit\publish\publish_manifest_20260709T201045Z_310aff8c_2016-05-31.json
```

## 5. Validaciones por periodo

| Periodo | comparison_before | comparison_after | validation_status | rows_inserted | Idempotencia |
| --- | --- | --- | --- | ---: | --- |
| `2016-06-30` | `new_period` | `already_exists` | `passed` | 3,691,605 | `success / no_op / skipped`, rows_inserted `0` |
| `2016-04-30` | `new_period` | `already_exists` | `passed` | 3,665,505 | `success / no_op / skipped`, rows_inserted `0` |
| `2016-05-31` | `new_period` | `already_exists` | `passed` | 3,683,768 | `success / no_op / skipped`, rows_inserted `0` |

Manifests de idempotencia:

```text
outputs\audit\publish\publish_manifest_20260709T175052Z_e2b050c3_2016-06-30.json
outputs\audit\publish\publish_manifest_20260709T195118Z_f4a1e225_2016-04-30.json
outputs\audit\publish\publish_manifest_20260709T202517Z_4ed7708e_2016-05-31.json
```

## 6. Estado despues de la operacion

Snapshot after:

```text
outputs\audit\snapshots\snapshot_after_bulk_publish_20260709T203205Z.json
```

| Elemento | Valor |
| --- | --- |
| Concentrado rows | 26,718,841 |
| Periodos en concentrado | `2016-01-31`, `2016-02-29`, `2016-03-31`, `2016-04-30`, `2016-05-31`, `2016-06-30`, `2026-01-31` |
| Raw disponibles | `2016-02-29`, `2016-03-31`, `2016-04-30`, `2016-05-31`, `2016-06-30` |
| Raw no presentes en concentrado | vacio |

Conteo final por periodo:

| Periodo | Filas |
| --- | ---: |
| `2016-01-31` | 3,638,419 |
| `2016-02-29` | 3,655,343 |
| `2016-03-31` | 3,652,496 |
| `2016-04-30` | 3,665,505 |
| `2016-05-31` | 3,683,768 |
| `2016-06-30` | 3,691,605 |
| `2026-01-31` | 4,731,705 |
| **Total** | **26,718,841** |

## 7. Evidencia local

Snapshots:

```text
outputs\audit\snapshots\snapshot_before_bulk_publish_20260709T192307Z.json
outputs\audit\snapshots\snapshot_after_bulk_publish_20260709T203205Z.json
```

Manifests de publicacion real:

```text
outputs\audit\publish\publish_manifest_20260709T173848Z_9b61633b_2016-06-30.json
outputs\audit\publish\publish_manifest_20260709T193830Z_e28efa23_2016-04-30.json
outputs\audit\publish\publish_manifest_20260709T201045Z_310aff8c_2016-05-31.json
```

Manifests de idempotencia:

```text
outputs\audit\publish\publish_manifest_20260709T175052Z_e2b050c3_2016-06-30.json
outputs\audit\publish\publish_manifest_20260709T195118Z_f4a1e225_2016-04-30.json
outputs\audit\publish\publish_manifest_20260709T202517Z_4ed7708e_2016-05-31.json
```

Backups:

```text
outputs\audit\publish\backups\imss_concentrado_20260709T193830Z_e28efa23_before.csv
```

`outputs/` esta ignorado por Git y se conserva como evidencia operativa local. Estos archivos se citan por ruta, pero no se agregan al repositorio.

## 8. Estado Git

`data/processed/imss_concentrado.csv` esta ignorado por Git.

Evidencia de `git check-ignore`:

```text
.gitignore:19:data/processed/* data/processed/imss_concentrado.csv
```

Evidencia esperada en `git status --ignored`:

```text
!! data/processed/imss_concentrado.csv
```

## 9. Exclusiones explicitas

Confirmaciones de alcance:

- No PostgreSQL.
- No staging.
- No final.
- No `period_control`.
- No `run_manifest`.
- No ETL historico.
- No versionado de `data/processed`.
- No versionado de `outputs`.
- No publicacion de evidencia local en Git.

## 10. Dictamen

El concentrado local quedo sincronizado con todos los raw disponibles.

```text
RAW_NOT_IN_CONCENTRADO = vacio
```

La publicacion fue:

- append-only;
- respaldada con backup previo;
- validada con comparacion funcional antes/despues;
- idempotente en re-ejecucion;
- sin intervencion de PostgreSQL.

## 11. Riesgos / siguientes pasos

Este checkpoint no propone implementacion nueva. Solo deja posibles frentes posteriores:

- Definir si PostgreSQL se alimentara desde concentrado actualizado o desde aggregate validado.
- Crear checkpoint documental posterior si se decide cargar PostgreSQL.
- Definir politica de retencion y respaldo para `outputs/audit`.

## 12. PRs previos relevantes

| PR | Descripcion |
| --- | --- |
| #26 | Descarga raw con manifest |
| #27 | Retries / timeouts / backoff |
| #28 | Validacion inicial raw |
| #29 | Procesamiento raw -> agregado temporal |
| #30 | Comparacion funcional read-only contra concentrado |
| #31 | Normalizacion compatible de dimensiones |
| #32 | Fingerprint numerico estable |
| #33 | Checkpoint tecnico raw flow |
| #34 | Publish plan dry-run |
| #35 | Publish insert-only real al concentrado CSV |
