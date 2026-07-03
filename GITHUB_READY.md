# GitHub Ready - Snapshot tecnico

## Descripcion del proyecto

Este proyecto contiene un pipeline ETL local para descargar, transformar, agregar, auditar y visualizar datos abiertos del IMSS. El flujo principal procesa archivos CSV grandes por bloques, normaliza diferencias historicas de layout y genera un consolidado analitico por periodo, entidad, sexo, rango de edad, rango UMA y sector economico.

## Estado actual

Estado clasificado: **ETL funcional local / prototipo tecnico avanzado**.

El nucleo del procesamiento historico esta implementado en `etl_imss.py` y usa `config/config.yaml` para construir las URLs, definir los periodos a procesar, el tamano de chunk y el archivo de salida. Existen scripts auxiliares para auditoria, perfilado y exportaciones con DuckDB. El proyecto esta en reestructura inicial.

La salida del ETL historico se publica con staging por corrida completa: primero escribe a un archivo temporal `*.tmp` y solo reemplaza el archivo final si todos los periodos configurados terminan correctamente.

## Archivos excluidos

El snapshot excluye artefactos locales, temporales y salidas pesadas:

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `temp_*.csv`
- `imss_analisis_profundo*.csv`
- `*.parquet`
- `*.xlsx`
- `data/raw/`
- `data/interim/`
- `data/processed/`
- `logs/`
- archivos CSV generados por auditoria, perfilado y exportaciones
- `.ipynb_checkpoints/`
- `*.log`

## Archivos versionables

Se consideran versionables los archivos fuente, configuracion publica y documentacion:

- `README.md`
- `GITHUB_READY.md`
- `.gitignore`
- `requirements.txt`
- `config/config.yaml`
- `config/config.example.yaml`
- `etl_imss.py`
- `imss_duckdb_exports.py`
- `src/imss_engine/audit.py`
- `legacy/audit/audit_pandas_legacy.py`
- `legacy/audit/auditoria_profunda_legacy.py`
- `legacy/audit/filtrar_valores_legacy.py`
- `legacy/audit/imss_csv_profiler_legacy.py`
- `legacy/audit/imss_csv_profiler_export_legacy.py`
- `legacy/audit/validate_imss_output_experimental.py`
- `legacy/imss_etl_legacy.py`
- `legacy/join_manual_legacy.py`
- `legacy/main_analysis_legacy.py`
- `legacy/viz_exploratory_legacy.py`
- `notebooks/review.ipynb`
- `src/imss_engine/`
- `scripts/`
- `docs/`
- `tests/test_etl.py`

## Revision de config/config.yaml

`config/config.yaml` no contiene credenciales, tokens, usuarios, contrasenas ni rutas privadas sensibles. Contiene una URL publica del IMSS, parametros de ejecucion y lista de meses. Por lo tanto, se deja como archivo versionable.

## Advertencias conocidas

- `etl_imss.py` ya tiene guardia `if __name__ == "__main__"`, pero no se debe remover porque evita descargas al importar funciones.
- `legacy/main_analysis_legacy.py`, `legacy/viz_exploratory_legacy.py` y `legacy/join_manual_legacy.py` contienen nombres de archivo o rutas hardcodeadas.
- El proyecto depende de disponibilidad de red y del portal de datos del IMSS para ejecutar el ETL.
- Las dependencias en `requirements.txt` no estan fijadas por version.
- El entorno virtual local `.venv/` no debe subirse a GitHub.
- Los CSV consolidados y temporales son artefactos generados y no deben versionarse.

## Comando sugerido para ejecutar el ETL

Despues de crear y activar un entorno virtual e instalar dependencias:

```powershell
python etl_imss.py
```

Comandos sugeridos de preparacion local:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python etl_imss.py
```

## Comandos sugeridos para inicializar Git

Si el repositorio aun no esta inicializado correctamente:

```powershell
git init
git status
git add .gitignore GITHUB_READY.md README.md requirements.txt config/ src/ scripts/ docs/ legacy/ notebooks/ tests/ pyproject.toml *.py
git status
```

No hacer commit hasta revisar el `git status` y confirmar el conjunto final de archivos.
