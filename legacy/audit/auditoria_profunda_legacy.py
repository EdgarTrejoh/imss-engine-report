import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
import pandas as pd
import sys
import os

def auditoria_profunda(archivo_csv, columna):
    """
    Detecta valores ocultos, espacios, tipos mixtos y caracteres especiales
    """
    
    logging.info(f"🔬 AUDITORÍA PROFUNDA: {columna}")
    logging.info("="*100 + "\n")
    
    # Leer sin procesar tipos automáticamente
    df = pd.read_csv(archivo_csv, dtype=str, keep_default_na=False)
    
    logging.info(f"📂 Archivo: {archivo_csv}")
    logging.info(f"📊 Total registros: {len(df):,}\n")
    
    if columna not in df.columns:
        logging.info(f"❌ Error: Columna '{columna}' no existe")
        logging.info(f"Columnas disponibles: {', '.join(df.columns)}\n")
        return
    
    serie = df[columna]
    
    # 1. ANÁLISIS DE VALORES ÚNICOS CRUDOS
    logging.info("🔍 1. VALORES ÚNICOS (sin limpiar)")
    logging.info("-"*100)
    valores_unicos = serie.unique()
    logging.info(f"Total de valores únicos detectados: {len(valores_unicos)}\n")
    
    # 2. DETECCIÓN DE ESPACIOS Y CARACTERES ESPECIALES
    logging.info("🧹 2. ANÁLISIS DE ESPACIOS Y CARACTERES ESPECIALES")
    logging.info("-"*100)
    
    resultados = []
    for valor in valores_unicos:
        valor_limpio = valor.strip()
        tiene_espacios_inicio = valor != valor.lstrip()
        tiene_espacios_fin = valor != valor.rstrip()
        tiene_saltos_linea = '\n' in valor or '\r' in valor
        tiene_tabs = '\t' in valor
        es_vacio = valor == ''
        longitud = len(valor)
        
        # Representación visible
        valor_repr = repr(valor)
        
        resultados.append({
            'valor_original': valor_repr,
            'valor_limpio': valor_limpio,
            'longitud': longitud,
            'espacios_inicio': '✓' if tiene_espacios_inicio else '',
            'espacios_fin': '✓' if tiene_espacios_fin else '',
            'saltos_linea': '✓' if tiene_saltos_linea else '',
            'tabulaciones': '✓' if tiene_tabs else '',
            'es_vacio': '✓' if es_vacio else '',
            'conteo': (serie == valor).sum()
        })
    
    df_resultados = pd.DataFrame(resultados)
    df_resultados = df_resultados.sort_values('conteo', ascending=False)
    
    # Mostrar en consola
    logging.info(f"{'Valor (repr)':<30} {'Limpio':<15} {'Long':>5} {'Esp.Ini':>8} {'Esp.Fin':>8} {'\\n':>5} {'\\t':>5} {'Vacío':>6} {'Conteo':>12}")
    logging.info("-"*100)
    
    for _, row in df_resultados.iterrows():
        logging.info(f"{str(row['valor_original'])[:30]:<30} "
              f"{str(row['valor_limpio'])[:15]:<15} "
              f"{row['longitud']:>5} "
              f"{row['espacios_inicio']:>8} "
              f"{row['espacios_fin']:>8} "
              f"{row['saltos_linea']:>5} "
              f"{row['tabulaciones']:>5} "
              f"{row['es_vacio']:>6} "
              f"{row['conteo']:>12,}")
    
    logging.info("-"*100 + "\n")
    
    # 3. VALORES PROBLEMÁTICOS
    logging.info("⚠️  3. VALORES PROBLEMÁTICOS DETECTADOS")
    logging.info("-"*100)
    
    problemas = []
    count_espacios_inicio = (df_resultados['espacios_inicio'] == '✓').sum()
    count_espacios_fin = (df_resultados['espacios_fin'] == '✓').sum()
    count_saltos_linea = (df_resultados['saltos_linea'] == '✓').sum()
    count_tabulaciones = (df_resultados['tabulaciones'] == '✓').sum()
    count_vacios = (df_resultados['es_vacio'] == '✓').sum()
    
    if count_espacios_inicio > 0:
        problemas.append(f"✗ {count_espacios_inicio} valores con espacios al inicio")
    if count_espacios_fin > 0:
        problemas.append(f"✗ {count_espacios_fin} valores con espacios al final")
    if count_saltos_linea > 0:
        problemas.append(f"✗ {count_saltos_linea} valores con saltos de línea")
    if count_tabulaciones > 0:
        problemas.append(f"✗ {count_tabulaciones} valores con tabulaciones")
    if count_vacios > 0:
        problemas.append(f"✗ {count_vacios} valores vacíos (no NULL)")
    
    if problemas:
        for problema in problemas:
            logging.info(problema)
    else:
        logging.info("✅ No se detectaron problemas con espacios o caracteres especiales")
    
    logging.info("-"*100 + "\n")
    
    # 4. VALORES DESPUÉS DE LIMPIAR
    logging.info("🧽 4. VALORES ÚNICOS DESPUÉS DE LIMPIAR")
    logging.info("-"*100)
    
    valores_limpios = serie.str.strip().unique()
    logging.info(f"Valores únicos antes de limpiar: {len(valores_unicos)}")
    logging.info(f"Valores únicos después de limpiar: {len(valores_limpios)}")
    logging.info(f"Diferencia: {len(valores_unicos) - len(valores_limpios)} valores eran duplicados con espacios\n")
    
    # Guardar resultados
    archivo_salida = f"auditoria_profunda_{columna}.csv"
    df_resultados.to_csv(archivo_salida, index=False)
    logging.info(f"💾 Resultados guardados en: {archivo_salida}\n")
    
    # 5. RECOMENDACIONES
    logging.info("💡 5. RECOMENDACIONES")
    logging.info("-"*100)
    if problemas:
        logging.info("Se recomienda limpiar los datos usando:")
        logging.info("  df[columna] = df[columna].str.strip()  # Eliminar espacios")
        logging.info("  df[columna] = df[columna].replace('', pd.NA)  # Convertir vacíos en NA")
    else:
        logging.info("✅ Los datos están limpios en esta columna")
    logging.info("="*100 + "\n")


if __name__ == "__main__":
    logging.info("\n" + "🔬 AUDITORÍA PROFUNDA DE DATOS".center(100, "=") + "\n")
    
    if len(sys.argv) < 3:
        logging.info("❌ Error: Faltan argumentos\n")
        logging.info("📖 Uso:")
        logging.info("   python auditoria_profunda.py <archivo.csv> <columna>\n")
        logging.info("📝 Ejemplos:")
        logging.info("   python auditoria_profunda.py datos.csv cve_entidad")
        logging.info("   python auditoria_profunda.py datos.csv sexo\n")
        sys.exit(1)
    
    archivo = sys.argv[1]
    columna = sys.argv[2]
    
    if not os.path.exists(archivo):
        logging.info(f"❌ Error: No se encontró el archivo '{archivo}'\n")
        sys.exit(1)
    
    try:
        auditoria_profunda(archivo, columna)
    except Exception as e:
        logging.info(f"❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)