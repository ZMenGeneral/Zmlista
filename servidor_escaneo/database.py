# -*- coding: utf-8 -*-
"""
Base de datos para escaneos usando Supabase.
Reutiliza el cliente minimal existente en supabase_client.py.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_CODIGO)
sys.path.insert(0, os.path.join(CARPETA_PROYECTO, 'codigo'))

from supabase_client import _config, _headers, _request, SupabaseError


TABLA = 'escaneos'


def guardar_escaneo(codigo, datos_extra=''):
    """Guarda un escaneo. Si el código ya existe, incrementa la cantidad.
    Devuelve (cantidad_total, es_nuevo)."""
    now = datetime.now(timezone.utc).isoformat()

    try:
        existente = _request('GET', TABLA,
                             f'?codigo=eq.{urllib.parse.quote(codigo)}&select=id,cantidad')
    except SupabaseError:
        existente = []

    if existente:
        fila = existente[0]
        nueva_cant = fila['cantidad'] + 1
        _request('PATCH', TABLA,
                 f'?id=eq.{fila["id"]}',
                 cuerpo={'cantidad': nueva_cant, 'fecha_actualizacion': now},
                 prefer='return=minimal')
        return nueva_cant, False
    else:
        _request('POST', TABLA,
                 '?on_conflict=codigo',
                 cuerpo={
                     'codigo': codigo,
                     'datos_extra': datos_extra,
                     'cantidad': 1,
                     'fecha_escaneo': now,
                     'fecha_actualizacion': now,
                 },
                 prefer='resolution=merge-duplicates,return=minimal')
        return 1, True


def obtener_todos(limite=500):
    """Devuelve los escaneos más recientes."""
    return _request('GET', TABLA,
                    f'?select=*&order=fecha_actualizacion.desc&limit={limite}') or []


def obtener_estadisticas():
    """Devuelve estadísticas generales."""
    filas = _request('GET', TABLA, '?select=codigo,cantidad') or []
    codigos = len(filas)
    unidades = sum(f.get('cantidad', 0) for f in filas)
    return {'codigos_unicos': codigos, 'unidades_totales': unidades}


def limpiar():
    """Elimina todos los registros."""
    _request('DELETE', TABLA, '?id=gt.0')
