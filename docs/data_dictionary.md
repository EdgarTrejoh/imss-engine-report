# Data Dictionary

This document is a derived working dictionary for the local IMSS engine. It is based on the business rules approved for Phase 2 and the repository fixtures. Official methodology source files such as `diccionario_de_datos_imss.csv`, `glosario_datos_abiertos_asegurados.pdf`, `preguntas_frecuentes_datos_abiertos_asegurados.pdf` and official catalog files were not found locally in this repository during this pass. Any rule not listed here remains pending official-source validation.

## Nature of the Source

The IMSS asegurados file is treated as an aggregated cube. Each row represents a combination of dimensions with aggregated metrics. Rows must not be treated as individual workers or unique people.

## Dimensions

| Field | Status | Notes |
| --- | --- | --- |
| `periodo_informacion` | Required analytically | Extracted from source URL in the historical ETL. |
| `cve_delegacion` | Dimension | Preserved when present. |
| `cve_subdelegacion` | Dimension | Preserved when present. |
| `cve_entidad` | Dimension | Preserved when present. |
| `cve_municipio` | Dimension | Preserved when present. |
| `tamaño_patron` | Dimension | `NA` is not automatically interpreted as no employment. |
| `sexo` | Dimension | Preserved as source category. |
| `rango_edad` | Dimension | `ND` is a valid category, not an automatic error. |
| `rango_salarial` | Source income range | VSM / salario minimo range. Not renamed to UMA. |
| `rango_uma` | Source income range | UMA range where available. Not backfilled from VSM. |
| `rango_ingreso_vsm` | Derived dimension | Copy of `rango_salarial`; null if unavailable. |
| `rango_ingreso_uma` | Derived dimension | Copy of `rango_uma`; null if unavailable. |
| `sector_economico_1` | Dimension | Preserved as string. |
| `sector_economico_2` | Dimension | Preserved as string. |
| `sector_economico_4` | Dimension | Preserved as string. |
| `ptpd` | Dimension | Platform digital flag where available; null when absent historically. |

`sector_economico_3` is intentionally not part of the documented layout for this phase and must not be created.

## Analytical Key

The Phase 2 analytical key used for duplicate validation is:

1. `periodo_informacion`
2. `cve_delegacion`
3. `cve_subdelegacion`
4. `cve_entidad`
5. `cve_municipio`
6. `tamaño_patron`
7. `sexo`
8. `rango_edad`
9. `rango_ingreso_vsm`
10. `rango_ingreso_uma`
11. `sector_economico_1`
12. `sector_economico_2`
13. `sector_economico_4`
14. `ptpd`

`timestamp` is not part of the analytical key.

## Concentrado Control Fields

The insert-only concentrado workflow records period-level control metadata in the manifest, not as required analytical columns in the CSV:

| Field | Location | Notes |
| --- | --- | --- |
| `period_fingerprint_hash` | Manifest period result | SHA256 over a stable period summary. |
| `rows_loaded` | Manifest period result | Rows inserted into `data/processed/imss_concentrado.csv`. |
| `rows_existing_in_concentrado` | Manifest period result | Existing rows for the same `periodo_informacion`. |
| `status` | Manifest period result | One of the official insert-only period statuses. |

## Core Metrics

| Field | Status | Notes |
| --- | --- | --- |
| `asegurados` | Source metric | Distinct from `ta`; not recalculated. |
| `no_trabajadores` | Source metric | Asegurados without associated employment. |
| `ta` | Source metric | Puestos de trabajo afiliados / empleos asegurados. |
| `ta_sal` | Source denominator | Denominator for total SBC. |
| `tpu`, `tpc`, `teu`, `tec` | Source metrics | Position components by permanence and urban/campo. |
| `tpu_sal`, `tpc_sal`, `teu_sal`, `tec_sal` | Source denominators | SBC denominators by component. |
| `masa_sal_ta` | Official salary mass metric | Do not recalculate or replace. |
| `masa_sal_tpu`, `masa_sal_tpc`, `masa_sal_teu`, `masa_sal_tec` | Salary mass components | Used for derived salary mass and SBC. |

## Derived Metrics

| Field | Formula |
| --- | --- |
| `puestos_permanentes` | `tpu + tpc` |
| `puestos_eventuales` | `teu + tec` |
| `puestos_urbanos` | `tpu + teu` |
| `puestos_campo` | `tpc + tec` |
| `masa_sal_permanentes` | `masa_sal_tpu + masa_sal_tpc` |
| `masa_sal_eventuales` | `masa_sal_teu + masa_sal_tec` |
| `masa_sal_urbanos` | `masa_sal_tpu + masa_sal_teu` |
| `masa_sal_campo` | `masa_sal_tpc + masa_sal_tec` |

## SBC Metrics

SBC must use `*_sal` denominators. If the denominator is zero or missing, the result is null/NaN.

| Field | Formula |
| --- | --- |
| `sbc_total` | `masa_sal_ta / ta_sal` |
| `sbc_permanente_urbano` | `masa_sal_tpu / tpu_sal` |
| `sbc_permanente_campo` | `masa_sal_tpc / tpc_sal` |
| `sbc_eventual_urbano` | `masa_sal_teu / teu_sal` |
| `sbc_eventual_campo` | `masa_sal_tec / tec_sal` |
| `sbc_permanentes` | `(masa_sal_tpu + masa_sal_tpc) / (tpu_sal + tpc_sal)` |
| `sbc_eventuales` | `(masa_sal_teu + masa_sal_tec) / (teu_sal + tec_sal)` |
| `sbc_urbanos` | `(masa_sal_tpu + masa_sal_teu) / (tpu_sal + teu_sal)` |
| `sbc_campo` | `(masa_sal_tpc + masa_sal_tec) / (tpc_sal + tec_sal)` |
