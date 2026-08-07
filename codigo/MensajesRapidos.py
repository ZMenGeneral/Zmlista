# -*- coding: utf-8 -*-
"""
MensajesRapidos.py
Opcion 5: genera mensajes rapidos para las descripciones de cobranza.
    Pide una fecha, pide un periodo de dias,
    calcula el dia en que termina la secuencia
    y muestra el mensaje: R DD-MM CREDITO z DIAS
"""
import datetime

import consola


def pedir_fecha():
    while True:
        texto = input('  Fecha (DD/MM/AAAA): ').strip()
        try:
            return datetime.datetime.strptime(texto, '%d/%m/%Y').date()
        except ValueError:
            print('  ' + consola.rojo('Fecha invalida. Usa el formato DD/MM/AAAA.'))


def pedir_periodo():
    while True:
        texto = input('  Periodo de dias: ').strip()
        try:
            dias = int(texto)
            if dias > 0:
                return dias
            print('  ' + consola.rojo('El periodo debe ser mayor que 0.'))
        except ValueError:
            print('  ' + consola.rojo('Cantidad invalida. Usa un numero entero.'))


def main():
    while True:
        consola.titulo('MENSAJES RAPIDOS', ancho=52)
        fecha = pedir_fecha()
        dias = pedir_periodo()
        fecha_final = fecha + datetime.timedelta(days=dias)

        consola.separador(52)
        print('  Fecha inicial:   ' + consola.cian(fecha.strftime('%d/%m/%Y')))
        print('  Periodo (dias):  ' + consola.cian(str(dias)))
        print('  Fecha final:     ' + consola.verde(fecha_final.strftime('%d/%m/%Y')))
        print()
        mensaje = f'R {fecha.strftime("%d-%m")} CREDITO {dias} DIAS'
        print('  Mensaje:')
        print('  ' + consola.amarillo(consola.negrita(mensaje)))
        consola.separador(52)
        print()

        respuesta = input('  Otro mensaje? (Enter para SI, N para salir): ').strip().lower()
        if respuesta == 'n':
            print()
            break


if __name__ == '__main__':
    main()
