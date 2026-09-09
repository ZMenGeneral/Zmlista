# -*- coding: utf-8 -*-
"""
HistorialPiezasDanadas.py
OPCION 13 - HISTORIAL DE PIEZAS DANADAS:
    Registra piezas danadas o devueltas con codigo, razon, vendedor,
    cliente e imagenes. Todo se almacena en Supabase y las imagenes
    se copian a la carpeta compartida en la red.

    Submenu:
        1. Registrar pieza danada
        2. Ver historial completo
        3. Buscar por codigo / vendedor / cliente
        4. Ver imagenes de un registro
        5. Cargar piezas con marca
        6. Reporte de piezas danadas por marca
        7. Salir
"""
import os
import sys
import json
import shutil
import uuid
import subprocess
from datetime import datetime

import consola
from supabase_client import (
    insertar_pieza_danada,
    listar_piezas_danadas,
    buscar_piezas_danadas,
    obtener_pieza_danada,
    eliminar_pieza_danada,
    upsert_pieza,
    upsert_piezas,
    listar_piezas,
    buscar_piezas_marca,
    SupabaseError,
)
try:
    from ConvertirListaExcel import parse_txt
except Exception:
    parse_txt = None

CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_CODIGO)
CARPETA_IMAGENES_RED = r'Z:\Angel Malaver\RESPALDOS\ZMlista\imagenes'


def _input(texto):
    try:
        return input(texto)
    except EOFError:
        return ''


def _enter():
    try:
        input('\n  Presiona Enter para continuar...')
    except EOFError:
        pass


def _seleccionar_imagenes():
    """Abre un dialogo para seleccionar una o varias imagenes.
    Devuelve lista de rutas seleccionadas."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    paths = filedialog.askopenfilenames(
        title='Selecciona las imagenes de la pieza',
        filetypes=[
            ('Imagenes', '*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp'),
            ('JPEG', '*.jpg;*.jpeg'),
            ('PNG', '*.png'),
            ('Todos los archivos', '*.*'),
        ],
    )
    root.destroy()
    return list(paths)


def _copiar_imagenes(rutas_origen):
    """Copia imagenes a la carpeta compartida en la red.
    Crea una subcarpeta con un ID corto para organizar.
    Devuelve lista de rutas destino (relativas a la carpeta imagenes)."""
    if not os.path.isdir(CARPETA_IMAGENES_RED):
        os.makedirs(CARPETA_IMAGENES_RED, exist_ok=True)

    carpeta_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    carpeta_destino = os.path.join(CARPETA_IMAGENES_RED, carpeta_id)
    os.makedirs(carpeta_destino, exist_ok=True)

    rutas_copiadas = []
    for ruta in rutas_origen:
        nombre = os.path.basename(ruta)
        destino = os.path.join(carpeta_destino, nombre)
        try:
            shutil.copy2(ruta, destino)
            rutas_copiadas.append(destino)
        except Exception as e:
            print(consola.amarillo(f'  No se pudo copiar {nombre}: {e}'))

    return rutas_copiadas


def _fecha_corta(iso_str):
    """Convierte un timestamp ISO a formato legible DD/MM/YYYY HH:MM."""
    if not iso_str:
        return '-'
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return str(iso_str)[:16]


def _fmt_listaregistros(registros):
    """Muestra una tabla resumida de registros."""
    lineas = []
    lineas.append(
        consola.negrita(
            f"  {'#':<4} {'CODIGO':<12} {'CANT':<6} {'FECHA':<18} {'VENDEDOR':<18} {'CLIENTE':<20} {'RAZON'}"
        )
    )
    print('  ' + '-' * 108)
    for i, r in enumerate(registros, 1):
        cod = consola.naranja(r.get('codigo', ''))
        cant = consola.naranja(str(r.get('cantidad', 1)))
        fecha = _fecha_corta(r.get('creado_en'))
        vendedor = r.get('vendedor') or '-'
        cliente = r.get('cliente') or '-'
        razon = (r.get('razon_dano') or '-')[:35]
        imgs = len(r.get('imagenes') or [])
        img_tag = f' [{consola.cian(str(imgs) + " img")}]' if imgs else ''
        print(f'  {i:<4} {cod:<12} {cant:<6} {fecha:<18} {vendedor:<18} {cliente:<20} {razon}{img_tag}')
    print('  ' + '-' * 108)


def _mostrar_detalle(reg):
    """Muestra el detalle completo de un registro."""
    print()
    print('=' * 60)
    print(consola.cian(consola.negrita('  DETALLE DE PIEZA DANADA')))
    print('=' * 60)
    print(f'  Codigo:          {consola.naranja(reg.get("codigo", ""))}')
    print(f'  Cantidad:        {consola.naranja(str(reg.get("cantidad", 1)))}')
    print(f'  Razon del dano:  {reg.get("razon_dano") or "-"}')
    print(f'  Razon devolucion:{reg.get("razon_devolucion") or "-"}')
    print(f'  Vendedor:        {reg.get("vendedor") or "-"}')
    print(f'  Cliente:         {reg.get("cliente") or "-"}')
    print(f'  Notas:           {reg.get("notas") or "-"}')
    print(f'  Fecha registro:  {_fecha_corta(reg.get("creado_en"))}')
    imgs = reg.get('imagenes') or []
    print(f'  Imagenes:        {len(imgs)} archivo(s)')
    for img in imgs:
        existe = consola.verde('OK') if os.path.exists(img) else consola.rojo('NO EXISTE')
        print(f'    - {os.path.basename(img)}  [{existe}]')
    print('=' * 60)


# ----------------------------------------------------------------
# OPCION 1: Registrar pieza danada
# ----------------------------------------------------------------
def registrar():
    consola.titulo('REGISTRAR PIEZA DANADA', ancho=50)

    ultimo_codigo = ''

    while True:
        print()
        print('-' * 50)
        codigo = _input('  Codigo de la pieza (ej: f7298): ').strip()
        if not codigo:
            print('  Debes ingresar un codigo.')
            continue

        razon_dano = _input('  Razon del dano: ').strip()
        if not razon_dano:
            print('  Debes indicar la razon del dano.')
            continue

        cantidad = _input('  Cantidad de piezas: ').strip()
        try:
            cantidad_int = max(1, int(float(cantidad)))
        except (ValueError, TypeError):
            print(consola.rojo('  Cantidad invalida. Debe ser un numero.'))
            continue

        razon_dev = _input('  Razon de devolucion (Enter si no aplica): ').strip()
        vendedor = _input('  Vendedor: ').strip()
        cliente = _input('  Cliente: ').strip()
        notas = _input('  Notas adicionales (Enter si no hay): ').strip()

        imagenes_rutas = []
        agregar_imgs = _input('  Deseas agregar imagenes? [s/N]: ').strip().lower()
        if agregar_imgs in ('s', 'si', 'y', 'yes'):
            while True:
                seleccion = _seleccionar_imagenes()
                if seleccion:
                    imagenes_rutas.extend(seleccion)
                    print(consola.verde(f'  {len(seleccion)} imagen(es) seleccionada(s).'))
                mas = _input('  Agregar mas imagenes? [s/N]: ').strip().lower()
                if mas not in ('s', 'si', 'y', 'yes'):
                    break

        print()
        print('-' * 50)
        print(consola.negrita('  RESUMEN:'))
        print(f'  Codigo:     {consola.naranja(codigo)}')
        print(f'  Cantidad:   {consola.naranja(cantidad_int)}')
        print(f'  Dano:       {razon_dano}')
        if razon_dev:
            print(f'  Devolucion: {razon_dev}')
        if vendedor:
            print(f'  Vendedor:   {vendedor}')
        if cliente:
            print(f'  Cliente:    {cliente}')
        if imagenes_rutas:
            print(f'  Imagenes:   {len(imagenes_rutas)} archivo(s)')
        if notas:
            print(f'  Notas:      {notas}')
        print('-' * 50)

        confirmar = _input('  Guardar este registro? [S/n]: ').strip().lower()
        if confirmar in ('n', 'no'):
            print('  Registro cancelado.')
            return

        imgs_copiadas = []
        if imagenes_rutas:
            print()
            print('  Copiando imagenes a la carpeta compartida...')
            imgs_copiadas = _copiar_imagenes(imagenes_rutas)
            if imgs_copiadas:
                print(consola.verde(f'  {len(imgs_copiadas)} imagen(es) copiada(s).'))
            else:
                print(consola.amarillo('  No se copiaron imagenes (error o cancelado).'))

        registro = {
            'codigo': codigo,
            'cantidad': cantidad_int,
            'razon_dano': razon_dano,
            'razon_devolucion': razon_dev or None,
            'vendedor': vendedor or None,
            'cliente': cliente or None,
            'imagenes': imgs_copiadas or [],
            'notas': notas or None,
        }

        try:
            insertar_pieza_danada(registro)
            print()
            print(consola.verde('  Registro guardado exitosamente en Supabase.'))
        except SupabaseError as e:
            print(consola.rojo(f'  Error de Supabase: {e}'))
            print('  El registro NO se guardo.')
            return

        ultimo_codigo = codigo
        print()
        otra = _input('  Registrar otra pieza con el MISMO codigo? [s/N]: ').strip().lower()
        if otra not in ('s', 'si', 'y', 'yes'):
            break


# ----------------------------------------------------------------
# OPCION 2: Ver historial completo
# ----------------------------------------------------------------
def ver_historial():
    consola.titulo('HISTORIAL COMPLETO - PIEZAS DANADAS', ancho=58)

    try:
        registros = listar_piezas_danadas()
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        return

    if not registros:
        print('  No hay registros en el historial todavia.')
        return

    print(f'\n  Total de registros: {consola.negrita(str(len(registros)))}')
    _fmt_listaregistros(registros)

    while True:
        print()
        print('  Ingresa el NUMERO de un registro para ver detalle.')
        print('  Enter para volver al submenu.')
        opcion = _input('  Registro: ').strip()
        if not opcion:
            break
        if opcion.isdigit() and 1 <= int(opcion) <= len(registros):
            _mostrar_detalle(registros[int(opcion) - 1])
            _enter()
        else:
            print(consola.amarillo('  Numero invalido.'))


# ----------------------------------------------------------------
# OPCION 3: Buscar
# ----------------------------------------------------------------
def buscar():
    consola.titulo('BUSCAR PIEZAS DANADAS', ancho=50)

    print('  Buscar por:')
    print('  1. Codigo')
    print('  2. Vendedor')
    print('  3. Cliente')
    print()
    campo_opcion = _input('  Opcion: ').strip()

    mapa = {'1': 'codigo', '2': 'vendedor', '3': 'cliente'}
    campo = mapa.get(campo_opcion)
    if not campo:
        print(consola.amarillo('  Opcion invalida.'))
        return

    valor = _input(f'  Buscar {campo}: ').strip()
    if not valor:
        print('  No ingresaste nada.')
        return

    try:
        resultados = buscar_piezas_danadas(campo, valor)
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        return

    if not resultados:
        print(f'  No se encontraron resultados para "{valor}".')
        return

    print(f'\n  Resultados: {consola.negrita(str(len(resultados)))} registro(s)')
    _fmt_listaregistros(resultados)

    while True:
        print()
        print('  Ingresa el NUMERO de un registro para ver detalle.')
        print('  Enter para volver al submenu.')
        opcion = _input('  Registro: ').strip()
        if not opcion:
            break
        if opcion.isdigit() and 1 <= int(opcion) <= len(resultados):
            _mostrar_detalle(resultados[int(opcion) - 1])
            _enter()
        else:
            print(consola.amarillo('  Numero invalido.'))


# ----------------------------------------------------------------
# OPCION 4: Ver imagenes de un registro
# ----------------------------------------------------------------
def ver_imagenes():
    consola.titulo('VER IMAGENES DE PIEZA DANADA', ancho=50)

    try:
        registros = listar_piezas_danadas()
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        return

    con_imagenes = [r for r in registros if r.get('imagenes')]
    if not con_imagenes:
        print('  No hay registros con imagenes.')
        return

    print(f'\n  Registros con imagenes: {len(con_imagenes)}')
    _fmt_listaregistros(con_imagenes)

    while True:
        print()
        print('  Ingresa el NUMERO de un registro para ver sus imagenes.')
        print('  Enter para volver al submenu.')
        opcion = _input('  Registro: ').strip()
        if not opcion:
            break
        if not opcion.isdigit() or not (1 <= int(opcion) <= len(con_imagenes)):
            print(consola.amarillo('  Numero invalido.'))
            continue

        reg = con_imagenes[int(opcion) - 1]
        imgs = reg.get('imagenes') or []
        print()
        print(consola.cian(consola.negrita(
            f'  Imagenes de {reg.get("codigo", "?")} ({len(imgs)} archivo(s)):')))
        print('-' * 60)
        for i, img in enumerate(imgs, 1):
            existe = os.path.exists(img)
            estado = consola.verde('Disponible') if existe else consola.rojo('No encontrada')
            print(f'    {i}. {os.path.basename(img)}  [{estado}]')
            print(f'       {consola.amarillo(img)}')
        print('-' * 60)

        abrir = _input('  Abrir carpeta de imagenes? [s/N]: ').strip().lower()
        if abrir in ('s', 'si', 'y', 'yes'):
            carpeta = os.path.dirname(imgs[0]) if imgs else None
            if carpeta and os.path.isdir(carpeta):
                subprocess.Popen(f'explorer "{carpeta}"')
            else:
                print(consola.rojo('  La carpeta no existe en la red.'))


# ----------------------------------------------------------------
# OPCION 5: Cargar piezas con marca (TXT / Excel / manual)
# ----------------------------------------------------------------
RUTA_TXT_LISTA = r'\\PRINCIPAL\a2admin\Empre001\REPORTS\LISTA DE PRECIO 2023.TXT'
CARPETA_TXT_LISTA = r'\\PRINCIPAL\a2admin\Empre001\REPORTS'
NOMBRE_TXT_LISTA = 'LISTA DE PRECIO 2023'


def _encontrar_txt_lista():
    """Devuelve la ruta del TXT de lista de precios en la red.
    Busca el nombre exacto y, si no, cualquier archivo que empiece con
    'LISTA DE PRECIO' en la carpeta. Si no hay nada, devuelve None."""
    import glob as _glob
    if os.path.exists(RUTA_TXT_LISTA):
        return RUTA_TXT_LISTA
    if os.path.isdir(CARPETA_TXT_LISTA):
        candidatos = _glob.glob(os.path.join(CARPETA_TXT_LISTA, 'LISTA DE PRECIO*'))
        if candidatos:
            candidatos.sort(key=os.path.getmtime, reverse=True)
            return candidatos[0]
    return None


def _cargar_desde_txt():
    import tkinter as tk
    from tkinter import filedialog

    ruta = _encontrar_txt_lista()
    if not ruta:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        ruta = filedialog.askopenfilename(
            title='Selecciona el archivo TXT de lista de precios',
            filetypes=[('Archivos TXT', '*.txt'), ('Todos los archivos', '*.*')],
            initialdir=CARPETA_TXT_LISTA if os.path.isdir(CARPETA_TXT_LISTA) else None,
        )
        root.destroy()
        if not ruta:
            return None
        print(consola.amarillo('  No estaba el archivo en la red; se selecciono manualmente.'))

    if parse_txt is None:
        print(consola.rojo('  No se pudo cargar el lector de TXT.'))
        return None

    try:
        filas = parse_txt(ruta)
    except Exception as e:
        print(consola.rojo(f'  Error leyendo el TXT: {e}'))
        return None

    result = []
    for f in filas:
        codigo = f.get('codigo', '').strip()
        if not codigo:
            continue
        result.append({
            'codigo_pieza': codigo,
            'descripcion': f.get('desc', '').strip(),
            'marca': f.get('prov', '').strip(),
        })
    return {'origen': os.path.basename(ruta), 'tipo': 'TXT', 'items': result}


def _cargar_desde_excel():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    ruta = filedialog.askopenfilename(
        title='Selecciona el Excel de piezas',
        filetypes=[('Archivos Excel', '*.xlsx'), ('Todos los archivos', '*.*')],
    )
    root.destroy()
    if not ruta:
        return None

    try:
        from openpyxl import load_workbook
        wb = load_workbook(ruta, data_only=True)
        ws = wb.active
    except Exception as e:
        print(consola.rojo(f'  Error leyendo el Excel: {e}'))
        return None

    hdr_row = None
    cols = {}
    for r in range(1, 21):
        encontradas = {}
        for c in range(1, (ws.max_column or 2) + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str):
                u = v.strip().upper().replace('Í', 'I').replace('Ó', 'O') \
                     .replace('É', 'E').replace('Á', 'A').replace('Ú', 'U') \
                     .replace('Ñ', 'N')
                if 'PIEZA' in u or 'CODIGO' in u or 'COD' in u:
                    encontradas['pieza'] = c
                elif 'DESC' in u:
                    encontradas['desc'] = c
                elif 'MARCA' in u:
                    encontradas['marca'] = c
        if 'pieza' in encontradas:
            hdr_row = r
            cols = encontradas
            break

    if not hdr_row or 'pieza' not in cols:
        hdr_row = 0
        cols = {'pieza': 1, 'desc': 2, 'marca': 3}

    result = []
    for r in range(hdr_row + 1, (ws.max_row or hdr_row) + 1):
        codigo = ws.cell(r, cols.get('pieza', 1)).value
        if codigo is None or str(codigo).strip() == '':
            continue
        result.append({
            'codigo_pieza': str(codigo).strip(),
            'descripcion': str(ws.cell(r, cols.get('desc', 2)).value or '').strip(),
            'marca': str(ws.cell(r, cols.get('marca', 3)).value or '').strip(),
        })

    return {'origen': os.path.basename(ruta), 'tipo': 'Excel', 'items': result}


def _cargar_manual():
    print('  CARGAR PIEZA MANUAL: escribe codigo, descripcion y marca.')
    print('  (Deja el codigo vacio para terminar)')
    result = []
    while True:
        print()
        codigo = _input('  Codigo de pieza: ').strip()
        if not codigo:
            break
        desc = _input('  Descripcion: ').strip()
        marca = _input('  Marca: ').strip()
        result.append({
            'codigo_pieza': codigo,
            'descripcion': desc,
            'marca': marca,
        })
        print(consola.verde(f'  Agregada: {codigo} ({marca})'))
    return {'origen': 'MANUAL', 'tipo': 'Manual', 'items': result}


def cargar_piezas_con_marca():
    consola.titulo('CARGAR PIEZAS CON MARCA', ancho=50)

    print('  Origen de las piezas:')
    print('  1. Desde TXT de lista de precios')
    print('  2. Desde Excel')
    print('  3. Manual')
    print()
    opcion = _input('  Opcion: ').strip()

    if opcion == '1':
        datos = _cargar_desde_txt()
    elif opcion == '2':
        datos = _cargar_desde_excel()
    elif opcion == '3':
        datos = _cargar_manual()
    else:
        print(consola.amarillo('  Opcion invalida.'))
        return

    if not datos or not datos.get('items'):
        print('  No se cargaron piezas.')
        return

    items = datos['items']
    print(f'\n  Se leyeron {consola.negrita(str(len(items)))} pieza(s) desde {datos["tipo"]} ({datos["origen"]}).')

    con_marca = [p for p in items if p.get('marca')]
    print(f'  Piezas con marca: {consola.verde(str(len(con_marca)))}')
    print(f'  Piezas sin marca: {consola.amarillo(str(len(items) - len(con_marca)))}')

    print()
    print('  Primeras 5:')
    for p in items[:5]:
        marca = p.get('marca') or '-'
        print(f'    {p["codigo_pieza"]:<15} | Marca: {marca:<15} | {p.get("descripcion", "")[:30]}')
    if len(items) > 5:
        print(f'    ... y {len(items) - 5} mas')

    print()
    conf = _input('  Guardar en Supabase? [S/n]: ').strip().lower()
    if conf in ('n', 'no'):
        print('  Cancelado.')
        return

    try:
        n = upsert_piezas(items)
        print(consola.verde(f'  {n} pieza(s) guardadas/actualizadas en Supabase.'))
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))


# ----------------------------------------------------------------
# OPCION 6: Reporte de piezas danadas por marca
# ----------------------------------------------------------------
def _obtener_marca(codigo, marca_por_codigo):
    """Busca la marca de un codigo en el catalogo probando variaciones:
    - Coincidencia exacta
    - Espacios convertidos a guiones ('2C5158 020' -> '2C5158-020')
    - Prefijo M (melling a veces no lleva la M en los anillos)
    - Quitando prefijo M si el codigo lo tiene
    - Solo la base del codigo (antes del espacio/guion)
    """
    codigo = (codigo or '').strip()
    if not codigo:
        return ''

    if codigo in marca_por_codigo:
        return marca_por_codigo.get(codigo, '')

    variables = [codigo]
    con_guion = codigo.replace(' ', '-')
    variables.append(con_guion)
    con_guion2 = codigo.replace(' ', '-').replace('- ', '-')
    variables.append(con_guion2)
    sin_espacios = codigo.replace(' ', '')
    variables.append(sin_espacios)

    for v in list(variables):
        if v.upper().startswith('M') and v[1:] not in variables:
            variables.append(v[1:])
        if 'M' + v not in variables:
            variables.append('M' + v)
        partes = [p for p in v.replace('-', ' ').split() if p]
        if partes:
            variables.append(v[:len(partes[0])] if v.startswith(partes[0]) else partes[0])

    for v in variables:
        if v and v in marca_por_codigo:
            return marca_por_codigo.get(v, '')

    base = codigo.split()[0].split('-')[0] if codigo.split() else codigo.split('-')[0]
    if not base:
        base = codigo
    for i in range(len(base), 0, -1):
        cand = base[:i]
        for suf_mode in ('-', ' ', ''):
            for suf in ('020', '030', '040', '050', 'STD', 'MA', 'CP10'):
                if cand + suf_mode + suf in marca_por_codigo:
                    return marca_por_codigo.get(cand + suf_mode + suf, '')
    return ''


def reporte_por_marca():
    consola.titulo('REPORTE DE PIEZAS DANADAS POR MARCA', ancho=60)

    try:
        danadas = listar_piezas_danadas()
        piezas = listar_piezas()
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        return

    if not danadas:
        print('  No hay piezas danadas registradas.')
        return

    marca_por_codigo = {p.get('codigo_pieza', ''): p.get('marca', '') for p in piezas}

    por_marca = {}
    sin_marca = []
    for d in danadas:
        codigo = d.get('codigo', '')
        marca = _obtener_marca(codigo, marca_por_codigo) or 'SIN MARCA'
        cantidad = int(d.get('cantidad') or 1)
        registro = {
            'codigo': codigo,
            'cantidad': cantidad,
            'razon': d.get('razon_dano') or '',
            'razon_devolucion': d.get('razon_devolucion') or '',
            'cliente': d.get('cliente') or '',
            'vendedor': d.get('vendedor') or '',
            'fecha': _fecha_corta(d.get('creado_en')),
            'imagenes': d.get('imagenes') or [],
        }
        data = por_marca.setdefault(marca, {'registros': [], 'total_piezas': 0})
        data['registros'].append(registro)
        data['total_piezas'] += cantidad
        if marca == 'SIN MARCA':
            sin_marca.append(codigo)

    total_piezas = sum(d.get('cantidad') or 1 for d in danadas)

    print(f'\n  Total piezas danadas: {consola.negrita(str(total_piezas))}  |  '
          f'Registros: {consola.negrita(str(len(danadas)))}')
    if sin_marca:
        print(consola.amarillo(f'  Aviso: {len(set(sin_marca))} codigo(s) sin marca en el catalogo de piezas.'))

    ordenadas = sorted(por_marca.items(), key=lambda kv: kv[1]['total_piezas'], reverse=True)

    print()
    print('=' * 62)
    for marca, data in ordenadas:
        print()
        print(consola.cian(consola.negrita(f'  {marca.upper()}')))
        print(f'  Total piezas danadas: {consola.rojo(str(data["total_piezas"]))}  |  '
              f'Registros: {len(data["registros"])}')
        print('-' * 62)
        for r in data['registros']:
            print(f'    {r["codigo"]:<14} x{r["cantidad"]:<4} {r["fecha"]}  {r["razon"][:35]}')
            cliente = r['cliente'] or '-'
            vendedor = r['vendedor'] or '-'
            if cliente != '-' or vendedor != '-':
                print(f'      Cliente: {cliente} | Vendedor: {vendedor}')
        print('-' * 62)
    print('=' * 62)

    print()
    reporte = '  Generar reporte en archivo? '
    generar = _input(reporte + '[s/N]: ').strip().lower()
    if generar in ('s', 'si', 'y', 'yes'):
        _guardar_reporte_marca(ordenadas, total_piezas, len(danadas))


def _imagen_temporal(ruta, max_dim=90):
    """Devuelve una miniatura PNG temporal de la imagen (o None si no existe)."""
    if not os.path.exists(ruta):
        return None
    try:
        from PIL import Image as PILImage
        img = PILImage.open(ruta)
        img.thumbnail((max_dim, max_dim))
        tmp_dir = os.path.join(CARPETA_PROYECTO, 'salidas', '_imgs_tmp')
        os.makedirs(tmp_dir, exist_ok=True)
        tmp = os.path.join(tmp_dir, uuid.uuid4().hex + '.png')
        img.convert('RGB').save(tmp, format='PNG')
        return tmp
    except Exception:
        return None


def _guardar_reporte_marca(ordenadas, total_piezas, total_registros, archivo=None):
    """Guarda el reporte por marca en Excel: una hoja por marca + resumen.
    Las imagenes de cada pieza se incorporan de forma visible (miniaturas)
    en la misma fila, a la derecha del codigo."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image as XLImage

    CARPETA_SALIDAS = os.path.join(CARPETA_PROYECTO, 'salidas')
    os.makedirs(CARPETA_SALIDAS, exist_ok=True)
    fecha = datetime.now().strftime('%d-%m-%Y')
    if archivo:
        out = archivo
    else:
        out = os.path.join(CARPETA_SALIDAS, f'Reporte Piezas Danadas por Marca {fecha}.xlsx')

    encabezados = ['N°', 'CODIGO', 'CANTIDAD', 'RAZON', 'RAZON DEVOLUCION',
                   'CLIENTE', 'VENDEDOR', 'FECHA', 'N° IMG']
    anchos = [5, 16, 10, 34, 24, 24, 24, 18, 8]
    COL_IMAGENES = len(encabezados) + 1  # columna J = 10, a la derecha

    def _hoja_titulo(ws):
        for col, h in enumerate(encabezados, 1):
            cel = ws.cell(1, col, h)
            cel.font = Font(bold=True, color='FFFFFF')
            cel.fill = PatternFill('solid', fgColor='7B2D26')
            cel.alignment = Alignment(horizontal='center', vertical='center')

    def _ajustar_hoja(ws, n_filas):
        for col, a in enumerate(anchos, 1):
            ws.column_dimensions[get_column_letter(col)].width = a
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = f'A1:{get_column_letter(len(encabezados))}{n_filas}'
        for fila in range(2, n_filas + 1):
            for col in range(1, len(encabezados) + 1):
                cel = ws.cell(fila, col)
                cel.font = Font(bold=True)
                cel.alignment = Alignment(horizontal='center', vertical='center')

    def _escribir_registro(ws, fila, r, num):
        ws.cell(fila, 1, num)
        ws.cell(fila, 2, r['codigo'])
        ws.cell(fila, 3, r['cantidad'])
        ws.cell(fila, 4, r['razon'])
        ws.cell(fila, 5, r['razon_devolucion'])
        ws.cell(fila, 6, r['cliente'])
        ws.cell(fila, 7, r['vendedor'])
        ws.cell(fila, 8, r['fecha'])
        imgs = r.get('imagenes') or []
        ws.cell(fila, 9, len(imgs))

    def _titulo_hoja_valido(nombre):
        """El nombre de una hoja Excel maximo 31 chars y sin \\ / ? * [ ] :"""
        nombre = str(nombre).replace('/', '-').replace('\\', '-') \
                             .replace('?', '').replace('*', '') \
                             .replace('[', '(').replace(']', ')') \
                             .replace(':', '-')
        return nombre[:31] or 'Hoja'

    tmp_generadas = []

    def _insertar_imagenes(ws, fila, r):
        imgs = r.get('imagenes') or []
        col = COL_IMAGENES
        for img_ruta in imgs:
            tmp = _imagen_temporal(img_ruta)
            if not tmp:
                continue
            tmp_generadas.append(tmp)
            try:
                xlimg = XLImage(tmp)
                ws.add_image(xlimg, f'{get_column_letter(col)}{fila}')
                col += 1
            except Exception:
                continue
        return col - COL_IMAGENES

    wb = Workbook()
    ws_resumen = wb.active
    ws_resumen.title = 'Resumen'
    for col, h in enumerate(['MARCA', 'TOTAL PIEZAS', 'REGISTROS'], 1):
        cel = ws_resumen.cell(1, col, h)
        cel.font = Font(bold=True, color='FFFFFF')
        cel.fill = PatternFill('solid', fgColor='1F4E78')
        cel.alignment = Alignment(horizontal='center', vertical='center')
    ws_resumen.column_dimensions['A'].width = 24
    ws_resumen.column_dimensions['B'].width = 14
    ws_resumen.column_dimensions['C'].width = 10
    ws_resumen.freeze_panes = 'A2'

    fila_resumen = 2
    for marca, data in ordenadas:
        for col, valor in enumerate([marca, data['total_piezas'], len(data['registros'])], 1):
            cel = ws_resumen.cell(fila_resumen, col, valor)
            cel.font = Font(bold=True)
            cel.alignment = Alignment(horizontal='center', vertical='center')
        fila_resumen += 1

        nombre_hoja = _titulo_hoja_valido(marca)
        ws = wb.create_sheet(title=nombre_hoja)
        _hoja_titulo(ws)
        fila = 2
        for r in data['registros']:
            _escribir_registro(ws, fila, r, fila - 1)
            n_imgs = _insertar_imagenes(ws, fila, r)
            if n_imgs:
                ws.row_dimensions[fila].height = 72
            fila += 1
        _ajustar_hoja(ws, fila - 1)

    wb.save(out)

    for tmp in tmp_generadas:
        try:
            os.remove(tmp)
        except Exception:
            pass
    try:
        os.rmdir(os.path.join(CARPETA_SALIDAS, '_imgs_tmp'))
    except Exception:
        pass

    print(consola.verde(f'  Reporte guardado: {out}'))
    print(consola.verde(f'  {len(ordenadas)} hoja(s) de marca + resumen generadas.'))


# ----------------------------------------------------------------
# Submenu principal
# ----------------------------------------------------------------
def main():
    while True:
        consola.limpiar()
        consola.titulo('HISTORIAL DE PIEZAS DANADAS', ancho=50)
        print('  1. Registrar pieza danada')
        print('  2. Ver historial completo')
        print('  3. Buscar por codigo / vendedor / cliente')
        print('  4. Ver imagenes de un registro')
        print('  5. Cargar piezas con marca')
        print('  6. Reporte de piezas danadas por marca')
        print('  7. Salir')
        print('=' * 50)
        print()

        opcion = _input('  Selecciona una opcion: ').strip()

        if opcion == '1':
            consola.limpiar()
            registrar()
        elif opcion == '2':
            consola.limpiar()
            ver_historial()
        elif opcion == '3':
            consola.limpiar()
            buscar()
        elif opcion == '4':
            consola.limpiar()
            ver_imagenes()
        elif opcion == '5':
            consola.limpiar()
            cargar_piezas_con_marca()
        elif opcion == '6':
            consola.limpiar()
            reporte_por_marca()
        elif opcion == '7':
            print('\n  Saliendo del historial de piezas danadas.')
            break
        else:
            print('\n  Opcion invalida.')

        _enter()


if __name__ == '__main__':
    main()
    try:
        input('\nPresiona Enter para cerrar...')
    except EOFError:
        pass
