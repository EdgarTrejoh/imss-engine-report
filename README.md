# IMSS Engine Report

Pipeline local en Python para descargar, procesar, auditar y analizar datos abiertos del IMSS. El objetivo futuro es convertir este repositorio en un motor de datos laborales, salariales y sectoriales para reportes economicos de Mexico y, posteriormente, integrarlo a un tablero economico central.

## Estado actual

El proyecto esta en una primera reestructura. El ETL historico real sigue en `etl_imss.py`; `main.py`, `imss_etl.py`, `join.py` y `viz.py` fueron separados como codigo legacy o exploratorio.

No hay PostgreSQL, API, dashboard, Docker ni CI/CD en esta etapa.

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

## Pruebas

`pytest` debe usarse con cuidado. La prueba actual importa funciones del ETL historico, por lo que el repositorio debe conservar la guardia `if __name__ == "__main__": main()` para evitar descargas reales durante imports.

No se debe usar `pytest` como validacion completa del ETL ni contra descargas reales.

## Datos y artefactos

Los datos pesados, temporales y salidas generadas no se versionan. Esto incluye `data/raw/`, `data/interim/`, `data/processed/`, `logs/`, CSV grandes, Parquet, bases locales y reportes generados.

## Riesgos conocidos

Ver:

- `docs/known_issues.md`
- `docs/data_dictionary.md`
- `docs/restructure_notes.md`
