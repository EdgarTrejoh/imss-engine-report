# PR #42 — Historical batch execute con limite de periodos

## Objetivo

Agregar ejecucion batch controlada para rangos historicos IMSS, reutilizando el orquestador single-period existente.

El PR #42 no implementa una nueva logica de carga. Para cada periodo elegible delega en:

```text
execute_single_period_pipeline(...)
```

## Regla operativa central

La ejecucion batch queda limitada a un maximo de 3 periodos por corrida mediante `--max-periods`.

El batch:

1. ejecuta primero el planner historico;
2. selecciona solo periodos elegibles;
3. excluye periodos ya cargados o bloqueados;
4. ejecuta cada periodo seleccionado con el pipeline single-period;
5. detiene la corrida ante la primera falla.

## Periodos elegibles

Solo se ejecutan periodos con:

- `download_process_load`
- `validate_process_load`

No se ejecutan:

- `skip_existing`
- `blocked_existing_pending`
- `blocked_existing_non_loaded`
- `blocked_partial_final`
- `blocked_inconsistent_state`

## Comando esperado

```powershell
.\.venv\Scripts\python.exe .\scripts\run_imss_historical_batch.py `
  --start-period 2016-08-31 `
  --end-period 2016-12-31 `
  --execute `
  --max-periods 3 `
  --stop-on-failure
```

## Exclusiones

Este PR no:

- reconstruye `data/processed/imss_concentrado.csv`;
- usa `publish_insert.py`;
- usa `publish_plan.py`;
- usa `raw_compare.py` como paso central;
- implementa Supabase;
- implementa housekeeping automatico;
- ejecuta periodos bloqueados;
- ejecuta mas de 3 periodos por corrida.

## Manifest

La corrida genera un manifest consolidado en:

```text
outputs/pipeline/historical_batch_execute_<run_id>_<start_period>_<end_period>.json
```

El manifest registra:

- plan inicial;
- periodos elegibles;
- periodos seleccionados;
- periodos no seleccionados por limite;
- resultado por periodo;
- conteos de exitos/fallas;
- flags de no escritura al concentrado;
- flags de uso de PostgreSQL.
