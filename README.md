# IMSS Engine Report

Motor local en Python para descargar, transformar, agregar, auditar y trazar datos abiertos del IMSS. El repositorio esta en estabilizacion tecnica: no es todavia una API, dashboard ni producto final.

## Estado Actual

- ETL principal: `etl_imss.py`.
- Modulos testeables: `src/imss_engine/`.
- Auditoria oficial DuckDB: `imss_duckdb_exports.py`.
- Manifest de corrida: `src/imss_engine/manifest.py`.
- Wrappers operativos: `scripts/`.
- Codigo historico o exploratorio: `legacy/`.
- Pruebas locales y CI ligero: `tests/` y `.github/workflows/tests.yml`.

No existen todavia PostgreSQL, API, dashboard, Docker, acumulacion historica controlada, `full_refresh`, `upsert_period` ni carga a base de datos.

## Setup Limpio

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest
```

Python recomendado: 3.11.

## Comandos Vigentes

Pruebas:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Auditoria manual DuckDB:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_audit.py .\ruta\archivo.csv --output-dir .\reports\audits\audit_manual
```

Revision Git:

```powershell
git status --short
git diff --check
```

ETL local, solo cuando se quiera descargar/procesar datos reales:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_etl.py
```

No ejecutes el ETL dentro de pruebas unitarias.

## Reglas De Negocio Fase 2

- La base IMSS se trata como cubo agregado, no como base individual.
- `asegurados`, `no_trabajadores` y `ta` se conservan como metricas distintas.
- `sector_economico_3` no se crea; se preservan `sector_economico_1`, `sector_economico_2` y `sector_economico_4`.
- `ptpd` se conserva cuando existe y queda nulo cuando no existe historicamente.
- VSM y UMA se separan en `rango_ingreso_vsm` y `rango_ingreso_uma`.
- El SBC se calcula con denominadores `*_sal`, no con `ta`.
- `timestamp` es metadato de corrida, no llave analitica.
- `NA`, `ND` y nulos no son errores automaticos.

## Salida, Auditoria Y Manifest

`etl_imss.py` publica la salida final con staging por corrida completa: escribe primero a un archivo temporal y reemplaza el CSV final con `os.replace()` solo si todos los periodos terminan correctamente.

Despues de publicar el archivo final, el ETL ejecuta la auditoria DuckDB sobre ese archivo. La auditoria integrada usa:

```text
reports/audits/<run_id>/
```

El manifest se guarda como:

```text
reports/manifests/manifest_<run_id>.json
```

El manifest registra config usada, hash de config, periodos/URLs, archivo final, hash del archivo final, auditoria generada, estado de auditoria y errores.

La auditoria manual puede sobrescribir outputs si se usa el mismo `--output-dir`. La auditoria integrada al ETL usa un directorio por `run_id` para conservar evidencia trazable de la corrida.

## Artefactos No Versionados

No se versionan datos pesados ni salidas generadas:

- `data/raw/`
- `data/interim/`
- `data/processed/`
- `reports/audits/`
- `reports/manifests/`
- `reports/profiles/`
- `reports/figures/`
- `logs/`
- `temp_*.csv`
- `*.tmp`
- `imss_analisis_profundo*.csv`
- `*.parquet`
- `*.xlsx`

Se conservan `.gitkeep` donde aplica para mantener la estructura.

## GitHub Actions

El workflow `Tests` ejecuta en `ubuntu-latest` con Python 3.11:

1. Checkout.
2. Setup Python.
3. Instalacion de `requirements.txt`.
4. `python -m pytest`.

No ejecuta `etl_imss.py`, no descarga datos reales, no llama al portal IMSS, no corre auditorias sobre CSV grande y no carga datos a ninguna base.

## Documentacion

- `docs/business_rules_imss.md`
- `docs/data_dictionary.md`
- `docs/restructure_notes.md`
- `docs/known_issues.md`
- `docs/plan_trabajo.md`
