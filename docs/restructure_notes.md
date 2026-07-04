# Restructure Notes

## Phase 1

The initial pass prepared repository organization without changing business logic:

- Keep `etl_imss.py` at the repository root as the historical executable until migration is safe.
- Move exploratory and legacy scripts to `legacy/` without deleting them.
- Create `src/imss_engine/` as the package location for modular ETL logic.
- Create operational wrappers under `scripts/`.
- Move configuration into `config/` and keep a sanitized example.

## Phase 2

This pass stabilizes business rules through pure, testable functions under `src/imss_engine/`:

- Schema validation for critical metric columns.
- Separate VSM and UMA income ranges.
- Preserve sector levels 1, 2 and 4 only.
- Include `ptpd` as a dimension when available and keep it null when absent.
- Preserve `asegurados`, `no_trabajadores` and `ta` as distinct metrics.
- Calculate worker-position, salary-mass and SBC metrics.
- Use `*_sal` denominators for SBC.
- Remove `timestamp` from the analytical aggregation key.
- Keep fixtures small and tests local without network calls.

## Phase 2 Audit Workflow

The official audit tool is the existing DuckDB-based `imss_duckdb_exports.py`. The provisional `scripts/validate_imss_output.py` logic was absorbed into that tool and the provisional script was moved to `legacy/audit/validate_imss_output_experimental.py`.

Operational wrappers now point to the DuckDB audit workflow:

- `python scripts/run_audit.py <archivo_csv>`
- `python scripts/run_profile.py <archivo_csv>` reuses the same audit workflow for now.
- `python scripts/run_exports.py <archivo_csv>` reuses the same audit workflow for now.

Audit outputs are generated under `reports/audits/` and are ignored by Git except for `.gitkeep`.

Active audit/validation files:

- `imss_duckdb_exports.py`
- `scripts/run_audit.py`
- `scripts/run_profile.py`
- `scripts/run_exports.py`
- `src/imss_engine/audit.py` for small reusable audit helpers used by tests.

Moved to legacy:

- `legacy/audit/audit_pandas_legacy.py`
- `legacy/audit/auditoria_profunda_legacy.py`
- `legacy/audit/imss_csv_profiler_legacy.py`
- `legacy/audit/imss_csv_profiler_export_legacy.py`
- `legacy/audit/filtrar_valores_legacy.py`
- `legacy/audit/validate_imss_output_experimental.py`

## Phase 2 Output Idempotency

`etl_imss.py` now writes each full run to a staging file derived from the configured output path. The final CSV is replaced with `os.replace` only after every configured period has been processed successfully.

If a period fails, the run aborts, the staging file is removed and the previous final output remains untouched.

This covers full-run idempotency. Incremental monthly upsert, partial-run recovery and append-safe period-level publishing are intentionally out of scope for this phase.

## Phase 2 Run Manifest

The ETL now writes a local JSON manifest under `reports/manifests/` for each run. The manifest records the run id, timestamps, status, config path and hash, configured URLs/periods, period-level results, final output path, final output SHA256 and file size.

After the final CSV is published, the ETL runs the official DuckDB audit against that final file and writes audit outputs under `reports/audits/<run_id>/`. The manifest records `audit_output_dir`, `audit_status`, `audit_files` and `audit_error`.

On ETL failure before publishing, the manifest is written with status `failed` and the previous final CSV is preserved. On audit failure after publishing, the final CSV remains available, but the manifest is marked `status: failed` and `audit_status: failed` because the run was not fully certified.

The manifest is intentionally local and file-based. Historical accumulation, period-level upsert, partial recovery and database loading remain out of scope.

## Environment And CI

The supported development runtime is Python 3.11. `requirements.txt` is intentionally minimal and contains only dependencies needed by the local engine, DuckDB audit and tests.

The repository includes a lightweight GitHub Actions workflow at `.github/workflows/tests.yml`. It runs `python -m pytest` on pushes and pull requests targeting `main`.

The workflow does not execute `etl_imss.py`, does not download IMSS files, does not run audits over large local CSV files and does not load data into any database.

## Insert-Only Concentrado

The current flow supports two explicit modes:

- `mes_consulta`: one configured period.
- `periodo_consulta`: an explicit ordered list of periods.

Both modes feed `data/processed/imss_concentrado.csv` with insert-only semantics. Existing periods are not overwritten. The period comparison unit is `periodo_informacion`, using row count and `period_fingerprint_hash`.

When `etl.mode` is active, legacy `etl.meses` must be empty. This is intentionally validated to avoid silently processing a different period list than the operator intended.

Light audit runs before insertion and checks required columns, expected period, forbidden `sector_economico_3`, VSM/UMA dimensions, `ptpd`, duplicate Phase 2 analytical keys, infinite SBC values and non-empty output.

## Out of Scope

PostgreSQL, API, dashboard, Docker, advanced CI/CD, cloud deployment, full-refresh orchestration, period-level upsert and full ETL execution in CI remain out of scope.
