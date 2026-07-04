# Known Issues

- Official methodology files were not found locally in this repository during Phase 2. The implemented rules are limited to the approved business rules supplied for this phase.
- `etl_imss.py` remains the historical executable. It now delegates chunk transformation and aggregation to `src/imss_engine`, but download orchestration is not refactored.
- `etl_imss.py` still performs real network downloads when executed directly; do not run it in tests.
- The ETL depends on availability and layout stability of the IMSS public files.
- Dependency versions in `requirements.txt` are not pinned.
- Some legacy/exploratory scripts may contain hardcoded local paths or assumptions.
- `main.py`, legacy visualizations and notebook analyses are outside the Phase 2 stabilization scope.
- PostgreSQL, API, dashboard, Docker and advanced CI/CD are intentionally not implemented in this phase.
- GitHub Actions currently provides only lightweight test validation with fixtures and no network-dependent ETL execution.
- Official catalog joins for sector, entity, sex, age and income ranges are pending until local documented catalog files are available.
- The DuckDB audit validates generated CSV structure and arithmetic consistency, but validation against official IMSS bulletins remains an external control and does not replace methodology validation.
- Full-run output idempotency is implemented with staging and atomic replace. Incremental upsert by period is still pending.
- Run manifests provide local technical traceability, but they are not a historical registry or period-level upsert log.
- Integrated DuckDB audit is part of run certification. If it fails after final CSV publication, the manifest records a failed run even though the CSV remains on disk.
- Two additional periods should be validated before treating the Phase 2 workflow as broadly stable.
- `ptpd` still needs historical review for periods where the source column does not appear.
- Do not open large generated CSV files in Excel; use DuckDB-based audit outputs or analytical tools built for large files.
- The concentrado is insert-only. There is no approved overwrite, `full_refresh` or `upsert_period` behavior yet.
