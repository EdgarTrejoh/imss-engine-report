# Checkpoint tecnico - flujo raw IMSS

Fecha: 2026-07-09

## Dictamen ejecutivo

El nuevo flujo raw IMSS ya reproduce funcionalmente periodos historicos existentes en el concentrado, sin modificar `data/processed/imss_concentrado.csv` ni PostgreSQL.

El flujo cerrado hasta este checkpoint es:

```text
descarga raw
-> validacion raw
-> procesamiento raw
-> normalizacion dimensional
-> comparacion funcional read-only
-> fingerprint numerico estable
```

Este checkpoint documenta el estado alcanzado antes de abrir cualquier frente de publicacion insert-only.

## Alcance alcanzado por PR

| PR | Titulo | Objetivo | Alcance | Que no toca | Resultado tecnico |
| --- | --- | --- | --- | --- | --- |
| #26 | Descarga raw con manifest | Crear downloader raw controlado por periodo. | Descarga un CSV raw mensual a `data/raw/imss/asegurados/YYYY/` y genera manifest local. | No procesa CSV, no toca concentrado, no carga PostgreSQL. | Raw descargable por periodo con SHA256, tamano y manifest local. |
| #27 | Retries / timeouts / backoff | Robustecer downloader raw. | Agrega intentos, timeouts, backoff incremental y evidencia de errores retryables. | No cambia ETL, no procesa datos, no publica. | Downloader raw mas tolerante a fallas recuperables. |
| #28 | Validacion inicial raw | Verificar que un raw descargado sea insumo minimo viable. | Valida existencia, tamano, hash, encoding, separador y columnas requeridas. | No procesa dataset completo, no agrega, no carga PostgreSQL. | Raw validado con manifest en `outputs/audit/raw_validation/`. |
| #29 | Procesamiento raw a agregado temporal | Procesar un raw validado por chunks. | Lee un unico periodo explicito, reutiliza `aggregate_imss_chunk` y escribe agregado temporal. | No toca `data/processed/`, no inserta al concentrado, no carga PostgreSQL. | Agregado temporal en `outputs/processing/` y manifest de procesamiento. |
| #30 | Comparacion funcional read-only contra concentrado | Comparar agregado temporal contra concentrado. | Calcula resumen y fingerprint funcional para clasificar `already_exists`, `new_period` o conflicto. | No escribe concentrado, no modifica datos, no descubre agregados. | Comparador read-only con manifest en `outputs/processing/`. |
| #31 | Normalizacion compatible de dimensiones | Homologar representacion de dimensiones del agregado raw. | Convierte blancos seleccionados a `NA` y sectores `1.0` a `1` antes de escribir el agregado temporal. | No maquilla la comparacion, no modifica concentrado, no cambia ETL. | Agregado temporal sale en dialecto compatible con concentrado historico. |
| #32 | Fingerprint numerico estable | Evitar falsos conflictos por ruido flotante. | Canonicaliza sumas enteras y `sum_masa_sal_ta` a 4 decimales antes de hashear. | No modifica CSVs, no aplica tolerancias ad hoc en el comparador. | Falsos conflictos por `5683478926.29` vs `5683478926.289999` quedan resueltos. |

## Periodos probados

### 2016-03-31

Contexto:

```text
Periodo historico ya existente en concentrado/PostgreSQL.
Raw ya existia localmente al momento de prueba.
Sirvio para detectar y resolver:
- conflicto por normalizacion dimensional;
- conflicto por precision flotante en fingerprint.
Resultado final despues de PR #31 y PR #32:
comparison_status = already_exists
```

Datos conocidos:

```text
periodo: 2016-03-31
raw_file_path: data\raw\imss\asegurados\2016\asg-2016-03-31.csv
raw_sha256: aeebe6084422db5d150eceda49133c0a85de12c761a6ff2d08ef9927ba4ad15e
row_count / aggregate_rows: 3652496
comparison_status final: already_exists
```

Hallazgos intermedios:

```text
Primero hubo conflict_existing_period_hash.
Las sumas y row_count coincidian.
La diferencia venia de:
- "" vs "NA" en dimensiones seleccionadas;
- sector_economico_* como "1.0" vs "1";
- ruido flotante en sum_masa_sal_ta.
```

Resultado final:

```text
aggregate_sum_masa_sal_ta: 5683478926.2900
existing_sum_masa_sal_ta: 5683478926.2900
aggregate_fingerprint: 0b410fedc81292cd50a30513c21f4f07faeb7c3d7b12760efb8104bb5bda9581
existing_fingerprint: 0b410fedc81292cd50a30513c21f4f07faeb7c3d7b12760efb8104bb5bda9581
comparison_status: already_exists
```

### 2016-02-29

Contexto:

```text
Periodo historico ya existente en concentrado/PostgreSQL.
Raw fue descargado con el nuevo flujo.
Sirvio como prueba limpia de punta a punta despues de PR #32.
```

Datos conocidos:

```text
periodo: 2016-02-29
download.status: success
download.downloaded: true
raw_file_path: data\raw\imss\asegurados\2016\asg-2016-02-29.csv
raw_sha256: 13eafe73b36a14383d5db65a51ccd369dde6f910a8c87af4af855ac8e9e96055
download_manifest: outputs\audit\download\download_20260708T235442Z_f0b7fbac_2016-02-29.json

validation.status: success
validation.valid: true
validation_manifest: outputs\audit\raw_validation\raw_validation_20260708T235737Z_4aad4ad8_2016-02-29.json

process.status: success
rows_read: 3655343
aggregate_rows: 3655343
dimension_normalization.applied: true
aggregate_output_path: outputs\processing\raw_aggregate_20260708T235820Z_abb0b64c_2016-02-29.csv
aggregate_sha256: 366ef7005377f95123e5afba8c256dbe7c8b0f27081f12643ecc11e084ae3f37
processing_manifest: outputs\processing\raw_processing_manifest_20260708T235820Z_abb0b64c_2016-02-29.json

compare.status: success
comparison_status: already_exists
aggregate_summary.row_count: 3655343
existing_summary.row_count: 3655343
aggregate_fingerprint: dd4c411db1b38c029ae001a22690bd431d9a4e343a39eece9ad13222253c629e
existing_fingerprint: dd4c411db1b38c029ae001a22690bd431d9a4e343a39eece9ad13222253c629e
compare_manifest: outputs\processing\raw_compare_manifest_20260709T000056Z_0c694fa9_2016-02-29.json
```

Resultado:

```text
Flujo limpio de punta a punta.
comparison_status = already_exists.
No se modifico concentrado.
No se modifico PostgreSQL.
```

## Evidencia local generada

Los manifests y artefactos de evidencia se generan localmente en:

```text
outputs/audit/download/
outputs/audit/raw_validation/
outputs/processing/
```

`outputs/` esta ignorado por Git, por lo que los manifests y agregados temporales no se versionan.

Esta evidencia es auditoria operativa local. No es todavia auditoria persistente centralizada en PostgreSQL ni en storage externo.

## Confirmaciones de no afectacion

```text
No se modifico data/processed/imss_concentrado.csv.
No se escribio en data/processed/.
No hubo carga a PostgreSQL.
No se modifico staging.
No se modifico final.
No se modifico period_control.
No se modifico run_manifest.
No se implemento housekeeping.
No se modifico etl_imss.py.
No se modifico config/config.yaml como parte de estos PRs.
```

## Estado tecnico alcanzado

El nuevo flujo raw IMSS ya reproduce funcionalmente periodos historicos existentes en el concentrado, sin modificar `data/processed` ni PostgreSQL.

```text
2016-03-31 valido correcciones de compatibilidad.
2016-02-29 valido descarga nueva y flujo limpio de punta a punta.
```

## Riesgos restantes

1. La auditoria sigue siendo local en `outputs/`.
2. La publicacion insert-only al concentrado aun no esta implementada.
3. PostgreSQL todavia no participa en el nuevo flujo raw.
4. Falta disenar un dry-run de publicacion antes de escribir en concentrado.
5. Falta definir politica de conservacion o persistencia de manifests.
6. `config/config.yaml` sigue con cambio local preexistente fuera del alcance.

## Siguiente frente recomendado

PR futuro:

```text
Publish plan / dry-run insert-only
```

Diseno sugerido:

```text
aggregate temporal
-> compare
-> if already_exists: no-op
-> if conflict: block
-> if new_period: generate publish_plan.json
-> no escribir concentrado todavia en primera fase
```

Despues de ese dry-run, en otro PR separado:

```text
insert-only real al concentrado
```

Este documento no implementa publicacion, housekeeping ni integracion PostgreSQL.
