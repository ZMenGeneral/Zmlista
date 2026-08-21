# -*- coding: utf-8 -*-
"""
Servidor de escaneo de códigos de barras.
Recibe escaneos desde una app móvil y los almacena en Supabase.
Muestra en tiempo real cada escaneo en la consola.

Uso:
    python servidor.py              (inicia en 0.0.0.0:8000)
    python servidor.py --port 9000  (puerto personalizado)
"""
import argparse
import html
import json
import os
import socket
import sys
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Optional
import uvicorn

import database
import comparar_factura

app = FastAPI(title='Servidor de Escaneo')

clientes_ws: list[WebSocket] = []


def obtener_ip_local():
    """Obtiene la IP local de la máquina."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


@app.post('/scan')
async def recibir_escaneo(data: dict):
    """Recibe un escaneo desde la app móvil."""
    codigo = str(data.get('codigo', '')).strip()[:100]
    datos_extra = str(data.get('datos_extra', '')).strip()[:200]

    if not codigo:
        return {'error': 'Código vacío'}

    cantidad, es_nuevo = database.guardar_escaneo(codigo, datos_extra)
    ahora = datetime.now().strftime('%H:%M:%S')

    pieza = database.buscar_barra(codigo)
    pieza_info = pieza.get('codigo_pieza') if pieza else None
    desc_info = pieza.get('descripcion', '') if pieza else ''

    if pieza_info:
        print(f'  [{ahora}] {consola_verde(codigo)} → {consola_cyan(pieza_info)} x{cantidad}')
    elif es_nuevo:
        print(f'  [{ahora}] {consola_verde(codigo)} x{cantidad} (nuevo)')
    else:
        print(f'  [{ahora}] {consola_amarillo(codigo)} x{cantidad} (+1)')

    respuesta = {
        'tipo': 'confirmacion',
        'codigo': codigo,
        'cantidad_total': cantidad,
        'nuevo': es_nuevo,
        'codigo_pieza': pieza_info,
        'descripcion': desc_info,
    }

    for ws in clientes_ws[:]:
        try:
            await ws.send_json(respuesta)
        except Exception:
            clientes_ws.remove(ws)

    return respuesta


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket para comunicación en tiempo real."""
    await websocket.accept()
    clientes_ws.append(websocket)
    ip = websocket.client.host if websocket.client else '?'
    print(f'  [WS] Cliente conectado: {ip}')

    stats = database.obtener_estadisticas()
    await websocket.send_json({
        'tipo': 'conexion',
        'mensaje': 'Conectado al servidor de escaneo',
        'estadisticas': stats,
    })

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get('tipo') == 'solicitar_lista':
                escaneos = database.obtener_todos()
                await websocket.send_json({
                    'tipo': 'lista',
                    'escaneos': escaneos,
                })
            elif msg.get('tipo') == 'solicitar_estadisticas':
                stats = database.obtener_estadisticas()
                await websocket.send_json({
                    'tipo': 'estadisticas',
                    'estadisticas': stats,
                })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f'  [WS] Error: {e}')
    finally:
        if websocket in clientes_ws:
            clientes_ws.remove(websocket)
        print(f'  [WS] Cliente desconectado: {ip}')


@app.get('/piezas')
async def listar_piezas(buscar: Optional[str] = None):
    """Lista piezas del catálogo. Filtra por código o descripción."""
    return database.listar_piezas(buscar or '')


@app.get('/barra/{codigo_barra}')
async def buscar_barra(codigo_barra: str):
    """Busca si un barcode tiene pieza asociada."""
    pieza = database.buscar_barra(codigo_barra)
    if pieza:
        return {'codigo_barra': codigo_barra, **pieza}
    return {'error': 'no encontrado'}


@app.post('/asociar')
async def asociar(data: dict):
    """Vincula un barcode a una pieza."""
    codigo_barra = str(data.get('codigo_barra', '')).strip()[:100]
    codigo_pieza = str(data.get('codigo_pieza', '')).strip()[:100]
    if not codigo_barra or not codigo_pieza:
        return {'error': 'Faltan campos'}
    database.asociar_barra(codigo_barra, codigo_pieza)
    print(f'  [ASOC] {consola_cyan(codigo_barra)} → {consola_cyan(codigo_pieza)}')
    return {'ok': True, 'codigo_barra': codigo_barra, 'codigo_pieza': codigo_pieza}


@app.post('/cargar_piezas')
async def cargar_piezas(data: dict):
    """Recibe [{codigo_pieza, descripcion}] y los guarda en Supabase."""
    mapeos = data.get('piezas', [])
    if not mapeos:
        return {'error': 'Sin datos'}
    n = database.cargar_piezas(mapeos)
    print(f'  [PIEZAS] Cargadas {consola_verde(str(n))} piezas')
    return {'ok': True, 'insertadas': n}


@app.post('/comparar')
async def comparar(data: dict):
    """Recibe la ruta de un PDF de factura y devuelve sus items."""
    ruta = str(data.get('ruta', '')).strip()
    if not ruta or not os.path.exists(ruta):
        return {'error': 'Archivo no encontrado'}
    try:
        resultado = comparar_factura.extraer_items_factura(ruta)
        n = len(resultado['items'])
        print(f'  [FACTURA] {consola_cyan(resultado["factura"])} → {n} items')
        return resultado
    except Exception as e:
        return {'error': str(e)}


@app.get('/')
async def pagina_principal():
    """Página web básica para ver los escaneos."""
    escaneos = database.obtener_todos()
    stats = database.obtener_estadisticas()

    filas = ''
    for e in escaneos:
        fecha = e['fecha_escaneo'][:16].replace('T', ' ')
        codigo_safe = html.escape(str(e["codigo"]))
        datos_safe = html.escape(str(e["datos_extra"])[:50])
        filas += f'''
        <tr>
            <td>{codigo_safe}</td>
            <td>{datos_safe}</td>
            <td class="cant">{e["cantidad"]}</td>
            <td>{fecha}</td>
        </tr>'''

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Escaneos de Códigos</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
            h1 {{ text-align: center; color: #00d4ff; margin-bottom: 10px; }}
            .stats {{ text-align: center; margin-bottom: 20px; color: #aaa; }}
            .stats span {{ color: #00d4ff; font-weight: bold; font-size: 1.2em; }}
            table {{ width: 100%; border-collapse: collapse; background: #16213e; border-radius: 8px; overflow: hidden; }}
            th {{ background: #0f3460; padding: 12px; text-align: left; color: #00d4ff; }}
            td {{ padding: 10px 12px; border-bottom: 1px solid #1a1a3e; }}
            tr:hover {{ background: #1a1a3e; }}
            .cant {{ font-weight: bold; color: #00ff88; text-align: center; font-size: 1.1em; }}
            .refresh {{ text-align: center; margin-top: 15px; }}
            .refresh a {{ color: #00d4ff; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>Escaneos de Códigos de Barras</h1>
        <div class="stats">
            <span>{stats["codigos_unicos"]}</span> códigos únicos |
            <span>{stats["unidades_totales"]}</span> unidades totales
        </div>
        <table>
            <tr><th>Código</th><th>Datos Extra</th><th>Cantidad</th><th>Fecha</th></tr>
            {filas}
        </table>
        <div class="refresh"><a href="/">↻ Actualizar</a></div>
    </body>
    </html>'''


def consola_verde(texto):
    return f'\033[1;92m{texto}\033[0m'


def consola_amarillo(texto):
    return f'\033[1;93m{texto}\033[0m'


def consola_cyan(texto):
    return f'\033[1;96m{texto}\033[0m'


def generar_qr_terminal(url):
    """Genera un QR en la terminal usando caracteres ASCII."""
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    lines = []
    for row in matrix:
        linea = ''
        for cell in row:
            linea += '██' if cell else '  '
        lines.append(linea)
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Servidor de escaneo de códigos')
    parser.add_argument('--port', type=int, default=8000, help='Puerto (default: 8000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    args = parser.parse_args()

    ip = obtener_ip_local()
    url = f'http://{ip}:{args.port}'

    print()
    print('=' * 55)
    print('  SERVIDOR DE ESCANEO DE CODIGOS DE BARRAS')
    print('=' * 55)
    print()
    print(f'  IP local: {consola_verde(ip)}')
    print(f'  Puerto:   {consola_verde(args.port)}')
    print()
    print(f'  URL App:      {consola_amarillo(url)}')
    print(f'  WebSocket:    {consola_amarillo(f"ws://{ip}:{args.port}/ws")}')
    print(f'  API Scan:     {consola_amarillo(f"http://{ip}:{args.port}/scan")}')
    print()
    print('  Escanea para conectar desde el celular:')
    print()
    print(generar_qr_terminal(url))
    print()
    print('  Esperando escaneos...')
    print('-' * 55)
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
