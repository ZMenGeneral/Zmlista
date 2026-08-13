# -*- coding: utf-8 -*-
"""
MenuPrincipal.py
Menu tipo do-while con 6 opciones.
    Opcion 1: Convertir TXT de precios a Excel
    Opcion 2: Lista en Bs (convierte un Excel de precios a Bolivares)
    Opcion 3: Verificar envios de ZOOM (guia en PDF)
    Opcion 4: Guias ZOOM almacenadas en Supabase (confirmar fechas cambiadas)
    Opcion 5: Analizar cobranza (PDF de CUENTAS POR COBRAR)
    Opcion 6: Mensajes rapidos para descripciones de cobranza
    Opcion 7: Comparar 2 Excel por codigo y mayor cantidad (temporal)
    Opcion 8: No vendidos (ventas PDF vs pedido)
    Opcion 9: No vendidos: historial por mes (Supabase)
    Opcion 10: Salir / cerrar el programa

Al iniciar revisa GitHub automaticamente: si hay actualizaciones,
descarga la version nueva y reinicia el programa.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'codigo'))

import ConvertirListaExcel as conversor
import VerificarEnvios as verificador
import GuiasZoom as guias
import AnalizarCobranza as analizador
import MensajesRapidos as mensajes
import CompararListas as comparador
import CompararVentas as novendidos
import consola


def preguntar(texto):
    try:
        return input(texto)
    except EOFError:
        return '5'


def actualizar_desde_github():
    """Si hay commits nuevos en GitHub, hace pull y reinicia el programa."""
    import subprocess
    try:
        git = subprocess.run(['git', 'fetch', 'origin', 'main'],
                             capture_output=True, cwd=RAIZ, timeout=30)
        if git.returncode != 0:
            return
        atras = subprocess.run(['git', 'rev-list', '--count', 'HEAD..origin/main'],
                               capture_output=True, text=True, cwd=RAIZ, timeout=30)
        n = int((atras.stdout or '0').strip() or '0')
        if n <= 0:
            return
        print()
        print(f'  Hay {n} actualizacion(es) en GitHub. Actualizando el programa...')
        pull = subprocess.run(['git', 'pull', '--ff-only', 'origin', 'main'],
                              capture_output=True, text=True, cwd=RAIZ, timeout=120)
        if pull.returncode == 0:
            print('  Programa actualizado. Reiniciando...')
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            msg = (pull.stderr or pull.stdout or '').strip()
            print('  No se pudo actualizar automaticamente.')
            print('  Guarda tus cambios locales (haz commit) y abre el menu de nuevo.')
            print('  Detalle: ' + msg[:250])
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f'  (No se pudieron revisar actualizaciones: {e})')


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
    print('  4. Guias ZOOM almacenadas')
    print('  5. Analizar cobranza (PDF)')
    print('  6. Mensajes rapidos')
    print('  7. Comparar 2 Excel por codigo (temporal)')
    print('  8. No vendidos (ventas vs pedido)')
    print('  9. No vendidos: historial por mes')
    print('  10. Salir')
    print('=' * 52)
    print()


def main():
    actualizar_desde_github()
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
            guias.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '5':
            consola.limpiar()
            analizador.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '6':
            consola.limpiar()
            mensajes.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '7':
            consola.limpiar()
            comparador.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '8':
            consola.limpiar()
            novendidos.main()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '9':
            consola.limpiar()
            novendidos.consultar_historial()
            preguntar('\n  Presiona Enter para volver al menu...')
        elif opcion == '10':
            print()
            print('  Cerrando programa. Hasta luego!')
            break
        else:
            print('\n  Opcion invalida, intenta de nuevo.')
            preguntar('  Presiona Enter para continuar...')
    print()


if __name__ == '__main__':
    main()
