"""Copy only revalidated frozen-byte inputs; no EDA or repository writes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
if HERE != Path('E:/FPGA/GAOYUNFPGA/138K_try/m3_continuation_20261005'):
    raise ValueError('Unexpected output root')
AUDIT = HERE / 'audit_snapshot'
audit = json.loads((AUDIT / 'input_audit.json').read_text(encoding='utf-8'))
norm = json.loads((AUDIT / 'normalized_audit.json').read_text(encoding='utf-8'))
OUT = HERE / 'proven_bundle'
records = []
missing = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(name, data, expected, source, method, folder='sources'):
    if sha(data) != expected:
        raise ValueError('Identity changed: ' + name)
    target = OUT / folder / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Refuse overwrite: ' + name)
    target.write_bytes(data)
    records.append({'name': name, 'source': source, 'method': method,
                    'sha256': expected, 'copy': str(target), 'bytes': len(data)})


for item in audit['files']:
    name, expected = item['name'], item['expected_actual_sha256']
    proven = HERE / 'recovery/hash_proven_inputs' / name
    if proven.is_file():
        save(name, proven.read_bytes(), expected, str(proven), 'SHA-gated recovery')
        continue
    direct = item['actual_matches']
    if direct:
        # Prefer a formal source over an output test fixture when available.
        direct = sorted(direct, key=lambda x: ('/code/output/' in x['path'].replace('\\', '/'), len(x['path'])))
        source = Path(direct[0]['path'])
        save(name, source.read_bytes(), expected, str(source), 'direct frozen-byte match')
        continue
    matches = next((x['matches'] for x in norm['files'] if x['name'] == name), [])
    if matches:
        match = matches[0]
        source = Path(match['path'])
        text = source.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
        if match['variant'].startswith('historical'):
            for change in match['replacements']:
                text = text.replace('"' + change['from'] + '"', '"' + change['to'] + '"')
        if match['variant'].endswith('CRLF'):
            text = text.replace('\n', '\r\n')
        save(name, text.encode('utf-8'), expected, str(source), match['variant'])
        continue
    missing.append({'name': name, 'expected_sha256': expected})

project_count = len(records)
for item in audit['roms']:
    source = Path(item['matches'][0]['path'])
    save(item['name'], source.read_bytes(), item['expected_sha256'], str(source),
         'direct ROM identity', 'rom')
snapshot = HERE / 'recovery/audio_e5eb025/code/rtl'
for relative, expected in [
    ('common/sine_table.svh', '969fc7d1036e359fc55c3b0ca18eaf3c8a123a146ed95c32a81e52ee10519cca'),
    ('board/sustain_controller_ports.svh', '8c51459cd47a7e21609cc02780a93af7d6be0fd5bf2d2278edda92e8a7ef486d')
]:
    source = snapshot / relative
    save(source.name, source.read_bytes(), expected, str(source),
         'e5eb025 Git snapshot; independently recorded header SHA', 'include')
assert len(audit['files']) == 47
assert project_count == 46
assert [x['name'] for x in missing] == ['DVI_TX_Top.v']
assert len(audit['roms']) == 7
parser = next(x for x in records if x['name'] == 'midi_event_parser.sv')
assert parser['sha256'] == '834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6'
report = {
    'scope': 'Recovered frozen bytes, NOT original final manifest or runnable project',
    'project_entries_expected': 47, 'project_entries_proven_copied': project_count,
    'ROMs_proven_copied': 7, 'headers_proven_copied': 2,
    'missing': missing, 'records': records,
    'original_absolute_paths_preserved_for_identity': True,
    'relocatable_build_copy_created': False,
    'original_V0171_manifest_available': False,
    'EDA_gate': 'BLOCKED_INPUT_CLOSURE', 'PnR_executed': False,
    'source_repo_written': False,
}
(HERE / 'proven_bundle_manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('PASS: 46/47 frozen project entries + 7 ROMs + 2 headers rehashed and copied.')
print('PASS: exact de68038 parser identity; only missing entry is DVI_TX_Top.v.')
print('EDA GATE: BLOCKED_INPUT_CLOSURE; no synthesis/PnR invoked.')
