import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
import pandas as pd
import sys
import os

def filtrar_valores_unicos(archivo_csv, columna=None, guardar=True):
    """
    Muestra los valores únicos de una o todas las columnas de un CSV
    """
    
    logging.info(f"📂 Leyendo archivo: {archivo_csv}...")
    df = pd.read_csv(archivo_csv, low_memory=False)
    
    logging.info(f"✅ Archivo cargado: {len(df):,} registros\n")
    
    # Si se especifica una columna
    if columna:
        if columna not in df.columns:
            logging.info(f"❌ Error: La columna '{columna}' no existe")
            logging.info(f"📋 Columnas disponibles: {', '.join(df.columns)}\n")
            return
        
        valores_unicos = df[columna].unique()
        conteo = df[columna].value_counts().sort_index()
        
        logging.info(f"🔍 Columna: {columna}")
        logging.info(f"📊 Total de valores únicos: {len(valores_unicos)}\n")
        logging.info("="*80)
        logging.info(f"{'Valor':<50} {'Cantidad':>15} {'%':>10}")
        logging.info("="*80)
        
        for valor, cantidad in conteo.items():
            porcentaje = (cantidad / len(df)) * 100
            valor_str = str(valor) if pd.notna(valor) else 'NULL'
            logging.info(f"{valor_str:<50} {int(cantidad):>15,} {porcentaje:>9.2f}%")
        
        logging.info("="*80 + "\n")
        
        # Guardar resultados
        if guardar:
            archivo_salida = f"valores_unicos_{columna}.csv"
            df_resultado = pd.DataFrame({
                'valor': conteo.index,
                'cantidad': conteo.values,
                'porcentaje': (conteo.values / len(df)) * 100
            })
            df_resultado.to_csv(archivo_salida, index=False)
            logging.info(f"💾 Resultados guardados en: {archivo_salida}\n")
    
    else:
        # Mostrar resumen de todas las columnas
        logging.info("📋 RESUMEN DE VALORES ÚNICOS POR COLUMNA")
        logging.info("="*80)
        logging.info(f"{'Columna':<30} {'Tipo':<15} {'Valores Únicos':>15} {'Top 3 valores'}")
        logging.info("="*80)
        
        resultados = []
        for col in df.columns:
            valores_unicos = df[col].nunique()
            tipo_dato = str(df[col].dtype)
            
            # Top 3 valores más frecuentes
            top_valores = df[col].value_counts().head(3).index.tolist()
            top_str = ', '.join([str(v)[:20] for v in top_valores])
            
            logging.info(f"{col:<30} {tipo_dato:<15} {valores_unicos:>15,} {top_str}")
            
            resultados.append({
                'columna': col,
                'tipo_dato': tipo_dato,
                'valores_unicos': valores_unicos,
                'top_1': top_valores[0] if len(top_valores) > 0 else None,
                'top_2': top_valores[1] if len(top_valores) > 1 else None,
                'top_3': top_valores[2] if len(top_valores) > 2 else None
            })
        
        logging.info("="*80 + "\n")
        
        if guardar:
            archivo_salida = "resumen_valores_unicos.csv"
            pd.DataFrame(resultados).to_csv(archivo_salida, index=False)
            logging.info(f"💾 Resumen guardado en: {archivo_salida}\n")
    
    logging.info("💡 Tip: Para ver detalle de una columna específica:")
    logging.info(f"   python {sys.argv[0]} {archivo_csv} nombre_columna\n")


if __name__ == "__main__":
    logging.info("\n" + "🔍 FILTRADOR DE VALORES ÚNICOS".center(80, "=") + "\n")
    
    if len(sys.argv) < 2:
        logging.info("❌ Error: Falta el archivo CSV\n")
        logging.info("📖 Uso:")
        logging.info("   # Ver resumen de todas las columnas:")
        logging.info("   python filtrar_valores.py archivo.csv\n")
        logging.info("   # Ver detalle de una columna específica:")
        logging.info("   python filtrar_valores.py archivo.csv nombre_columna\n")
        logging.info("📝 Ejemplos:")
        logging.info("   python filtrar_valores.py datos.csv")
        logging.info("   python filtrar_valores.py datos.csv cve_entidad")
        logging.info("   python filtrar_valores.py datos.csv sexo\n")
        sys.exit(1)
    
    archivo = sys.argv[1]
    columna_filtro = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(archivo):
        logging.info(f"❌ Error: No se encontró el archivo '{archivo}'\n")
        sys.exit(1)
    
    try:
        filtrar_valores_unicos(archivo, columna_filtro)
    except Exception as e:
        logging.info(f"❌ Error: {e}\n")
        sys.exit(1)