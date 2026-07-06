-- Initial lightweight analytical views.
-- These views are intentionally simple and can be optimized later.

CREATE OR REPLACE VIEW imss.vw_period_control AS
SELECT
    periodo_informacion,
    status,
    row_count,
    period_fingerprint_hash,
    sum_asegurados,
    sum_no_trabajadores,
    sum_ta,
    sum_ta_sal,
    sum_masa_sal_ta,
    run_id,
    source_url,
    loaded_at,
    error_message
FROM imss.imss_period_control;

CREATE OR REPLACE VIEW imss.vw_empleo_mensual_entidad AS
SELECT
    periodo_informacion,
    cve_entidad,
    SUM(asegurados) AS asegurados,
    SUM(no_trabajadores) AS no_trabajadores,
    SUM(ta) AS ta,
    SUM(ta_sal) AS ta_sal,
    SUM(masa_sal_ta) AS masa_sal_ta,
    SUM(masa_sal_ta) / NULLIF(SUM(ta_sal), 0) AS sbc_total_calculado
FROM imss.imss_hechos_asegurados
GROUP BY periodo_informacion, cve_entidad;

CREATE OR REPLACE VIEW imss.vw_empleo_sector_1 AS
SELECT
    periodo_informacion,
    sector_economico_1,
    SUM(asegurados) AS asegurados,
    SUM(no_trabajadores) AS no_trabajadores,
    SUM(ta) AS ta,
    SUM(ta_sal) AS ta_sal,
    SUM(masa_sal_ta) AS masa_sal_ta,
    SUM(masa_sal_ta) / NULLIF(SUM(ta_sal), 0) AS sbc_total_calculado
FROM imss.imss_hechos_asegurados
GROUP BY periodo_informacion, sector_economico_1;

CREATE OR REPLACE VIEW imss.vw_empleo_sector_4 AS
SELECT
    periodo_informacion,
    sector_economico_1,
    sector_economico_2,
    sector_economico_4,
    SUM(asegurados) AS asegurados,
    SUM(no_trabajadores) AS no_trabajadores,
    SUM(ta) AS ta,
    SUM(ta_sal) AS ta_sal,
    SUM(masa_sal_ta) AS masa_sal_ta,
    SUM(masa_sal_ta) / NULLIF(SUM(ta_sal), 0) AS sbc_total_calculado
FROM imss.imss_hechos_asegurados
GROUP BY
    periodo_informacion,
    sector_economico_1,
    sector_economico_2,
    sector_economico_4;

CREATE OR REPLACE VIEW imss.vw_sbc_entidad_genero AS
SELECT
    periodo_informacion,
    cve_entidad,
    sexo,
    SUM(ta) AS ta,
    SUM(ta_sal) AS ta_sal,
    SUM(masa_sal_ta) AS masa_sal_ta,
    SUM(masa_sal_ta) / NULLIF(SUM(ta_sal), 0) AS sbc_total_calculado,
    SUM(masa_sal_tpu + masa_sal_tpc) / NULLIF(SUM(tpu_sal + tpc_sal), 0) AS sbc_permanentes_calculado,
    SUM(masa_sal_teu + masa_sal_tec) / NULLIF(SUM(teu_sal + tec_sal), 0) AS sbc_eventuales_calculado
FROM imss.imss_hechos_asegurados
GROUP BY periodo_informacion, cve_entidad, sexo;
