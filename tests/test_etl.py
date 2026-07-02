import pytest
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from etl_imss import periodo_from_url
from audit import normalizar_serie

def test_periodo_from_url():
    """Prueba que el extractor de periodo por URL funcione correctamente"""
    url_valida = "http://datos.imss.gob.mx/sites/default/files/asg-2021-09-30.csv"
    assert periodo_from_url(url_valida) == "2021-09-30"
    
    url_invalida = "http://datos.imss.gob.mx/sites/default/files/asg-sin-fecha.csv"
    assert periodo_from_url(url_invalida) == "0000-00-00"

def test_normalizar_serie():
    """Prueba la normalización de strings de auditoría"""
    datos = pd.Series(["  espacios ", "texto", "", "NAN", "NONE", "Ok  "])
    resultado = normalizar_serie(datos)
    
    assert resultado.iloc[0] == "ESPACIOS"
    assert resultado.iloc[1] == "TEXTO"
    assert pd.isna(resultado.iloc[2])
    assert pd.isna(resultado.iloc[3])
    assert pd.isna(resultado.iloc[4])
    assert resultado.iloc[5] == "OK"
