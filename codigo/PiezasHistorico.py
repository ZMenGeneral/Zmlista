# -*- coding: utf-8 -*-
"""
PiezasHistorico.py
OPCION 12 - HISTORICO DE TODAS NUESTRAS PIEZAS:
    Catalogo historico de todas las piezas (codigo, descripcion y marca de
    fabricante). Permite actualizar la lista desde el TXT de precios en la red
    y consultar el historial completo.

    Submenu:
        1. Actualizar lista de piezas (TXT en la red)
        2. Ver historico completo
        3. Buscar pieza
        4. Estadisticas
        5. Salir
"""
import os
import sys

import consola
from supabase_client import (
    upsert_pieza,
    upsert_piezas,
    listar_piezas,
    buscar_piezas_marca,
    SupabaseError,
)

CARPETA_CODIGO = os.path.dirname(os.path.abspath(__file__))
CARPETA_PROYECTO = os.path.dirname(CARPETA_CODIGO)

RUTA_TXT_LISTA = r'\\PRINCIPAL\a2admin\Empre001\REPORTS\LISTA DE PRECIO 2023.TXT'
CARPETA_TXT_LISTA = r'\\PRINCIPAL\a2admin\Empre001\REPORTS'


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


def _encontrar_txt_lista():
    """Devuelve la ruta del TXT de lista de precios en la red."""
    import glob as _glob
    if os.path.exists(RUTA_TXT_LISTA):
        return RUTA_TXT_LISTA
    if os.path.isdir(CARPETA_TXT_LISTA):
        candidatos = _glob.glob(os.path.join(CARPETA_TXT_LISTA, 'LISTA DE PRECIO*'))
        if candidatos:
            candidatos.sort(key=os.path.getmtime, reverse=True)
            return candidatos[0]
    return None


def _leer_txt_lista():
    """Lee el TXT de lista de precios y devuelve las piezas con su marca.
    Marca = campo prov (marca de fabricante)."""
    from ConvertirListaExcel import parse_txt

    ruta = _encontrar_txt_lista()
    if not ruta:
        print(consola.rojo('  No se encontro el TXT de lista de precios en la red.'))
        print('  Busca en: ' + CARPETA_TXT_LISTA)
        return None

    try:
        filas = parse_txt(ruta)
    except Exception as e:
        print(consola.rojo(f'  Error leyendo el TXT: {e}'))
        return None

    items = []
    for f in filas:
        codigo = f.get('codigo', '').strip()
        if not codigo:
            continue
        items.append({
            'codigo_pieza': codigo,
            'descripcion': f.get('desc', '').strip(),
            'marca': f.get('prov', '').strip(),
        })
    return {'ruta': ruta, 'items': items}


def _limpiar_pantalla_pagina(piezas, inicio, fin):
    """Muestra piezas [inicio:fin] con cabecera."""
    print()
    print(consola.negrita(
        f"  {'#':<6} {'CODIGO':<20} {'MARCA':<20} {'DESCRIPCION'}"))
    print('  ' + '-' * 90)
    for i in range(inicio, min(fin, len(piezas))):
        p = piezas[i]
        marca = p.get('marca') or '-'
        print(f'  {i + 1:<6} {p["codigo_pieza"]:<20} {marca:<20} {p.get("descripcion", "")[:45]}')
    print('  ' + '-' * 90)


# ----------------------------------------------------------------
# OPCION 1: Actualizar lista desde TXT
# ----------------------------------------------------------------
def actualizar_lista():
    consola.titulo('ACTUALIZAR LISTA DE PIEZAS', ancho=50)

    print('  Leyendo el TXT de lista de precios desde la red...')
    datos = _leer_txt_lista()
    if not datos or not datos.get('items'):
        print('  No se pudieron leer piezas.')
        return

    items = datos['items']
    con_marca = [p for p in items if p.get('marca')]
    print(consola.verde(f'  Archivo: {datos["ruta"]}'))
    print(f'  Piezas leidas: {consola.negrita(str(len(items)))}')
    print(f'  Con marca: {consola.verde(str(len(con_marca)))}  '
          f'Sin marca: {consola.amarillo(str(len(items) - len(con_marca)))}')

    print()
    print('  Primeras 5:')
    for p in items[:5]:
        marca = p.get('marca') or '-'
        print(f'    {p["codigo_pieza"]:<15} | Marca: {marca:<15} | {p.get("descripcion", "")[:30]}')
    print(f'    ... y {len(items) - 5} mas')

    print()
    conf = _input('  Actualizar la lista en Supabase? [S/n]: ').strip().lower()
    if conf in ('n', 'no'):
        print('  Cancelado.')
        return

    try:
        n = upsert_piezas(items)
        print()
        print(consola.verde(f'  Lista actualizada: {n} pieza(s) guardadas/actualizadas.'))
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        print('  Revisa que exista la columna marca en la tabla piezas '
              '(config/agregar_columna_marca_piezas.sql).')


# ----------------------------------------------------------------
# OPCION 2: Ver historico completo
# ----------------------------------------------------------------
def ver_historico():
    consola.titulo('HISTORICO DE TODAS NUESTRAS PIEZAS', ancho=60)

    try:
        piezas = listar_piezas()
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        return

    if not piezas:
        print('  No hay piezas en el catalogo.')
        print('  Usa la opcion 1 (actualizar lista) para cargarlas.')
        return

    total = len(piezas)
    por_pagina = 25
    pagina = 1
    paginas = max(1, (total + por_pagina - 1) // por_pagina)

    print(f'\n  Total piezas en el historico: {consola.negrita(str(total))}')

    while True:
        consola.limpiar()
        print()
        print('=' * 60)
        print(consola.cian(consola.negrita(
            f'  HISTORICO DE PIEZAS  |  Pagina {pagina}/{paginas}  |  Total: {total}')))
        print('=' * 60)

        inicio = (pagina - 1) * por_pagina
        _limpiar_pantalla_pagina(piezas, inicio, inicio + por_pagina)

        print()
        print('  [N] Pagina siguiente   [P] Pagina anterior')
        print('  [n] Numero de pagina   [B] Buscar   [S] Salir')
        opcion = _input('  Opcion: ').strip().lower()

        if opcion in ('s', 'salir', ''):
            break
        elif opcion == 'n':
            if pagina < paginas:
                pagina += 1
            else:
                print(consola.amarillo('  Ya estas en la ultima pagina.'))
                _enter()
        elif opcion == 'p':
            if pagina > 1:
                pagina -= 1
            else:
                print(consola.amarillo('  Ya estas en la primera pagina.'))
                _enter()
        elif opcion == 'b':
            _buscar_desde_historico(piezas, total)
        elif opcion.isdigit():
            num = int(opcion)
            if 1 <= num <= paginas:
                pagina = num
            else:
                print(consola.amarillo(f'  Pagina invalida (1-{paginas}).'))
                _enter()
        else:
            print(consola.amarillo('  Opcion invalida.'))
            _enter()


def _buscar_desde_historico(piezas, total):
    valor = _input('  Buscar pieza (codigo, marca o descripcion): ').strip()
    if not valor:
        return
    resultados = [p for p in piezas
                  if valor.upper() in p.get('codigo_pieza', '').upper()
                  or valor.upper() in (p.get('marca') or '').upper()
                  or valor.upper() in (p.get('descripcion') or '').upper()]
    if not resultados:
        print(consola.amarillo('  Sin resultados.'))
        _enter()
        return
    print(consola.verde(f'\n  {len(resultados)} resultado(s) de {total} piezas.'))
    _limpiar_pantalla_pagina(resultados, 0, len(resultados))
    _enter()


# ----------------------------------------------------------------
# OPCION 3: Buscar pieza
# ----------------------------------------------------------------
def buscar():
    consola.titulo('BUSCAR PIEZA EN EL CATALOGO', ancho=50)

    valor = _input('  Buscar por codigo, marca o descripcion: ').strip()
    if not valor:
        print('  No ingresaste nada.')
        return

    try:
        resultados = buscar_piezas_marca(valor)
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        return

    if not resultados:
        print(f'  No se encontraron piezas para "{valor}".')
        return

    print(consola.verde(f'\n  {len(resultados)} resultado(s):'))
    _limpiar_pantalla_pagina(resultados, 0, len(resultados))

    print()
    print('  Tambien puedes buscar en el historico completo '
          '(opcion 2) para ver paginas de resultados.')


# ----------------------------------------------------------------
# OPCION 4: Estadisticas
# ----------------------------------------------------------------
def estadisticas():
    consola.titulo('ESTADISTICAS DEL CATALOGO', ancho=50)

    try:
        piezas = listar_piezas()
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        return

    total = len(piezas)
    con_marca = [p for p in piezas if p.get('marca')]
    sin_marca = total - len(con_marca)
    marcas = sorted(set(p.get('marca', '').strip() for p in piezas if p.get('marca')))

    print(f'  Total piezas:             {consola.negrita(str(total))}')
    print(f'  Con marca:                {consola.verde(str(len(con_marca)))}')
    print(f'  Sin marca:                {consola.amarillo(str(sin_marca))}')
    print(f'  Marcas distintas:         {consola.cian(str(len(marcas)))}')
    print()
    print('  Marcas:')
    for m in marcas:
        n = sum(1 for p in piezas if p.get('marca', '').strip() == m)
        print(f'    - {m:<20} {consola.cian(str(n))} piezas')


# ----------------------------------------------------------------
# Submenu principal
# ----------------------------------------------------------------
def main():
    while True:
        consola.limpiar()
        consola.titulo('HISTORICO DE TODAS NUESTRAS PIEZAS', ancho=60)
        print('  1. Actualizar lista de piezas (TXT en la red)')
        print('  2. Ver historico completo')
        print('  3. Buscar pieza')
        print('  4. Estadisticas')
        print('  5. Salir')
        print('=' * 60)
        print()

        opcion = _input('  Selecciona una opcion: ').strip()

        if opcion == '1':
            consola.limpiar()
            actualizar_lista()
        elif opcion == '2':
            consola.limpiar()
            ver_historico()
        elif opcion == '3':
            consola.limpiar()
            buscar()
        elif opcion == '4':
            consola.limpiar()
            estadisticas()
        elif opcion == '5':
            print('\n  Saliendo del historico de piezas.')
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