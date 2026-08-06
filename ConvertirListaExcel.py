# -*- coding: utf-8 -*-
"""
ConvertirListaExcel.py
Convierte listas de precios en TXT (ancho fijo, Windows-1252) y rellena la
plantilla "LISTA base.xlsx" generando un archivo nuevo:

    "Lista Zm DD-MM-AAAA.xlsx"

Uso:
    python ConvertirListaExcel.py                          (abre explorador de archivos)
    python ConvertirListaExcel.py "C:/ruta/archivo.txt"
    python ConvertirListaExcel.py "C:/ruta/carpeta"        (convierte todos los *.txt)

Comportamiento:
    - Quita productos con existencia 0
    - Limpia la categoria (solo para el orden; no se escribe en la plantilla)
    - Ordena por Categoria y luego por Codigo
    - Rellena la plantilla LISTA base:
        B = CODIGO
        C = DESCRIPCION
        D = MODELO  (marca del vehiculo, ej: CHEVROLET / FORD)
        E = MARCA   (marca del proveedor, ej: MELLING)
        F = PRECIO
        G = CANT    (se deja vacia)
    - Actualiza la fecha (celda B10) con la fecha de hoy
    - Conserva el logo y el formato de la plantilla
"""
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from xml.sax.saxutils import escape

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
NS_X14AC = 'http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac'
NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ET.register_namespace('', NS)
ET.register_namespace('mc', NS_MC)
ET.register_namespace('x14ac', NS_X14AC)
ET.register_namespace('r', NS_R)

TAIL_RE = re.compile(r'^\s*([\d.,]+)\s+([\d.,]+)\s*$')


def parse_number(value):
    """Convierte '218,62' -> 218.62  y  '1.456,00' -> 1456.0. None si no es numero."""
    if not value or not value.strip():
        return None
    clean = value.strip().replace('.', '').replace(',', '.')
    try:
        return float(clean)
    except ValueError:
        return None


def parse_txt(path):
    with open(path, 'r', encoding='cp1252') as f:
        lines = f.read().splitlines()

    rows = []
    for line in lines:
        if not line.strip() or len(line) < 40:
            continue

        codigo = line[0:41].strip()
        desc = line[41:82].strip()
        cat = re.sub(r'^\d+-', '', line[82:123]).strip()
        marca = line[123:164].strip()
        prov = line[164:205].strip()

        existencia = None
        precio = None
        if len(line) > 205:
            m = TAIL_RE.match(line[205:])
            if m:
                existencia = parse_number(m.group(1))
                precio = parse_number(m.group(2))

        rows.append({
            'codigo': codigo,
            'desc': desc,
            'cat': cat,
            'marca': marca,
            'prov': prov,
            'existencia': existencia,
            'precio': precio,
        })
    return rows


def _localname(tag):
    return tag.rsplit('}', 1)[-1]


def _col_num(ref):
    letters = ''.join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n


def _xml_bytes(root):
    return (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            + ET.tostring(root, encoding='UTF-8'))


def _prepare_shared_strings(ss_data, fecha_text, valores):
    """Devuelve (bytes_sharedStrings, diccionario valor->indice)."""
    sst = ET.fromstring(ss_data)
    sis = [e for e in sst if _localname(e.tag) == 'si']

    indice_por_valor = {}
    for i, si in enumerate(sis):
        t = si.findtext(f'{{{NS}}}t') or ''
        indice_por_valor[t] = i

    # Reemplaza la cadena "DD/MM/AAAA" por la fecha de hoy
    if 'DD/MM/AAAA' in indice_por_valor:
        si_fecha = sis[indice_por_valor['DD/MM/AAAA']]
        t_el = si_fecha.find(f'{{{NS}}}t')
        t_el.text = fecha_text

    indice_por_valor = {}
    for i, si in enumerate(sis):
        t = si.findtext(f'{{{NS}}}t') or ''
        indice_por_valor[t] = i

    for valor in valores:
        if valor not in indice_por_valor:
            si = ET.SubElement(sst, f'{{{NS}}}si')
            ET.SubElement(si, f'{{{NS}}}t').text = valor
            indice_por_valor[valor] = len(sis)
            sis.append(si)

    total = len(sis)
    sst.set('count', str(total))
    sst.set('uniqueCount', str(total))

    return _xml_bytes(sst), indice_por_valor


def _fill_sheet(sheet_data, filas, string_idx):
    """Rellena las celdas de la hoja. filas = lista de dicts por producto."""
    root = ET.fromstring(sheet_data)
    sheet_data_el = root.find(f'{{{NS}}}sheetData')

    filas_por_numero = {}
    for row_el in sheet_data_el:
        if _localname(row_el.tag) == 'row':
            filas_por_numero[int(row_el.get('r'))] = row_el

    max_fila = max(filas_por_numero) if filas_por_numero else 0

    def obtener_fila(num):
        row_el = filas_por_numero.get(num)
        if row_el is None:
            row_el = ET.SubElement(sheet_data_el, f'{{{NS}}}row')
            row_el.set('r', str(num))
            filas_por_numero[num] = row_el
            return row_el
        return row_el

    def obtener_celda(row_el, ref, col_num):
        for child in row_el:
            if _localname(child.tag) == 'c' and child.get('r') == ref:
                return child
        # inserta en orden de columna
        cell = ET.Element(f'{{{NS}}}c')
        cell.set('r', ref)
        pos = 0
        for idx, child in enumerate(row_el):
            if _localname(child.tag) == 'c' and _col_num(child.get('r')) > col_num:
                pos = idx
                break
            pos = idx + 1
        row_el.insert(pos, cell)
        return cell

    def poner_valor(cell, valor, es_texto):
        if es_texto:
            cell.set('t', 's')
            v = cell.find(f'{{{NS}}}v')
            if v is None:
                v = ET.SubElement(cell, f'{{{NS}}}v')
            v.text = str(string_idx[valor])
        else:
            if 't' in cell.attrib:
                del cell.attrib['t']
            v = cell.find(f'{{{NS}}}v')
            if v is None:
                v = ET.SubElement(cell, f'{{{NS}}}v')
            v.text = repr(valor)

    for i, r in enumerate(filas):
        num = 13 + i
        row_el = obtener_fila(num)
        if r['codigo']:
            poner_valor(obtener_celda(row_el, f'B{num}', 2), r['codigo'], True)
        if r['desc']:
            poner_valor(obtener_celda(row_el, f'C{num}', 3), r['desc'], True)
        if r['marca']:
            poner_valor(obtener_celda(row_el, f'D{num}', 4), r['marca'], True)
        if r['prov']:
            poner_valor(obtener_celda(row_el, f'E{num}', 5), r['prov'], True)
        if r['precio'] is not None:
            poner_valor(obtener_celda(row_el, f'F{num}', 6), r['precio'], False)

    return _xml_bytes(root)


def build_from_base(rows, base_path, out_path):
    """Rellena la plantilla LISTA base con los productos y guarda out_path."""
    fecha = date.today().strftime('%d/%m/%Y')

    valores = []
    for r in rows:
        for campo in ('codigo', 'desc', 'marca', 'prov'):
            v = r[campo]
            if v and v not in valores:
                valores.append(v)

    z = zipfile.ZipFile(base_path)
    ss_bytes, string_idx = _prepare_shared_strings(
        z.read('xl/sharedStrings.xml'), fecha, valores)
    sheet_bytes = _fill_sheet(z.read('xl/worksheets/sheet1.xml'), rows, string_idx)

    i = 0
    while True:
        try:
            destino = out_path if i == 0 else f"{os.path.splitext(out_path)[0]}.({i}){os.path.splitext(out_path)[1]}"
            with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as z2:
                for item in z.infolist():
                    data = z.read(item.filename)
                    if item.filename == 'xl/sharedStrings.xml':
                        data = ss_bytes
                    elif item.filename == 'xl/worksheets/sheet1.xml':
                        data = sheet_bytes
                    z2.writestr(item, data)
            return destino
        except PermissionError:
            i += 1
        finally:
            z.close()


def ask_file_dialog():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askopenfilename(
        title='Selecciona el archivo TXT de lista de precios',
        filetypes=[('Archivos TXT', '*.txt'), ('Todos los archivos', '*.*')],
        initialdir=r'\\PRINCIPAL\a2admin\Empre001\REPORTS',
    )
    root.destroy()
    return path


def main():
    args = sys.argv[1:]
    origen = args[0] if len(args) >= 1 else None

    carpeta_proyecto = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(carpeta_proyecto, 'LISTA base.xlsx')

    if not os.path.exists(base_path):
        print(f'No se encontro la plantilla: {base_path}')
        return

    if not origen:
        origen = ask_file_dialog()
        if not origen:
            print('No seleccionaste ningun archivo. Cancelado.')
            return

    if os.path.isdir(origen):
        items = sorted(
            os.path.join(origen, f)
            for f in os.listdir(origen)
            if f.lower().endswith('.txt')
        )
    else:
        items = [origen]

    nombre = 'Lista Zm ' + date.today().strftime('%d-%m-%Y') + '.xlsx'

    total = 0
    for idx, item in enumerate(items):
        rows = parse_txt(item)
        total_parse = len(rows)

        rows = [r for r in rows if r['existencia'] is None or r['existencia'] != 0]
        removed = total_parse - len(rows)

        rows.sort(key=lambda r: (r['cat'].lower(), r['codigo'].lower()))

        if len(items) > 1:
            base_nombre, ext = os.path.splitext(nombre)
            out = os.path.join(carpeta_proyecto, f"{base_nombre} ({idx + 1}){ext}")
        else:
            out = os.path.join(carpeta_proyecto, nombre)

        out = build_from_base(rows, base_path, out)
        print(f"OK: {total_parse} lineas -> {len(rows)} productos "
              f"(se quitaron {removed} con existencia 0) -> {out}")
        total += len(rows)

    print(f"Total productos convertidos: {total}")


if __name__ == '__main__':
    main()
    try:
        input('Presiona Enter para cerrar...')
    except EOFError:
        pass
