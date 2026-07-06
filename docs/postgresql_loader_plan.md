# PostgreSQL Loader Plan

## Estado De Esta Rama

Esta rama crea solo un skeleton tecnico para una futura integracion PostgreSQL.

No implementa carga masiva, no abre conexiones automaticamente, no lee el CSV concentrado grande y no modifica ninguna base de datos.

## Componentes Creados

- `src/imss_engine/postgres/config.py`: lectura segura de variables `IMSS_PG_*`.
- `src/imss_engine/postgres/connection.py`: helper futuro para construir conexion cuando exista driver.
- `src/imss_engine/postgres/loader.py`: contratos placeholder para el flujo insert-only.
- `scripts/run_postgres_loader.py`: CLI dry-run que imprime el plan y no toca PostgreSQL.
- `.env.example`: variables esperadas sin secretos reales.

## Variables De Entorno

```text
IMSS_PG_HOST
IMSS_PG_PORT
IMSS_PG_DATABASE
IMSS_PG_USER
IMSS_PG_PASSWORD
```

El skeleton puede importarse sin estas variables. Si faltan, el CLI dry-run solo reporta configuracion incompleta.

## Flujo Futuro Insert-Only

El loader futuro debe seguir este orden:

1. Validar `periodo_informacion`.
2. Verificar si el periodo ya existe en `imss.imss_period_control` y `imss.imss_hechos_asegurados`.
3. Preparar `imss.imss_staging_asegurados`.
4. Validar staging contra reglas IMSS vigentes.
5. Promover staging a `imss.imss_hechos_asegurados` solo si el periodo es nuevo y valido.
6. Registrar resultado en `imss.imss_period_control`.
7. Registrar manifest en `imss.imss_run_manifest`.

La version inicial debe conservar semantica insert-only. Periodos existentes deben resolverse como `already_exists` o conflicto, no sobrescribirse.

## Reglas De Negocio Que Debe Respetar

- No crear `sector_economico_3`.
- Conservar `sector_economico_1`, `sector_economico_2` y `sector_economico_4`.
- Separar `rango_ingreso_vsm` y `rango_ingreso_uma`.
- Incluir `ptpd`; si no existe historicamente, usar `no_disponible` o valor tecnico aprobado, nunca asumir `0`.
- No calcular SBC con `ta`.
- Calcular SBC con denominadores `*_sal`.
- No usar `timestamp` en la llave analitica.

## Fuera De Alcance

Esta rama no implementa:

- carga masiva desde `data/processed/imss_concentrado.csv`;
- lectura del CSV grande;
- `upsert_period`;
- `full_refresh`;
- sobrescritura de periodos;
- API;
- dashboard;
- Docker;
- cloud;
- Supabase;
- BigQuery.

## Comando Dry-Run

```powershell
python scripts/run_postgres_loader.py --period 2026-01-31
```

El comando imprime el plan de pasos futuro, no abre conexion y no lee archivos de datos.
