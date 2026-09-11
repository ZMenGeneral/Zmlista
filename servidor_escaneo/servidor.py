# -*- coding: utf-8 -*-
"""
Servidor de escaneo de códigos de barras.
Recibe escaneos desde el navegador del celular (aplicacion web) y los
almacena en Supabase. Muestra en tiempo real cada escaneo en la consola.

El acceso es SOLO por código QR: la URL lleva un token secreto (?t=TOKEN)
que autoriza la entrada; sin él todo devuelve 404. La cámara del navegador
exige HTTPS, así que se sirven dos puertos:
  - HTTP  8000  (API / app Expo legacy)
  - HTTPS 8443  (escaner web en el navegador del celular)

Uso:
    python servidor.py   (inicia ambos servidores y muestra el QR)
"""
import argparse
import hmac
import html
import ipaddress
import json
import os
import secrets
import socket
import sys
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn

import database
import comparar_factura

CARPETA_SERVIDOR = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_SERVIDOR)
sys.path.insert(0, os.path.join(CARPETA_PROYECTO, 'codigo'))

app = FastAPI(title='Servidor de Escaneo')

CARPETA_STATIC = os.path.join(CARPETA_SERVIDOR, 'static')
if os.path.isdir(CARPETA_STATIC):
    app.mount('/static', StaticFiles(directory=CARPETA_STATIC), name='static')

clientes_ws: list[WebSocket] = []


def _obtener_token():
    """Token secreto de acceso. Se genera una sola vez y se guarda en
    token_web.txt. Solo la URL del QR que lo incluya puede usar el servidor."""
    ruta = os.path.join(CARPETA_SERVIDOR, 'token_web.txt')
    if not os.path.exists(ruta):
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(secrets.token_hex(32))
    with open(ruta, encoding='utf-8') as f:
        return f.read().strip()


TOKEN_WEB = _obtener_token()

RUTAS_PROTEGIDAS = (
    '/', '/app', '/scan', '/piezas', '/asociar',
    '/cargar_piezas', '/comparar', '/limpiar', '/ultimo', '/facturas',
    '/explorar', '/borrar_codigo',
)


def _token_valido(valor):
    if not TOKEN_WEB or not valor:
        return False
    return hmac.compare_digest(valor, TOKEN_WEB)


@app.middleware('http')
async def _auth_web(request: Request, call_next):
    """Todo acceso requiere el token (query ?t= o cabecera X-Access-Token).
    Si no lo trae, devuelve 404 para que parezca que el servidor no existe."""
    ruta = request.url.path
    protegida = (ruta in RUTAS_PROTEGIDAS or ruta.startswith('/barra'))
    if protegida:
        valor = request.query_params.get('t') \
            or request.headers.get('X-Access-Token') or ''
        if not _token_valido(valor):
            return Response(status_code=404)
    return await call_next(request)


def _ips_locales():
    """Lista las IPs IPv4 no-loopback de la máquina."""
    ips = []
    try:
        _, _, lista = socket.gethostbyname_ex(socket.gethostname())
        ips = [ip for ip in lista if not ip.startswith('127.')]
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            ips = [ip]
        except Exception:
            ips = ['127.0.0.1']
    return ips


def obtener_ip_local():
    """Obtiene la IP local de la máquina.

    Si el hotspot móvil de Windows está activo (subred 192.168.137.x),
    los celulares se conectan a esa IP y se debe usar en el QR/URL.
    Si no, usa la IP de la red con salida a internet (comportamiento previo).
    """
    ips = _ips_locales()
    for ip in ips:
        if ip.startswith('192.168.137.'):
            return ip
    return ips[0]


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
    if not _token_valido(websocket.query_params.get('t', '')):
        await websocket.close(code=4401)
        return
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
                for e in escaneos:
                    pieza = database.buscar_barra(e.get('codigo', ''))
                    e['codigo_pieza'] = pieza.get('codigo_pieza') if pieza else None
                    e['descripcion'] = pieza.get('descripcion', '') if pieza else ''
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
    """Recibe la(s) ruta(s) de PDF(s) de factura y devuelve sus items.
    Si llegan varias rutas (ruta o rutas), las combina en un solo resultado
    (sumando cantidades por codigo) para comparar contra el escaneo."""
    rutas = data.get('rutas') or None
    if not rutas:
        ruta = str(data.get('ruta', '')).strip()
        rutas = [ruta] if ruta else []
    rutas = [r for r in rutas if r and os.path.exists(r)]
    if not rutas:
        return {'error': 'Archivo no encontrado'}
    try:
        comb_items = {}
        numeros = []
        for r in rutas:
            resultado = comparar_factura.extraer_items_factura(r)
            num = resultado.get('factura')
            if num:
                numeros.append(num)
            for it in resultado.get('items', []):
                cod = it.get('codigo')
                if cod not in comb_items:
                    comb_items[cod] = dict(it)
                else:
                    comb_items[cod]['cant'] = comb_items[cod].get('cant', 0) \
                        + it.get('cant', 0)
        items = list(comb_items.values())
        etiqueta = ', '.join(numeros) if numeros else \
            ', '.join(os.path.basename(r) for r in rutas)
        print(f'  [FACTURA] {consola_cyan(etiqueta)}'
              f' -> {len(items)} items ({len(rutas)} nota(s))')
        return {'factura': etiqueta, 'items': items, 'notas': len(rutas)}
    except Exception as e:
        return {'error': str(e)}


@app.delete('/limpiar')
async def limpiar():
    """Elimina todos los escaneos de la sesión."""
    database.limpiar()
    print(f'  [LIMPIAR] Todos los escaneos eliminados')
    return {'ok': True}


@app.delete('/ultimo')
async def borrar_ultimo():
    """Elimina el escaneo más reciente."""
    codigo = database.borrar_ultimo()
    if codigo:
        print(f'  [BORRAR] Último: {consola_amarillo(codigo)}')
        return {'ok': True, 'codigo': codigo}
    return {'ok': False, 'error': 'No hay escaneos'}


@app.delete('/borrar_codigo')
async def borrar_codigo(codigo: str = ''):
    """Elimina todos los escaneos de un código específico.
    Sirve para quitar un código leído por error desde el historial."""
    codigo = codigo.strip()
    if not codigo:
        return {'ok': False, 'error': 'Sin código'}
    n = database.borrar_codigo(codigo)
    print(f'  [BORRAR] Código {consola_amarillo(codigo)}: '
          f'{n} registro(s) eliminado(s)')
    return {'ok': True, 'codigo': codigo, 'eliminados': n}


@app.get('/facturas')
async def listar_facturas(buscar: Optional[str] = None, anio: Optional[int] = None):
    """Lista las facturas disponibles en la carpeta de red.
    Devuelve TODAS las del anio (actual por defecto) con opcion de buscar
    por numero de factura/nota (ej: N12345) y de indicar otro anio."""
    try:
        import AnalizarFacturas
        pdfs = AnalizarFacturas.obtener_facturas_anio(anio=anio, buscar=buscar)
        return {'facturas': pdfs}
    except Exception as e:
        return {'error': str(e), 'facturas': []}


@app.get('/explorar')
async def explorar(ruta: Optional[str] = None):
    """Explora la carpeta de facturas en arbol (muestra carpetas y archivos).
    ruta es la subcarpeta relativa (vacia = raiz). Devuelve carpetas y
    archivos con su ruta ABSOLUTA (para /comparar) y relativa (para navegar)."""
    try:
        import AnalizarFacturas
        for candidata in (r'Z:\ZM Autopartes\FACTURAS',
                          AnalizarFacturas.RUTA_BASE):
            if os.path.isdir(candidata):
                base = candidata
                break
        else:
            base = AnalizarFacturas.RUTA_BASE

        ruta_rel = (ruta or '').strip().replace('\\', '/').strip('/')
        partes = [p for p in ruta_rel.split('/') if p and p not in ('.', '..')]
        objetivo = os.path.normpath(os.path.join(base, *partes))
        if os.path.commonpath([os.path.normpath(base), objetivo]) \
                != os.path.normpath(base):
            return {'error': 'Ruta invalida', 'carpetas': [], 'archivos': []}
        if not os.path.isdir(objetivo):
            return {'error': 'Carpeta no existe', 'carpetas': [], 'archivos': []}

        carpetas, archivos = [], []
        for nombre in sorted(os.listdir(objetivo)):
            ruta_item = os.path.join(objetivo, nombre)
            rel = '/'.join(partes + [nombre])
            if os.path.isdir(ruta_item):
                carpetas.append({'nombre': nombre, 'rel': rel, 'abs': ruta_item})
            else:
                archivos.append({'nombre': nombre, 'rel': rel, 'abs': ruta_item})
        print(f'  [EXPLORAR] "{objetivo}" -> '
              f'{len(carpetas)} carpeta(s), {len(archivos)} archivo(s)')
        return {
            'ruta': '/'.join(partes),
            'nombre': os.path.basename(objetivo) or 'FACTURAS',
            'carpetas': carpetas,
            'archivos': archivos,
        }
    except Exception as e:
        return {'error': str(e), 'carpetas': [], 'archivos': []}


@app.get('/', response_class=HTMLResponse)
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


@app.get('/app', response_class=HTMLResponse)
async def pagina_escaner():
    """Escáner de códigos en el navegador: replica la funcionalidad de la
    app Expo (escaneo, historial, piezas, asociar y comparacion con notas)."""
    return _HTML_ESCANER


_HTML_ESCANER = r'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Escáner de Códigos</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,Helvetica,Arial,sans-serif;background:#1a1a2e;color:#eee;padding:14px}
h1{text-align:center;color:#00d4ff;font-size:20px;margin-bottom:6px}
.subcon{text-align:center;color:#00ff88;font-size:11px;margin-bottom:10px}
.vista{display:none}
.vista.on{display:block}

/* botones */
.fila{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin:8px 0}
.btn{border:none;border-radius:12px;font-size:15px;font-weight:bold;color:#fff;padding:14px 20px}
.btn:active{opacity:.7}
.b-cyan{background:#00d4ff;color:#111}.b-pur{background:#9b59b6}.b-red{background:#e74c3c}
.b-ora{background:#e67e22}.b-azul{background:#0f3460}.b-gris{background:#666}
.btn.peq{padding:10px 16px;font-size:13px}

/* stats */
.stats{display:flex;gap:14px;justify-content:center;margin:6px 0 4px}
.stat{background:#16213e;border-radius:12px;padding:12px 22px;text-align:center;min-width:110px}
.stat b{font-size:26px;color:#00ff88;display:block}.stat span{font-size:11px;color:#888}

/* historial */
.tit{color:#888;font-size:13px;margin:10px 0 6px}
.item{background:#16213e;border-radius:8px;padding:10px 14px;margin-bottom:6px;
      display:flex;justify-content:space-between;align-items:center}
.item .cod{color:#00ff88;font-weight:bold;font-size:15px}
.item .bar{color:#666;font-size:11px;margin-top:1px}
.item .cant{color:#eee;font-size:16px;font-weight:bold}
.item .der{display:flex;align-items:center;gap:12px}
.item .xdel{width:30px;height:30px;border-radius:8px;background:#e74c3c;color:#fff;
            display:flex;align-items:center;justify-content:center;font-size:14px;
            cursor:pointer;flex:none}
.item .xedit{width:30px;height:30px;border-radius:8px;background:#00d4ff;
            display:flex;align-items:center;justify-content:center;font-size:15px;
            cursor:pointer;flex:none}
.item .xdel:active,.item .xedit:active{opacity:.7}
.vacio{color:#666;text-align:center;margin:30px 0;font-size:14px}

/* camara */
.vidWrap{position:relative;width:100%;max-width:480px;margin:0 auto;border-radius:12px;overflow:hidden;background:#000}
#video{width:100%;height:260px;object-fit:cover;display:block}
#frame{position:absolute;top:50%;left:50%;width:72%;height:120px;transform:translate(-50%,-50%);
       border:2px solid #00d4ff;border-radius:10px;box-shadow:0 0 0 2000px rgba(0,0,0,.35)}
.estado{text-align:center;margin:10px 0;font-size:14px;min-height:20px}
.ok{color:#00ff88;font-weight:bold}
.warn{color:#f39c12;font-weight:bold}
.err{color:#e74c3c}
.det{text-align:center;color:#888;font-size:12px;margin-bottom:8px;min-height:15px}

/* input */
.in{width:100%;padding:12px;border-radius:8px;border:none;font-size:15px;background:#0f3460;color:#fff;margin-bottom:8px}
.res button{display:block;width:100%;text-align:left;background:#16213e;color:#eee;border:1px solid #0f3460;
            padding:10px 12px;border-radius:8px;margin:4px 0;font-size:13px}
.res button b{color:#00ff88}

/* facturas */
.grupo{background:#16213e;border-radius:8px;margin-bottom:8px;overflow:hidden}
.grupo .head{display:flex;justify-content:space-between;padding:12px 14px;background:#0f3460}
.grupo .mes{color:#00d4ff;font-weight:bold;font-size:14px}
.grupo .n{color:#888;font-size:12px}
.grupo .cuerpo{padding:8px}
.fact{display:flex;align-items:center;gap:10px;background:#0f3460;padding:8px 10px;border-radius:6px;margin-bottom:4px}
.fact .chk{width:22px;height:22px;border-radius:5px;border:2px solid #888;flex:none;display:flex;align-items:center;justify-content:center;color:#1a1a2e;font-weight:bold}
.fact.sel{background:#1a4a4a}.fact.sel .chk{background:#00ff88;border-color:#00ff88}
.fact .inf{flex:1}.fact .nom{color:#eee;font-size:13px}.fact .fec{color:#666;font-size:11px}
.fact .ver{background:#00d4ff;color:#111;border-radius:6px;padding:6px 12px;font-size:12px;font-weight:bold}
.fact.carp{cursor:pointer}.fact.carp .chk{border:none;background:#0f3460;color:#00d4ff;font-size:15px}
#rutaExplorador{color:#aaa;font-size:12px;margin:8px 2px;min-height:16px;word-break:break-all}
#rutaExplorador .crumb{color:#00d4ff;cursor:pointer;text-decoration:underline}

/* resultado comparacion */
.sec{margin-bottom:10px}
.sec h3{font-size:14px;margin-bottom:6px;color:#eee}
.secli{max-height:200px;overflow:auto}
.citem{padding:8px 10px;border-radius:6px;margin-bottom:4px;display:flex;justify-content:space-between;font-size:13px}
.cli{background:#1a3a1a}.cli2{background:#3a1a1a}.cli3{background:#3a3a1a}
.citem b{color:#eee}.citem span{color:#888;font-size:11px}
.volverTop{text-align:center;margin:10px 0}
.volverTop a{color:#e74c3c;text-decoration:none;font-weight:bold}
</style>
</head>
<body>
<h1>Escáner de Códigos</h1>
<div class="subcon" id="estadoConex">Conectando...</div>

<!-- VISTA: INICIO -->
<div class="vista on" id="vInicio">
  <div class="stats">
    <div class="stat"><b id="stCod">0</b><span>CODIGOS</span></div>
    <div class="stat"><b id="stUni">0</b><span>UNIDADES</span></div>
  </div>
  <div class="fila">
    <button class="btn b-cyan" onclick="vista('vScan')">Escanear</button>
    <button class="btn b-pur" onclick="abrirFacturas()">Comparar</button>
  </div>
  <div class="fila">
    <button class="btn b-red peq" onclick="reiniciar()">Reiniciar</button>
    <button class="btn b-ora peq" onclick="borrarUltimo()">Borrar último</button>
  </div>
  <div class="tit">ÚLTIMOS ESCANEOS</div>
  <div id="listaH"></div>
</div>

<!-- VISTA: ESCANER -->
<div class="vista" id="vScan">
  <div class="vidWrap">
    <video id="video" muted playsinline></video>
    <div id="frame"></div>
  </div>
  <div class="estado" id="estadoScan">Presiona INICIAR</div>
  <div class="det" id="detScan"></div>
  <div class="fila">
    <button class="btn b-cyan" id="btnIni">Iniciar</button>
    <button class="btn b-red" id="btnDet">Detener</button>
    <button class="btn b-azul" onclick="vista('vInicio')">Volver</button>
  </div>
</div>

<!-- VISTA: PIEZAS -->
<div class="vista" id="vPiezas">
  <h1>Selecciona la Pieza</h1>
  <div class="subcon" id="piezaPendiente"></div>
  <input class="in" id="buscarPieza" placeholder="Buscar pieza..." oninput="buscarPiezas()">
  <div class="res" id="resPiezas"></div>
  <div class="fila"><button class="btn b-red" onclick="vista('vInicio')">Volver</button></div>
</div>

<!-- VISTA: FACTURAS -->
<div class="vista" id="vFact">
  <div class="fila" style="justify-content:space-between">
    <input class="in" id="buscarFact" placeholder="Buscar nota (ej: N12345)" style="flex:1;margin:0"
           onkeydown="if(event.key==='Enter')cargarFact()">
    <button class="btn b-cyan peq" onclick="cargarFact()">Buscar</button>
  </div>
  <div class="fila" style="justify-content:space-between;margin-top:6px">
    <button class="btn b-pur peq" onclick="mostrarExplorador()">📁 Carpetas</button>
    <button class="btn b-cyan peq" onclick="cargarFact()">📋 Por mes</button>
  </div>
  <div id="rutaExplorador"></div>
  <div id="gruposFact"></div>
  <div class="fila" id="btnCompararWrap"></div>
  <div class="fila"><button class="btn b-red" onclick="vista('vInicio')">Volver</button></div>
</div>

<!-- VISTA: RESULTADO -->
<div class="vista" id="vRes">
  <div class="volverTop"><a href="javascript:vista('vInicio')">← Volver</a></div>
  <h1>Resultado</h1>
  <div class="subcon" id="resFactura"></div>
  <div id="cuerpoRes"></div>
  <div class="fila"><button class="btn b-red" onclick="resetearComparacion()">Resetear</button></div>
</div>

<script src="/static/zxing.min.js"></script>
<script>
'use strict';
var T = (new URLSearchParams(location.search)).get('t') || '';
var escaneos = [];          // historial [{codigo,cantidad,codigo_pieza,descripcion,barra}]
var stats = { codigos_unicos: 0, unidades_totales: 0 };
var contadorScan = 0, ultimoCodigo = '', piezaActual = '', codigoPendiente = '';
var reader = null, activo = false, ultimoProcesado = '', ultimaVezProcesado = 0;
var lecturasFiltro = {};   // codigo -> {cant, t}: repeticiones consecutivas del mismo codigo
var facturasSel = {};
var busquedaFact = '';

function $(id){ return document.getElementById(id); }
function vista(nombre){
  if(nombre !== 'vScan') detenerScan();
  document.querySelectorAll('.vista').forEach(function(v){ v.classList.remove('on'); });
  $(nombre).classList.add('on');
}

/* ---------- WEB SOCKET (tiempo real, igual que la app) ---------- */
var wsApp = null;
function conectarWS(){
  try{
    var ws = new WebSocket('wss://' + location.host + '/ws?t=' + T);
    wsApp = ws;
    ws.onopen = function(){
      $('estadoConex').textContent = 'Conectado';
      try{ ws.send(JSON.stringify({tipo:'solicitar_lista'})); }catch(e){}
      try{ ws.send(JSON.stringify({tipo:'solicitar_estadisticas'})); }catch(e){}
    };
    ws.onmessage = function(ev){
      try{
        var m = JSON.parse(ev.data);
        if(m.tipo === 'conexion' && m.estadisticas){ stats = m.estadisticas; }
        if(m.tipo === 'estadisticas'){ stats = m.estadisticas; }
        if(m.tipo === 'lista'){ escaneos = m.escaneos || []; }
        pintarInicio();
      }catch(e){}
    };
    ws.onclose = function(){
      setTimeout(function(){
        try{ conectarWS(); }catch(e){}
      }, 3000);
    };
  }catch(e){}
}

/* ---------- helpers ---------- */
function escAttr(s){ return String(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'); }
function escHtml(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function api(url, opts){
  var o = opts || {};
  o.headers = Object.assign(o.headers || {}, { 'X-Access-Token': T });
  if(o.body && !o.headers['Content-Type']) o.headers['Content-Type']='application/json';
  return fetch(url, o).then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); });
}
function beep(ok){
  try{
    var C = window.AudioContext || window.webkitAudioContext;
    if(!C) return;
    var ctx = new C(), o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'square'; o.frequency.value = ok ? 1200 : 300;
    g.gain.setValueAtTime(0.08, ctx.currentTime);
    o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.15);
    setTimeout(function(){ ctx.close(); }, 300);
  }catch(e){}
}
function pintarInicio(){
  $('stCod').textContent = stats.codigos_unicos || 0;
  $('stUni').textContent = stats.unidades_totales || 0;
  var html = '';
  (escaneos||[]).slice(0,20).forEach(function(it){
    var tit = it.codigo_pieza || it.codigo;
    html += '<div class="item">'
      + '<div><div class="cod">'+escHtml(tit)+'</div>'
      + '<div class="bar">'+escHtml(it.codigo)+'</div>'
      + (it.descripcion ? '<div class="bar">'+escHtml(it.descripcion)+'</div>' : '')
      + '</div><div class="der"><div class="cant">x'+escHtml(String(it.cantidad))+'</div>'
      + '<div class="xedit" onclick="event.stopPropagation();reasignarEscan(this)" data-codigo="'+escAttr(it.codigo)+'" title="Corregir pieza">✏️</div>'
      + '<div class="xdel" onclick="event.stopPropagation();eliminarEscan(this)" data-codigo="'+escAttr(it.codigo)+'" title="Eliminar de la BD">✕</div></div></div>';
  });
  $('listaH').innerHTML = html || '<div class="vacio">Sin escaneos</div>';
}
function eliminarEscan(el){
  var codigo = el.getAttribute('data-codigo');
  if(!confirm('Eliminar el código '+codigo+' de la base de datos?')) return;
  api('/borrar_codigo?codigo='+encodeURIComponent(codigo), { method:'DELETE' })
    .then(function(r){
      if(r.ok){
        escaneos = (escaneos||[]).filter(function(h){ return h.codigo !== codigo; });
        stats = { codigos_unicos: escaneos.length,
                  unidades_totales: escaneos.reduce(function(s,h){ return s+h.cantidad; },0) };
        pintarInicio();
      } else {
        alert(r.error || 'No se pudo eliminar');
      }
    })
    .catch(function(){ alert('No se pudo eliminar'); });
  return false;
}
function reasignarEscan(el){
  var codigo = el.getAttribute('data-codigo');
  codigoPendiente = codigo;
  vista('vPiezas');
  $('piezaPendiente').textContent = 'Corrige la pieza del barcode: '+codigo;
  $('buscarPieza').value = '';
  buscarPiezas('');
  return false;
}
function actualizarTrasScan(msg){
  // msg: {codigo,cantidad_total,nuevo,codigo_pieza,descripcion}
  escaneos = escaneos.filter(function(h){ return h.codigo !== msg.codigo; });
  escaneos.unshift({
    codigo: msg.codigo, cantidad: msg.cantidad_total,
    codigo_pieza: msg.codigo_pieza || null,
    descripcion: msg.descripcion || '', barra: msg.codigo,
  });
  stats.codigos_unicos = stats.codigos_unicos + (msg.nuevo ? 1 : 0);
  stats.unidades_totales = stats.unidades_totales + 1;
  pintarInicio();
}

/* ---------- ESCANER ---------- */
function iniciarScan(){
  if(activo) return;
  if(typeof ZXing === 'undefined'){ $('estadoScan').textContent = 'Libreria no disponible'; return; }
  reader = new ZXing.BrowserMultiFormatReader();
  reader.decodeFromConstraints(
    { video:{ facingMode:{ ideal:'environment' } }, audio:false },
    $('video'),
    function(result){
      if(!result) return;
      var t = result.getText(); if(!t) return;
      var ahora = Date.now();
      // Filtro anti-error: exige el MISMO codigo N leido consecutivamente
      // en poco tiempo antes de aceptar. Asi un destello o lectura suelta
      // (ej. confundir '7' con '1') no llega a registrarse.
      var lec = lecturasFiltro[t];
      if(!lec || ahora - lec.t > 1800){ lecturasFiltro[t] = {cant:1, t:ahora}; return; }
      lec.cant++; lec.t = ahora;
      if(lec.cant < 2) return;
      var veces = lec.cant;
      delete lecturasFiltro[t];
      if(ahora - ultimaVezProcesado < 1200) return;
      if(t === ultimoProcesado && ahora - ultimaVezProcesado < 2500) return;
      ultimaVezProcesado = ahora;
      procesar(t);
    })
  .then(function(){ activo = true; $('estadoScan').textContent = 'Escaneando...'; })
  .catch(function(e){ $('estadoScan').className='estado err'; $('estadoScan').textContent='No se pudo abrir la camara'; });
}
function detenerScan(){
  if(reader){ try{ reader.reset(); }catch(e){} reader = null; }
  lecturasFiltro = {};
  var vid = $('video');
  if(vid && vid.srcObject){
    try{ var st = vid.srcObject; (st.getTracks && st.getTracks()).forEach(function(tr){ tr.stop(); }); }catch(e){}
    vid.srcObject = null;
  }
  activo = false;
  $('estadoScan').textContent = 'Camara detenida';
}
function procesar(codigo){
  contadorScan++; ultimoCodigo = codigo;
  $('detScan').textContent = '';
  api('/scan', { method:'POST', body: JSON.stringify({ codigo:codigo, datos_extra:'' }) })
  .then(function(d){
    if(d.codigo_pieza){
      beep(true); piezaActual = d.codigo_pieza;
      $('estadoScan').className = 'estado ok';
      $('estadoScan').textContent = '✓ '+d.codigo_pieza+'  (total: x'+d.cantidad_total+')';
      $('detScan').textContent = d.descripcion || '';
      actualizarTrasScan(d);
    } else {
      beep(false);
      codigoPendiente = codigo;
      $('estadoScan').className = 'estado warn';
      $('estadoScan').textContent = 'Sin asociar: '+codigo;
      $('detScan').textContent = 'Selecciona la pieza';
      actualizarTrasScan(d);
      abrirPiezas(codigo);
    }
    setTimeout(function(){ piezaActual=''; }, 2500);
  })
  .catch(function(){ $('estadoScan').className='estado err'; $('estadoScan').textContent='Error al enviar el escaneo'; });
}
$('btnIni').addEventListener('click', iniciarScan);
$('btnDet').addEventListener('click', detenerScan);

/* ---------- PIEZAS (codigo sin asociar) ---------- */
function abrirPiezas(codigo){
  vista('vPiezas');
  $('piezaPendiente').textContent = 'Barcode: '+codigo;
  $('buscarPieza').value = '';
  buscarPiezas('');
}
function buscarPiezas(){
  var q = $('buscarPieza').value || '';
  api('/piezas?buscar='+encodeURIComponent(q), {})
    .then(function(arr){
      var out = '';
      (arr||[]).slice(0,12).forEach(function(p){
        var nom = p.descripcion||''.replace(/'/g,'&#39;');
        out += '<button data-code="'+escAttr(p.codigo_pieza)+'" data-desc="'+escAttr(nom)+'" onclick="asociar(this)"><b>'+escHtml(p.codigo_pieza)+'</b> '+escHtml(nom)+'</button>';
      });
      $('resPiezas').innerHTML = out || '<div class="vacio">No se encontraron piezas</div>';
    })
    .catch(function(){ $('resPiezas').innerHTML = '<div class="vacio">Sin conexion</div>'; });
}
function asociar(btn){
  var code = btn.getAttribute('data-code');
  var desc = btn.getAttribute('data-desc');
  if(!codigoPendiente) return;
  var codigo = codigoPendiente;
  codigoPendiente = '';
  api('/asociar', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ codigo_barra: codigo, codigo_pieza: code }) })
  .then(function(){
    escaneos = escaneos.map(function(h){
      if((h.codigo === codigo || h.barra === codigo)){ h.codigo_pieza = code; h.descripcion = desc; }
      return h;
    });
    pintarInicio();
    vista('vInicio');
  })
  .catch(function(){ $('resPiezas').innerHTML = '<div class="vacio">No se pudo asociar</div>'; });
}

/* ---------- ACCIONES INICIO ---------- */
function reiniciar(){
  if(!confirm('¿Borrar todos los escaneos?')) return;
  api('/limpiar', { method:'DELETE' }).then(function(){ escaneos=[]; stats={codigos_unicos:0,unidades_totales:0}; pintarInicio(); }).catch(function(){});
}
function borrarUltimo(){
  if(escaneos.length===0){ alert('No hay escaneos para borrar.'); return; }
  api('/ultimo', { method:'DELETE' }).then(function(r){
    if(r.ok){ escaneos.shift(); stats.unidades_totales=Math.max(0,stats.unidades_totales-1);
      stats.codigos_unicos=Math.max(0,stats.codigos_unicos-1); pintarInicio(); }
  }).catch(function(){});
}

/* ---------- FACTURAS / COMPARAR ---------- */
function abrirFacturas(){
  if(escaneos.length===0){ alert('Escanea algunos productos primero.'); return; }
  vista('vFact'); mostrarExplorador();
}
function cargarFact(){
  modoFact = 'mes';
  $('rutaExplorador').innerHTML = '';
  api('/facturas?buscar='+encodeURIComponent(busquedaFact), {})
    .then(function(d){
      if(d.error) throw new Error(d.error);
      var grupos = agruparMes(d.facturas || []);
      var html='';
      grupos.forEach(function(g){
        html += '<div class="grupo"><div class="head"><span class="mes">'+g.mes+'</span>'
          + '<span class="n">'+g.items.length+' nota(s) ▼</span></div><div class="cuerpo">';
        g.items.forEach(function(p){
          var sel = facturasSel[p.ruta] ? ' sel' : '';
          html += '<div class="fact'+sel+'" onclick="toggleFact(this)" data-ruta="'+escAttr(p.ruta)+'">'
            + '<div class="chk">'+(facturasSel[p.ruta]?'✓':'')+'</div>'
            + '<div class="inf"><div class="nom">'+escHtml(p.nombre)+'</div>'
            + '<div class="fec">'+escHtml(p.fecha||'')+'</div></div>'
            + '<span class="ver" onclick="event.stopPropagation();verFact(this)">Ver</span></div>';
        });
        html += '</div></div>';
      });
      $('gruposFact').innerHTML = html || '<div class="vacio">Sin facturas</div>';
      pintarCompararBtn();
    })
    .catch(function(e){ $('gruposFact').innerHTML='<div class="vacio">'+(e.message||'Error')+'</div>'; });
}
function agruparMes(pdfs){
  var meses=['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO',
             'SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'];
  var grupos={};
  pdfs.forEach(function(p){
    var f=p.fecha, mes='Sin fecha';
    if(typeof f==='string' && f.length>=7){
      var partes=f.split('-').map(Number), mm=null;
      if(partes.length===3 && partes[0]>1000) mm=partes[1];
      else if(partes.length===2) mm=partes[1];
      if(mm && mm>=1 && mm<=12) mes=meses[mm-1];
      else { var may=f.toUpperCase(); mes=meses.find(function(m){return may.indexOf(m)>=0;})||'Sin fecha'; }
    } else if(f) { var may2=String(f).toUpperCase();
      mes=meses.find(function(m){return may2.indexOf(m)>=0;})||'Sin fecha'; }
    if(!grupos[mes]) grupos[mes]=[];
    grupos[mes].push(p);
  });
  var orden={}; meses.forEach(function(m,i){orden[m]=i;});
  return Object.keys(grupos).map(function(m){return {mes:m,items:grupos[m]};})
    .sort(function(a,b){return (orden[a.mes]??99)-(orden[b.mes]??99);});
}
function toggleFact(el){
  var ruta = el.getAttribute('data-ruta');
  if(facturasSel[ruta]) delete facturasSel[ruta];
  else facturasSel[ruta]=true;
  cargarFact();
}

/* ---------- EXPLORADOR DE CARPETAS ---------- */
var rutaArbol = '';
var modoFact = 'arbol';
function pintarRutaArbol(){
  var html='';
  var partes = rutaArbol.split('/').filter(Boolean);
  partes.forEach(function(p,i){
    html += '<span class="crumb" onclick="irRutaArbol('+i+')">'+escHtml(p)+'</span>';
    if(i<partes.length-1) html+= ' <span class="crumb-sep">/</span>';
  });
  $('rutaExplorador').innerHTML = rutaArbol ? 'Ruta: <span onclick="irRutaArbol(0)">[raíz]</span> / '+html : 'Ruta: [raíz]';
}
function irRutaArbol(hasta){
  rutaArbol = rutaArbol.split('/').slice(0,hasta).join('/');
  pintarExplorador();
}
function toggleFact(el){
  var ruta = el.getAttribute('data-ruta');
  if(facturasSel[ruta]) delete facturasSel[ruta];
  else facturasSel[ruta]=true;
  if(modoFact === 'arbol'){ pintarExplorador(); pintarCompararBtn(); }
  else cargarFact();
}
function mostrarExplorador(){
  modoFact = 'arbol';
  rutaArbol = '';
  pintarExplorador();
}
function pintarExplorador(){
  pintarRutaArbol();
  $('gruposFact').innerHTML = '<div class="vacio">Cargando...</div>';
  api('/explorar?ruta='+encodeURIComponent(rutaArbol), {})
    .then(function(d){
      if(d.error) throw new Error(d.error);
      var html = rutaArbol
        ? '<div class="grupo"><div class="fact carp" onclick="subirExplorador()">'
          + '<div class="chk">⬆</div><div class="inf"><div class="nom">Subir</div></div></div></div>'
        : '';
      (d.carpetas||[]).forEach(function(c){
        html += '<div class="fact carp" onclick="entrarExplorador(this)" data-rel="'+escAttr(c.rel)+'">'
          + '<div class="chk">📁</div><div class="inf"><div class="nom">'+escHtml(c.nombre)+'</div></div></div>';
      });
      (d.archivos||[]).forEach(function(f){
        var sel = facturasSel[f.abs] ? ' sel' : '';
        html += '<div class="fact'+sel+'" onclick="toggleFact(this)" data-ruta="'+escAttr(f.abs)+'">'
          + '<div class="chk">'+(facturasSel[f.abs]?'✓':'')+'</div>'
          + '<div class="inf"><div class="nom">'+escHtml(f.nombre)+'</div>'
          + '<div class="fec">'+escHtml(f.rel)+'</div></div>'
          + '<span class="ver" onclick="event.stopPropagation();verFact(this)">Ver</span></div>';
      });
      $('gruposFact').innerHTML = html || '<div class="vacio">Carpeta vacía</div>';
      pintarCompararBtn();
    })
    .catch(function(e){ $('gruposFact').innerHTML='<div class="vacio">'+(e.message||'Error')+'</div>'; });
}
function entrarExplorador(el){
  rutaArbol = el.getAttribute('data-rel');
  pintarExplorador();
}
function subirExplorador(){
  var partes = rutaArbol.split('/');
  partes.pop();
  rutaArbol = partes.join('/');
  pintarExplorador();
}
function verFact(el){
  var ruta = el.getAttribute('data-ruta');
  comparar([{ruta:ruta}]);
}
function pintarCompararBtn(){
  var n=Object.keys(facturasSel).length;
  $('btnCompararWrap').innerHTML = n>0
    ? '<button class="btn b-pur" onclick="confirmarComparar()">Comparar '+n+' nota(s) seleccionada(s)</button>'
    : '';
}
function confirmarComparar(){
  var lista=Object.keys(facturasSel).map(function(r){return {ruta:r};});
  if(lista.length===0){ alert('Marca al menos una nota para comparar.'); return; }
  comparar(lista);
}
function comparar(listaNotas){
  var rutas=listaNotas.map(function(f){return f.ruta;}).filter(Boolean);
  api('/comparar', { method:'POST', body: JSON.stringify({ rutas: rutas }) })
    .then(function(res){
      if(res.error) throw new Error(res.error);
      var esc={};
      escaneos.forEach(function(h){ var k=h.codigo_pieza||h.codigo; esc[k]=(esc[k]||0)+h.cantidad; });
      var fac={};
      res.items.forEach(function(it){ fac[it.codigo]=(fac[it.codigo]||0)+it.cant; });
      var coin=[],faltan=[],sobran=[];
      Object.keys(fac).forEach(function(c){
        if(esc[c]) coin.push({codigo:c,factura:fac[c],escaneado:esc[c]});
        else faltan.push({codigo:c,factura:fac[c]});
      });
      Object.keys(esc).forEach(function(c){ if(!fac[c]) sobran.push({codigo:c,escaneado:esc[c]}); });
      $('resFactura').textContent = 'Factura: '+(res.factura||'')+(rutas.length>1?' ('+rutas.length+' notas combinadas)':'');
      var html='';
      if(coin.length) html+=seccion('✅ Coinciden ('+coin.length+')','cli',coin.map(function(i){return '<b>'+i.codigo+'</b><span>factura: '+i.factura+' | escaneado: '+i.escaneado+'</span>';}));
      if(faltan.length) html+=seccion('❌ Faltan ('+faltan.length+')','cli2',faltan.map(function(i){return '<b>'+i.codigo+'</b><span>cant: '+i.factura+'</span>';}));
      if(sobran.length) html+=seccion('⚠️ Sobran ('+sobran.length+')','cli3',sobran.map(function(i){return '<b>'+i.codigo+'</b><span>escaneado: '+i.escaneado+'</span>';}));
      $('cuerpoRes').innerHTML = html || '<div class="vacio">Sin resultados</div>';
      vista('vRes');
    })
    .catch(function(e){ alert('No se pudo comparar: '+(e.message||e)); });
}
function seccion(tit,cls,items){
  return '<div class="sec"><h3>'+tit+'</h3><div class="secli">'
    + items.map(function(i){ return '<div class="citem '+cls+'"><div>'+i+'</div></div>'; }).join('')
    + '</div></div>';
}
function resetearComparacion(){
  api('/limpiar', { method:'DELETE' }).then(function(){
    escaneos=[]; stats={codigos_unicos:0,unidades_totales:0}; pintarInicio();
  }).catch(function(){});
  vista('vInicio');
}

/* ---------- ARRANQUE ---------- */
conectarWS();
pintarInicio();
window.addEventListener('beforeunload', function(){ detenerScan(); });
window.addEventListener('pagehide', function(){ detenerScan(); });
</script>
</body>
</html>'''


def consola_verde(texto):
    return f'\033[1;92m{texto}\033[0m'


def consola_amarillo(texto):
    return f'\033[1;93m{texto}\033[0m'


def consola_cyan(texto):
    return f'\033[1;96m{texto}\033[0m'


def generar_qr_terminal(url):
    """Genera un QR en la terminal usando caracteres ASCII (compacto:
    cada linea dibuja dos filas del QR con caracteres de medio bloque)."""
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    lines = []
    for r in range(0, len(matrix), 2):
        fila_sup = matrix[r]
        fila_inf = matrix[r + 1] if r + 1 < len(matrix) else [False] * len(matrix)
        linea = ''
        for sup, inf in zip(fila_sup, fila_inf):
            if sup and inf:
                linea += '█'
            elif sup and not inf:
                linea += '▀'
            elif not sup and inf:
                linea += '▄'
            else:
                linea += ' '
        lines.append(linea)
    return '\n'.join(lines)


def _certificado_autofirma():
    """Genera (si no existen) cert.pem y key.pem de autofirma con los nombres
    de host validos. El celular mostrara una advertencia que se acepta una
    sola vez; es necesaria para el acceso a la camara via HTTPS."""
    cert_dir = os.path.join(CARPETA_SERVIDOR, 'certs')
    os.makedirs(cert_dir, exist_ok=True)
    certf = os.path.join(cert_dir, 'cert.pem')
    keyf = os.path.join(cert_dir, 'key.pem')
    if os.path.exists(certf) and os.path.exists(keyf):
        return certf, keyf

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'ZMLISTA scanner')])
    san = [x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]
    for ip in _ips_locales():
        try:
            san.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except Exception:
            pass
    cert = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(keyf, 'wb') as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    with open(certf, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f'  [CERT] Certificado HTTPS generado en {consola_cyan(cert_dir)}')
    return certf, keyf


def iniciar_servidores():
    """Arranca los dos servidores en threads separados:
    - HTTP  8000: API / app Expo legacy
    - HTTPS 8443: escaner web en el navegador (necesita HTTPS para la camara)
    Retorna (puerto_http, puerto_https)."""
    import threading

    def correr(cfg):
        uvicorn.run(app, host='0.0.0.0', **cfg)

    th = threading.Thread(
        target=correr, kwargs={'cfg': {'port': 8000, 'log_level': 'warning'}},
        daemon=True)
    th.start()

    certf, keyf = _certificado_autofirma()
    th2 = threading.Thread(
        target=correr,
        kwargs={'cfg': {'port': 8443, 'log_level': 'warning',
                        'ssl_certfile': certf, 'ssl_keyfile': keyf}},
        daemon=True)
    th2.start()

    return 8000, 8443


def main():
    parser = argparse.ArgumentParser(description='Servidor de escaneo de códigos')
    parser.add_argument('--port', type=int, default=8000, help='Puerto (default: 8000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    args = parser.parse_args()

    puerto_http, puerto_https = iniciar_servidores()
    ip = obtener_ip_local()
    url = f'http://{ip}:{puerto_http}'
    url_web = f'https://{ip}:{puerto_https}/app?t={TOKEN_WEB}'

    print()
    print('=' * 60)
    print('  SERVIDOR DE ESCANEO DE CODIGOS DE BARRAS (WEB)')
    print('=' * 60)
    print()
    print(f'  IP local: {consola_verde(ip)}')
    print()
    print('  Escaner WEB en el navegador del celular.')
    print('  Acceso SOLO por este QR (lleva el codigo de autorizacion):')
    print()
    try:
        print(generar_qr_terminal(url_web))
    except ImportError:
        print('  (instala qrcode para ver el QR: pip install qrcode)')
    except Exception:
        pass
    print()
    print(f'  URL: {consola_amarillo(url_web)}')
    print(f'  API: {consola_amarillo(url)}')
    print()
    print('  En el celular: acepta la advertencia del certificado (una vez)')
    print('  y luego presiona INICIAR para usar la camara.')
    print('-' * 60)
    print()
    print('  Esperando escaneos...')
    print()

    while True:
        time.sleep(3600)


if __name__ == '__main__':
    main()
