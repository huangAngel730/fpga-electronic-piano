"""Inspect local PDF references; all derived output stays in this experiment."""
import hashlib
import json
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parent
if ROOT.parent != Path('E:/FPGA/GAOYUNFPGA/138K_try'):
    raise ValueError('Unauthorized output root')
summaries = []
for name in ('board_138k_schematic.pdf', 'gowin_user_guide.pdf'):
    p = ROOT / name
    document = fitz.open(p)
    records = []
    terms = ('V22', 'AA13', 'AB13', 'Y12', '50MHz') if name.startswith('board') else (
        'Tcl', 'gw_sh', 'gw_ide', 'run pnr', 'Run All', 'Place & Route')
    for index, page in enumerate(document):
        text = page.get_text()
        hits = [term for term in terms if term.lower() in text.lower()]
        if hits or name.startswith('board'):
            output = ROOT / (p.stem + f'_page_{index+1}.txt')
            output.write_text(text, encoding='utf-8')
            records.append({'page': index+1, 'terms': hits, 'text_file': output.name})
            if name.startswith('board'):
                page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7)).save(
                    ROOT / f'board_138k_page_{index+1}.png')
    summaries.append({'file': name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                      'page_count': len(document), 'matched_pages': records})
(ROOT / 'reference_inspection.json').write_text(json.dumps(summaries, indent=2)+'\n', encoding='utf-8')
for summary in summaries:
    print(summary['file'], 'pages=', summary['page_count'], 'sha256=', summary['sha256'])
