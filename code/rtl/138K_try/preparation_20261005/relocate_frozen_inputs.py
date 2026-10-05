"""Create a path-only relocated copy while preserving frozen SHA-proven bytes."""
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re

HERE = Path(__file__).resolve().parent
if HERE != Path('E:/FPGA/GAOYUNFPGA/138K_try/preparation_20261005'):
    raise ValueError('Unexpected output root')
PROOF = HERE.parent / 'm3_continuation_20261005/proven_bundle_manifest.json'
source_manifest = json.loads(PROOF.read_text(encoding='utf-8'))
OUT = HERE / 'relocated_bundle'
file_literal = re.compile(r'"([^"\r\n]+\.(?:mem|hex|svh))"')
data_names = {r['name']: OUT / ('include' if r['name'].endswith('.svh') else 'rom') / r['name']
              for r in source_manifest['records'] if r['name'].endswith(('.mem', '.hex', '.svh'))}
records = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(text):
    return file_literal.sub(lambda m: '"<data:' + PureWindowsPath(m[1]).name + '>"', text)


for record in source_manifest['records']:
    source = Path(record['copy'])
    raw = source.read_bytes()
    if sha(raw) != record['sha256']:
        raise ValueError('Frozen proof changed: ' + record['name'])
    folder = source.parent.name
    target = OUT / folder / record['name']
    changes = []
    data = raw
    if source.suffix in ('.sv', '.v'):
        original = raw.decode('utf-8')

        def replace(match):
            literal = match[1]
            name = PureWindowsPath(literal).name
            if name not in data_names:
                raise ValueError('Unknown data dependency: ' + literal)
            replacement = data_names[name].as_posix()
            changes.append({'from': literal, 'to': replacement, 'offset': match.start()})
            return '"' + replacement + '"'

        rewritten = file_literal.sub(replace, original)
        if canonical(original) != canonical(rewritten):
            raise ValueError('Non-path change detected')
        data = rewritten.encode('utf-8')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Conflicting relocated copy')
    target.write_bytes(data)
    records.append({'name': record['name'], 'original': str(source), 'relocated': str(target),
                    'old_sha256': sha(raw), 'new_sha256': sha(data),
                    'changes': changes, 'non_path_identity_passed': True})

for record in records:
    if record['name'].endswith(('.cst', '.sdc', '.mem', '.svh')):
        assert record['old_sha256'] == record['new_sha256']
    target = Path(record['relocated'])
    if target.suffix in ('.sv', '.v'):
        for match in file_literal.finditer(target.read_text(encoding='utf-8')):
            assert Path(match[1]).is_file(), match[1]
            assert Path(match[1]).is_relative_to(OUT), match[1]
assert len(records) == 55
report = {
    'scope': 'Path-only preparation; not a final manifest or runnable frozen V0171 project',
    'frozen_project_entries_available': 46, 'frozen_project_entries_expected': 47,
    'missing': source_manifest['missing'],
    'replaced_path_occurrences': sum(len(r['changes']) for r in records),
    'CST_SDC_ROM_headers_byte_identical': True,
    'all_visible_include_ROM_references_resolved_inside_copy': True,
    'original_proven_bundle_unchanged': True, 'records': records,
    'GPRJ_options_finalized': False, 'PnR_of_V0171_executed': False,
}
(HERE / 'relocation_manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('PASS: 55 frozen proof files rehashed; path-only copy created.')
print('PASS: CST/SDC/ROM/header bytes unchanged; all visible data/include paths local.')
print('Path replacements:', report['replaced_path_occurrences'])
print('V0171 remains blocked by original DVI IP and frozen runtime metadata.')
