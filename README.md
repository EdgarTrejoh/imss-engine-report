# 📊 IMSS Data Pipeline: Análisis Histórico de Asegurados

Este proyecto automatiza la extracción, limpieza y consolidación de los datos abiertos del IMSS (Instituto Mexicano del Seguro Social). El script está diseñado para procesar archivos de gran volumen (millones de registros) de manera eficiente, transformándolos en un resumen analítico listo para Business Intelligence o Ciencia de Datos.

## 🚀 Características Principales
Descarga Resiliente: Utiliza requests con manejo de User-Agent y timeouts para evitar bloqueos por parte del servidor (Error 403).

Procesamiento en Disco: Descarga archivos temporales para minimizar el uso de memoria RAM, permitiendo procesar archivos de +500MB en equipos estándar.

Normalización Histórica: Detecta automáticamente cambios en el layout de los datos (como la transición de rango_salarial a rango_uma en 2017).

Agregación Multidimensional: Consolida la información por Entidad, Sexo, Rango de Edad, UMA y Sector Económico.

## 🛠️ Requisitos
Para ejecutar este script, necesitas Python 3.x y las siguientes librerías:

```
Bash
# Crear entorno virtual
python -m venv .venv

# Activar entorno (Windows)
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## 📂 Estructura del Proyecto
**main.py**: Script principal de extracción y procesamiento.

**temp_*.csv**: Archivos temporales (se eliminan automáticamente tras procesarse).

**imss_analisis_profundo.csv**: El archivo de salida consolidado.

## ⚙️ Funcionamiento del Código
El pipeline sigue este flujo lógico para cada URL proporcionada:

* **Identificación**: Extrae el periodo de la URL mediante expresiones regulares.

* **Descarga Segura**: Realiza una petición HTTP simulando un navegador para obtener el archivo .csv.

* **Mapeo Dinámico**: * Si el archivo es anterior a febrero de 2017, renombra rango_salarial a rango_uma.

* **Normaliza** valores nulos a la etiqueta "no_ligados_a_patron".

* **Cálculo de Métricas**: Suma trabajadores permanentes (urbanos + campo) y eventuales, así como sus masas salariales.

* **Consolidación**: Agrupa y suma todos los registros en bloques de 400,000 filas para evitar saturar la memoria.

## 📝 Notas de Versión
v1.2: Implementada descarga a disco por flujo (stream) para corregir el bloqueo de pantalla.

v1.1: Añadida lógica de compatibilidad para UMA/Salario Mínimo (Pre-2017).

v1.0: Versión inicial con procesamiento por chunks.