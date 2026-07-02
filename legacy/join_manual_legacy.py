import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
import pandas as pd

# 1. Definir los nombres de tus archivos
file1 = "imss_analisis_profundo_02.csv"
file2 = "imss_analisis_profundo_01.csv"
output_file = "imss_analisis_profundo.csv"

logging.info("Iniciando consolidación de archivos...")

# 2. Cargar los archivos
# Usamos low_memory=False para evitar advertencias de tipos de datos
df1 = pd.read_csv(file1, encoding="utf-8-sig", low_memory=False)
df2 = pd.read_csv(file2, encoding="utf-8-sig", low_memory=False)

logging.info(f"-> Archivo 1: {len(df1)} filas cargadas.")
logging.info(f"-> Archivo 2: {len(df2)} filas cargadas.")

# 3. Unir los DataFrames (Concatenar)
df_total = pd.concat([df1, df2], ignore_index=True)

# 4. Eliminar duplicados (Crucial por si el proceso tronó y reinició en el mismo periodo)
# Identificamos duplicados basados en todas las columnas excepto el 'timestamp' 
# porque el timestamp será diferente en cada ejecución
cols_para_verificar = [c for c in df_total.columns if c != 'timestamp']
df_final = df_total.drop_duplicates(subset=cols_para_verificar)

# 5. Guardar el resultado final
df_final.to_csv(output_file, index=False, encoding="utf-8-sig")

logging.info("-" * 30)
logging.info(f"✅ ¡ÉXITO! Archivo final creado: {output_file}")
logging.info(f"Total de filas consolidadas: {len(df_final)}")
if len(df_total) > len(df_final):
    logging.info(f"Se eliminaron {len(df_total) - len(df_final)} filas duplicadas encontradas.")