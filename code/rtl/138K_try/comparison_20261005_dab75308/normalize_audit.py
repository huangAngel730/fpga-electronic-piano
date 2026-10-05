"""Hash-prove path-only or newline-only identity; never change repository data."""
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re

ROOT = Path(__file__).resolve().parent
if ROOT.parent != Path('E:/FPGA/GAOYUNFPGA/138K_try'):
    raise ValueError('Unauthorized output directory')
audit = json.loads((ROOT / 'input_audit.json').read_text(encoding='utf-8'))
manifest = json.loads(Path(audit['manifest']).read_text(encoding='utf-8'))
rom_paths = {PureWindowsPath(k).name: k.replace('\\', '/') for k in manifest['roms']}
input_by_name = {PureWindowsPath(x['input_source']).name: x for x in manifest['source_builds']}
results = []
for item in audit['files']:
    if item['actual_matches']:
        continue
    expected = item['expected_actual_sha256']
    attempted = []
    matched = []
    for candidate in item['candidates']:
        if not candidate:
            continue
        p = Path(candidate['path'])
        original = p.read_text(encoding='utf-8-sig')
        variations = {'LF': original.replace('\r\n', '\n')}
        replacement_log = []
        rewritten = variations['LF']
        for literal in set(re.findall(r'"([^"\r\n]+\.(?:mem|hex))"', rewritten)):
            name = PureWindowsPath(literal).name
            if name in rom_paths:
                replacement_log.append({'from': literal, 'to': rom_paths[name]})
                rewritten = rewritten.replace('"' + literal + '"', '"' + rom_paths[name] + '"')
        variations['historical_actual_ROM_paths_LF'] = rewritten
        variations['CRLF'] = variations['LF'].replace('\n', '\r\n')
        variations['historical_actual_ROM_paths_CRLF'] = rewritten.replace('\n', '\r\n')
        for label, content in variations.items():
            digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
            attempted.append({'path': str(p), 'variant': label, 'sha256': digest})
            if digest == expected:
                matched.append({'path': str(p), 'variant': label, 'sha256': digest,
                                'replacements': replacement_log if label.startswith('historical') else []})
    results.append({'name': item['name'], 'expected_actual_sha256': expected,
                    'matches': matched, 'attempts': attempted})
report = {'scope': 'Limited explicit ROM-path/LF/CRLF hash identity checks; no logical substitutions',
          'files': results, 'all_actual_inputs_available': all(
              x['actual_matches'] or any(y['name'] == x['name'] and y['matches'] for y in results)
              for x in audit['files'])}
(ROOT / 'normalized_audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
for item in results:
    print(f"{item['name']}: normalized_actual_matches={len(item['matches'])}")
print('ALL_ACTUAL_INPUTS_AVAILABLE', report['all_actual_inputs_available'])
