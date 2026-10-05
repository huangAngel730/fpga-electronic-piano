"""Make documented Bank5 declaration-only copies and explicitly retain control options."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
model_result = json.loads((HERE / 'pll_model_test/result.json').read_text(encoding='utf-8'))
assert model_result['passed'] and model_result['compile_exit'] == model_result['run_exit'] == 0
schematic = ROOT / 'comparison_20261005_dab75308/board_138k_schematic.pdf'
assert hashlib.sha256(schematic.read_bytes()).hexdigest() == '326c45a7ae05e990d5f885fba6ec9b589d966941aa3c00f7d43122d99c068af7'
records = []
for version in ['B', 'C']:
    source_dir = HERE / f'138K_{version}_pll_migration'
    out = HERE / f'138K_{version}_electrical_migration'
    if out.exists():
        raise ValueError('Preserve prior electrical candidate')
    out.mkdir()
    changes = []
    hashes = {}
    for folder in ['sources', 'constraints', 'rom', 'include']:
        for source_file in (source_dir / folder).iterdir():
            target = out / folder / source_file.name
            target.parent.mkdir(exist_ok=True)
            data = source_file.read_bytes()
            if source_file.suffix in ('.v', '.sv'):
                data = data.replace(source_dir.as_posix().encode(), out.as_posix().encode())
            if source_file.name == 'audio_visual.cst':
                text = data.decode('utf-8')
                old_lines = text.splitlines(keepends=True)
                new_lines = []
                for line in old_lines:
                    if re.match(r'IO_PORT\s+"(?:sys_rst_n|key_n\[0\]|key_n\[1\])"', line):
                        assert 'IO_TYPE=LVCMOS15' in line and 'BANK_VCCIO=1.5' in line
                        new_line = line.replace('IO_TYPE=LVCMOS15', 'IO_TYPE=LVCMOS33').replace('BANK_VCCIO=1.5', 'BANK_VCCIO=3.3')
                        changes.append({'from': line.strip(), 'to': new_line.strip()})
                        line = new_line
                    new_lines.append(line)
                assert len(changes) == 3
                data = ''.join(new_lines).encode('utf-8')
                assert re.findall(r'^IO_LOC.*$', text, re.M) == re.findall(r'^IO_LOC.*$', data.decode(), re.M)
                assert re.findall(r'^INS_LOC.*$', text, re.M) == re.findall(r'^INS_LOC.*$', data.decode(), re.M)
            target.write_bytes(data)
            hashes[str(target.relative_to(out))] = hashlib.sha256(data).hexdigest()
    tree = ET.fromstring((source_dir / 'audio_visual_coexistence_top.gprj').read_bytes())
    for node in tree.findall('./FileList/File'):
        node.set('path', node.attrib['path'].replace(source_dir.as_posix(), out.as_posix()))
    (out / 'audio_visual_coexistence_top.gprj').write_bytes(
        ET.tostring(tree, encoding='utf-8', xml_declaration=True))
    tcl = (source_dir / 'run.tcl').read_text(encoding='utf-8').replace(source_dir.as_posix(), out.as_posix())
    options = ['set_option -place_option 0', 'set_option -route_option 0',
               'set_option -ireg_in_iob 1', 'set_option -oreg_in_iob 1',
               'set_option -ioreg_in_iob 1', 'set_option -correct_hold_violation 1',
               'set_option -clock_route_order 0', 'set_option -route_maxfan 23']
    tcl = tcl.replace('run all\n', '\n'.join(options) + '\nrun all\n')
    (out / 'run.tcl').write_text(tcl, encoding='utf-8')
    assert (out / 'constraints/audio_visual_hold055.sdc').read_bytes() == (
        HERE / '60K_control/constraints/audio_visual_hold055.sdc').read_bytes()
    records.append({'label': out.name, 'file_SHA256': hashes, 'CST_changes': changes,
                    'IO_LOC_and_INS_LOC_unchanged': True, 'SDC_byte_identical': True,
                    'explicit_control_PnR_options': options,
                    'reason': '138K core schematic Bank5=3.3V; actual CT1136 on inherited 1.5V inputs',
                    'scope': 'Offline compatibility experiment only; bottom-board/real inputs unverified',
                    'programmed': False})
report = {'time': datetime.now().astimezone().isoformat(), 'candidates': records,
          'references': {'core_schematic': str(schematic),
                         'options_manual_text_pages': [123, 124, 125, 127]},
          'original_CST_SDC_modified': False, 'original_repo_written': False}
(HERE / 'electrical_migration_manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('PASS prepared B/C candidates: exactly 3 Bank5 input declarations adapted; all ball/fixed locations retained')
print('PASS SDC unchanged; original 60K placement/routing/IO-register option requests explicit')
