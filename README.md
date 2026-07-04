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

No existen todavia PostgreSQL, BigQuery, API, dashboard, Docker, scheduler, `full_refresh`, `upsert_period` ni carga cloud automatizada.

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

## Concentrado Insert-Only

La fase actual agrega consolidacion historica local insert-only hacia:

```text
data/processed/imss_concentrado.csv
```

Modos soportados en `config/config.yaml`:

- `mes_consulta`: procesa un solo mes declarado en `etl.mes_consulta`.
- `periodo_consulta`: procesa la lista explicita `etl.periodo_consulta.meses` en el orden declarado.

Cuando `etl.mode` esta activo, `etl.meses` es legacy y debe quedar vacio (`meses: []`). Si `etl.meses` trae valores, el ETL falla con error claro para evitar procesar un periodo distinto al esperado.

Ejemplo `periodo_consulta`:

```yaml
etl:
  base_url: "http://datos.imss.gob.mx/sites/default/files/asg-{}.csv"
  chunk_size: 400000
  mode: "periodo_consulta"
  mes_consulta: "YYYY-MM-DD"  # ignorado en periodo_consulta
  periodo_consulta:
    meses:
      - "2016-01-31"
      - "2016-02-29"
      - "2016-03-31"
  output_file: "imss_analisis_profundo.csv"
  concentrado_file: "data/processed/imss_concentrado.csv"
  meses: []
```

No se calculan rangos automaticos, no se usan campos `desde`/`hasta` y no se sobrescriben periodos existentes.

Reglas insert-only por `periodo_informacion`:

- Periodo nuevo: `success_loaded`.
- Mismo periodo, mismo numero de filas y mismo hash ligero: `already_exists`.
- Mismo periodo, distinto numero de filas: `conflict_existing_period_row_count`.
- Mismo periodo, mismas filas y hash distinto: `conflict_existing_period_hash`.

El hash ligero `period_fingerprint_hash` resume el periodo con conteo de filas, sumas principales y cantidad de llaves analiticas distintas. Sirve para detectar cambios funcionales sin hacer auditoria forense del archivo completo.

Antes de insertar, cada periodo pasa por auditoria ligera: columnas requeridas, periodo correcto, ausencia de `sector_economico_3`, presencia de VSM/UMA y `ptpd`, duplicados por llave analitica Fase 2, SBC infinito y dataframe no vacio.

Esta fase no implementa `full_refresh`, `upsert_period`, sobrescritura de periodos existentes ni acumulacion en base de datos.

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
