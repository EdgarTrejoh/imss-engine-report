# Incidente de calidad dimensional — enero de 2025

## Resumen ejecutivo

La carga original de `2025-01-31` introdujo representaciones decimales en dos
dimensiones territoriales que conceptualmente son códigos enteros. El incidente
fue causado por inferencia independiente de tipos entre chunks de pandas, no
por el archivo raw ni por DuckDB.

Las métricas y el número de registros se conservaron. La afectación es
dimensional: parte de CDMX quedó identificada como `9.0` y otra como `9`,
fragmentando lógicamente la misma entidad.

## Periodo y corrida afectados

```text
Periodo: 2025-01-31
Run ID original: historical_batch_20260716T183039Z_3855c434_2025-01-31
```

## Causa raíz

La lectura raw utilizaba `pandas.read_csv()` sin tipos explícitos para todas las
dimensiones. pandas infiere el tipo de cada chunk de forma independiente.

El chunk con una única fila territorial incompleta fue inferido como `float64`
para `cve_entidad` y `cve_subdelegacion`. Los códigos enteros válidos del mismo
chunk se serializaron posteriormente como texto decimal:

```text
9  → 9.0
54 → 54.0
```

DuckDB recibió agregados parciales ya alterados; no originó la conversión.

## Evidencia

- 243,035 filas quedaron afectadas.
- Esas filas presentaron `cve_entidad = '9.0'`.
- Las mismas filas presentaron `cve_subdelegacion` con sufijo `.0`.
- El raw contiene `cve_entidad = '9'` y no contiene `9.0`.
- En el raw, `cve_entidad = '9'` aparece 497,096 veces.
- Las subdelegaciones raw incluyen `1`, `6`, `11`, `16`, `54`, `56`, `57` y
  `58`, siempre como códigos enteros.
- Existe una sola fila raw con `cve_entidad` vacía.
- Febrero y marzo de 2025 no presentan la anomalía.

## Impacto

El incidente fragmentó lógicamente CDMX entre `9` y `9.0`. Consultas,
agrupaciones o joins territoriales podían tratar ambas representaciones como
entidades distintas.

No se perdieron registros. Las métricas enteras se conservaron exactamente y
las masas salariales permanecieron dentro de la tolerancia de punto flotante
aprobada. La afectación fue dimensional, no cuantitativa.

## Corrección

Se definió `RAW_DIMENSION_DTYPES` para leer como `string` las dimensiones raw:

```text
cve_delegacion, cve_subdelegacion, cve_entidad, cve_municipio,
sector_economico_1, sector_economico_2, sector_economico_4,
tamaño_patron, sexo, rango_edad, rango_salarial, rango_uma, ptpd
```

Las métricas conservan su tratamiento numérico anterior. No se convirtió todo
el archivo a texto.

También se agregó una normalización defensiva limitada a columnas aprobadas de
códigos enteros:

```text
^([0-9]+)\.0$ → \1
```

La regla no se aplica a texto libre ni a métricas. Los valores normalizados por
columna quedan registrados en el manifiesto.

Enero fue reprocesado localmente con DuckDB, chunks de 100,000 filas, encoding
`utf-8-sig`, memoria limitada a 1 GB y dos hilos. La suite terminó con:

```text
205 passed
0 failed
```

## Validación corregida

```text
Run ID corregido:                     20260716T202019Z_7cfb513a
Filas de salida:                      4,643,036
cve_entidad terminada en .0:                  0
cve_subdelegacion terminada en .0:            0
cve_entidad = '9':                      497,096
Entidades válidas distintas:                 32
Entidad vacía/no_disponible:                   1
Duplicados por llave analítica:                0
```

La normalización defensiva reportó cero reparaciones para el archivo real. Los
tipos explícitos evitaron la alteración durante la lectura.

## Decisión operativa

La corrección en PostgreSQL debe:

1. Retirar exclusivamente `2025-01-31` mediante una ruta transaccional.
2. Conservar intacto el manifiesto histórico de la corrida original.
3. Registrar una nueva corrida con el `run_id` reemplazado y la causa.
4. Reprocesar y recargar enero desde el raw con el pipeline corregido.
5. No modificar febrero, marzo ni ningún otro periodo.
6. No corregir las 243,035 filas mediante `UPDATE` directo.

La eliminación y recarga permanecen pendientes de una ruta que garantice una
sola conexión, una sola transacción y rollback total.

## Referencias

```text
Manifiesto de procesamiento corregido:
outputs/processing/duckdb_2025_01_dimension_strings/
raw_processing_manifest_20260716T202019Z_7cfb513a_2025-01-31.json

Manifiesto de validación raw:
outputs/audit/raw_validation/
raw_validation_20260716T202019Z_c069980f_2025-01-31.json

CSV corregido:
outputs/processing/duckdb_2025_01_dimension_strings/
raw_aggregate_20260716T202019Z_7cfb513a_2025-01-31.csv

Parquet corregido:
outputs/processing/duckdb_2025_01_dimension_strings/
raw_aggregate_20260716T202019Z_7cfb513a_2025-01-31.parquet

Reporte de validación:
outputs/processing/duckdb_2025_01_dimension_strings/
validation_dimension_strings_20260716T202019Z_7cfb513a.json
```

El manifiesto histórico original permanece en PostgreSQL y no debe eliminarse
ni alterarse.

## Estado

```text
Causa identificada:             sí
Corrección de código:           validada
Salida local corregida:         validada
PostgreSQL:                     carga posterior reportada como exitosa
Verificacion dimensional en DB: pendiente de consulta operativa
Manifiesto histórico:           conservado
Febrero y marzo modificados:    no
```

## Actualizacion operativa — 2026-07-17

Una corrida historical batch posterior reporto `2025-01-31` con estado
`success`, accion `loaded` y 4,643,036 filas finales. Esa corrida utilizo el
lector por chunks con los tipos dimensionales corregidos, aunque su manifest
registro el antiguo selector `processing_engine: pandas` antes de que dicho
selector fuera retirado.

La arquitectura vigente ya no permite esa seleccion: DuckDB es el unico motor
productivo de consolidacion y pandas se limita a lectura y transformacion por
chunks. Esta actualizacion documental no abrio PostgreSQL; por ello la
confirmacion directa de cero codigos `.0` en la tabla final debe conservarse
como control operativo, no darse por ejecutada aqui.
