# IMSS Business Rules - Phase 2

This document records the business rules implemented in Phase 2. It is derived from the approved project instructions for this phase. Official source methodology files were searched for locally but were not found in the repository; unresolved definitions are marked as pending.

## Implemented Rules

1. The asegurados source is an aggregated cube, not an individual nominative table.
2. `asegurados`, `no_trabajadores` and `ta` are preserved as distinct source metrics.
3. `ta` is not overwritten by `tpu + tpc + teu + tec`; the difference is exposed as `diff_ta_componentes`.
4. `asegurados` is not recalculated from `ta + no_trabajadores`; the difference is exposed as `diff_asegurados_ta_no_trabajadores`.
5. Worker-position derived metrics:
   - `puestos_permanentes = tpu + tpc`
   - `puestos_eventuales = teu + tec`
   - `puestos_urbanos = tpu + teu`
   - `puestos_campo = tpc + tec`
6. Salary-mass derived metrics:
   - `masa_sal_permanentes = masa_sal_tpu + masa_sal_tpc`
   - `masa_sal_eventuales = masa_sal_teu + masa_sal_tec`
   - `masa_sal_urbanos = masa_sal_tpu + masa_sal_teu`
   - `masa_sal_campo = masa_sal_tpc + masa_sal_tec`
7. `masa_sal_ta` is retained as the official total salary mass metric; component differences are exposed as `diff_masa_sal_componentes`.
8. SBC uses only `*_sal` denominators:
   - `sbc_total = masa_sal_ta / ta_sal`
   - `sbc_permanente_urbano = masa_sal_tpu / tpu_sal`
   - `sbc_permanente_campo = masa_sal_tpc / tpc_sal`
   - `sbc_eventual_urbano = masa_sal_teu / teu_sal`
   - `sbc_eventual_campo = masa_sal_tec / tec_sal`
   - `sbc_permanentes = (masa_sal_tpu + masa_sal_tpc) / (tpu_sal + tpc_sal)`
   - `sbc_eventuales = (masa_sal_teu + masa_sal_tec) / (teu_sal + tec_sal)`
   - `sbc_urbanos = (masa_sal_tpu + masa_sal_teu) / (tpu_sal + teu_sal)`
   - `sbc_campo = (masa_sal_tpc + masa_sal_tec) / (tpc_sal + tec_sal)`
9. Zero, null or missing SBC denominators produce null/NaN, not infinity or artificial zero.
10. `rango_salarial` and `rango_uma` are not merged:
    - `rango_ingreso_vsm = rango_salarial`
    - `rango_ingreso_uma = rango_uma`
11. `sector_economico_3` is not created. The implemented sector layout is `sector_economico_1`, `sector_economico_2`, `sector_economico_4`.
12. Sector codes are read and preserved as strings.
13. `ptpd` is preserved when present. When absent, it is created as null, not zero.
14. `ND`, `NA` and null-like source values are not automatic errors or blanket replacements.
15. `timestamp` is allowed as run metadata but is not part of the analytical aggregation key.

## Pending Official Validation

- Official data dictionary column descriptions.
- Official glossary definitions.
- Official FAQ interpretation for edge cases.
- Official catalogs for sector, income range, entity, sex and age.
- Any documented rule for converting or comparing VSM and UMA ranges.
- Any documented correspondence between IMSS sectors and external classifications.

## Audit Controls

The Phase 2 DuckDB audit is an internal consistency control for generated CSV outputs. It validates layout, expected metrics, derived arithmetic, SBC denominators, duplicate analytical keys and `ptpd` distribution.

Validation against official IMSS bulletins is a separate external control. It can detect high-level deviations, but it does not replace the repository's methodology, schema and arithmetic validations.

## Output Publishing

The historical ETL publishes its final CSV at the end of a complete successful run. During execution it writes to a temporary staging output and replaces the configured final output atomically only after all configured periods finish.

This is run-level idempotency, not monthly upsert behavior.

## Run Traceability

The ETL writes a JSON manifest for each local run in `reports/manifests/`. The manifest records technical lineage for the configured source URLs, periods, configuration hash, output file hash, period results and any failure message.

This manifest supports auditability of a local run. It does not change IMSS business rules and does not implement historical accumulation, incremental upsert or database persistence.

## Insert-Only Concentrado Control

`data/processed/imss_concentrado.csv` is a local publication target for validated periods. It is insert-only in this phase: existing periods are not overwritten.

Duplicate and conflict detection uses `periodo_informacion`, row count and `period_fingerprint_hash`. This control does not change any IMSS metric formula or analytical key.
