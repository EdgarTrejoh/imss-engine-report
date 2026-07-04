# GitHub Ready - Snapshot Tecnico

## Descripcion Del Proyecto

`imss-engine-report` es un motor local en Python para procesar, auditar y trazar datos abiertos del IMSS. El proyecto esta en estabilizacion tecnica, no es todavia una API, dashboard ni producto final.

## Estado Actual

- ETL principal: `etl_imss.py`.
- Paquete modular: `src/imss_engine/`.
- Auditoria oficial DuckDB: `imss_duckdb_exports.py`.
- Manifest de corrida: `src/imss_engine/manifest.py`.
- Wrappers operativos: `scripts/`.
- Historico/exploratorio: `legacy/`.
- CI ligero: `.github/workflows/tests.yml`.

No existen todavia PostgreSQL, BigQuery, API, dashboard, Docker, scheduler, `full_refresh`, `upsert_period` ni carga cloud automatizada.

## Salidas Y Trazabilidad

El ETL publica la salida final con staging por corrida completa y replace atomico. Si la corrida falla antes de publicar, el archivo final anterior se conserva.

Cuando una corrida publica el archivo final, ejecuta auditoria DuckDB integrada en:

```text
reports/audits/<run_id>/
```

El manifest queda en:

```text
reports/manifests/manifest_<run_id>.json
```

La auditoria manual puede usar cualquier `--output-dir`; si se reutiliza el mismo directorio, sus archivos pueden sobrescribirse.

## Concentrado Insert-Only

El concentrado oficial local es:

```text
data/processed/imss_concentrado.csv
```

Los modos soportados son `mes_consulta` y `periodo_consulta`. Ambos cargan solo periodos nuevos y detectan duplicados/conflictos por `periodo_informacion`, row count y `period_fingerprint_hash`.

La fase no implementa `full_refresh`, `upsert_period` ni sobrescritura de periodos existentes.

## Archivos Excluidos

El snapshot excluye artefactos locales, temporales y salidas pesadas:

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `temp_*.csv`
- `imss_analisis_profundo*.csv`
- `*.tmp`
- `*.parquet`
- `*.xlsx`
- `data/raw/*`
- `data/interim/*`
- `data/processed/*`
- `reports/audits/*`
- `reports/manifests/*`
- `reports/profiles/*`
- `reports/figures/*`
- `logs/*`
- `.ipynb_checkpoints/`
- `*.log`

Se conservan `.gitkeep` en carpetas de estructura.

## Archivos Versionables Principales

- `README.md`
- `GITHUB_READY.md`
- `.gitignore`
- `.gitattributes`
- `requirements.txt`
- `pyproject.toml`
- `.github/workflows/tests.yml`
- `config/config.yaml`
- `config/config.example.yaml`
- `etl_imss.py`
- `imss_duckdb_exports.py`
- `src/imss_engine/`
- `scripts/`
- `docs/`
- `tests/`
- `legacy/`
- `notebooks/review.ipynb`

## Revision De Configuracion

`config/config.yaml` no contiene credenciales, tokens, usuarios ni contrasenas. Contiene URL publica del IMSS, parametros de ejecucion y lista de meses. `config/config.example.yaml` es el ejemplo seguro para entornos limpios.

## Comandos Recomendados

Setup local:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Validacion:

```powershell
.\.venv\Scripts\python.exe -m pytest
git status --short
git diff --check
```

Auditoria manual:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_audit.py .\ruta\archivo.csv --output-dir .\reports\audits\audit_manual
```

ETL local, solo si se quiere descargar/procesar datos reales:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_etl.py
```

## Advertencias

- No ejecutar el ETL como parte de tests.
- Las pruebas deben seguir usando fixtures pequenos y sin red.
- Los CSV consolidados, auditorias, manifests y temporales son artefactos generados y no deben versionarse.
- Las dependencias se mantienen minimas para entorno limpio y CI ligero.
