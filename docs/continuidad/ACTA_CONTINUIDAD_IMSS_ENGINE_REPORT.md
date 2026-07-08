# ACTA DE CONTINUIDAD — IMSS ENGINE REPORT

## 1. Nombre del proyecto

**IMSS Engine Report**

Repositorio: `EdgarTrejoh/imss-engine-report`

Ruta local: `C:\proyectos\02_etl_process\02_imss`

---

## 2. Objetivo del proyecto

Construir un motor ETL auditable para procesar información histórica del IMSS desde CSV fuente hacia PostgreSQL, preservando trazabilidad por periodo, con capas separadas de staging, final, control de periodo, manifest de corrida y validaciones de integridad.

---

## 3. Estado actual reconocido

**Fase estable local PostgreSQL.**

El flujo base ya está funcionando en `main` para:

```text
check-existing
register-period-control
register-run-manifest
load-staging
promote-staging-final
validate-post-promotion
finalize-period-control
finalize-run-manifest
check-housekeeping-eligibility
summary-reserved-periods
```

No se ha implementado housekeeping real del CSV.

---

## 4. Avance confirmado

### Periodos del CSV actual detectados

```text
2016-01-31
2016-02-29
2016-03-31
2026-01-31
```

### Filas detectadas en CSV

```text
2016-01-31   3,638,419
2016-02-29   3,655,343
2016-03-31   3,652,496
2026-01-31   4,731,705
TOTAL        15,677,963
```

### Periodos cargados y cerrados en PostgreSQL

```text
2016-01-31   staging + final + period_control loaded + run_manifest completed + eligibility true
2016-02-29   staging + final + period_control loaded + run_manifest completed + eligibility true
2016-03-31   staging + final + period_control loaded + run_manifest completed + eligibility true
2026-01-31   staging + final + period_control loaded + run_manifest completed + eligibility true
```

### PRs recientes cerrados

```text
PR #21: finalize-run-manifest
PR #22: check-housekeeping-eligibility
PR #23: dotenv + resumen compacto de periodos resguardados
```

### Último estado Git confirmado

```text
main...origin/main
Merge PR #23: 2e2e2b0
```

---

## 5. Pendientes reales

### Resuelto en PR #23

```text
1. Lectura automática de .env.
2. Salida compacta/resumen para periodos resguardados.
```

### Pendiente

```text
1. Diseñar downloader histórico por periodo.
2. Descargar archivos faltantes para completar 10 años.
3. Procesar nuevos periodos uno por uno o por lotes controlados.
4. Implementar housekeeping real del CSV solo después de snapshot, manifest y hashes.
5. Definir estrategia de almacenamiento formal de evidencia JSON de pre-checks.
```

No está pendiente “arreglar” enero 2016, febrero 2016, marzo 2016 ni enero 2026: esos periodos ya quedaron cerrados según evidencia operativa.

---

## 6. Decisiones tomadas

```text
1. PostgreSQL v1 es insert-only.
2. No existe upsert_period.
3. No existe full_refresh.
4. staging es acumulativo y sirve como landing/evidencia técnica.
5. final es acumulativo y sirve como capa curada.
6. El CSV fuente no se limpia manualmente ni destructivamente.
7. Housekeeping real no se implementa hasta tener snapshot, manifest, hashes y comando formal.
8. El pre-check de elegibilidad solo diagnostica; no modifica nada.
9. Los periodos se cargan de forma controlada por ciclo completo.
10. No se debe cargar “10 años” a ciegas en un CSV gigante sin estrategia.
11. Se recomienda procesar histórico por archivo/periodo, no mediante un único CSV monstruo.
12. .env puede cargarse automáticamente, pero no debe versionarse.
13. outputs/ es evidencia operativa local y no debe versionarse.
```

---

## 7. Reglas y restricciones del usuario

```text
1. No inventar avance.
2. No marcar tareas como terminadas si no están verificadas.
3. No asumir información no confirmada.
4. No borrar código útil; si se retira, mover a legacy.
5. No usar Streamlit por defecto.
6. No llamar MVP automáticamente a los proyectos.
7. No abrir frentes nuevos sin cerrar el frente actual.
8. No limpiar CSV sin manifest, snapshot y evidencia.
9. No usar pandas/DataFrame en el loader PostgreSQL de grandes archivos.
10. No modificar PostgreSQL desde housekeeping real salvo lecturas de control, cuando aplique formalmente.
11. No mezclar housekeeping con carga a staging o promoción a final.
12. Responder paso a paso, un comando a la vez.
```

---

## 8. Arquitectura / stack definido

```text
Lenguaje: Python
Base local: PostgreSQL 18.3
DB local: imss_engine_test
CLI: scripts/run_postgres_loader.py
Módulo principal: src/imss_engine/postgres/loader.py
Control: imss.imss_period_control
Manifest: imss.imss_run_manifest
Staging: imss.imss_staging_asegurados
Final: imss.imss_hechos_asegurados
CSV fuente: data/processed/imss_concentrado.csv
Evidencia local no versionada: outputs/
```

### Flujo operativo validado

```text
1. check-existing
2. register-period-control
3. register-run-manifest
4. load-staging
5. promote-staging-final
6. validate-post-promotion
7. finalize-period-control
8. finalize-run-manifest
9. check-housekeeping-eligibility
10. summary-reserved-periods
```

---

## 9. Archivos, rutas, repositorios o entregables mencionados

```text
Repositorio:
https://github.com/EdgarTrejoh/imss-engine-report

Ruta local:
C:\proyectos\02_etl_process\02_imss

CSV fuente:
data\processed\imss_concentrado.csv

Archivo de plan housekeeping:
docs/source_csv_housekeeping_plan.md

Plan loader PostgreSQL:
docs/postgresql_loader_plan.md

Acta de continuidad:
docs/continuidad/ACTA_CONTINUIDAD_IMSS_ENGINE_REPORT.md

Script CLI:
scripts/run_postgres_loader.py

Loader:
src/imss_engine/postgres/loader.py
```

### Ramas recientes

```text
feature/imss-postgres-final-run-manifest
feature/imss-source-csv-housekeeping-eligibility
feature/imss-dotenv-and-reserved-periods-summary
```

### Commits relevantes

```text
PR #21 mergeado a main: 6b0c67d
PR #22 mergeado a main: 240f025
PR #23 mergeado a main: 2e2e2b0
```

---

## 10. Problemas, errores o riesgos detectados

```text
1. El JSON de pre-check global puede ser largo; para revisión operativa ya existe summary-reserved-periods.
2. El JSON impreso en consola no se guarda automáticamente.
3. Housekeeping real aún no existe.
4. Limpiar CSV manualmente sería riesgo alto.
5. Un CSV único con 10 años puede volverse demasiado grande y caro de escanear.
6. El loader actual escanea el CSV completo para cargar un periodo.
7. Ya ocurrió un bug en desarrollo donde validate_period devolvía LoaderStepResult y eso rompía psycopg; fue corregido antes del merge del PR #22.
8. Existió un problema local previo de mojibake en columna tamaño_patron; fue corregido localmente.
9. outputs/ contiene evidencia local y debe permanecer fuera de Git.
10. .env contiene credenciales locales y debe permanecer fuera de Git.
```

---

## 11. Último punto exacto donde nos quedamos

Se confirmó que los cuatro periodos presentes en `imss_concentrado.csv` están cargados, promovidos, validados, cerrados y elegibles para housekeeping futuro.

Después se confirmó el cierre de PR #23:

```text
feat: add dotenv loading and reserved periods summary
```

El proyecto ya puede cargar `.env` automáticamente y consultar un resumen compacto de periodos resguardados con:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --summary-reserved-periods
```

o filtrando un periodo:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_postgres_loader.py --summary-reserved-periods --period 2026-01-31
```

---

## 12. Próxima acción recomendada

Crear un PR pequeño y controlado para el siguiente frente:

```text
PR #24: downloader histórico por periodo con manifest, sin carga automática.
```

Alcance recomendado:

```text
1. Diseñar downloader histórico por periodo.
2. No cargar automáticamente a PostgreSQL.
3. No tocar staging/final/period_control/run_manifest.
4. Guardar raw por archivo original si se confirma carpeta objetivo.
5. Generar manifest de descarga.
6. No mezclar descarga con housekeeping real.
```

---

## 13. Supuestos prohibidos

```text
1. No asumir que ya están descargados los 10 años.
2. No asumir que existen 120 archivos.
3. No asumir que el CSV actual contiene más de 4 periodos.
4. No asumir que housekeeping real existe.
5. No asumir que el JSON de pre-check quedó guardado salvo evidencia explícita en outputs/.
6. No asumir que se puede borrar o reescribir imss_concentrado.csv.
7. No asumir que los periodos futuros se pueden cargar en lote sin validación individual.
8. No asumir que staging es temporal.
9. No asumir que final puede sobrescribirse.
10. No asumir que run_manifest o period_control pueden modificarse fuera de su flujo formal.
```

---

## 14. Información que falta confirmar

```text
1. Fuente exacta para descargar los archivos históricos IMSS.
2. Estructura de nombres esperada de los 120 archivos.
3. Si los archivos históricos vienen mensuales, diarios o acumulados.
4. Si el pipeline actual ya tiene downloader o solo CSV consolidado.
5. Si se va a conservar raw por archivo original.
6. Carpeta objetivo para raw histórico.
7. Carpeta objetivo para processed mensual.
8. Si se quiere procesar abril-diciembre 2016 primero o descargar los 10 años completos antes.
9. Si se desea guardar evidencia JSON en outputs/housekeeping/ u otro destino formal.
10. Si la contraseña PostgreSQL se manejará solo en .env local o también con otro mecanismo.
```

---

## Actualización — PR #23 cerrado

Fecha: 2026-07-07

PR #23:
feat: add dotenv loading and reserved periods summary

Merge en main:
2e2e2b0

Estado:
Cerrado e integrado a main.

Cambios confirmados:

1. Lectura automática de `.env` implementada.
2. `.env` no sobrescribe variables de entorno existentes.
3. `outputs/` agregado a `.gitignore`.
4. Comando `--summary-reserved-periods` agregado.
5. Filtro opcional `--period` agregado.
6. Resumen compacto read-only validado contra PostgreSQL local.
7. Tests agregados y ejecutados correctamente.

Validación:

- `pytest`: 54 passed.
- `git diff --check`: OK.
- Validación real PostgreSQL local: OK.

Periodos devueltos por `--summary-reserved-periods`:

- `2016-01-31`
- `2016-02-29`
- `2016-03-31`
- `2026-01-31`

Fuera de alcance confirmado:

- No se tocó `data/processed/imss_concentrado.csv`.
- No se modificó staging.
- No se modificó final.
- No se modificó `period_control`.
- No se modificó `run_manifest`.
- No se implementó housekeeping real.
- No se implementó downloader.
- No se usó pandas/DataFrame.
- No se versionó `.env`.
- No se versionó `outputs/`.

Pendientes posteriores:

1. Diseñar downloader histórico por periodo.
2. Definir almacenamiento formal de evidencia JSON.
3. Diseñar housekeeping real con snapshot, manifest y hashes.
4. Descargar/procesar histórico faltante de forma controlada.

---

## Actualización — Estrategia histórica pendiente

Después de PR #23 y PR #24, el siguiente frente recomendado es definir la estrategia de descarga histórica y evidencia operativa antes de implementar downloader o housekeeping real.

Documento de referencia:

`docs/continuidad/IMSS_HISTORICAL_DOWNLOAD_AND_EVIDENCE_STRATEGY.md`

---

## Actualización — PR #26 en curso

PR #26 prepara un downloader histórico IMSS separado del ETL y del loader PostgreSQL.

Alcance previsto:

- Descargar un solo periodo por comando explícito.
- Conservar raw en `data/raw/imss/asegurados/YYYY/`.
- Generar manifest local en `outputs/audit/download/`.
- No tocar `data/processed/imss_concentrado.csv`.
- No cargar PostgreSQL.
- No implementar housekeeping real.

---

## Documento listo para reentrada

Continuar desde:

```text
Siguiente paso sugerido: PR #24 para downloader histórico por periodo con manifest, sin carga automática.
```
