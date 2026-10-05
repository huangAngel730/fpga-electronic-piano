"""Audit M2 originals and construct a path-only frozen 60K control project."""
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path, PureWindowsPath
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
PACKAGE = ROOT / 'M2_DVI_V0171_originals_20261005'
ORIGINAL = PACKAGE / 'originals/V0171'
OUT = HERE / '60K_control'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def confined(path, root=ROOT):
    result = Path(path).resolve()
    if not result.is_relative_to(root):
        raise ValueError('Path outside expected root: ' + str(path))
    return result


def save(path, data):
    path = confined(path, HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError('Refuse to overwrite different preparation file: ' + str(path))
    path.write_bytes(data)


inventory = json.loads((PACKAGE / 'PACKAGE_INVENTORY.json').read_text(encoding='utf-8'))
rows = list(csv.DictReader(io.StringIO((PACKAGE / 'FILE_LIST.tsv').read_text(encoding='utf-8')), delimiter='\t'))
checksums = {}
for line in (PACKAGE / 'FILES_SHA256.txt').read_text(encoding='utf-8').splitlines():
    checksum, relative = line.split('  ', 1)
    checksums[relative] = checksum
assert len(rows) == len(checksums) == inventory['originalFileCount'] == 31
inventory_by_path = {r['archivePath']: r for r in inventory['originalFiles']}
assert set(inventory_by_path) == set(checksums) == {r['archive_path'] for r in rows}
audit = []
for row in rows:
    relative = row['archive_path']
    path = confined(PACKAGE / relative, PACKAGE)
    raw = path.read_bytes()
    checksum = digest(raw)
    assert checksum == row['sha256'] == checksums[relative] == inventory_by_path[relative]['sha256']
    assert len(raw) == int(row['bytes']) == inventory_by_path[relative]['sizeBytes']
    audit.append({'path': relative, 'bytes': len(raw), 'sha256': checksum})
for name in ['FILE_LIST.tsv', 'FILES_SHA256.txt']:
    assert (ROOT / name).read_bytes() == (PACKAGE / name).read_bytes()

manifest_bytes = (ORIGINAL / 'input_manifest.json').read_bytes()
assert digest(manifest_bytes) == '1e29e550b129176e06fe609631229ae7c03a22ed3ad9ac4652f0705c7a234a36'
gui = (PACKAGE / 'originals/dvi_gui/DVI_TX_Top.v').read_bytes()
dvi = (PACKAGE / 'originals/dvi_actual_lf/DVI_TX_Top.v').read_bytes()
assert digest(gui) == 'b378c6a41d06a14215dc9ec54ed20bfc91309a0bb1543c589246717da3aee2ab'
assert digest(dvi) == '162f68cab4262f8a3acae17f2fc66b6d9ef403815fd5ebeeecf30b59d88e203c'
assert gui.replace(b'\r\n', b'\n') == dvi
manifest = json.loads(manifest_bytes)
proof = json.loads((ROOT / 'm3_continuation_20261005/proven_bundle_manifest.json').read_text(encoding='utf-8'))
by_name = {r['name']: r for r in proof['records']}
assert len(by_name) == 55
source_hashes = {}
for record in manifest['source_builds']:
    name = PureWindowsPath(record['actual_source']).name
    assert name not in source_hashes
    source_hashes[name] = record['actual_sha']
assert len(source_hashes) == 47
original_tree = ET.fromstring((ORIGINAL / 'audio_visual_coexistence_top.gprj').read_bytes())
files = original_tree.findall('./FileList/File')
assert len(files) == 47
assert {PureWindowsPath(f.attrib['path']).name for f in files} == set(source_hashes)
assert original_tree.find('Device').text == 'gw5at60b-002'
assert original_tree.find('Device').attrib['pn'] == 'GW5AT-LV60PG484AC1/I0'

raw_by_name = {}
for name, record in by_name.items():
    path = confined(record['copy'])
    raw = path.read_bytes()
    assert digest(raw) == record['sha256']
    if name in source_hashes:
        assert digest(raw) == source_hashes[name], name
    raw_by_name[name] = (path, raw)
raw_by_name['DVI_TX_Top.v'] = (PACKAGE / 'originals/dvi_actual_lf/DVI_TX_Top.v', dvi)
assert source_hashes['DVI_TX_Top.v'] == digest(dvi)
for name in ['audio_visual.cst', 'audio_visual_hold055.sdc', 'midi_event_parser.sv']:
    package_path = ORIGINAL / ('constraints' if name.endswith(('.cst', '.sdc')) else '') / name
    assert package_path.read_bytes() == raw_by_name[name][1]
for path, checksum in manifest['roms'].items():
    assert digest(raw_by_name[PureWindowsPath(path).name][1]) == checksum


def target(name):
    folder = ('rom' if name.endswith(('.mem', '.hex')) else 'include' if name.endswith('.svh')
              else 'constraints' if name.endswith(('.cst', '.sdc')) else 'sources')
    return OUT / folder / name


literal = re.compile(r'"([^"\r\n]+\.(?:mem|hex|svh))"')


def canonical(text):
    return literal.sub(lambda m: '"<data:' + PureWindowsPath(m[1]).name + '>"', text)


copied = []
for name, (original_path, raw) in raw_by_name.items():
    rewritten = raw
    changes = []
    if name.endswith(('.sv', '.v')):
        text = raw.decode('utf-8')

        def replace(match):
            data_name = PureWindowsPath(match[1]).name
            assert data_name in raw_by_name, match[1]
            replacement = target(data_name).as_posix()
            changes.append({'from': match[1], 'to': replacement, 'offset': match.start()})
            return '"' + replacement + '"'

        new_text = literal.sub(replace, text)
        assert canonical(text) == canonical(new_text)
        rewritten = new_text.encode('utf-8')
    save(target(name), rewritten)
    copied.append({'name': name, 'original': str(original_path), 'target': str(target(name)),
                   'original_SHA256': digest(raw), 'target_SHA256': digest(rewritten),
                   'path_replacements': changes, 'non_path_identity': True})
assert len(copied) == 56
assert sum(len(r['path_replacements']) for r in copied) == 20
for record in copied:
    if record['name'].endswith(('.v', '.sv')):
        for match in literal.finditer(Path(record['target']).read_text(encoding='utf-8')):
            assert confined(match[1], OUT).is_file()
    else:
        assert record['original_SHA256'] == record['target_SHA256']

project_changes = []
for node in files:
    old = node.attrib['path']
    new = target(PureWindowsPath(old).name).as_posix()
    node.set('path', new)
    project_changes.append({'from': old, 'to': new})
project = ET.tostring(original_tree, encoding='utf-8', xml_declaration=True)
save(OUT / 'audio_visual_coexistence_top.gprj', project)
old_tcl = (ORIGINAL / 'run.tcl').read_bytes().decode('utf-8')
lines = old_tcl.splitlines()
assert len(lines) == 4
assert lines[0].startswith('open_project {')
assert lines[1:] == ['set_option -top_module audio_visual_coexistence_top',
                      'set_option -verilog_std sysv2017', 'run all']
lines[0] = 'open_project {' + (OUT / 'audio_visual_coexistence_top.gprj').as_posix() + '}'
save(OUT / 'run.tcl', ('\n'.join(lines) + '\n').encode('utf-8'))

report = {'time': datetime.now().astimezone().isoformat(), 'package_original_files_verified': 31,
          'ZIP_available_for_hash_check': False,
          'root_sidecar_lists_match_package': True, 'manifest_SHA256': digest(manifest_bytes),
          'DVI_GUI_LF_identity_passed': True, 'frozen_project_entries_verified': 47,
          'ROMs_verified': len(manifest['roms']), 'headers_verified_from_proof': 2,
          'source_copies': copied, 'project_path_replacements': project_changes,
          'CST_SDC_byte_identical': True, 'GPRJ_file_order_device_and_non_path_options_preserved': True,
          'Tcl_non_path_options_preserved': True,
          'original_repo_written': False, 'M2_originals_modified': False,
          'build_executed_by_this_preparation': False, 'package_audit': audit}
save(HERE / 'input_audit.json', (json.dumps(report, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
print('PASS M2 package: 31 originals + sidecar lists verified; original manifest and both DVI hashes match')
print('PASS frozen closure: 47/47 project entries, 7 ROMs, 2 headers; 56 physical files copied')
print('PASS control relocation: 20 paths only; CST/SDC unchanged; GPRJ order/device and Tcl options preserved')
print('ZIP not supplied; individual extracted-file hashes verified, no claim of ZIP hash verification')
