# -*- coding: utf-8 -*-
"""
supabase_client.py
Cliente minimo para Supabase (PostgREST) usando solo urllib de la libreria
estandar. Lee las credenciales de config/supabase.json (NO se suben a git).

Tablas usadas:
    - public.guias_zoom  (guias de ZOOM)
    - public.no_vendidos (historial de no vendidos por mes y cliente)
"""
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_CODIGO)
ARCHIVO_CREDENCIALES = os.path.join(CARPETA_PROYECTO, 'config', 'supabase.json')


class SupabaseError(Exception):
    pass


def _config():
    if not os.path.exists(ARCHIVO_CREDENCIALES):
        raise SupabaseError(
            f'No se encontro config/supabase.json con las credenciales de Supabase.')
    with open(ARCHIVO_CREDENCIALES, 'r', encoding='utf-8') as f:
        return json.load(f)


def _headers(extra=None):
    cfg = _config()
    h = {
        'apikey': cfg['apikey'],
        'Authorization': 'Bearer ' + cfg.get('anon', cfg['apikey']),
        'Content-Type': 'application/json',
    }
    if extra:
        h.update(extra)
    return h


def _request(method, tabla, params='', cuerpo=None, prefer=None, timeout=30):
    cfg = _config()
    url = cfg['url'].rstrip('/') + '/' + tabla + params
    data = json.dumps(cuerpo).encode('utf-8') if cuerpo is not None else None
    extra = {'Prefer': prefer} if prefer else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers(extra))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texto = r.read().decode('utf-8')
            return json.loads(texto) if texto else None
    except urllib.error.HTTPError as e:
        detalle = e.read().decode('utf-8', errors='replace')
        raise SupabaseError(f'Supabase HTTP {e.code}: {detalle[:500]}')


def upsert_guia(datos):
    """Inserta o actualiza una guia usando la columna 'guia' como clave unica.
    Actualiza actualizado_en con la hora actual (momento del analisis)."""
    datos = dict(datos)
    datos['actualizado_en'] = datetime.now(timezone.utc).isoformat()
    return _request('POST', 'guias_zoom', '?on_conflict=guia',
                    cuerpo=datos, prefer='resolution=merge-duplicates,return=minimal')


def listar_guias():
    """Devuelve todas las guias ordenadas por guia desc."""
    return _request('GET', 'guias_zoom', '?select=*&order=guia.desc') or []


def marcar_cambiadas(guias, valor):
    """Pone fecha_cambiada = valor (True/False) en las guias indicadas."""
    if not guias:
        return 0
    lista = ','.join(guias)
    _request('PATCH', 'guias_zoom', f'?guia=in.({lista})',
             cuerpo={'fecha_cambiada': bool(valor)}, prefer='return=minimal')
    return len(guias)


def upsert_no_vendido(datos):
    """Inserta o actualiza un registro de NO VENDIDO usando
    (mes, cliente, codigo) como clave unica."""
    datos = dict(datos)
    datos['actualizado_en'] = datetime.now(timezone.utc).isoformat()
    return _request('POST', 'no_vendidos', '?on_conflict=mes,cliente,codigo',
                    cuerpo=datos, prefer='resolution=merge-duplicates,return=minimal')


def listar_no_vendidos_mes(mes):
    """Devuelve los registros de NO VENDIDOS de un mes (YYYY-MM)."""
    return _request('GET', 'no_vendidos',
                    f'?select=*&mes=eq.{mes}&order=cliente.asc,codigo.asc') or []


def listar_meses_no_vendidos():
    """Devuelve los meses que tienen registros de NO VENDIDOS, mas reciente primero."""
    filas = _request('GET', 'no_vendidos', '?select=mes&order=mes.desc') or []
    meses = []
    vistos = set()
    for f in filas:
        m = f.get('mes')
        if m and m not in vistos:
            vistos.add(m)
            meses.append(m)
    return meses
