import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
import pandas as pd
from datetime import datetime
import sys
import os

# -------------------------
# Utilidades internas
# -------------------------
def normalizar_serie(serie: pd.Series) -> pd.Series:
    """
    Normaliza strings para auditoría:
    - strip espacios
    - upper
    - vacíos semánticos a NA
    """
    return (
        serie
        .astype("string")
        .str.strip()
        .str.upper()
        .replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
    )

# -------------------------
# Función principal
# -------------------------
def analizar_y_auditar_csv(archivo_entrada, archivo_salida="auditoria.csv"):

    logging.info(f"📂 Leyendo archivo: {archivo_entrada}...")
    df = pd.read_csv(archivo_entrada)

    auditoria = {
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archivo_origen": archivo_entrada,
        "ruta_completa": os.path.abspath(archivo_entrada),
        "tamaño_archivo_mb": round(os.path.getsize(archivo_entrada) / 1024**2, 2),
        "total_registros": len(df),
        "total_columnas": len(df.columns),
        "registros_duplicados": df.duplicated().sum(),
        "valores_nulos_total": int(df.isnull().sum().sum()),
        "memoria_uso_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
    }

    logging.info("🔍 Analizando columnas (modo forense)...")
    analisis_columnas = []

    for col in df.columns:
        serie = df[col]
        is_text = pd.api.types.is_object_dtype(serie) or pd.api.types.is_string_dtype(serie)

        nunique_raw = serie.nunique(dropna=True)

        if is_text:
            serie_norm = normalizar_serie(serie)
            nunique_norm = serie_norm.nunique(dropna=True)

            top_valores = (
                serie_norm
                .value_counts(dropna=False)
                .head(5)
                .to_dict()
            )

            fantasmas = nunique_raw - nunique_norm
        else:
            nunique_norm = "N/A"
            top_valores = "N/A"
            fantasmas = 0

        analisis_columnas.append({
            "columna": col,
            "tipo_dato": str(serie.dtype),
            "valores_nulos": int(serie.isnull().sum()),
            "porcentaje_nulos": round(serie.isnull().mean() * 100, 2),
            "nunique_raw": nunique_raw,
            "nunique_normalizado": nunique_norm,
            "valores_fantasma_detectados": fantasmas if is_text else "N/A",
            "top_5_valores": top_valores,
            "ejemplo_valor": repr(serie.dropna().iloc[0]) if serie.notna().any() else "N/A",
            "min": serie.min() if pd.api.types.is_numeric_dtype(serie) else "N/A",
            "max": serie.max() if pd.api.types.is_numeric_dtype(serie) else "N/A",
            "media": round(serie.mean(), 2) if pd.api.types.is_numeric_dtype(serie) else "N/A",
        })

    # -------------------------
    # Guardar resultados
    # -------------------------
    logging.info("💾 Guardando auditoría...")
    df_auditoria = pd.DataFrame([auditoria])
    df_auditoria.to_csv(archivo_salida, index=False)

    df_columnas = pd.DataFrame(analisis_columnas)
    archivo_detalle = archivo_salida.replace(".csv", "_detalle_columnas.csv")
    df_columnas.to_csv(archivo_detalle, index=False)

    if auditoria["registros_duplicados"] > 0:
        archivo_dup = archivo_salida.replace(".csv", "_duplicados.csv")
        df[df.duplicated(keep=False)].to_csv(archivo_dup, index=False)
        logging.info(f"⚠️  Duplicados guardados en: {archivo_dup}")

    # -------------------------
    # Resumen consola
    # -------------------------
    logging.info("\n" + "=" * 60)
    logging.info("✅ AUDITORÍA COMPLETADA – COMPITA 2.0")
    logging.info("=" * 60)
    logging.info(f"📊 Registros: {auditoria['total_registros']:,}")
    logging.info(f"📋 Columnas: {auditoria['total_columnas']}")
    logging.info(f"❌ Nulos totales: {auditoria['valores_nulos_total']:,}")
    logging.info(f"🧠 Memoria: {auditoria['memoria_uso_mb']} MB")
    logging.info("\n📄 Archivos generados:")
    logging.info(f"   ├─ {archivo_salida}")
    logging.info(f"   └─ {archivo_detalle}")
    logging.info("=" * 60 + "\n")

    return df, df_auditoria, df_columnas

# -------------------------
# CLI
# -------------------------
if __name__ == "__main__":

    logging.info("\n" + "🔎 ANALIZADOR DE CSV – COMPITA 2.0".center(60, "="))

    if len(sys.argv) < 2:
        logging.info("❌ Uso: python analizar_csv_v2.py <archivo.csv> [salida.csv]")
        sys.exit(1)

    archivo_entrada = sys.argv[1]
    archivo_salida = sys.argv[2] if len(sys.argv) > 2 else "auditoria.csv"

    if not os.path.exists(archivo_entrada):
        logging.info(f"❌ No se encontró el archivo: {archivo_entrada}")
        sys.exit(1)

    try:
        analizar_y_auditar_csv(archivo_entrada, archivo_salida)
    except Exception as e:
        logging.info(f"❌ Error inesperado: {e}")
        sys.exit(1)
