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


TABLA_ESCANEOS = 'escaneos'
TABLA_PIEZAS = 'piezas'
TABLA_CODIGOS_PIEZAS = 'codigos_piezas'


def guardar_escaneo(codigo, datos_extra=''):
    """Guarda un escaneo. Si el código ya existe, incrementa la cantidad.
    Devuelve (cantidad_total, es_nuevo)."""
    now = datetime.now(timezone.utc).isoformat()

    try:
        existente = _request('GET', TABLA_ESCANEOS,
                             f'?codigo=eq.{urllib.parse.quote(codigo)}&select=id,cantidad')
    except SupabaseError:
        existente = []

    if existente:
        fila = existente[0]
        nueva_cant = fila['cantidad'] + 1
        _request('PATCH', TABLA_ESCANEOS,
                 f'?id=eq.{fila["id"]}',
                 cuerpo={'cantidad': nueva_cant, 'fecha_actualizacion': now},
                 prefer='return=minimal')
        return nueva_cant, False
    else:
        _request('POST', TABLA_ESCANEOS,
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
    return _request('GET', TABLA_ESCANEOS,
                    f'?select=*&order=fecha_actualizacion.desc&limit={limite}') or []


def obtener_estadisticas():
    """Devuelve estadísticas generales."""
    filas = _request('GET', TABLA_ESCANEOS, '?select=codigo,cantidad') or []
    codigos = len(filas)
    unidades = sum(f.get('cantidad', 0) for f in filas)
    return {'codigos_unicos': codigos, 'unidades_totales': unidades}


def limpiar():
    """Elimina todos los registros."""
    _request('DELETE', TABLA_ESCANEOS, '?id=gt.0')


def borrar_ultimo():
    """Elimina el escaneo más reciente. Devuelve el código eliminado o None."""
    filas = _request('GET', TABLA_ESCANEOS,
                     '?select=id,codigo&order=fecha_actualizacion.desc&limit=1') or []
    if not filas:
        return None
    fila = filas[0]
    _request('DELETE', TABLA_ESCANEOS, f'?id=eq.{fila["id"]}')
    return fila.get('codigo')


# --- Funciones para piezas y vinculación barcode → pieza ---


def listar_piezas(buscar=''):
    """Lista piezas del catálogo. Filtra por código o descripción si buscar no está vacío."""
    if buscar:
        q = urllib.parse.quote(f'%{buscar}%')
        return _request('GET', TABLA_PIEZAS,
                        f'?or=(codigo_pieza.ilike.{q},descripcion.ilike.{q})'
                        f'&select=codigo_pieza,descripcion&order=codigo_pieza.asc') or []
    return _request('GET', TABLA_PIEZAS,
                    '?select=codigo_pieza,descripcion&order=codigo_pieza.asc') or []


def cargar_piezas(mapeos):
    """Bulk upsert de piezas. Recibe [{codigo_pieza, descripcion}].
    Devuelve la cantidad insertadas."""
    if not mapeos:
        return 0
    for m in mapeos:
        m.setdefault('descripcion', '')
    _request('POST', TABLA_PIEZAS,
             '?on_conflict=codigo_pieza',
             cuerpo=mapeos,
             prefer='resolution=merge-duplicates,return=minimal')
    return len(mapeos)


def buscar_barra(codigo_barra):
    """Busca si un barcode tiene pieza asociada.
    Devuelve {codigo_pieza, descripcion} o None."""
    try:
        filas = _request('GET', TABLA_CODIGOS_PIEZAS,
                         f'?codigo_barra=eq.{urllib.parse.quote(codigo_barra)}'
                         f'&select=codigo_pieza')
    except SupabaseError:
        return None
    if not filas:
        return None
    codigo_pieza = filas[0]['codigo_pieza']
    try:
        piezas = _request('GET', TABLA_PIEZAS,
                          f'?codigo_pieza=eq.{urllib.parse.quote(codigo_pieza)}'
                          f'&select=codigo_pieza,descripcion')
    except SupabaseError:
        piezas = []
    if piezas:
        return piezas[0]
    return {'codigo_pieza': codigo_pieza, 'descripcion': ''}


def asociar_barra(codigo_barra, codigo_pieza):
    """Vincula un barcode a una pieza. Si ya existía, actualiza."""
    _request('POST', TABLA_CODIGOS_PIEZAS,
             '?on_conflict=codigo_barra',
             cuerpo={
                 'codigo_barra': codigo_barra,
                 'codigo_pieza': codigo_pieza,
             },
             prefer='resolution=merge-duplicates,return=minimal')
