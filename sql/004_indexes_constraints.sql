-- Minimal indexes and integrity constraints for IMSS insert-only v1.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_imss_hechos_ptpd'
          AND conrelid = 'imss.imss_hechos_asegurados'::regclass
    ) THEN
        ALTER TABLE imss.imss_hechos_asegurados
            ADD CONSTRAINT chk_imss_hechos_ptpd
            CHECK (ptpd IN ('0', '1', 'no_disponible', 'no_aplica'));
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_imss_hechos_asegurados_analytic_key'
          AND conrelid = 'imss.imss_hechos_asegurados'::regclass
    ) THEN
        ALTER TABLE imss.imss_hechos_asegurados
            ADD CONSTRAINT uq_imss_hechos_asegurados_analytic_key
            UNIQUE (
                periodo_informacion,
                cve_delegacion,
                cve_subdelegacion,
                cve_entidad,
                cve_municipio,
                "tamaño_patron",
                sexo,
                rango_edad,
                rango_ingreso_vsm,
                rango_ingreso_uma,
                sector_economico_1,
                sector_economico_2,
                sector_economico_4,
                ptpd
            );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_imss_period_control_status'
          AND conrelid = 'imss.imss_period_control'::regclass
    ) THEN
        ALTER TABLE imss.imss_period_control
            ADD CONSTRAINT chk_imss_period_control_status
            CHECK (
                status IN (
                    'pending',
                    'loaded',
                    'already_exists',
                    'conflict_existing_period_row_count',
                    'conflict_existing_period_hash',
                    'failed_validation',
                    'failed_load'
                )
            );
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_imss_hechos_periodo
    ON imss.imss_hechos_asegurados (periodo_informacion);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_entidad
    ON imss.imss_hechos_asegurados (cve_entidad);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_municipio
    ON imss.imss_hechos_asegurados (cve_municipio);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_sector_1
    ON imss.imss_hechos_asegurados (sector_economico_1);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_sector_2
    ON imss.imss_hechos_asegurados (sector_economico_2);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_sector_4
    ON imss.imss_hechos_asegurados (sector_economico_4);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_sexo
    ON imss.imss_hechos_asegurados (sexo);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_rango_edad
    ON imss.imss_hechos_asegurados (rango_edad);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_rango_ingreso_uma
    ON imss.imss_hechos_asegurados (rango_ingreso_uma);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_ptpd
    ON imss.imss_hechos_asegurados (ptpd);

CREATE INDEX IF NOT EXISTS idx_imss_hechos_run_id
    ON imss.imss_hechos_asegurados (run_id);

CREATE INDEX IF NOT EXISTS idx_imss_staging_run_id
    ON imss.imss_staging_asegurados (run_id);

CREATE INDEX IF NOT EXISTS idx_imss_period_control_status
    ON imss.imss_period_control (status);

CREATE INDEX IF NOT EXISTS idx_imss_run_manifest_status
    ON imss.imss_run_manifest (status);
