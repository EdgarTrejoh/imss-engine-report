import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
import pandas as pd
import matplotlib.pyplot as plt

# 1. Cargar el archivo maestro
df = pd.read_csv("imss_analisis_profundo_concentrado.csv", encoding="utf-8-sig")
df['periodo_informacion'] = pd.to_datetime(df['periodo_informacion'])

# 2. Creación de métricas condicionales
# Asegurados totales (para cuadrar con reporte oficial)
# Asegurados con patrón (para cálculo de Salario Base de Cotización)
df['asegurados_con_patron'] = df.apply(
    lambda x: x['total_asegurados'] if x['rango_uma'] != "no_ligados_a_patron" else 0, axis=1
)
df['masa_con_patron'] = df.apply(
    lambda x: x['masa_salarial_total'] if x['rango_uma'] != "no_ligados_a_patron" else 0, axis=1
)

# 3. Agrupación Mensual
resumen = df.groupby(df['periodo_informacion'].dt.to_period('M')).agg({
    'total_asegurados': 'sum',
    'asegurados_con_patron': 'sum',
    'masa_con_patron': 'sum'
}).reset_index()

# Convertimos el periodo de vuelta a datetime para la gráfica
resumen['periodo_informacion'] = resumen['periodo_informacion'].dt.to_timestamp()

# 4. Cálculo del SBC Ajustado
resumen['sbc_ajustado'] = resumen['masa_con_patron'] / resumen['asegurados_con_patron']

resumen.to_excel("resumen.xlsx")

# 5. Visualización de la Brecha de Asegurados
plt.figure(figsize=(12, 6))
plt.plot(resumen['periodo_informacion'], resumen['total_asegurados'], 
         marker='o', label='Total Asegurados (Reporte IMSS)', color='#1f77b4', linewidth=2)
plt.plot(resumen['periodo_informacion'], resumen['asegurados_con_patron'], 
         marker='s', label='Asegurados con Patrón (Para SBC)', color='#ff7f0e', linestyle='--')

plt.title('Conciliación de Asegurados: Total vs. Ligados a Patrón', fontsize=14)
plt.xlabel('Periodo', fontsize=12)
plt.ylabel('Número de Personas', fontsize=12)
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)
plt.tight_layout()

logging.info("--- TABLA DE CONCILIACIÓN FINAL ---")
logging.info(resumen[['periodo_informacion', 'total_asegurados', 'asegurados_con_patron', 'sbc_ajustado']])

plt.show()