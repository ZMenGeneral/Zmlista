# -*- coding: utf-8 -*-
"""Utilidades de consola compartidas: limpiar pantalla, titulos, separadores y colores."""
import ctypes
import os


def _habilitar_colores():
    """Activa los codigos ANSI en la consola de Windows."""
    if os.name == 'nt':
        try:
            kernel32 = ctypes.windll.kernel32
            h = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint()
            if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h, mode.value | 0x0004)
        except Exception:
            pass


_habilitar_colores()

RESET = '\033[0m'
BOLD = '\033[1m'
ROJO = '\033[31m'
VERDE = '\033[32m'
AMARILLO = '\033[33m'
AZUL = '\033[34m'
MAGENTA = '\033[35m'
CIAN = '\033[36m'
ROJO_B = '\033[1;91m'
VERDE_B = '\033[1;92m'
AMARILLO_B = '\033[1;93m'
CIAN_B = '\033[1;96m'


def color(texto, *codigos):
    return ''.join(codigos) + str(texto) + RESET


def negrita(texto):
    return color(texto, BOLD)


def rojo(texto):
    return color(texto, ROJO_B)


def verde(texto):
    return color(texto, VERDE_B)


def amarillo(texto):
    return color(texto, AMARILLO_B)


def cian(texto):
    return color(texto, CIAN_B)


def limpiar():
    """Limpia la terminal."""
    os.system('cls')


def titulo(texto, ancho=60, simbolo='='):
    """Imprime un titulo centrado entre lineas de separacion."""
    print()
    print(simbolo * ancho)
    print('  ' + cian(negrita(texto)))
    print(simbolo * ancho)
    print()


def separador(ancho=60, simbolo='='):
    """Imprime una linea separadora."""
    print(simbolo * ancho)
