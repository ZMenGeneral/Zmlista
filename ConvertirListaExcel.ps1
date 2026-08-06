# =============================================================
# ConvertirListaExcel.ps1
# Convierte archivos TXT de lista de precios (ancho fijo, 236
# caracteres por linea, codificado en Windows-1252) a Excel .xlsx
# real (sin instalar modulos ni tener Excel).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\ConvertirListaExcel.ps1
#   powershell -ExecutionPolicy Bypass -File .\ConvertirListaExcel.ps1 -Origen "C:\ruta\archivo.txt"
#   powershell -ExecutionPolicy Bypass -File .\ConvertirListaExcel.ps1 -Origen "C:\ruta\archivo.txt" -Destino "C:\ruta\salida.xlsx"
#   powershell -ExecutionPolicy Bypass -File .\ConvertirListaExcel.ps1 -Origen "C:\carpeta"   (convierte todos los *.txt de la carpeta)
# =============================================================
param(
    [string]$Origen,
    [string]$Destino
)

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ---------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------
function ConvertTo-XmlText([string]$s) {
    if ($null -eq $s) { return '' }
    return $s.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
}

function ConvertTo-Number([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    $clean = $value.Replace('.', '').Replace(',', '.')
    try { return [double]::Parse($clean, [System.Globalization.CultureInfo]::InvariantCulture) }
    catch { return $null }
}

function Get-Field([string]$line, [int]$start, [int]$length) {
    if ($line.Length -ge ($start + $length)) { return $line.Substring($start, $length).Trim() }
    if ($line.Length -gt $start)            { return $line.Substring($start).Trim() }
    return ''
}

function Add-ZipEntry($zip, [string]$name, [string]$content) {
    $entry = $zip.CreateEntry($name)
    $stream = $entry.Open()
    $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
    $writer.Write($content)
    $writer.Close()
}

# ---------------------------------------------------------
# Columnas de ancho fijo (indices 0-based) y encabezados
# ---------------------------------------------------------
$cols = @(
    @{ Letter = 'A'; Header = 'Codigo';        Start = 0;   Length = 41; Type = 'text' },
    @{ Letter = 'B'; Header = 'Descripcion';   Start = 41;  Length = 41; Type = 'text' },
    @{ Letter = 'C'; Header = 'Categoria';     Start = 82;  Length = 41; Type = 'text' },
    @{ Letter = 'D'; Header = 'Marca Vehiculo';Start = 123; Length = 41; Type = 'text' },
    @{ Letter = 'E'; Header = 'Marca Proveedor';Start = 164;Length = 41; Type = 'text' },
    @{ Letter = 'F'; Header = 'Existencia';    Start = 205; Length = 0;  Type = 'number' },
    @{ Letter = 'G'; Header = 'Precio';        Start = 205; Length = 0;  Type = 'number' },
    @{ Letter = 'H'; Header = 'CANT';          Start = 0;   Length = 0;  Type = 'empty' }
)

$tailRegex = [regex]'^\s*([\d.,]+)\s+([\d.,]+)\s*$'
$enc = [System.Text.Encoding]::GetEncoding(1252)

# ---------------------------------------------------------
# Conversion de un solo archivo
# ---------------------------------------------------------
function Convert-ListaTxtAExcel([string]$txtPath, [string]$xlsxPath) {
    if (-not (Test-Path -LiteralPath $txtPath)) { throw "No existe el archivo: $txtPath" }

    $text = [System.IO.File]::ReadAllText($txtPath, $enc)
    $lines = $text -split "`r?`n"

    $rows = New-Object System.Collections.Generic.List[object]
    foreach ($raw in $lines) {
        $line = $raw.TrimEnd("`r").TrimEnd()
        if ([string]::IsNullOrEmpty($line)) { continue }
        if ($line.Length -lt 40) { continue }

        $codigo = Get-Field $line 0 41
        $desc   = Get-Field $line 41 41
        $cat    = ((Get-Field $line 82 41) -replace '^\d+-', '').Trim()
        $marca  = Get-Field $line 123 41
        $prov   = Get-Field $line 164 41

        $existencia = ''
        $precio = ''
        $tailStart = [Math]::Min(205, $line.Length)
        if ($line.Length -gt 205) {
            $m = $tailRegex.Match($line.Substring(205))
            if ($m.Success) {
                $existencia = $m.Groups[1].Value
                $precio     = $m.Groups[2].Value
            }
        }

        $rows.Add(@{
            Codigo     = $codigo
            Desc       = $desc
            Cat        = $cat
            Marca      = $marca
            Prov       = $prov
            Existencia = (ConvertTo-Number $existencia)
            Precio     = (ConvertTo-Number $precio)
            CANT       = $null
        })
    }

    # Eliminar productos sin existencia (0) y ordenar por Categoria y luego Codigo
    $totalParse = $rows.Count
    $rows = @($rows | Where-Object { $null -eq $_.Existencia -or $_.Existencia -ne 0 })
    $eliminados = $totalParse - $rows.Count
    $rows = @($rows | ForEach-Object { [pscustomobject]$_ } | Sort-Object -Property Cat, Codigo)

    # --- XML de la hoja ---
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    [void]$sb.Append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>')
    [void]$sb.Append('<col min="1" max="1" width="16"/><col min="2" max="2" width="58"/><col min="3" max="3" width="28"/><col min="4" max="4" width="20"/><col min="5" max="5" width="22"/><col min="6" max="6" width="12"/><col min="7" max="7" width="14"/><col min="8" max="8" width="10"/>')
    [void]$sb.Append('</cols><sheetData>')

    # Encabezados
    [void]$sb.Append('<row r="1">')
    for ($c = 0; $c -lt $cols.Count; $c++) {
        $L = $cols[$c].Letter
        $h = ConvertTo-XmlText $cols[$c].Header
        [void]$sb.Append('<c r="').Append($L).Append('1" s="1" t="inlineStr"><is><t xml:space="preserve">').Append($h).Append('</t></is></c>')
    }
    [void]$sb.Append('</row>')

    # Datos
    $rowNum = 2
    foreach ($r in $rows) {
        [void]$sb.Append('<row r="').Append($rowNum).Append('">')
        [void]$sb.Append('<c r="A').Append($rowNum).Append('" s="2" t="inlineStr"><is><t xml:space="preserve">').Append((ConvertTo-XmlText $r.Codigo)).Append('</t></is></c>')
        [void]$sb.Append('<c r="B').Append($rowNum).Append('" s="2" t="inlineStr"><is><t xml:space="preserve">').Append((ConvertTo-XmlText $r.Desc)).Append('</t></is></c>')
        [void]$sb.Append('<c r="C').Append($rowNum).Append('" s="2" t="inlineStr"><is><t xml:space="preserve">').Append((ConvertTo-XmlText $r.Cat)).Append('</t></is></c>')
        [void]$sb.Append('<c r="D').Append($rowNum).Append('" s="2" t="inlineStr"><is><t xml:space="preserve">').Append((ConvertTo-XmlText $r.Marca)).Append('</t></is></c>')
        [void]$sb.Append('<c r="E').Append($rowNum).Append('" s="2" t="inlineStr"><is><t xml:space="preserve">').Append((ConvertTo-XmlText $r.Prov)).Append('</t></is></c>')

        if ($null -ne $r.Existencia) {
            $v = $r.Existencia.ToString([System.Globalization.CultureInfo]::InvariantCulture)
            [void]$sb.Append('<c r="F').Append($rowNum).Append('" s="4"><v>').Append($v).Append('</v></c>')
        } else {
            [void]$sb.Append('<c r="F').Append($rowNum).Append('" s="4"/>')
        }

        if ($null -ne $r.Precio) {
            $v = $r.Precio.ToString([System.Globalization.CultureInfo]::InvariantCulture)
            [void]$sb.Append('<c r="G').Append($rowNum).Append('" s="3"><v>').Append($v).Append('</v></c>')
        } else {
            [void]$sb.Append('<c r="G').Append($rowNum).Append('" s="3"/>')
        }

        [void]$sb.Append('<c r="H').Append($rowNum).Append('" s="4"/>')

        [void]$sb.Append('</row>')
        $rowNum++
    }

    [void]$sb.Append('</sheetData>')
    [void]$sb.Append('<autoFilter ref="A1:H').Append($rowNum - 1).Append('"/></worksheet>')

    $lastDataRow = $rowNum - 1

    # --- Partes OOXML ---
    $contentTypes = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
        '<Default Extension="xml" ContentType="application/xml"/>' +
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' +
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
        '</Types>'

    $rootRels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
        '</Relationships>'

    $workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
        '<sheets><sheet name="LISTA DE PRECIOS" sheetId="1" r:id="rId1"/></sheets></workbook>'

    $workbookRels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>' +
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' +
        '</Relationships>'

    $styles = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
        '<numFmts count="2">' +
        '<numFmt numFmtId="164" formatCode="#,##0.00"/>' +
        '<numFmt numFmtId="165" formatCode="#,##0"/>' +
        '</numFmts>' +
        '<fonts count="2">' +
        '<font><sz val="11"/><color rgb="FF000000"/><name val="Calibri"/></font>' +
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>' +
        '</fonts>' +
        '<fills count="3">' +
        '<fill><patternFill patternType="none"/></fill>' +
        '<fill><patternFill patternType="gray125"/></fill>' +
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>' +
        '</fills>' +
        '<borders count="2">' +
        '<border><left/><right/><top/><bottom/><diagonal/></border>' +
        '<border><left style="thin"><color rgb="FFBFBFBF"/></left><right style="thin"><color rgb="FFBFBFBF"/></right><top style="thin"><color rgb="FFBFBFBF"/></top><bottom style="thin"><color rgb="FFBFBFBF"/></bottom><diagonal/></border>' +
        '</borders>' +
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
        '<cellXfs count="5">' +
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center"/></xf>' +
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>' +
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>' +
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>' +
        '</cellXfs>' +
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
        '</styleSheet>'

    # --- Crear el .xlsx (zip) ---
    $finalPath = $xlsxPath
    $tries = 0
    $zip = $null
    while ($null -eq $zip) {
        try {
            if (Test-Path -LiteralPath $finalPath) { Remove-Item -LiteralPath $finalPath -Force -ErrorAction SilentlyContinue }
            $zip = [System.IO.Compression.ZipFile]::Open($finalPath, [System.IO.Compression.ZipArchiveMode]::Create)
        } catch {
            $tries++
            if ($tries -ge 100) { throw }
            $finalPath = [System.IO.Path]::ChangeExtension($xlsxPath, ".($tries).xlsx")
        }
    }
    try {
        Add-ZipEntry $zip "[Content_Types].xml" $contentTypes
        Add-ZipEntry $zip "_rels/.rels" $rootRels
        Add-ZipEntry $zip "xl/workbook.xml" $workbook
        Add-ZipEntry $zip "xl/_rels/workbook.xml.rels" $workbookRels
        Add-ZipEntry $zip "xl/styles.xml" $styles
        Add-ZipEntry $zip "xl/worksheets/sheet1.xml" $sb.ToString()
    }
    finally {
        $zip.Dispose()
    }

    Write-Host ("OK: {0} lineas -> {1} productos (se quitaron {2} con existencia 0) -> {3}" -f $lines.Count, $rows.Count, $eliminados, $finalPath)
    return $rows.Count
}

# ---------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------
if ([string]::IsNullOrWhiteSpace($Origen)) {
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = 'Selecciona el archivo TXT de lista de precios'
    $dialog.Filter = 'Archivos TXT (*.txt)|*.txt|Todos los archivos (*.*)|*.*'
    $dialog.InitialDirectory = '\\PRINCIPAL\a2admin\Empre001\REPORTS'
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        Write-Host 'No seleccionaste ningun archivo. Cancelado.'
        exit 0
    }
    $Origen = $dialog.FileName
}

$items = @()
if (Test-Path -LiteralPath $Origen -PathType Container) {
    $items = Get-ChildItem -LiteralPath $Origen -Filter *.txt
} else {
    $items = @(Get-Item -LiteralPath $Origen)
}

$totalRows = 0
foreach ($item in $items) {
    $out = $Destino
    if ([string]::IsNullOrWhiteSpace($out)) {
        $out = [System.IO.Path]::ChangeExtension($item.FullName, '.xlsx')
    } elseif ((Test-Path -LiteralPath $out -PathType Container)) {
        $out = Join-Path $out ([System.IO.Path]::GetFileNameWithoutExtension($item.Name) + '.xlsx')
    }
    $totalRows += (Convert-ListaTxtAExcel $item.FullName $out)
}

Write-Output ("Total filas convertidas: {0}" -f $totalRows)
