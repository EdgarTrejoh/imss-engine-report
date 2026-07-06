-- Empty catalog structures for the IMSS analytical model.
-- Catalog loading is intentionally out of scope for this branch.

CREATE TABLE IF NOT EXISTS imss.cat_genero (
    sexo TEXT PRIMARY KEY,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS imss.cat_ptpd (
    ptpd TEXT PRIMARY KEY,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_cat_ptpd_codigo
        CHECK (ptpd IN ('0', '1', 'no_disponible', 'no_aplica'))
);

CREATE TABLE IF NOT EXISTS imss.cat_rango_edad (
    rango_edad TEXT PRIMARY KEY,
    descripcion TEXT,
    orden INTEGER,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS imss.cat_rango_ingreso_vsm (
    rango_ingreso_vsm TEXT PRIMARY KEY,
    descripcion TEXT,
    orden INTEGER,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS imss.cat_rango_ingreso_uma (
    rango_ingreso_uma TEXT PRIMARY KEY,
    descripcion TEXT,
    orden INTEGER,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS imss.cat_sector_economico_1 (
    sector_economico_1 TEXT PRIMARY KEY,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS imss.cat_sector_economico_2 (
    sector_economico_2 TEXT PRIMARY KEY,
    sector_economico_1 TEXT,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS imss.cat_sector_economico_4 (
    sector_economico_4 TEXT PRIMARY KEY,
    sector_economico_2 TEXT,
    sector_economico_1 TEXT,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS imss.cat_entidad_municipio (
    cve_entidad TEXT NOT NULL,
    cve_municipio TEXT NOT NULL,
    entidad TEXT,
    municipio TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (cve_entidad, cve_municipio)
);
