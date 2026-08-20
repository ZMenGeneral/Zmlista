import pdfplumber

pdf_path = r'\\Principal\c\Users\SERVIDOR\Documents\Negocio\ZM Autopartes\FACTURAS\2026\AGOSTO\17-08\FRANCISCO JOSE FUENMAYOR RIVAS N16775.pdf'

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        print(f'=== PAGE {i+1} (width={page.width}, height={page.height}) ===')
        print()
        words = page.extract_words(keep_blank_chars=True, x_tolerance=2, y_tolerance=2)
        
        # Group words by approximate y position (same line)
        lines = {}
        for w in words:
            top = round(w['top'], 1)
            found = False
            for key in list(lines.keys()):
                if abs(key - top) < 3:
                    lines[key].append(w)
                    found = True
                    break
            if not found:
                lines[top] = [w]
        
        # Sort by y position and print
        for y in sorted(lines.keys()):
            line_words = sorted(lines[y], key=lambda w: w['x0'])
            text_parts = []
            pos_parts = []
            for w in line_words:
                text_parts.append(w['text'])
                pos_parts.append(f"{w['text']}(x0={w['x0']:.1f},top={w['top']:.1f})")
            text = ' '.join(text_parts)
            positions = ' | '.join(pos_parts)
            print(f'y={y:7.1f}: {positions}')
            print(f'          TEXT: {text}')
            print()
        
        # Also print tables if any
        print('--- TABLES ---')
        tables = page.extract_tables()
        for ti, table in enumerate(tables):
            print(f'Table {ti}: {len(table)} rows')
            for ri, row in enumerate(table):
                print(f'  Row {ri}: {row}')
            print()
