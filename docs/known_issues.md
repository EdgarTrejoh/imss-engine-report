# Known Issues

- `etl_imss.py` is still the historical ETL implementation and has not been modularized yet.
- The current aggregation uses `sector_economico_1`; the target model requires preserving `sector_economico_1` through `sector_economico_4`.
- `timestamp` is currently part of the aggregation key, which affects idempotency.
- PostgreSQL, API, dashboard, Docker and CI/CD are intentionally not implemented yet.
- Some legacy/exploratory scripts may contain hardcoded local paths or assumptions.
- Test coverage is minimal and should not be treated as validation of the full ETL.
