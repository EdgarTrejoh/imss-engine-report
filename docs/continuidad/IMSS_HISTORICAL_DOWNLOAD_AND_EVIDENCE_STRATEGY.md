# Estrategia histórica IMSS y evidencia operativa

## 1. Objetivo

Definir cómo descargar, conservar, validar y procesar archivos históricos IMSS por periodo sin depender de un único CSV gigante y sin poner en riesgo los periodos ya cargados en PostgreSQL.

## 2. Estado operativo actual

Los periodos actuales resguardados son:

- `2016-01-31`
- `2016-02-29`
- `2016-03-31`
- `2026-01-31`

El proyecto ya cuenta con el comando `--summary-reserved-periods` para consultar un resumen compacto read-only de los periodos preservados en `imss.imss_hechos_asegurados`.

También existe el pre-check de elegibilidad de housekeeping, que diagnostica si un periodo tiene evidencia suficiente para considerarse candidato a una limpieza futura del CSV operativo.

Housekeeping real no existe todavía. El downloader histórico queda separado de la carga y debe operar por periodo con manifest local.

El CSV actual `data/processed/imss_concentrado.csv` no debe tocarse todavía.

## 3. Información pendiente de confirmar

Antes de implementar un downloader o un flujo histórico, falta confirmar:

- Fuente exacta de descarga.
- URL base o mecanismo de obtención.
- Estructura de nombres esperada.
- Si los archivos son mensuales, diarios, acumulados o comprimidos.
- Si existen cambios de estructura entre años.
- Carpeta definitiva para raw histórico.
- Carpeta definitiva para processed mensual.
- Estrategia para evitar duplicados.
- Estrategia para guardar evidencia JSON.

## 4. Propuesta de estructura de carpetas

Propuesta conceptual, sin crear carpetas todavía salvo que ya existan:

```text
data/
  raw/
    imss/
      asegurados/
        yyyy/
          asg-yyyy-mm-dd.csv
  processed/
    imss_concentrado.csv
outputs/
  audit/
    housekeeping/
    summary/
    download/
```

Reglas de uso:

- `data/raw/` conserva archivos fuente originales.
- `data/processed/` contiene derivados operativos.
- `outputs/` contiene evidencia local no versionada.
- La evidencia futura debería migrar a una tabla/base de auditoría.

## 5. Manifest de descarga

Campos esperados:

- `run_id`
- `downloaded_at`
- `source_url`
- `periodo_informacion`
- `raw_file_path`
- `file_exists`
- `file_size_bytes`
- `sha256`
- `status`
- `error_message`

El PR #26 implementa el primer downloader controlado por periodo. Su alcance se limita a descargar un CSV raw, conservarlo en `data/raw/imss/asegurados/YYYY/`, calcular tamaño/hash y escribir un manifest local en `outputs/audit/download/`. No procesa CSV, no toca `data/processed/imss_concentrado.csv` y no carga PostgreSQL.

## 6. Manifest de procesamiento propuesto

Campos esperados:

- `run_id`
- `periodo_informacion`
- `raw_file_path`
- `processed_file_path`
- `rows_read`
- `rows_valid`
- `rows_rejected`
- `schema_version`
- `validation_status`
- `created_at`

## 7. Regla de procesamiento histórico

No se deben cargar 10 años a ciegas.

El procesamiento histórico debe iniciar con una ventana pequeña y verificable. Una sugerencia inicial es abril-diciembre 2016, solo si la fuente y estructura quedan confirmadas.

La alternativa más conservadora es descargar un solo periodo faltante y validarlo de punta a punta antes de ampliar el alcance.

## 8. Reglas de seguridad operativa

- No borrar CSV fuente sin snapshot, manifest y hashes.
- No limpiar `imss_concentrado.csv` manualmente.
- No mezclar downloader con carga a PostgreSQL.
- No mezclar housekeeping con loader.
- No usar pandas/DataFrame en loader PostgreSQL de grandes archivos.
- No sobrescribir final.
- No modificar staging/final/period_control/run_manifest fuera de sus comandos formales.

## 9. Próximos PRs sugeridos

- PR #26: downloader con manifest, sin carga automática.
- PR #27: prueba controlada de descarga de 1 periodo.
- PR #28: procesamiento controlado de nuevos periodos.
- PR posterior: almacenamiento formal de evidencia JSON.
- PR posterior: housekeeping real con snapshot, manifest y hashes.
