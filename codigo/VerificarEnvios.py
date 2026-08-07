# -*- coding: utf-8 -*-
"""
VerificarEnvios.py
OPCION 3 - Verificar envios de ZOOM:
    Lee un PDF con numeros de guia, consulta la API publica de ZOOM y
    muestra en pantalla el estado de cada envio. Si la mercancia ya fue
    retirada/entregada, indica CUANDO y POR QUIEN.

API usada (publica, sin credenciales):
    GET https://api.zoom.red/canguroazul/getZoomTrackWs
        ?tipo_busqueda=1&web=1&codigo=<NUMERO_DE_GUIA>

Uso:
    python VerificarEnvios.py                         (abre explorador para el PDF)
    python VerificarEnvios.py "C:/ruta/guia.pdf"
    python VerificarEnvios.py 1694708010 1553486107   (verifica guias directas)
"""
import os
import re
import sys
import time
import json
import urllib.request
import urllib.error

import consola

URL_API = 'https://api.zoom.red/canguroazul/getZoomTrackWs'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

CARPETA_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_PDFS = os.path.join(CARPETA_PROYECTO, 'pdfs')

ENTREGADAS = ('ENTREGADO AL DESTINO', 'ENTREGADO AL CLIENTE', 'ENTREGADO')
DISPONIBLES = ('DISPONIBLE PARA EL RETIRO EN TAQUILLA',)


def consultar(guia, reintentos=2):
    """Consulta la API de ZOOM y devuelve el JSON parseado. Lanza excepcion
    si no se puede obtener la informacion."""
    url = URL_API + f'?tipo_busqueda=1&web=1&codigo={guia}'
    req = urllib.request.Request(url, headers=HEADERS)
    ultimo_error = None
    for intento in range(reintentos + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8-sig'))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo_error = e
            if intento < reintentos:
                time.sleep(1.5)
    raise RuntimeError(f'Error de red: {ultimo_error}')


def extraer_guias_pdf(path):
    """Extrae numeros de guia (10 digitos) del texto de un PDF."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    texto = '\n'.join((pag.extract_text() or '') for pag in reader.pages)
    guias = []
    vistos = set()
    for m in re.finditer(r'\b\d{10}\b', texto):
        g = m.group(0)
        if g not in vistos:
            vistos.add(g)
            guias.append(g)
    return guias, len(reader.pages)


def ask_pdf_dialog():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askopenfilename(
        title='Selecciona el PDF con los numeros de guia',
        filetypes=[('Archivos PDF', '*.pdf'), ('Todos los archivos', '*.*')],
        initialdir=CARPETA_PDFS if os.path.isdir(CARPETA_PDFS) else CARPETA_PROYECTO,
    )
    root.destroy()
    return path


def _fecha_corta(s):
    """'2026-08-06 11:21:53.621919' -> '06/08/2026 11:21'."""
    if not s:
        return s
    s = s.strip()
    try:
        if ' ' in s:
            fecha, hora = s.split(' ', 1)
            hora = hora.split('.')[0][:5]
        else:
            fecha, hora = s, ''
        partes = fecha.split('-')
        if len(partes) == 3:
            fecha = f'{partes[2]}/{partes[1]}/{partes[0]}'
        return (fecha + ' ' + hora).strip()
    except Exception:
        return s


def formatear_resumen(guia, data):
    """Construye el texto de resultado de una guia."""
    ent = (data or {}).get('entidadRespuesta') or {}
    iz = ent.get('infoZoom') or {}
    track = ent.get('tracking') or []

    lineas = []
    lineas.append('=' * 58)
    lineas.append(consola.cian(consola.negrita(f'GUIA: {guia}')))

    if not iz:
        lineas.append('  Estado: GUIA NO ENCONTRADA EN LA BASE DE DATOS')
        return lineas

    estatus = iz.get('descripcion_estatus') or 'SIN ESTADO'
    origen = (iz.get('origen') or {}).get('nombre') or '-'
    destino = (iz.get('destino') or {}).get('nombre') or '-'
    fechaven = iz.get('fecha') or ''
    servicio = iz.get('nombreservicio') or '-'
    peso = iz.get('peso') or '-'
    piezas = iz.get('nropiezas') or '-'
    casillero = iz.get('codcasillero') or ''

    lineas.append(f'  Estado: {estatus}')
    lineas.append(f'  Enviado: {fechaven}  |  Origen: {origen}  ->  Destino: {destino}')
    lineas.append(f'  Servicio: {servicio}  |  Peso: {peso}  |  Piezas: {piezas}')
    if casillero and casillero.strip() != '-':
        lineas.append(f'  Casillero/Destinatario: {casillero}')

    entrega = None
    for t in track:
        nom = ((t.get('estatus') or {}).get('nombre') or '').upper()
        if nom in ENTREGADAS or (t.get('receptor') or '').strip():
            entrega = t
            break

    if entrega is not None:
        receptor = (entrega.get('receptor') or '').strip()
        usuario = ((entrega.get('usuario') or {}).get('nombre') or '').strip()
        oficina = ((entrega.get('oficina') or {}).get('nombre') or '').strip()
        lineas.append('-' * 58)
        lineas.append(consola.verde('  RETIRADA/ENTREGADA: SI'))
        lineas.append(f'  Fecha de entrega: {_fecha_corta(entrega.get("fechahorareal"))}')
        if receptor:
            lineas.append(f'  Recibida por: {receptor}')
        if usuario:
            lineas.append(f'  Registrado por: {usuario}')
        if oficina:
            lineas.append(f'  Oficina: {oficina}')
    else:
        lineas.append('-' * 58)
        lineas.append(consola.amarillo('  RETIRADA/ENTREGADA: NO (aun en proceso)'))

    if track:
        lineas.append('-' * 58)
        lineas.append('  Ultimos eventos:')
        for t in track[:4]:
            nom = ((t.get('estatus') or {}).get('nombre') or '')
            ofi = ((t.get('oficina') or {}).get('nombre') or '')
            fecha = _fecha_corta(t.get('fechahorareal'))
            extra = ''
            if (t.get('receptor') or '').strip():
                extra = f"  [recibe: {t.get('receptor')}]"
            linea = f'    {fecha}  {nom}'
            if ofi:
                linea += f'  ({ofi})'
            lineas.append(linea + extra)

    return lineas


def verificar_guias(guias):
    ok = 0
    error = 0
    for i, guia in enumerate(guias, 1):
        print(f'\n  [{i}/{len(guias)}] Consultando guia {guia} ...')
        try:
            data = consultar(guia)
            cod = data.get('codrespuesta') or ''
            if cod not in ('COD_000',):
                print(f'  Respuesta de ZOOM: {data.get("mensaje") or cod}')
                error += 1
                continue
            for linea in formatear_resumen(guia, data):
                print(linea)
            ok += 1
        except Exception as e:
            print(f'  ERROR: {e}')
            error += 1

    print()
    print('=' * 58)
    print(consola.cian(consola.negrita(
        f'  RESUMEN: {ok} verificadas, {error} con error, total {len(guias)}')))
    print('=' * 58)


def main():
    consola.titulo('OPCION 3 - VERIFICAR ENVIOS ZOOM', ancho=58)

    args = sys.argv[1:]

    guias = []
    if args and args[0].lower().endswith('.pdf'):
        path = args[0]
        if not os.path.exists(path):
            print(f'No se encontro el PDF: {path}')
            return
        guias, npags = extraer_guias_pdf(path)
        print(f'  PDF: {path}')
        print(f'  Paginas: {npags}  |  Guias encontradas: {len(guias)}')
    elif args:
        for a in args:
            g = re.sub(r'\D', '', a)
            if g:
                guias.append(g)
    else:
        path = ask_pdf_dialog()
        if not path:
            print('  No seleccionaste ningun PDF. Cancelado.')
            return
        guias, npags = extraer_guias_pdf(path)
        print(f'  PDF: {path}')
        print(f'  Paginas: {npags}  |  Guias encontradas: {len(guias)}')

    if not guias:
        manual = input('  No se encontraron guias de 10 digitos en el PDF. '
                       'Escribelas separadas por espacio: ').strip()
        guias = [re.sub(r'\D', '', p) for p in re.split(r'[\s,;]+', manual) if re.sub(r'\D', '', p)]

    if not guias:
        print('  No hay guias para verificar. Cancelado.')
        return

    print('  Guias a verificar:')
    print('    ' + ', '.join(guias))
    confirmar = input('  Confirmar verificacion? [s/N]: ').strip().lower()
    if confirmar not in ('s', 'si', 'y', 'yes'):
        print('  Cancelado.')
        return

    verificar_guias(guias)


if __name__ == '__main__':
    main()
    try:
        input('Presiona Enter para cerrar...')
    except EOFError:
        pass
