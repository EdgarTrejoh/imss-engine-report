# Source CSV Housekeeping Plan

## Estado

Este documento describe un diseno propuesto para housekeeping auditable de `data/processed/imss_concentrado.csv`.

El housekeeping todavia no esta implementado. No existe aun un comando operativo para limpiar, reescribir o archivar el CSV fuente. Este plan no autoriza cambios destructivos sobre el archivo.

## Proposito

`data/processed/imss_concentrado.csv` es un archivo operativo grande. El proyecto busca recabar y procesar hasta 10 anos de informacion IMSS, por lo que mantener periodos ya cerrados dentro del CSV operativo puede volver costoso el manejo local.

El housekeeping auditable debe servir para:

- reducir el tamano operativo de `imss_concentrado.csv`;
- evitar reprocesar periodos ya cargados y promovidos;
- preparar el archivo para seguir incorporando mas periodos;
- mantener trazabilidad completa del archivo fuente y del archivo resultante.

## Principio Central

El CSV fuente no debe modificarse destructivamente.

Antes de generar un nuevo concentrado operativo, debe conservarse evidencia del archivo original o una copia archivada. Ninguna eliminacion logica de periodos debe hacerse sin manifest.

El housekeeping no debe mezclarse con carga a staging ni con promocion a final. Su objetivo es administrar el CSV operativo despues de que la evidencia en PostgreSQL ya fue validada.

## Contexto De Capas

`imss.imss_staging_asegurados` es acumulativa por periodo y funciona como landing normalizado y evidencia tecnica de carga.

`imss.imss_hechos_asegurados` es acumulativa por periodo y funciona como capa final/curada para consulta analitica.

`data/processed/imss_concentrado.csv` es una capa operativa local. Puede reducirse en una etapa posterior, pero solo con evidencia suficiente de que los periodos retirados ya quedaron preservados y validados en PostgreSQL.

## Flujo Objetivo Propuesto

Este flujo es diseno, no implementacion actual:

1. Detectar periodos presentes en `imss_concentrado.csv`.
2. Consultar periodos existentes en `imss.imss_staging_asegurados`.
3. Consultar periodos existentes en `imss.imss_hechos_asegurados`.
4. Identificar periodos elegibles para exclusion del CSV operativo.
5. Excluir solo periodos que ya esten cargados en staging y promovidos a final.
6. Generar copia archivada del CSV original o snapshot previo.
7. Generar nuevo `imss_concentrado.csv` operativo sin los periodos excluidos.
8. Generar manifest de housekeeping.
9. Validar conteos antes y despues.
10. Validar hashes.
11. Conservar el manifest junto con la evidencia.
12. No tocar PostgreSQL durante este housekeeping, salvo lecturas de control cuando exista implementacion formal.

## Criterios Para Excluir Un Periodo

Un periodo solo puede excluirse del CSV operativo si cumple todos los criterios:

- existe en `imss.imss_staging_asegurados`;
- existe en `imss.imss_hechos_asegurados`;
- los conteos staging/final cuadran;
- las metricas principales staging/final cuadran;
- la promocion final fue validada;
- no existe conflicto en `imss.imss_period_control`.

## Criterios Para No Excluir Un Periodo

No debe excluirse un periodo si:

- solo esta en el CSV;
- esta en staging pero no en final;
- esta en final pero no tiene evidencia consistente en staging;
- hay conteos distintos;
- hay agregados distintos;
- existe error o estado ambiguo;
- no hay manifest previo suficiente.

## Manifest Esperado

El manifest de housekeeping deberia ser JSON y contener, como minimo:

```json
{
  "housekeeping_run_id": null,
  "created_at": null,
  "source_csv_path": null,
  "source_csv_size_bytes": null,
  "source_csv_hash": null,
  "archive_csv_path": null,
  "archive_csv_hash": null,
  "output_csv_path": null,
  "output_csv_size_bytes": null,
  "output_csv_hash": null,
  "periods_detected": [],
  "periods_excluded": [],
  "periods_retained": [],
  "rows_input": null,
  "rows_excluded": null,
  "rows_output": null,
  "validation_status": null,
  "postgres_checks": [],
  "notes": null
}
```

Los campos sin dato verificable deben permanecer en `null` o listas vacias. No deben inventarse hashes, conteos ni estados.

## Ejemplo Conceptual: `2026-01-31`

El periodo `2026-01-31` ya fue cargado y promovido segun la evidencia operativa disponible. Estos valores sirven como ejemplo de evidencia que un housekeeping futuro tendria que verificar antes de retirar el periodo del CSV operativo:

```text
periodo procesado: 2026-01-31
staging: 4,731,705
final: 4,731,705
ptpd no_disponible: 4,731,705
ptpd zero: 0
sum_ta: 22,508,972
sum_ta_sal: 22,443,851
sum_masa_sal_ta: 14,876,447,189.29
```

Estos valores no significan que el housekeeping este implementado. Solo documentan el tipo de evidencia que debe conservarse y validarse.

## Riesgos Que Debe Evitar

- Borrar evidencia fuente sin respaldo.
- Quitar periodos incompletos.
- Reprocesar periodos ya cerrados.
- Mezclar housekeeping con carga o promocion.
- Modificar PostgreSQL desde un proceso cuyo objetivo sea limpiar el CSV operativo.
- Sobrescribir `imss_concentrado.csv` sin snapshot o manifest.

## Hardening Relacionado

Este plan depende de hardening operativo adicional:

- validacion post-promocion reusable;
- manifest final de corrida;
- estados de periodo;
- hashes;
- checks de conteo;
- guardrails para impedir exclusiones ambiguas.

## Fuera De Alcance Actual

Este plan no implementa:

- comando de housekeeping;
- reescritura de `imss_concentrado.csv`;
- archivado real de CSV fuente;
- modificaciones en PostgreSQL;
- cambios en staging;
- cambios en final;
- `upsert_period`;
- `full_refresh`;
- API;
- dashboard;
- Docker;
- cloud.
