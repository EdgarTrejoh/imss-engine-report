import pandas as pd
import re
from datetime import datetime
import requests
import io
import os
import time
import yaml
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)["etl"]

URLS = [config["base_url"].format(mes) for mes in config["meses"]]
OUTPUT_FILE = config["output_file"]
CHUNK_SIZE = config["chunk_size"]

# Columnas Base
COL_ENTIDAD             = "cve_entidad"
COL_SEXO                = "sexo"
COL_RANGO_EDAD          = "rango_edad"
COL_RANGO_UMA           = "rango_uma"
COL_RANGO_SALARIAL_OLD  = "rango_salarial" # El nombre anterior a febrero 2017
COL_SECTOR              = "sector_economico_1"
COL_PERIODO             = "periodo_informacion"

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
    temp_file = f"temp_{periodo}.csv" # Archivo temporal en disco
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    logging.info(f"Iniciando: {periodo}")
    
    try:
        # 1. DESCARGA AL DISCO (Para no saturar la RAM)
        logging.info("Descargando archivo desde el IMSS...")
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(temp_file, 'wb') as f:
                for chunk_dl in r.iter_content(chunk_size=8192):
                    f.write(chunk_dl)
        
        # 2. PROCESAMIENTO POR CHUNKS DESDE DISCO
        chunks = pd.read_csv(temp_file, sep="|", encoding="latin-1", chunksize=CHUNK_SIZE, low_memory=False)
        
        agg_global = None
        for i, chunk in enumerate(chunks, start=1):
            logging.info(f"Procesando bloque {i}...")
            # ... (Aquí va TODA tu lógica de limpieza y cálculos de antes) ...
            # --- NORMALIZACIÓN DE COLUMNA DE RANGO ---
            # Si existe la columna vieja y no la nueva, la renombramos
            if COL_RANGO_SALARIAL_OLD in chunk.columns and COL_RANGO_UMA not in chunk.columns:
                chunk = chunk.rename(columns={COL_RANGO_SALARIAL_OLD: COL_RANGO_UMA})
            
            # Si por alguna razón no existe ninguna (caso raro), la creamos vacía para no romper el group_cols
            if COL_RANGO_UMA not in chunk.columns:
                chunk[COL_RANGO_UMA] = "no_identificado"

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

            # Lógica de agrupación y concatenación 

        # 3. GUARDADO FINAL Y LIMPIEZA
        mode = "w" if first_file else "a"
        agg_global.to_csv(OUTPUT_FILE, mode=mode, header=first_file, index=False, encoding="utf-8-sig")
        
        logging.info(f"{periodo} finalizado. Eliminando temporal...")
        os.remove(temp_file) # Borramos el pesado archivo original para ahorrar espacio
        
    except Exception as e:
        logging.error(f"Error en {periodo}: {e}")
        if os.path.exists(temp_file): os.remove(temp_file)
        return

    time.sleep(3)

# =================== EJECUCIÓN ======================
first = True
for url in URLS:
    procesar_url(url, first_file=first)
    first = False

logging.info(f"PROCESO COMPLETO: {OUTPUT_FILE}")