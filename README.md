# IMSS Engine Report

Pipeline local en Python para descargar, procesar, auditar y analizar datos abiertos del IMSS. El objetivo futuro es convertir este repositorio en un motor de datos laborales, salariales y sectoriales para reportes economicos de Mexico.

## Estado actual

El proyecto esta en Fase 2: **ETL funcional local / prototipo tecnico avanzado**.

El ETL historico real sigue en `etl_imss.py`, pero la normalizacion, transformacion, metricas y agregacion ya tienen funciones testeables en `src/imss_engine/`. `main.py`, `imss_etl.py`, `join.py` y `viz.py` fueron separados como codigo legacy o exploratorio.

No hay PostgreSQL, API, dashboard, Docker ni CI/CD en esta etapa.

## Reglas de negocio estabilizadas

- La base IMSS se trata como cubo agregado, no como base individual.
- `asegurados`, `no_trabajadores` y `ta` se conservan como metricas distintas.
- `sector_economico_3` no existe en el layout implementado; se preservan `sector_economico_1`, `sector_economico_2` y `sector_economico_4`.
- `ptpd` se conserva cuando existe y queda nulo cuando no existe historicamente.
- VSM y UMA se separan en `rango_ingreso_vsm` y `rango_ingreso_uma`.
- El SBC se calcula con denominadores `*_sal`, no con `ta`.
- `timestamp` es metadato de corrida, no llave analitica.
- `NA`, `ND` y nulos no son errores automaticos.

## Estructura

```text
config/              Configuracion local y ejemplo publico
src/imss_engine/     Paquete base para la futura modularizacion
scripts/             Wrappers operativos minimos
tests/               Pruebas unitarias y fixtures
docs/                Notas tecnicas y documentacion inicial
legacy/              Scripts historicos o exploratorios
notebooks/           Notebooks de revision
data/                Datos locales no versionados
reports/             Auditorias, perfiles, manifests y figuras generadas
logs/                Logs locales no versionados
```

## Uso local

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

El ETL historico se ejecuta explicitamente con:

```powershell
python etl_imss.py
```

Tambien existe un wrapper:

```powershell
python scripts/run_etl.py
```

Importar `etl_imss.py` no debe iniciar descargas. Las descargas solo deben ocurrir al ejecutar el entrypoint.

`etl_imss.py` genera la salida final con staging por corrida: escribe primero en un archivo temporal `*.tmp` y solo reemplaza el CSV final si todos los periodos terminan correctamente. Si la corrida falla, el archivo final anterior no se reemplaza y el temporal se limpia.

La idempotencia actual es a nivel corrida completa. El upsert incremental por periodo queda fuera de esta fase.

## Manifiesto de corrida

Cada corrida del ETL genera un manifiesto tecnico JSON en `reports/manifests/` con formato `manifest_<run_id>.json`.

El manifiesto registra evidencia local de linaje: `run_id`, inicio y fin de corrida, estado `success` o `failed`, ruta y hash de configuracion, archivo de salida, hash y tamano del archivo final, periodos configurados, resultado por periodo, URL fuente, columnas detectadas, filas leidas/procesadas cuando estan disponibles y errores si ocurren.

Despues de publicar el archivo final, el ETL ejecuta la auditoria DuckDB sobre ese archivo y guarda sus resultados en `reports/audits/<run_id>/`. El manifiesto registra `audit_output_dir`, `audit_status`, `audit_files` y `audit_error`.

Si la auditoria falla despues de publicar el CSV final, el archivo final se conserva, pero el manifiesto queda con `status: failed` y `audit_status: failed`; esa corrida no queda certificada.

El manifiesto garantiza trazabilidad tecnica de corrida, archivo final publicado, hash, periodos y fallas. No implementa acumulacion historica, upsert incremental por periodo, recuperacion parcial ni carga a base de datos.

## Pruebas

Las pruebas usan fixtures pequenos en `tests/fixtures/` y no deben llamar red ni descargar archivos reales.

```powershell
python -m pytest
```

## Auditoria DuckDB

La herramienta oficial de auditoria/validacion de salida para Fase 2 es `imss_duckdb_exports.py`, ejecutada mediante el wrapper operativo:

```powershell
python scripts/run_audit.py <archivo_csv>
```

La auditoria exporta reportes pequenos a `reports/audits/` y valida layout, columnas faltantes, ausencia de `sector_economico_3`, resumen general y por periodo, composicion de puestos, masa salarial, SBC con denominador `ta_sal`, duplicados por llave analitica Fase 2 y distribucion de `ptpd`.

Cuando se ejecuta manualmente, puede usarse un directorio reemplazable:

```powershell
python scripts/run_audit.py <archivo_csv> --output-dir reports/audits/audit_2026_05
```

Cuando se ejecuta integrada al ETL, la auditoria usa `reports/audits/<run_id>/` para dejar evidencia trazable de esa corrida.

No se recomienda abrir CSV grandes en Excel. Para revisar salidas grandes usa DuckDB, Polars, pandas por chunks o los reportes exportados en `reports/audits/`.

## Datos y artefactos

Los datos pesados, temporales y salidas generadas no se versionan. Esto incluye `data/raw/`, `data/interim/`, `data/processed/`, `logs/`, CSV grandes, Parquet, bases locales y reportes generados.

## Riesgos conocidos

Ver:

- `docs/known_issues.md`
- `docs/data_dictionary.md`
- `docs/restructure_notes.md`
- `docs/business_rules_imss.md`
