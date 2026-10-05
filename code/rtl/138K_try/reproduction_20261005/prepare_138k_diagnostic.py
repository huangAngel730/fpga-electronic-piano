"""Prepare device-only 138K copies, retaining frozen constraints to expose incompatibilities."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
control = HERE / '60K_control'
audit = json.loads((HERE / 'input_audit.json').read_text(encoding='utf-8'))
assert audit['frozen_project_entries_verified'] == 47
literal = re.compile(r'"([^"\r\n]+\.(?:mem|hex|svh))"')
changes = []
for label, device_id, name in [
    ('138K_B_frozen_constraints', 'gw5ast138b-011', 'GW5AST-138B'),
    ('138K_C_frozen_constraints', 'gw5ast138c-007', 'GW5AST-138C'),
]:
    out = HERE / label
    if out.exists():
        raise ValueError('Preserve existing diagnostic directory')
    out.mkdir()
    records = []
    for record in audit['source_copies']:
        source = Path(record['target'])
        assert source.is_relative_to(control)
        raw = source.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record['target_SHA256']
        target = out / source.relative_to(control)
        data = raw
        if source.suffix in ('.v', '.sv'):
            text = raw.decode('utf-8')

            def replace(match):
                path = Path(match[1])
                assert path.is_relative_to(control)
                return '"' + (out / path.relative_to(control)).as_posix() + '"'

            rewritten = literal.sub(replace, text)
            assert literal.sub('"<path>"', text) == literal.sub('"<path>"', rewritten)
            data = rewritten.encode('utf-8')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        records.append({'name': source.name, 'control_SHA256': record['target_SHA256'],
                        'target_SHA256': hashlib.sha256(data).hexdigest(),
                        'target': str(target), 'non_path_identity': True})
    tree = ET.fromstring((control / 'audio_visual_coexistence_top.gprj').read_bytes())
    device = tree.find('Device')
    previous = {'id': device.text, **device.attrib}
    device.text = device_id
    device.set('name', name)
    device.set('pn', 'GW5AST-LV138PG484AC1/I0')
    for node in tree.findall('./FileList/File'):
        source = Path(node.attrib['path'])
        node.set('path', (out / source.relative_to(control)).as_posix())
    (out / 'audio_visual_coexistence_top.gprj').write_bytes(
        ET.tostring(tree, encoding='utf-8', xml_declaration=True))
    tcl = (control / 'run.tcl').read_text(encoding='utf-8').replace(control.as_posix(), out.as_posix())
    (out / 'run.tcl').write_text(tcl, encoding='utf-8')
    changes.append({'label': label, 'device_before': previous,
                    'device_after': {'id': device.text, **device.attrib}, 'files': records,
                    'CST_SDC_unchanged': True, 'IP_source_unchanged': True,
                    'scope': 'Device-only diagnostic, NOT electrically adapted or board-release design',
                    'known_board_voltage_mismatch': ['sys_rst_n', 'key_n[0]', 'key_n[1]'],
                    'fixed_PLL_and_reset_locations_not_removed': True})
(HERE / '138k_diagnostic_manifest.json').write_text(
    json.dumps(changes, indent=2) + '\n', encoding='utf-8')
print('PASS prepared 138K B/C device-only diagnostics; SDC/CST/IP bytes preserved')
print('NOT hardware-ready: deliberate frozen electrical/fixed-location assumptions must be validated')
