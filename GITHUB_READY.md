# GitHub Ready - Snapshot tecnico

## Descripcion del proyecto

Este proyecto contiene un pipeline ETL local para descargar, transformar, agregar, auditar y visualizar datos abiertos del IMSS. El flujo principal procesa archivos CSV grandes por bloques, normaliza diferencias historicas de layout y genera un consolidado analitico por periodo, entidad, sexo, rango de edad, rango UMA y sector economico.

## Estado actual

Estado clasificado: **ETL funcional local / prototipo tecnico avanzado**.

El nucleo del procesamiento esta implementado en `etl_imss.py` y usa `config.yaml` para construir las URLs, definir los periodos a procesar, el tamano de chunk y el archivo de salida. Existen scripts auxiliares para auditoria, perfilado, exportaciones con DuckDB y visualizacion.

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
- `config.yaml`
- `etl_imss.py`
- `imss_etl.py`
- `audit.py`
- `auditoria_profunda.py`
- `filtrar_valores.py`
- `imss_csv_profiler.py`
- `imss_csv_profiler_export.py`
- `imss_duckdb_exports.py`
- `join.py`
- `main.py`
- `viz.py`
- `review.ipynb`
- `tests/test_etl.py`

## Revision de config.yaml

`config.yaml` no contiene credenciales, tokens, usuarios, contrasenas ni rutas privadas sensibles. Contiene una URL publica del IMSS, parametros de ejecucion y lista de meses. Por lo tanto, se deja como archivo versionable.

## Advertencias conocidas

- No ejecutar `pytest` sin ajustar primero `etl_imss.py`, porque `tests/test_etl.py` importa `etl_imss.py` y ese archivo ejecuta el pipeline a nivel global.
- `etl_imss.py` no tiene guardia `if __name__ == "__main__"`, por lo que importar funciones dispara la ejecucion completa.
- `main.py`, `viz.py` y `join.py` contienen nombres de archivo o rutas hardcodeadas.
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
git add .gitignore GITHUB_READY.md README.md requirements.txt config.yaml *.py tests/test_etl.py review.ipynb
git status
```

No hacer commit hasta revisar el `git status` y confirmar el conjunto final de archivos.
