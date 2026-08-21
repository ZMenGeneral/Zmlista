# -*- coding: utf-8 -*-
"""
comparar_factura.py
Extrae items de un PDF de factura usando pdfplumber.
Reutiliza la lógica de AnalizarFacturas.py adaptada para el servidor.
"""
import os
import re

import pdfplumber


def _parsear_cantidad(texto):
    texto = texto.strip().replace(',', '.')
    if not texto:
        return None
    try:
        val = float(texto)
        if val != int(val):
            return None
        return int(val)
    except ValueError:
        return None


def _agrupar_lineas(words):
    words = sorted(words, key=lambda w: (w['top'], w['x0']))
    lineas = []
    for w in words:
        if lineas and abs(w['top'] - lineas[-1]['top']) < 3:
            lineas[-1]['words'].append(w)
        else:
            lineas.append({'top': w['top'], 'words': [w]})
    for ln in lineas:
        ln['words'].sort(key=lambda w: w['x0'])
    return lineas


def _norm(t):
    return t.upper().replace('Ó', 'O').replace('Í', 'I').replace('Á', 'A') \
             .replace('\ufffd', '').replace('?', '').strip()


def extraer_numero_factura(nombre_archivo):
    base = os.path.splitext(nombre_archivo)[0]
    match = re.search(r'[Nn]\d+', base)
    if match:
        return match.group(0).upper()
    return base


def extraer_items_factura(ruta_pdf):
    """Lee un PDF de factura y extrae los items.
    Devuelve {factura: str, items: [{codigo, desc, cant}]}."""
    items = []
    columnas = {}
    nombre = os.path.basename(ruta_pdf)
    numero = extraer_numero_factura(nombre)

    with pdfplumber.open(ruta_pdf) as pdf:
        for pag in pdf.pages:
            for ln in _agrupar_lineas(pag.extract_words()):
                texto = ' '.join(w['text'] for w in ln['words'])
                u = _norm(texto)

                if not columnas:
                    for w in ln['words']:
                        t = _norm(w['text'])
                        if t in ('CODIGO', 'CDIGO', 'COD', 'ARTICULO', 'ITEM'):
                            columnas['codigo'] = w['x0']
                        elif t in ('DESCRIPCION', 'DESCRIP', 'DESC', 'PRODUCTO', 'NOMBRE'):
                            columnas['desc'] = w['x0']
                        elif t in ('CANT', 'CANT.', 'CANTIDAD', 'UNID', 'UNIDADES', 'QTY'):
                            columnas['cant'] = w['x0']
                    if 'codigo' in columnas:
                        continue
                    continue

                if 'TOTAL' in u or 'PAGINA' in u or 'SUBTOTAL' in u:
                    continue

                if 'codigo' not in columnas:
                    continue

                cant_cols = columnas.get('cant')
                if cant_cols is None:
                    continue

                cant_words = [w for w in ln['words']
                              if abs(w['x0'] - cant_cols) < 25]
                cant_texto = ' '.join(w['text'] for w in cant_words)
                cant = _parsear_cantidad(cant_texto)
                if cant is None:
                    continue

                codigo_cols = columnas.get('codigo')
                code_words = [w for w in ln['words']
                              if abs(w['x0'] - codigo_cols) < 20]
                codigo = ''.join(w['text'] for w in
                                 sorted(code_words, key=lambda w: w['x0'])).strip()
                if not codigo:
                    continue

                desc_cols = columnas.get('desc')
                desc = ''
                if desc_cols is not None:
                    desc_words = [w for w in ln['words']
                                  if w['x0'] >= desc_cols and w['x0'] < cant_cols]
                    desc = ' '.join(w['text'] for w in desc_words).strip()

                items.append({
                    'codigo': codigo,
                    'desc': desc,
                    'cant': cant,
                })

    return {'factura': numero, 'items': items}
