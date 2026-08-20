# -*- coding: utf-8 -*-
"""
AnalizarFacturas.py
OPCION 10 - Analizar facturas (PDFs de facturas de compra):

Escanea la ruta de red de facturas y muestra los PDFs de los ultimos 5 dias
del mes y anio actuales. Permite seleccionar uno o varios PDFs y extrae
los items comprados (codigo, descripcion, cantidad, precio) de cada factura.

Las cantidades deben ser enteros; se descartan floats y valores no numericos.

Uso:
    python AnalizarFacturas.py
"""
import os
import re
import sys
from datetime import date, timedelta

import pdfplumber

import consola

CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_CODIGO)

RUTA_BASE = r'\\Principal\c\Users\SERVIDOR\Documents\Negocio\ZM Autopartes\FACTURAS'

MESES = {1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL', 5: 'MAYO', 6: 'JUNIO',
         7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE',
         12: 'DICIEMBRE'}


def preguntar(texto):
    try:
        return input(texto)
    except EOFError:
        return ''


def _parsear_cantidad(texto):
    """Intenta convertir texto a cantidad entera.
    Devuelve None si no es valido (letras, floats, etc)."""
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
             .replace('\ufffd', '').strip()


def obtener_facturas_recientes():
    """Escanea la ruta de red y devuelve lista de PDFs de los ultimos 5 dias
    del mes y anio actuales. Cada elemento es dict con keys: ruta, nombre, factura."""
    hoy = date.today()
    anio = hoy.year
    mes = hoy.month
    mes_nombre = MESES[mes]

    carpeta_mes = os.path.join(RUTA_BASE, str(anio), mes_nombre)
    if not os.path.isdir(carpeta_mes):
        return []

    pdfs = []
    for dia in range(1, 32):
        try:
            fecha = date(anio, mes, dia)
        except ValueError:
            break
        if abs((hoy - fecha).days) > 5:
            continue
        carpeta_dia = os.path.join(carpeta_mes, fecha.strftime('%d-%m'))
        if not os.path.isdir(carpeta_dia):
            continue
        for archivo in os.listdir(carpeta_dia):
            if archivo.lower().endswith('.pdf'):
                ruta = os.path.join(carpeta_dia, archivo)
                numero = extraer_numero_factura(archivo)
                pdfs.append({
                    'ruta': ruta,
                    'nombre': archivo,
                    'factura': numero,
                    'fecha': fecha,
                })
    pdfs.sort(key=lambda p: _numero_factura_orden(p['factura']))
    return pdfs


def _numero_factura_orden(factura):
    """Extrae el numero numerico para ordenar (ej: N16758 -> 16758)."""
    match = re.search(r'(\d+)', factura)
    return int(match.group(1)) if match else 0


def extraer_numero_factura(nombre_archivo):
    """Extrae el numero de factura del nombre del archivo (ej: N16774.pdf -> N16774)."""
    base = os.path.splitext(nombre_archivo)[0]
    match = re.search(r'[Nn]\d+', base)
    if match:
        return match.group(0).upper()
    return base


def extraer_items_factura(path):
    """Lee un PDF de factura y extrae los items de la tabla.
    Devuelve lista de dicts: {codigo, desc, cant, precio}."""
    items = []
    columnas = {}  # nombre -> x0

    with pdfplumber.open(path) as pdf:
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
                        elif t in ('CANT', 'CANTIDAD', 'UNID', 'UNIDADES', 'QTY'):
                            columnas['cant'] = w['x0']
                        elif t in ('PRECIO', 'PREC', 'P.UNIT', 'PUNIT', 'COSTO', 'IMPORTE'):
                            pass
                        elif t == 'UNITARIO':
                            pass
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

    return items


def mostrar_factura(numero, items, nombre_archivo):
    """Muestra en consola el detalle de una factura."""
    print()
    print('-' * 65)
    print(f'  FACTURA: {consola.cian(consola.negrita(numero))}')
    print(f'  Archivo: {nombre_archivo}')
    print('-' * 65)
    if not items:
        print('  ' + consola.amarillo('No se encontraron items en esta factura.'))
        return
    print(f'  {"CODIGO":<18} {"DESCRIPCION":<36} {"CANT":>6}')
    print(f'  {"-"*18} {"-"*36} {"-"*6}')
    total_cant = 0
    for it in items:
        desc_corta = it['desc'][:34] if it['desc'] else ''
        print(f'  {it["codigo"]:<18} {desc_corta:<36} {it["cant"]:>6}')
        total_cant += it['cant']
    print(f'  {"-"*18} {"-"*36} {"-"*6}')
    print(f'  {"TOTAL":<56} {consola.negrita(total_cant):>6}')


def seleccionar_facturas(pdfs):
    """Muestra las facturas disponibles y permite al usuario seleccionar una o varias.
    Devuelve lista de facturas seleccionadas."""
    print()
    print('  FACTURAS DISPONIBLES (ultimos 5 dias):')
    print()
    for i, p in enumerate(pdfs, 1):
        fecha_str = p['fecha'].strftime('%d-%m-%Y')
        print(f'    {i:>3}. [{p["factura"]}] {p["nombre"]}  ({fecha_str})')
    print()
    print('  Separa multiples numeros con coma (ej: 1,3,5) o escribe "todas" para todas.')
    print()

    sel = preguntar('  Selecciona facturas: ').strip()
    if not sel:
        return []

    if sel.lower() in ('todas', 'all', 'a'):
        return pdfs

    indices = []
    for parte in sel.split(','):
        parte = parte.strip()
        try:
            idx = int(parte) - 1
            if 0 <= idx < len(pdfs):
                indices.append(idx)
        except ValueError:
            continue

    return [pdfs[i] for i in sorted(set(indices))]


def main():
    consola.titulo('OPCION 10 - ANALIZAR FACTURAS (PDF)')

    print(f'  Buscando facturas en: {RUTA_BASE}')
    print(f'  Anio: {date.today().year}  Mes: {MESES[date.today().month]}')
    print()

    pdfs = obtener_facturas_recientes()
    if not pdfs:
        carpeta_mes = os.path.join(RUTA_BASE, str(date.today().year),
                                   MESES[date.today().month])
        print('  ' + consola.amarillo('No se encontraron facturas en los ultimos 5 dias.'))
        if os.path.isdir(carpeta_mes):
            print(f'  La carpeta del mes existe: {carpeta_mes}')
            print('  Carpetas de dias encontradas:')
            for d in sorted(os.listdir(carpeta_mes)):
                print(f'    - {d}')
        else:
            print(f'  La carpeta del mes NO existe: {carpeta_mes}')
            print('  Carpetas disponibles en el anio:')
            carpeta_anio = os.path.join(RUTA_BASE, str(date.today().year))
            if os.path.isdir(carpeta_anio):
                for m in sorted(os.listdir(carpeta_anio)):
                    print(f'    - {m}')
            else:
                print(f'    (carpeta del anio no existe: {carpeta_anio})')
        return

    seleccionadas = seleccionar_facturas(pdfs)
    if not seleccionadas:
        print('  No seleccionaste ninguna factura. Cancelado.')
        return

    resumen_total = {}
    for p in seleccionadas:
        print(f'\n  Leyendo {p["nombre"]}...')
        try:
            items = extraer_items_factura(p['ruta'])
        except Exception as e:
            print('  ' + consola.rojo(f'Error al leer el PDF: {e}'))
            continue
        mostrar_factura(p['factura'], items, p['nombre'])
        for it in items:
            cod = it['codigo']
            if cod not in resumen_total:
                resumen_total[cod] = {'codigo': cod, 'desc': it['desc'], 'cant': 0}
            resumen_total[cod]['cant'] += it['cant']

    if len(seleccionadas) > 1:
        print()
        print('=' * 65)
        print('  ' + consola.negrita('RESUMEN TOTAL (todas las facturas seleccionadas)'))
        print('=' * 65)
        print(f'  {"CODIGO":<18} {"DESCRIPCION":<36} {"CANT":>6}')
        print(f'  {"-"*18} {"-"*36} {"-"*6}')
        gran_total = 0
        for cod in sorted(resumen_total, key=lambda c: resumen_total[c]['cant'], reverse=True):
            it = resumen_total[cod]
            desc_corta = it['desc'][:34] if it['desc'] else ''
            print(f'  {it["codigo"]:<18} {desc_corta:<36} {it["cant"]:>6}')
            gran_total += it['cant']
        print(f'  {"-"*18} {"-"*36} {"-"*6}')
        print(f'  {"TOTAL":<56} {consola.negrita(gran_total):>6}')
        print('=' * 65)


if __name__ == '__main__':
    main()
    try:
        input('Presiona Enter para cerrar...')
    except EOFError:
        pass
