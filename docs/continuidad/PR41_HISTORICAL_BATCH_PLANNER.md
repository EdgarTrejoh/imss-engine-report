# PR #41 — Historical batch planner dry-run

## Objetivo

Agregar una planeacion historica en modo dry-run para el flujo IMSS basado en periodos mensuales.

El planner permite revisar un rango de periodos antes de ejecutar cualquier carga real:

```text
rango de cierres de mes
-> raw esperado por periodo
-> estado PostgreSQL por periodo
-> accion recomendada conservadora
-> manifest local de planificacion
```

## Alcance

El PR #41 solo planea. No ejecuta cargas historicas.

El planner:

- genera periodos mensuales de cierre de mes;
- verifica si existe raw local en `data/raw/imss/asegurados/YYYY/asg-YYYY-MM-DD.csv`;
- consulta PostgreSQL con `check_existing_period`;
- clasifica cada periodo con una accion recomendada;
- genera manifest local en `outputs/pipeline/`.

## Acciones recomendadas

| Accion | Uso |
|---|---|
| `skip_existing` | El periodo ya esta cargado en PostgreSQL con `period_control.status = loaded`. |
| `download_process_load` | No existe raw local y PostgreSQL no tiene el periodo. |
| `validate_process_load` | Existe raw local y PostgreSQL no tiene el periodo. |
| `blocked_existing_pending` | Existe `period_control` en `pending`. |
| `blocked_existing_non_loaded` | Existe `period_control` con status distinto de `loaded` o `pending`. |
| `blocked_partial_final` | Hay filas en final sin periodo cargado formalmente. |
| `blocked_inconsistent_state` | Estado ambiguo o contradictorio. |

## Exclusiones

Este PR no:

- descarga raw;
- procesa raw;
- carga staging;
- promueve a final;
- modifica `period_control`;
- modifica `run_manifest`;
- toca `data/processed/imss_concentrado.csv`;
- usa `publish_insert.py`;
- usa `publish_plan.py`;
- usa `raw_compare.py`;
- ejecuta Supabase;
- implementa housekeeping.

## Comando esperado

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --start-period 2016-08-31 `
  --end-period 2016-12-31 `
  --dry-run
```

`--execute` queda explicitamente fuera de alcance para PR #41.
