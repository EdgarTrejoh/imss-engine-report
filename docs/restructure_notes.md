# Restructure Notes

## Scope

This pass only prepares repository organization. It does not change the business logic of the ETL, add storage infrastructure, expose an API, or create a dashboard.

## Decisions

- Keep `etl_imss.py` at the repository root as the historical executable until the ETL is migrated safely.
- Move exploratory and legacy scripts to `legacy/` without deleting them.
- Create `src/imss_engine/` as a package skeleton for future modularization.
- Create operational wrappers under `scripts/`; they should not perform downloads merely by being imported.
- Move `config.yaml` into `config/` and keep a sanitized `config.example.yaml`.

## Not Verified

- Full ETL execution was not verified in this pass by design.
- Download behavior and IMSS server availability were not verified.
- Output parity between the historical ETL and future package modules is not verified.
