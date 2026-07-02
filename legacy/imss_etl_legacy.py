import pandas as pd
import re
from datetime import datetime
import yaml
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)["etl"]

URLS = [config["base_url"].format(mes) for mes in config["meses"]]
OUTPUT_FILE = config["output_file"]
CHUNK_SIZE = config["chunk_size"]

# Columnas Base
COL_ENTIDAD     = "cve_entidad"
COL_SEXO        = "sexo"
COL_RANGO_EDAD  = "rango_edad"
COL_RANGO_UMA   = "rango_uma"
COL_SECTOR      = "sector_economico_1"
COL_PERIODO     = "periodo_informacion"

# Mapeo de columnas para sumas (Basado en layout IMSS)
# Permanentes: tpu (urbano) + tpc (campo)
# Eventuales: teu (urbano) + tec (campo)
# Masa Salarial Total: masa_sal_ta (ya la incluimos por compatibilidad)

# =========================================================

def periodo_from_url(url):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", url)
    if not m: return "0000-00-00"
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

def procesar_url(url, first_file):
    periodo = periodo_from_url(url)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"Procesando Sector y Estabilidad: {periodo}")

    agg_global = None

    try:
        chunks = pd.read_csv(url, sep="|", encoding="latin-1", chunksize=CHUNK_SIZE, low_memory=False)
    except Exception as e:
        logging.error(f"Error: {e}")
        return

    for i, chunk in enumerate(chunks, start=1):
        logging.info(f"Analizando bloque {i}...")

        # 1. Crear Dimensiones y Metadatos
        chunk[COL_PERIODO] = periodo
        chunk["fuente"] = "IMSS"
        chunk["timestamp"] = timestamp

        # 2. Tratamiento de Nulos en etiquetas
        dimensiones = [COL_ENTIDAD, COL_SEXO, COL_RANGO_EDAD, COL_RANGO_UMA, COL_SECTOR]
        for col in dimensiones:
            chunk[col] = chunk[col].fillna("no_ligados_a_patron")

        # 3. Cálculos de consolidación (Permanentes vs Eventuales)
        # Convertimos a numérico primero
        cols_num = ['tpu', 'tpc', 'teu', 'tec', 'masa_sal_tpu', 'masa_sal_tpc', 'masa_sal_teu', 'masa_sal_tec', 'ta', 'masa_sal_ta']
        for c in cols_num:
            chunk[c] = pd.to_numeric(chunk[c], errors="coerce").fillna(0)

        chunk['trabajadores_permanentes'] = chunk['tpu'] + chunk['tpc']
        chunk['trabajadores_eventuales']  = chunk['teu'] + chunk['tec']
        chunk['masa_sal_permanentes']     = chunk['masa_sal_tpu'] + chunk['masa_sal_tpc']
        chunk['masa_sal_eventuales']      = chunk['masa_sal_teu'] + chunk['masa_sal_tec']

        # 4. Agrupación por todas las dimensiones
        group_cols = ["fuente", "timestamp", COL_PERIODO, COL_ENTIDAD, COL_SEXO, COL_RANGO_EDAD, COL_RANGO_UMA, COL_SECTOR]
        
        agg_chunk = chunk.groupby(group_cols, as_index=False).agg(
            total_asegurados=('ta', 'sum'),
            masa_salarial_total=('masa_sal_ta', 'sum'),
            trabajadores_permanentes=('trabajadores_permanentes', 'sum'),
            trabajadores_eventuales=('trabajadores_eventuales', 'sum'),
            masa_sal_permanentes=('masa_sal_permanentes', 'sum'),
            masa_sal_eventuales=('masa_sal_eventuales', 'sum')
        )

        # 5. Acumular
        if agg_global is None:
            agg_global = agg_chunk
        else:
            agg_global = pd.concat([agg_global, agg_chunk], ignore_index=True)
            agg_global = agg_global.groupby(group_cols, as_index=False).sum()

    # Guardado
    mode = "w" if first_file else "a"
    agg_global.to_csv(OUTPUT_FILE, mode=mode, header=first_file, index=False, encoding="utf-8-sig")
    logging.info(f"Periodo {periodo} integrado correctamente.")

# =================== EJECUCIÓN ======================
first = True
for url in URLS:
    procesar_url(url, first_file=first)
    first = False

logging.info(f"PROCESO COMPLETO: {OUTPUT_FILE}")