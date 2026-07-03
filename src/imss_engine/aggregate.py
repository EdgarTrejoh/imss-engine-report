"""Aggregation layer for IMSS data."""

from __future__ import annotations

import pandas as pd

from .metrics import add_validation_differences, calculate_sbc_metrics
from .normalize import normalize_dimensions
from .schema import CRITICAL_METRIC_COLUMNS, validate_required_columns
from .transform import (
    add_salary_mass_metrics,
    add_worker_metrics,
    convert_numeric_columns,
)


GROUP_COLUMNS: tuple[str, ...] = (
    "periodo_informacion",
    "cve_delegacion",
    "cve_subdelegacion",
    "cve_entidad",
    "cve_municipio",
    "tamaño_patron",
    "sexo",
    "rango_edad",
    "rango_ingreso_vsm",
    "rango_ingreso_uma",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "ptpd",
)

DERIVED_SUM_COLUMNS: tuple[str, ...] = (
    "puestos_permanentes",
    "puestos_eventuales",
    "puestos_urbanos",
    "puestos_campo",
    "masa_sal_permanentes",
    "masa_sal_eventuales",
    "masa_sal_urbanos",
    "masa_sal_campo",
)


def get_group_columns() -> list[str]:
    """Return the approved analytical aggregation key without timestamp."""
    return list(GROUP_COLUMNS)


def aggregate_imss_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize, transform and aggregate one IMSS chunk without side effects."""
    validation = validate_required_columns(df)
    if not validation["valid"]:
        missing = ", ".join(validation["missing_required_columns"])
        raise ValueError(f"Missing required IMSS metric columns: {missing}")

    out = normalize_dimensions(df)
    out = convert_numeric_columns(out)
    out = add_worker_metrics(out)
    out = add_salary_mass_metrics(out)

    sum_columns = list(CRITICAL_METRIC_COLUMNS) + list(DERIVED_SUM_COLUMNS)
    aggregated = (
        out.groupby(get_group_columns(), as_index=False, dropna=False)[sum_columns]
        .sum(min_count=1)
    )
    aggregated = calculate_sbc_metrics(aggregated)
    aggregated = add_validation_differences(aggregated)
    return aggregated
