# -*- coding: utf-8 -*-
"""
MenuPrincipal.py
Menu tipo do-while con 5 opciones.
    Opcion 1: Convertir TXT de precios a Excel
    Opcion 2: Lista en Bs (convierte un Excel de precios a Bolivares)
    Opcion 5: Salir / cerrar el programa
    Opciones 3, 4: reservadas (en desarrollo)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ConvertirListaExcel as conversor


def preguntar(texto):
    try:
        return input(texto)
    except EOFError:
        return '5'


def mostrar_menu():
    os.system('cls')
    print('=' * 48)
    print('                MENU PRINCIPAL')
    print('=' * 48)
    print('  1. Convertir TXT de precios a Excel')
    print('  2. Lista en Bs')
    print('  3. (En desarrollo)')
    print('  4. (En desarrollo)')
    print('  5. Salir')
    print('=' * 48)


def main():
    while True:
        mostrar_menu()
        opcion = preguntar('  Selecciona una opcion: ').strip()

        if opcion == '1':
            conversor.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '2':
            conversor.main_lista_bs()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion in ('3', '4'):
            print(f'\n  Opcion {opcion} en desarrollo.')
            preguntar('  Presiona Enter para continuar...')
        elif opcion == '5':
            print('\n  Cerrando programa. Hasta luego!')
            break
        else:
            print('\n  Opcion invalida, intenta de nuevo.')
            preguntar('  Presiona Enter para continuar...')
    print()


if __name__ == '__main__':
    main()
