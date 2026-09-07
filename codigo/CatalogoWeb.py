# -*- coding: utf-8 -*-
"""
CatalogoWeb.py
OPCION 15 - CATALOGO WEB:
    Servidor local (FastAPI) que muestra nuestro catalogo de piezas (la
    tabla 'piezas' de Supabase con codigo, descripcion y marca) en el
    navegador. Al hacer clic en una pieza, consulta el sitio web del
    fabricante (best effort) buscando el codigo y muestra las imagenes e
    informacion encontradas, con enlaces directos a la busqueda del
    fabricante.

    El servidor se abre automaticamente en el navegador (http://127.0.0.1)
    y tambien queda disponible en la red local para celulares/otros PCs.

    Endpoints:
        GET /                       -> pagina web del catalogo
        GET /api/catalogo           -> lista completa de piezas (con cache)
        GET /api/fabricante?codigo&marca  -> consulta best effort al fabricante
"""
import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

import consola
import fabricantes
from supabase_client import listar_piezas, SupabaseError

CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_CODIGO)
sys.path.insert(0, CARPETA_PROYECTO)

CACHE_SEGUNDOS = 600
_cache = {'ts': 0, 'piezas': []}


def _ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def _puerto_libre(inicio=8001):
    for puerto in range(inicio, inicio + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', puerto))
                return puerto
            except OSError:
                continue
    return inicio


def _catalogo():
    """Lista de piezas con cache en memoria (se refresca cada 10 min)."""
    if (time.time() - _cache['ts']) > CACHE_SEGUNDOS or not _cache['piezas']:
        _cache['piezas'] = listar_piezas()
        _cache['ts'] = time.time()
    return _cache['piezas']


def crear_app():
    app = FastAPI(title='Catalogo ZMlista')

    @app.get('/', response_class=HTMLResponse)
    def portada():
        return PAGINA_HTML

    @app.get('/api/catalogo')
    def api_catalogo(marca: str = '', q: str = ''):
        try:
            piezas = _catalogo()
        except SupabaseError as e:
            return {'error': str(e), 'piezas': []}
        m = marca.strip().upper()
        b = q.strip().upper()
        if m:
            piezas = [p for p in piezas if (p.get('marca') or '').upper() == m]
        if b:
            piezas = [p for p in piezas
                      if b in (p.get('codigo_pieza') or '').upper()
                      or b in (p.get('descripcion') or '').upper()
                      or b in (p.get('marca') or '').upper()]
        return {
            'total': len(piezas),
            'piezas': piezas,
        }

    @app.get('/api/fabricante')
    def api_fabricante(codigo: str = Query(...), marca: str = ''):
        return fabricantes.consulta_fabricante(codigo, marca)

    return app


def main():
    try:
        piezas = listar_piezas()
        _cache['piezas'] = piezas
        _cache['ts'] = time.time()
    except SupabaseError as e:
        print(consola.rojo('  (ERROR) No se pudo leer el catalogo de Supabase:'))
        print('  ' + str(e))
        return

    puerto = _puerto_libre()
    ip = _ip_local()
    app = crear_app()

    threading.Timer(1.0, lambda: webbrowser.open(
        f'http://127.0.0.1:{puerto}')).start()

    print()
    print(f'  Catalogo web iniciado en {consola.verde(f"http://127.0.0.1:{puerto}")}')
    print(f'  Abre desde tu celular: {consola.verde(f"http://{ip}:{puerto}")}')
    print('  Ctrl+C para volver al menu.')
    print()
    try:
        uvicorn.run(app, host='0.0.0.0', port=puerto, log_level='warning')
    except KeyboardInterrupt:
        print()
        print('  Catalogo web detenido.')
    except SystemExit:
        print()
        print('  Catalogo web detenido.')


PAGINA_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Catalogo ZMlista</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Segoe UI, Arial, sans-serif; background: #f2f4f8; color: #1c2333; }
  header { background: #16294b; color: #fff; padding: 18px 22px; }
  header h1 { font-size: 20px; letter-spacing: .5px; }
  header p { font-size: 13px; opacity: .8; margin-top: 3px; }
  .wrap { max-width: 1100px; margin: 18px auto; padding: 0 14px; }
  .stats { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
  .stat { background: #fff; border: 1px solid #dfe3ec; border-radius: 10px;
          padding: 10px 16px; min-width: 120px; }
  .stat b { font-size: 20px; color: #16294b; display: block; }
  .stat span { font-size: 12px; color: #67718a; }
  .filtros { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
  .filtros input, .filtros select { padding: 10px 12px; border: 1px solid #cdd4e2;
          border-radius: 8px; font-size: 14px; background: #fff; }
  .filtros input { flex: 1; min-width: 220px; }
  .tabla { width: 100%; border-collapse: collapse; background: #fff;
           border: 1px solid #dfe3ec; border-radius: 10px; overflow: hidden; }
  .tabla th { background: #eef1f7; text-align: left; padding: 10px 12px;
              font-size: 12px; text-transform: uppercase; letter-spacing: .4px;
              position: sticky; top: 0; }
  .tabla td { padding: 9px 12px; border-top: 1px solid #eef1f7;
              font-size: 13px; vertical-align: middle; }
  .tabla tr:hover { background: #f7f9fd; }
  .cod { font-weight: 700; color: #16294b; }
  .marca { display: inline-block; background: #e6eefc; color: #1d4d8f;
           padding: 2px 8px; border-radius: 20px; font-size: 11px;
           font-weight: 600; white-space: nowrap; }
  .btn { background: #1d4d8f; color: #fff; border: 0; padding: 6px 12px;
         border-radius: 8px; font-size: 12px; cursor: pointer; }
  .btn:hover { background: #163a6e; }
  .panel { display: none; background: #fff; border: 1px solid #dfe3ec;
           border-radius: 10px; padding: 16px; margin-top: 16px; }
  .panel h2 { font-size: 16px; margin-bottom: 4px; }
  .panel .sub { color: #67718a; font-size: 12px; margin-bottom: 12px; }
  .panel .proveedor { font-weight: 600; color: #1d4d8f; font-size: 13px; }
  .panel .desc { font-size: 13px; margin: 8px 0; color: #333d55; }
  .imgs { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
  .imgs img { width: 120px; height: 120px; object-fit: contain; border: 1px solid #dfe3ec;
              border-radius: 8px; background: #fafbfe; cursor: zoom-in; }
  .enlaces a { display: inline-block; margin: 3px 6px 3px 0; color: #1d4d8f;
               font-size: 12px; }
  .btn-grande { display: inline-block; background: #2a9d3f; color: #fff;
               text-decoration: none; padding: 10px 18px; border-radius: 8px;
               font-size: 14px; margin-top: 6px; }
  .btn-grande:hover { background: #238034; }
  .variantes { margin: 10px 0; }
  .chip { display: inline-block; background: #eef1f7; border: 1px solid #cdd4e2;
          border-radius: 20px; padding: 2px 10px; font-size: 12px;
          font-weight: 600; color: #16294b; margin: 2px 4px 2px 0; }
  .chip b { color: #1d4d8f; }
  .seccion-titulo { font-size: 13px; font-weight: 700; color: #1d4d8f;
                    margin: 14px 0 6px; }
  .specs { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 18px;
           font-size: 13px; }
  .specs b { color: #16294b; }
  .tabla-scroll { max-height: 300px; overflow: auto; border: 1px solid #dfe3ec;
                  border-radius: 8px; }
  .apps-movil { display: none; }
  @media (max-width: 700px) {
    .tabla-scroll { display: none; }
    .apps-movil { display: block; font-size: 13px; }
    .apps-movil .card-app { border: 1px solid #dfe3ec; border-radius: 8px;
                            padding: 8px 10px; margin: 6px 0; background: #fafbfe; }
    .specs { grid-template-columns: 1fr; }
  }
  .aviso { font-size: 12px; color: #a16207; background: #fff6e4;
           padding: 8px 10px; border-radius: 8px; margin-top: 8px; }
  .cargando { color: #67718a; font-size: 13px; padding: 10px 0; }
  .vacio { text-align: center; color: #67718a; padding: 24px; font-size: 14px; }
  @media (max-width: 700px) {
    .oculto-movil { display: none; }
  }
</style>
</head>
<body>
<header>
  <h1>Catalogo ZMlista</h1>
  <p>Busca una pieza de nuestro historial y consulta su fabricante.</p>
</header>
<div class="wrap">
  <div class="stats">
    <div class="stat"><b id="stTotal">...</b><span>piezas</span></div>
    <div class="stat"><b id="stMarcas">...</b><span>marcas</span></div>
    <div class="stat"><b id="stVistos">0</b><span>resultados</span></div>
  </div>

  <div class="filtros">
    <input id="buscar" placeholder="Buscar por codigo, descripcion o marca...">
    <select id="fMarca"><option value="">Todas las marcas</option></select>
  </div>

  <table class="tabla" id="tabla">
    <thead><tr>
      <th>Codigo</th><th>Marca</th>
      <th class="oculto-movil">Descripcion</th><th></th>
    </tr></thead>
    <tbody id="cuerpo"></tbody>
  </table>
  <div class="vacio" id="vacio" style="display:none"></div>

  <div class="panel" id="panel">
    <div class="proveedor" id="pProveedor"></div>
    <h2 id="pCodigo"></h2>
    <div class="sub" id="pMarca"></div>
    <div class="cargando" id="pCargando">Buscando en el fabricante...</div>
    <div id="pContenido" style="display:none">
      <div class="desc" id="pDescripcion"></div>
      <div class="imgs" id="pImagenes"></div>
      <div class="variantes" id="pVariantes"></div>
      <div class="seccion-titulo">Especificaciones</div>
      <div class="specs" id="pSpecs"></div>
      <div class="seccion-titulo" id="pAppsTitulo"></div>
      <div class="tabla-scroll">
        <table class="tabla">
          <thead><tr><th>Marca</th><th>Modelo</th><th>A&ntilde;o</th><th>Motor</th></tr></thead>
          <tbody id="pAppsBody"></tbody>
        </table>
      </div>
      <div class="apps-movil" id="pAppsMovil"></div>
      <div class="enlaces" id="pEnlaces"></div>
      <a class="btn-grande" id="pEnlace" target="_blank" rel="noopener">Abrir en fabricante</a>
      <div class="aviso" id="pAviso"></div>
    </div>
  </div>
</div>

<script>
var piezas = [];
var marcas = [];

function esconder(el) { el.style.display = 'none'; }
function mostrar(el) { el.style.display = ''; }

function cargar() {
  fetch('/api/catalogo').then(function (r) { return r.json(); }).then(function (d) {
    if (d.error) { document.getElementById('vacio').textContent =
        'Error de Supabase: ' + d.error; mostrar(document.getElementById('vacio'));
        return; }
    piezas = d.piezas;
    var unicas = {};
    piezas.forEach(function (p) {
      var m = (p.marca || '-').trim();
      unicas[m] = (unicas[m] || 0) + 1;
    });
    marcas = Object.keys(unicas).sort();
    document.getElementById('stTotal').textContent = d.total;
    document.getElementById('stMarcas').textContent = marcas.length;
    var sel = document.getElementById('fMarca');
    marcas.forEach(function (m) {
      var o = document.createElement('option');
      o.value = m; o.textContent = m + ' (' + unicas[m] + ')';
      sel.appendChild(o);
    });
    pintar();
  });
}

function filtro() {
  var t = document.getElementById('buscar').value.toUpperCase();
  var m = document.getElementById('fMarca').value;
  return piezas.filter(function (p) {
    var ok = !t || (p.codigo_pieza || '').toUpperCase().indexOf(t) >= 0
             || (p.descripcion || '').toUpperCase().indexOf(t) >= 0
             || (p.marca || '').toUpperCase().indexOf(t) >= 0;
    if (m && (p.marca || '') !== m) ok = false;
    return ok;
  });
}

function pintar() {
  var cuerpo = document.getElementById('cuerpo');
  cuerpo.innerHTML = '';
  var res = filtro();
  document.getElementById('stVistos').textContent = res.length;
  if (!res.length) {
    var v = document.getElementById('vacio');
    v.textContent = 'Sin resultados para esa busqueda.';
    mostrar(v);
  } else {
    esconder(document.getElementById('vacio'));
  }
  res.forEach(function (p) {
    var tr = document.createElement('tr');
    var td1 = document.createElement('td');
    td1.className = 'cod';
    td1.textContent = p.codigo_pieza;
    var td2 = document.createElement('td');
    var b = document.createElement('span');
    b.className = 'marca';
    b.textContent = (p.marca || '-').trim() || '-';
    td2.appendChild(b);
    var td3 = document.createElement('td');
    td3.className = 'oculto-movil';
    td3.textContent = p.descripcion || '';
    var td4 = document.createElement('td');
    var btn = document.createElement('button');
    btn.className = 'btn';
    btn.textContent = 'Fabricante';
    btn.onclick = function () {
      verFabricante(p.codigo_pieza, p.marca || '');
    };
    td4.appendChild(btn);
    tr.appendChild(td1); tr.appendChild(td2);
    tr.appendChild(td3); tr.appendChild(td4);
    cuerpo.appendChild(tr);
  });
}

function verFabricante(codigo, marca) {
  var panel = document.getElementById('panel');
  mostrar(panel);
  document.getElementById('pCodigo').textContent = codigo;
  document.getElementById('pMarca').textContent = 'Marca: ' + (marca || 'VARIOS');
  document.getElementById('pProveedor').textContent = 'Consultando fabricante...';
  esconder(document.getElementById('pContenido'));
  mostrar(document.getElementById('pCargando'));
  try { panel.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  catch (e) { panel.scrollIntoView(); }
  var url = '/api/fabricante?codigo=' + encodeURIComponent(codigo) +
            '&marca=' + encodeURIComponent(marca);
  fetch(url).then(function (r) { return r.json(); }).then(function (d) {
    esconder(document.getElementById('pCargando'));
    mostrar(document.getElementById('pContenido'));
    document.getElementById('pProveedor').textContent =
        'Proveedor: ' + (d.proveedor || '-');
    if (d.tipo_pieza) {
      document.getElementById('pMarca').textContent +=
          '  |  ' + d.tipo_pieza;
    }
    document.getElementById('pDescripcion').textContent = d.descripcion || '';

    var vr = document.getElementById('pVariantes');
    vr.innerHTML = '';
    (d.variantes || []).forEach(function (v) {
      var c = document.createElement('span');
      c.className = 'chip';
      c.innerHTML = '<b>' + v.numero + '</b>' +
          (v.tipo ? ' &middot; ' + v.tipo : '');
      vr.appendChild(c);
    });
    if (!(d.variantes || []).length) { vr.innerHTML = ''; }

    var imgs = document.getElementById('pImagenes');
    imgs.innerHTML = '';
    (d.imagenes || []).slice(0, 8).forEach(function (img) {
      var a = document.createElement('a');
      a.href = img; a.target = '_blank'; a.rel = 'noopener';
      var e = document.createElement('img');
      e.src = img; e.loading = 'lazy';
      e.onerror = function () { e.style.display = 'none'; };
      a.appendChild(e);
      imgs.appendChild(a);
    });
    if (!(d.imagenes || []).length) {
      imgs.innerHTML = '<span class="aviso" style="display:block">Sin imagen del producto: abre el enlace del fabricante.</span>';
    }

    var specs = document.getElementById('pSpecs');
    specs.innerHTML = '';
    (d.specs || []).forEach(function (s) {
      var fi = document.createElement('div');
      fi.innerHTML = '<b>' + s.nombre + ':</b> ' + s.valor;
      specs.appendChild(fi);
    });
    if (!(d.specs || []).length) { esconder(specs); }

    var appsTitulo = document.getElementById('pAppsTitulo');
    var appsBody = document.getElementById('pAppsBody');
    var appsMovil = document.getElementById('pAppsMovil');
    appsBody.innerHTML = '';
    appsMovil.innerHTML = '';
    var apps = d.aplicaciones || [];
    if (apps.length) {
      appsTitulo.textContent = 'Autos donde aplica (' + apps.length + ')';
      apps.forEach(function (a) {
        var tr = document.createElement('tr');
        [a.marca, a.modelo, a.ano, a.motor].forEach(function (v) {
          var td = document.createElement('td');
          td.textContent = v || '';
          tr.appendChild(td);
        });
        appsBody.appendChild(tr);
        var card = document.createElement('div');
        card.className = 'card-app';
        card.textContent = (a.marca || '') + ' ' + (a.modelo || '') +
            ' - ' + (a.ano || '');
        if (a.motor) card.textContent += ' (' + a.motor + ')';
        appsMovil.appendChild(card);
      });
    } else {
      esconder(appsTitulo);
    }

    var ens = document.getElementById('pEnlaces');
    ens.innerHTML = '';
    (d.enlaces || []).forEach(function (en) {
      var a = document.createElement('a');
      a.href = en; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = 'Enlace: ' + en;
      ens.appendChild(a);
    });

    document.getElementById('pEnlace').href = d.buscar_url || '#';
    var aviso = document.getElementById('pAviso');
    if (d.error) {
      aviso.innerHTML = d.error;
    } else if (d.tipo === 'ficha' || (d.imagenes && d.imagenes.length)) {
      aviso.innerHTML = '';
    } else {
      aviso.innerHTML = 'Este fabricante no permite extraer datos automaticamente. Abre el enlace del fabricante para ver la pieza y sus aplicaciones.';
    }
  }).catch(function () {
    esconder(document.getElementById('pCargando'));
    mostrar(document.getElementById('pContenido'));
    var aviso = document.getElementById('pAviso');
    aviso.innerHTML = 'La consulta al fabricante fallo. Abre el enlace manualmente.';
    mostrar(aviso);
  });
}

document.getElementById('buscar').addEventListener('input', pintar);
document.getElementById('fMarca').addEventListener('change', pintar);
cargar();
</script>
</body>
</html>
"""


if __name__ == '__main__':
    main()