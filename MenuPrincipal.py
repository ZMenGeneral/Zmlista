# -*- coding: utf-8 -*-
"""
MenuPrincipal.py
Menu tipo do-while con 5 opciones.
    Opcion 1: Convertir TXT de precios a Excel
    Opcion 2: Lista en Bs (convierte un Excel de precios a Bolivares)
     Opcion 3: Verificar envios de ZOOM (guia en PDF)
     Opcion 4: Analizar cobranza (PDF de CUENTAS POR COBRAR)
     Opcion 5: Salir / cerrar el programa
"""
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'codigo'))

import ConvertirListaExcel as conversor
import VerificarEnvios as verificador
import AnalizarCobranza as analizador
import consola


def preguntar(texto):
    try:
        return input(texto)
    except EOFError:
        return '5'


def mostrar_menu():
    consola.limpiar()
    print()
    print('=' * 52)
    print('                MENU PRINCIPAL')
    print('=' * 52)
    print()
    print('  1. Convertir TXT de precios a Excel')
    print('  2. Lista en Bs')
    print('  3. Verificar envios ZOOM (PDF)')
    print('  4. Analizar cobranza (PDF)')
    print('  5. Salir')
    print('=' * 52)
    print()


def main():
    while True:
        mostrar_menu()
        opcion = preguntar('  Selecciona una opcion: ').strip()

        if opcion == '1':
            consola.limpiar()
            conversor.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '2':
            consola.limpiar()
            conversor.main_lista_bs()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '3':
            consola.limpiar()
            verificador.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '4':
            consola.limpiar()
            analizador.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '5':
            print()
            print('  Cerrando programa. Hasta luego!')
            break
        else:
            print('\n  Opcion invalida, intenta de nuevo.')
            preguntar('  Presiona Enter para continuar...')
    print()


if __name__ == '__main__':
    main()
