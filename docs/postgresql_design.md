# PostgreSQL Design

## Objetivo

PostgreSQL sera la capa local maestra para conservar el historico analitico del motor IMSS. El CSV concentrado sigue siendo util como puente operativo, pero no debe ser el historico maestro definitivo: es pesado, dificil de consultar con control transaccional y limitado para validar periodos, manifests y linaje.

Esta primera version crea solo el diseno SQL. No implementa loader Python ni conexion a PostgreSQL.

## Alcance V1 Insert-Only

La version inicial es insert-only:

- Periodos nuevos se insertan una sola vez.
- Periodos existentes se detectan por la llave analitica y por control de periodo.
- No hay `upsert_period`.
- No hay `full_refresh`.
- No hay sobrescritura de periodos aprobada.

El objetivo es preparar una carga futura desde `data/processed/imss_concentrado.csv` o desde salidas controladas del ETL hacia PostgreSQL.

## Archivos SQL

- `sql/001_schema.sql`: crea el esquema `imss`.
- `sql/002_tables_core.sql`: crea tablas core, staging, control de periodos y manifests.
- `sql/003_tables_catalogs.sql`: crea estructuras vacias de catalogos.
- `sql/004_indexes_constraints.sql`: crea constraints e indices minimos.
- `sql/005_views_light_layer.sql`: crea vistas ligeras iniciales.

## Tablas Core

### `imss.imss_hechos_asegurados`

Tabla historica final. Conserva dimensiones, metricas, datos derivados y metadatos de linaje.

Es la capa curada para consulta analitica y debe operar como historico acumulativo por periodo. La promocion desde staging debe ser insert-only: si un periodo ya existe en final, no se debe promover otra vez de forma automatica.

Las dimensiones de la llave analitica son `NOT NULL`. Para campos historicamente no disponibles se deben usar valores tecnicos controlados como:

- `no_disponible`
- `no_aplica`

### `imss.imss_staging_asegurados`

Tabla de staging. Tiene columnas equivalentes a la final y agrega:

- `staging_id`
- `run_id`
- `staging_loaded_at`

La staging permite mayor flexibilidad para validar antes de promover a la tabla final.

Operativamente, staging funciona como landing normalizado y evidencia tecnica de carga. Debe conservarse como tabla acumulativa por periodo para conciliacion, auditoria y reproceso controlado. No debe borrarse automaticamente despues de promover datos a final.

Si un periodo ya existe en staging, la carga normal debe rechazarse. Cualquier reproceso debe tratarse como flujo explicito de correccion y no como overwrite automatico.

El CSV fuente `data/processed/imss_concentrado.csv` no debe limpiarse ni modificarse como parte de staging ni de la promocion a final. La depuracion del CSV fuente corresponde a una etapa posterior de housekeeping auditable con archivo original o archivado, archivo resultante, conteos, periodos conservados/excluidos, hashes y manifest.

### `imss.imss_period_control`

Tabla de control por periodo. Registra estado, conteo de filas, fingerprint, sumas principales, `run_id`, fuente y error.

Estados contemplados:

- `pending`
- `loaded`
- `already_exists`
- `conflict_existing_period_row_count`
- `conflict_existing_period_hash`
- `failed_validation`
- `failed_load`

### `imss.imss_run_manifest`

Tabla para conservar manifests de corrida en `JSONB`.

Esto permite mantener dentro de PostgreSQL la misma evidencia que hoy existe como JSON local: `run_id`, modo, timestamps, estado, hash de configuracion y manifest completo.

## Llave Analitica

La llave unica de idempotencia de `imss.imss_hechos_asegurados` es:

```text
periodo_informacion
cve_delegacion
cve_subdelegacion
cve_entidad
cve_municipio
tamaño_patron
sexo
rango_edad
rango_ingreso_vsm
rango_ingreso_uma
sector_economico_1
sector_economico_2
sector_economico_4
ptpd
```

`timestamp` no forma parte de la llave analitica.

## Sectores IMSS

No existe `sector_economico_3` en este diseno.

Se conservan unicamente:

- `sector_economico_1`
- `sector_economico_2`
- `sector_economico_4`

Estos sectores no se documentan como SCIAN.

## PTPD

`ptpd` es dimension obligatoria en la tabla final. Cuando la fuente historica no tenga la columna, el loader futuro debe usar un valor tecnico controlado, preferentemente `no_disponible`, no `0`.

El catalogo `imss.cat_ptpd` contempla:

- `0`
- `1`
- `no_disponible`
- `no_aplica`

## VSM vs UMA

`rango_ingreso_vsm` y `rango_ingreso_uma` permanecen separados.

No se debe rellenar UMA a partir de VSM ni fusionar ambos campos. Sus catalogos tambien estan separados:

- `imss.cat_rango_ingreso_vsm`
- `imss.cat_rango_ingreso_uma`

## SBC

El SBC no debe calcularse como `masa_sal_ta / ta`.

Las vistas calculan SBC con denominadores `*_sal`, por ejemplo:

```text
SUM(masa_sal_ta) / NULLIF(SUM(ta_sal), 0)
```

## Vistas Ligeras

La capa ligera inicial incluye:

- `imss.vw_period_control`
- `imss.vw_empleo_mensual_entidad`
- `imss.vw_empleo_sector_1`
- `imss.vw_empleo_sector_4`
- `imss.vw_sbc_entidad_genero`

No son vistas optimizadas. Solo exponen consultas iniciales legibles para revisar periodos, empleo y SBC.

## Fuera De Alcance

Esta rama no implementa:

- loader Python;
- conexion a PostgreSQL;
- `.env` real;
- carga de catalogos;
- `upsert_period`;
- `full_refresh`;
- API;
- dashboard;
- Docker;
- Supabase;
- BigQuery;
- nube;
- visualizacion.
