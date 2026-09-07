# -*- coding: utf-8 -*-
"""
fabricantes.py
Conectores "best effort" hacia los sitios web de los fabricantes de piezas.

Para cada marca del catalogo define: proveedor, URL base y URL de busqueda.

Tipos de conector:
  'ficha_cloyes'  # Ficha COMPLETA por codigo en Cloyes/LINDeco (administrable via
                  # AJAX publico): foto real del producto, descripcion,
                  # especificaciones y tabla de aplicaciones (ano/marca/modelo/
                  # motor).
  'pagina'        # Se descarga la pagina de resultados (sitios WordPress) y se
                  # extraen titulo, descripcion e imagenes del producto.
  'enlace'        # El sitio es una app con JavaScript (SPA/SAP) sin busqueda
                  # estable: solo se devuelve el enlace para abrir en el
                  # navegador.

La extraccion en vivo es opcional: si falla (anti-bot, cambio de estructura o
timeout), la consulta regresa ok=True con solo el enlace de busqueda para que
el usuario abra el sitio manualmente.
"""
import html
import re
import urllib.parse
from html.parser import HTMLParser

import requests

TIMEOUT = 12
_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/126.0.0.0 Safari/537.36'),
}
MAX_IMAGENES = 8
MAX_ENLACES = 8

CLOYES_AJAX = 'https://cloyes.com/wp-admin/admin-ajax.php'
CLOYES_ASSETS = 'https://cloyes.com/wp-content/uploads/CloyesAssets/'

DRIV_PART_URL = ('https://www.drivparts.com/content/loc-latam/loc-mx/'
                 'fmmp-corporate/es_MX/part-details.html')

# brandCode que usa el buscador de piezas de DRiV (part-details.html) para
# cada marca de Federal-Mogul del catalogo.
DRIV_BRAND_CODES = {
    'SEALED POWER': 'BDBR',
    'FEL-PRO': 'BCWV',
    'NATIONAL OIL SEALS': 'BCZK',
    'MOOG': 'BCCH',
    'CHAMPION': 'BBKH',
}

# Imagenes que ya aparecieron en la pagina de OTRO codigo: son decorativas
# del sitio (logos, banners) y se descartan.
_IMG_COMUNES = {}


CONECTORES = [
    {
        'marcas': ['CLOYES', 'LINDECO', 'DYNAGEAR', 'CY-LENT'],
        'proveedor': 'Cloyes / LINDeco',
        'base': 'https://cloyes.com',
        'buscar': 'https://cloyes.com/part-finder/?partno={codigo}',
        'tipo': 'ficha_cloyes',
    },
    {
        'marcas': ['MELLING', 'MELL-GEAR'],
        'proveedor': 'Melling Engine Parts',
        'base': 'https://melling.com',
        'buscar': 'https://melling.com/?s={codigo}',
        'tipo': 'pagina',
    },
    {
        'marcas': ['HASTINGS'],
        'proveedor': 'Hastings Piston Rings',
        'base': 'https://hastingspistonrings.com',
        'buscar': 'https://hastingspistonrings.com/?s={codigo}',
        'tipo': 'pagina',
    },
    {
        'marcas': ['SEALED POWER', 'FEL-PRO', 'NATIONAL OIL SEALS', 'MOOG',
                   'CHAMPION'],
        'proveedor': 'Federal-Mogul (DRiV)',
        'base': 'https://www.drivparts.com/',
        'buscar': 'https://www.drivparts.com/',
        'tipo': 'enlace',
    },
    {
        'marcas': ['MORESA'],
        'proveedor': 'Dacomsa / Moresa',
        'base': 'https://dacomsa.com',
        'buscar': 'https://dacomsa.com/dacomsastorefront/dacomsa/es',
        'tipo': 'enlace',
    },
    {
        'marcas': ['DURA-BOND'],
        'proveedor': 'Dura-Bond Bearing',
        'base': 'https://www.dura-bondbearing.com',
        'buscar': 'https://www.dura-bondbearing.com/parts-search/',
        'tipo': 'enlace',
    },
    {
        'marcas': [],
        'proveedor': 'Busqueda web',
        'base': 'https://www.bing.com/search?q={codigo}+{marca}',
        'buscar': 'https://www.bing.com/search?q={codigo}+{marca}',
        'tipo': 'enlace',
    },
]


def conector_para(marca):
    """Devuelve el conector para una marca (normalizada), o el generico."""
    marca = _normalizar(marca)
    for c in CONECTORES:
        if marca in _marcas_norm(c):
            return c
    return CONECTORES[-1]


def _marcas_norm(c):
    return [_normalizar(m) for m in c['marcas']]


def _normalizar(texto):
    texto = (texto or '').strip().upper()
    for a, b in (('Á', 'A'), ('É', 'E'), ('Í', 'I'), ('Ó', 'O'),
                 ('Ú', 'U'), ('Ñ', 'N'), ('Ü', 'U')):
        texto = texto.replace(a, b)
    return texto


def _componer(plantilla, codigo, marca):
    return (plantilla
            .replace('{codigo}', urllib.parse.quote_plus(codigo))
            .replace('{marca}', urllib.parse.quote_plus(marca or '')))


def _buscar_url(codigo, marca, con):
    """URL de busqueda/ficha segun el conector."""
    marca_norm = _normalizar(marca)
    if con['tipo'] == 'enlace' and marca_norm in DRIV_BRAND_CODES:
        pn = codigo
        if marca_norm == 'NATIONAL OIL SEALS' and len(pn) > 1 \
                and pn[0] in 'Nn':
            pn = pn[1:]
        bc = DRIV_BRAND_CODES[marca_norm]
        return (DRIV_PART_URL + '?part_number=' +
                urllib.parse.quote_plus(pn) + '&brand_code=' +
                urllib.parse.quote_plus(bc))
    return _componer(con['buscar'], codigo, marca)


def _abs(url, base):
    try:
        return urllib.parse.urljoin(base, url)
    except Exception:
        return url


def _mayor_srcset(srcset):
    """Toma la URL mas grande de un atributo srcset 'url 900w, url2 600w'."""
    mejor = ''
    ancho_mejor = -1
    for parte in srcset.split(','):
        parte = parte.strip()
        if not parte:
            continue
        trozos = parte.rsplit(' ', 1)
        url = trozos[0]
        ancho = 0
        if len(trozos) > 1:
            try:
                ancho = int(re.sub(r'\D', '', trozos[1]) or 0)
            except ValueError:
                ancho = 0
        if ancho >= ancho_mejor:
            ancho_mejor = ancho
            mejor = url
    return mejor


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titulo = None
        self.descripcion = None
        self.imagenes = []
        self.enlaces = []
        self._en_title = 0
        self._saltos = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = dict(attrs)
        if tag in ('script', 'style', 'noscript'):
            self._saltos += 1
            return
        if self._saltos:
            return
        if tag == 'title':
            self._en_title += 1
        elif tag == 'meta':
            nombre = (a.get('name') or a.get('property') or '').lower()
            contenido = (a.get('content') or '').strip()
            if nombre in ('description', 'og:description',
                          'twitter:description'):
                if not self.descripcion and len(contenido) > 25:
                    self.descripcion = contenido[:400]
            elif nombre in ('og:image', 'twitter:image'):
                if contenido and not contenido.lower().startswith('data:'):
                    self.imagenes.append(contenido)
        elif tag == 'img':
            src = (a.get('srcset') or '') and _mayor_srcset(a['srcset'])
            if not src:
                src = (a.get('src') or '').strip()
            if src and not src.lower().startswith('data:'):
                self.imagenes.append(src)
        elif tag == 'a':
            href = (a.get('href') or '').strip()
            if href and not href.startswith(('#', 'javascript:', 'mailto:')):
                self.enlaces.append(href)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('script', 'style', 'noscript') and self._saltos:
            self._saltos -= 1
        elif tag == 'title':
            self._en_title = 0

    def handle_data(self, data):
        if self._en_title and not self._saltos:
            self.titulo = (self.titulo or '') + ' ' + data.strip()


def _imagenes_jsonld(texto):
    """Busca URLs de imagen en bloques JSON-LD (schema.org)."""
    encontradas = []
    for m in re.finditer(r'"(?:image|thumbnailUrl)"\s*:\s*"([^"]+)"', texto):
        url = html.unescape(m.group(1))
        if url and not url.startswith('data:'):
            encontradas.append(url)
    return encontradas


def _filtrar_comunes(imagenes, codigo):
    """Descarta imagenes ya vistas en la pagina de OTRO codigo (decorativas)."""
    activas = []
    marca = codigo.upper()
    for i in imagenes:
        otros = _IMG_COMUNES.setdefault(i, set())
        if marca not in otros:
            otros.add(marca)
            activas.append(i)
    return activas


def _parsear_pagina(texto, base_url, codigo):
    p = _Parser()
    try:
        p.feed(texto)
    except Exception:
        pass

    codigo_low = (codigo or '').lower()
    imagenes = [_abs(i, base_url) for i in
                p.imagenes + _imagenes_jsonld(texto)]
    imagenes = [i for i in imagenes
                if not i.lower().endswith('.svg')
                and 'logo' not in i.lower()]
    unicas = []
    for i in imagenes:
        if i not in unicas:
            unicas.append(i)
    # Solo son confiables las imagenes que contienen el codigo en la URL
    # (foto real del producto). Logos, banners y decoracion se descartan.
    imagenes = [i for i in unicas if codigo_low in i.lower()]
    imagenes = _filtrar_comunes(imagenes, codigo)[:MAX_IMAGENES]

    enlaces = [_abs(e, base_url) for e in p.enlaces]
    buenos = [e for e in enlaces if codigo_low in e.lower()]
    unicos = []
    for e in buenos + [e for e in enlaces
                       if '/product' in e.lower() or '/part' in e.lower()]:
        if e not in unicos:
            unicos.append(e)
    enlaces = unicos[:MAX_ENLACES]

    titulo = html.unescape(p.titulo or '').strip() or None
    if titulo:
        titulo = re.sub(r'\s+', ' ', titulo)
    descripcion = re.sub(r'\s+', ' ', p.descripcion or '').strip() or None

    return {
        'titulo': titulo,
        'descripcion': descripcion,
        'imagenes': imagenes,
        'enlaces': enlaces,
    }


# ----------------------------------------------------------------
# CONECTOR CLOYES: ficha completa por codigo
# ----------------------------------------------------------------

def _post_cloyes(action, **datos):
    cuerpo = dict(datos)
    cuerpo['action'] = action
    r = requests.post(CLOYES_AJAX, headers=_HEADERS, data=cuerpo,
                      timeout=TIMEOUT)
    return r.json()


def _sin_html(texto):
    if not texto:
        return None
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = html.unescape(texto)
    return re.sub(r'\s+', ' ', texto).strip() or None


def _ficha_cloyes(codigo, marca):
    resultado = {
        'ok': True,
        'tipo': 'ficha',
        'marca': 'LINDeco / Cloyes',
        'proveedor': 'Cloyes / LINDeco',
        'tipo_pieza': None,
        'titulo': None,
        'descripcion': None,
        'imagenes': [],
        'aplicaciones': [],
        'specs': [],
        'variantes': [],
        'enlaces': [],
        'buscar_url': 'https://cloyes.com/part-finder/?partno=' +
                      urllib.parse.quote_plus(codigo),
        'base_url': 'https://cloyes.com',
        'error': None,
    }
    busqueda = _normalizar(codigo).replace(' ', '')

    try:
        d = _post_cloyes('cloyes_get_partno_search', partno=busqueda,
                         page='1', parttype='')
    except Exception as e:
        resultado['error'] = 'Cloyes no respondio: ' + str(e)[:120]
        return resultado

    opciones = d.get('result') or []
    if d.get('success') != 'true' or not opciones:
        resultado['error'] = 'El codigo no aparece en el catalogo de Cloyes.'
        return resultado

    exacto = None
    for o in opciones:
        if _normalizar(o.get('cloyes_part_number')).replace(' ', '') == \
                busqueda:
            exacto = o
            break
    elegido = exacto or opciones[0]

    resultado['variantes'] = [
        {'numero': o.get('cloyes_part_number'),
         'tipo': o.get('part_type'),
         'imagen': CLOYES_ASSETS + o['file_name'] if o.get('file_name') else None}
        for o in opciones
    ]
    resultado['buscar_url'] = 'https://cloyes.com/part-finder-single/?partno=' + \
        urllib.parse.quote(elegido.get('cloyes_part_number') or '')

    try:
        det = _post_cloyes('cloyes_get_part_details',
                           partno=elegido['cloyes_part_number'], crossref='')
    except Exception as e:
        resultado['error'] = 'Cloyes no respondio: ' + str(e)[:120]
        return resultado

    if det.get('success') != 'true':
        resultado['error'] = 'Cloyes no devolvio detalles de ' + \
                             str(elegido.get('cloyes_part_number'))
        return resultado

    res = (det.get('result') or [{}])[0]
    resultado['tipo_pieza'] = res.get('part_type')
    resultado['titulo'] = elegido.get('cloyes_part_number')
    resultado['descripcion'] = _sin_html(res.get('part_comments'))

    imagenes = []
    for i in (det.get('images') or []):
        if i.get('file_name'):
            imagenes.append(CLOYES_ASSETS + i['file_name'])
    resultado['imagenes'] = imagenes[:MAX_IMAGENES]

    apps = det.get('applications') or []
    resultado['aplicaciones'] = [
        {'ano': a.get('year'), 'marca': a.get('make'),
         'modelo': a.get('model'), 'motor': a.get('engine')}
        for a in apps
    ]
    resultado['specs'] = [
        {'nombre': s.get('attribute_name'), 'valor': s.get('attribute')}
        for s in (det.get('specs') or [])
    ]
    return resultado


# ----------------------------------------------------------------
# Consulta principal
# ----------------------------------------------------------------

def consulta_fabricante(codigo, marca):
    """Consulta el fabricante de un codigo y devuelve info best-effort."""
    marca = (marca or '').strip()
    con = conector_para(marca)
    buscar_url = _buscar_url(codigo, marca, con)

    if con['tipo'] == 'ficha_cloyes':
        return _ficha_cloyes(codigo, marca)

    resultado = {
        'ok': True,
        'tipo': con['tipo'],
        'marca': _normalizar(marca) or 'VARIOS',
        'proveedor': con['proveedor'],
        'buscar_url': buscar_url,
        'base_url': _componer(con['base'], codigo, marca),
        'titulo': None,
        'descripcion': None,
        'imagenes': [],
        'aplicaciones': [],
        'specs': [],
        'variantes': [],
        'enlaces': [],
        'error': None,
    }

    if con['tipo'] != 'pagina':
        return resultado

    try:
        r = requests.get(buscar_url, headers=_HEADERS, timeout=TIMEOUT,
                         allow_redirects=True)
        if r.status_code != 200 or len(r.text) < 200:
            resultado['error'] = 'El sitio del fabricante respondio ' + \
                                 str(r.status_code)
            return resultado
        extra = _parsear_pagina(r.text, r.url, codigo)
        resultado.update(extra)
    except Exception as e:
        resultado['error'] = str(e)[:150]
    return resultado