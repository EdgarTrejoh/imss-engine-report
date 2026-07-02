# Data Dictionary

Initial working notes for the IMSS engine.

| Field | Current status | Notes |
| --- | --- | --- |
| `periodo_informacion` | Used | Period extracted from source file URL in the historical ETL. |
| `cve_entidad` | Used | Entity dimension. |
| `sexo` | Used | Sex dimension. |
| `rango_edad` | Used | Age range dimension. |
| `rango_uma` | Used | Normalized from historical `rango_salarial` when needed. |
| `sector_economico_1` | Used | Current aggregation sector dimension. |
| `sector_economico_2` | Pending | Must be preserved in future business model. |
| `sector_economico_3` | Pending | Must be preserved in future business model. |
| `sector_economico_4` | Pending | Must be preserved in future business model. |
| `total_asegurados` | Derived | Sum of `ta`. |
| `masa_salarial_total` | Derived | Sum of `masa_sal_ta`. |
| `trabajadores_permanentes` | Derived | `tpu + tpc`. |
| `trabajadores_eventuales` | Derived | `teu + tec`. |

This dictionary is incomplete and should be validated against official IMSS layouts before being used as a contract.
