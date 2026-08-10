# -*- coding: utf-8 -*-
"""
GuiasZoom.py
OPCION 4 - GUIAS ZOOM ALMACENADAS:
    Muestra todas las guias de ZOOM guardadas en Supabase (se guardan cada vez
    que se analizan en la opcion 3) y permite confirmar manualmente cuales guias
    ya tienen su fecha cambiada en el sistema externo.

Tabla: public.guias_zoom  (campo fecha_cambiada = SI/NO)
"""
import re
import sys

import consola
from supabase_client import listar_guias, marcar_cambiadas, SupabaseError

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def _vis(s):
    return len(ANSI.sub('', str(s)))


def _s(valor, ancho, relleno=' '):
    s = str(valor)
    vis = _vis(s)
    if vis > ancho:
        if vis == len(s):
            return s[:ancho]
        return s
    return s + relleno * (ancho - vis)


MAP_ESTADO = {
    'AFUERA PARA ENTREGA': 'AFUERA ENTREGA',
    'EN TRANSITO A SU DESTINO': 'EN TRANSITO',
    'TRASLADO CON FRECUENCIA VARIABLE': 'TRASLADO VAR',
    'DISPONIBLE PARA EL RETIRO EN TAQUILLA': 'EN TAQUILLA',
    'ENTREGADO AL DESTINO': 'ENTREGADO',
    'ENTREGADO AL CLIENTE': 'ENTREGADO CLIENTE',
    'ENTREGADO': 'ENTREGADO',
}


def _estado_corto(e):
    return MAP_ESTADO.get(e, e)


def _solo_fecha(s):
    if not s:
        return '-'
    s = s.strip().split(' ')[0]
    partes = s.split('-')
    if len(partes) == 3 and partes[0].isdigit() and len(partes[0]) == 4:
        return f'{partes[2]}/{partes[1]}/{partes[0]}'
    return s


def _fmt_actualizado(s):
    if not s:
        return '-'
    s = s.strip().replace('T', ' ').split('+')[0].split('.')[0]
    partes = s.split(' ')
    if len(partes) < 2:
        return s
    fecha = partes[0].split('-')
    fecha_s = f'{fecha[2]}/{fecha[1]}/{fecha[0]}' if len(fecha) == 3 else partes[0]
    return fecha_s + ' ' + partes[1][:5]


def _tabla(guias):
    lineas = []
    lineas.append(_s('NUM', 4) + ' ' + _s('GUIA', 10) + ' ' + _s('FECHA ENVIO', 12) + ' ' +
                  _s('CLIENTE', 38) + ' ' + _s('ESTADO', 20) + ' ' + _s('FECHA RETIRO', 12) + ' ' +
                  _s('ULT. ACTUALIZ.', 18) + ' ' + _s('RET', 4) + ' ' + _s('CAM', 4))
    lineas.append('-' * 130)
    for i, g in enumerate(guias, 1):
        ret = consola.verde('SI') if g.get('retirada') else consola.rojo('NO')
        cam = consola.verde('SI') if g.get('fecha_cambiada') else consola.rojo('NO')
        guia = consola.naranja(g.get('guia', ''))
        fenv = consola.naranja(_solo_fecha(g.get('fecha_envio')))
        fret = consola.naranja(_solo_fecha(g.get('fecha_entrega')))
        fact = consola.naranja(_fmt_actualizado(g.get('actualizado_en')))
        linea = (_s(i, 4) + ' ' + _s(guia, 10) + ' ' + _s(fenv, 12) + ' ' +
                 _s(g.get('casillero') or g.get('destino') or '', 38) + ' ' +
                 _s(_estado_corto(g.get('estado') or ''), 20) + ' ' +
                 _s(fret, 12) + ' ' + _s(fact, 18) + ' ' + _s(ret, 4) + ' ' + _s(cam, 4))
        lineas.append(linea)
    return lineas


def _seleccionar_guias(texto, guias):
    """Convierte lo escrito (numero de la lista NUM o guia de 10 digitos)
    en los numeros de guia correspondientes."""
    try:
        raw = input(texto).strip()
    except EOFError:
        return []
    if not raw:
        return []
    seleccion = []
    for p in raw.replace(',', ' ').replace(';', ' ').split():
        n = ''.join(c for c in p if c.isdigit())
        if not n:
            continue
        if n.isdigit() and 1 <= int(n) <= len(guias):
            seleccion.append(guias[int(n) - 1]['guia'])
        elif len(n) == 10:
            seleccion.append(n)
    return seleccion


def _leer_opcion():
    try:
        return input('  Opcion: ').strip()
    except EOFError:
        return '3'


def _enter():
    try:
        input('\n  Presiona Enter para continuar...')
    except EOFError:
        pass


def _mostrar_guias(guias):
    total = len(guias)
    marcadas = sum(1 for g in guias if g.get('fecha_cambiada'))
    print(f'\n  Total guias almacenadas: {total}  |  Cambiadas en sistema externo: '
          f'{consola.verde(str(marcadas))}  |  Pendientes: {consola.rojo(str(total - marcadas))}')
    print()
    for linea in _tabla(guias):
        print('  ' + linea)


def main():
    consola.titulo('OPCION 4 - GUIAS ZOOM ALMACENADAS', ancho=58)

    try:
        guias = listar_guias()
    except SupabaseError as e:
        print(consola.rojo(f'  Error de Supabase: {e}'))
        print('  Revisa config/supabase.json y que exista la tabla guias_zoom.')
        return

    if not guias:
        print('  No hay guias almacenadas todavia.')
        print('  Analiza algunas guias en la opcion 3 (Verificar envios ZOOM) para guardarlas.')
        return

    while True:
        consola.limpiar()
        _mostrar_guias(guias)

        print()
        print('=' * 58)
        print('  1. Marcar guias como CAMBIADAS en el sistema externo')
        print('  2. Desmarcar guias (aun no cambiadas)')
        print('  3. Salir')
        print('=' * 58)
        opcion = _leer_opcion()

        if opcion == '1':
            guias_m = _seleccionar_guias(
                '\n  Guias a marcar como cambiadas (numero de la lista): ', guias)
            if not guias_m:
                print('  No seleccionaste ninguna guia.')
            else:
                try:
                    n = marcar_cambiadas(guias_m, True)
                    print(consola.verde(f'  Marcadas {n} guias como cambiadas.'))
                    for g in guias:
                        if g.get('guia') in guias_m:
                            g['fecha_cambiada'] = True
                except SupabaseError as e:
                    print(consola.rojo(f'  Error de Supabase: {e}'))
        elif opcion == '2':
            guias_m = _seleccionar_guias(
                '\n  Guias a desmarcar (numero de la lista): ', guias)
            if not guias_m:
                print('  No seleccionaste ninguna guia.')
            else:
                try:
                    n = marcar_cambiadas(guias_m, False)
                    print(consola.verde(f'  Desmarcadas {n} guias.'))
                    for g in guias:
                        if g.get('guia') in guias_m:
                            g['fecha_cambiada'] = False
                except SupabaseError as e:
                    print(consola.rojo(f'  Error de Supabase: {e}'))
        elif opcion == '3':
            print('\n  Saliendo de la opcion 4.')
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
