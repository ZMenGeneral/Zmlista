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
        5. Salir
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
    SupabaseError,
)

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
            f"  {'#':<4} {'CODIGO':<12} {'FECHA':<18} {'VENDEDOR':<18} {'CLIENTE':<20} {'RAZON'}"
        )
    )
    print('  ' + '-' * 100)
    for i, r in enumerate(registros, 1):
        cod = consola.naranja(r.get('codigo', ''))
        fecha = _fecha_corta(r.get('creado_en'))
        vendedor = r.get('vendedor') or '-'
        cliente = r.get('cliente') or '-'
        razon = (r.get('razon_dano') or '-')[:35]
        imgs = len(r.get('imagenes') or [])
        img_tag = f' [{consola.cian(str(imgs) + " img")}]' if imgs else ''
        print(f'  {i:<4} {cod:<12} {fecha:<18} {vendedor:<18} {cliente:<20} {razon}{img_tag}')
    print('  ' + '-' * 100)


def _mostrar_detalle(reg):
    """Muestra el detalle completo de un registro."""
    print()
    print('=' * 60)
    print(consola.cian(consola.negrita('  DETALLE DE PIEZA DANADA')))
    print('=' * 60)
    print(f'  Codigo:          {consola.naranja(reg.get("codigo", ""))}')
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
        print('  5. Salir')
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
