# Plan De Trabajo

## Estado Actual

El repositorio contiene un motor local IMSS en estabilizacion. El ETL principal sigue en `etl_imss.py`; la logica de normalizacion, transformacion, metricas y agregacion vive en `src/imss_engine/` con pruebas unitarias.

La auditoria oficial esta en `imss_duckdb_exports.py`. El manifest de corrida esta en `src/imss_engine/manifest.py`.

## Cerrado En Fase 2

- Reglas de negocio IMSS estabilizadas.
- Auditoria DuckDB oficial.
- Idempotencia por corrida completa con staging y replace atomico.
- Manifest JSON de corrida.
- Integracion ETL -> archivo final -> auditoria DuckDB -> manifest.
- Pruebas locales con fixtures pequenos.
- GitHub Actions ligero para ejecutar `pytest` sin datos reales.
- Consolidacion insert-only hacia `data/processed/imss_concentrado.csv`.
- Modos `mes_consulta` y `periodo_consulta`.
- Hash ligero `period_fingerprint_hash`.
- Auditoria ligera por periodo antes de insertar.

## Operativo Actual

- Ejecutar tests: `python -m pytest`.
- Ejecutar auditoria manual: `python scripts/run_audit.py <archivo_csv> --output-dir reports/audits/audit_manual`.
- Ejecutar ETL local: `python scripts/run_etl.py`.
- Configurar `etl.mode` como `mes_consulta` o `periodo_consulta` antes de ejecutar ETL real.

## Fuera De Alcance Actual

- Acumulacion historica controlada.
- `full_refresh`.
- `upsert_period`.
- Append mensual.
- PostgreSQL o cualquier base de datos.
- API.
- Dashboard.
- Docker.
- Orquestacion productiva.
- Observabilidad avanzada.

## Siguiente Trabajo Sugerido

1. Definir estrategia formal de acumulacion historica.
2. Disenar `full_refresh` y `upsert_period` antes de implementarlos.
3. Definir contratos de salida para consumo analitico.
4. Validar periodos adicionales contra controles externos.
5. Evaluar almacenamiento persistente solo cuando el flujo local este cerrado.
