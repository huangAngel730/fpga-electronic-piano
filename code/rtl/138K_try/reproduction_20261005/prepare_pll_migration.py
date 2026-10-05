"""Create separately named primitive migration candidates; do not alter failed evidence."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
vendor = ROOT / 'tools/gowin_1_9_11_03/IDE/simlib/gw5a/prim_sim.v'
model = vendor.read_bytes()
text = model.decode('utf-8')
pll = re.search(r'^module PLL \(.*?^endmodule', text, re.M | re.S)
assert pll
source = (HERE / '60K_control/sources/TMDS_PLL_800_600_60.v').read_text(encoding='utf-8')
new = source.replace('PLLA PLLA_inst (', 'PLL PLLA_inst (')
assert new != source
new = new.replace('    .MDRDO(mdrdo),\n', '')
old_dynamic = '''    .MDCLK(gw_gnd),
    .MDOPC({gw_gnd,gw_gnd}),
    .MDAINC(gw_gnd),
    .MDWDI({gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd,gw_gnd})'''
new_static = '''    .ENCLK0(1'b1), .ENCLK1(1'b1),
    .ENCLK2(1'b0), .ENCLK3(1'b0), .ENCLK4(1'b0), .ENCLK5(1'b0), .ENCLK6(1'b0),
    .FBDSEL(6'b0), .IDSEL(6'b0), .MDSEL(7'b0), .MDSEL_FRAC(3'b0),
    .ODSEL0(7'b0), .ODSEL0_FRAC(3'b0),
    .ODSEL1(7'b0), .ODSEL2(7'b0), .ODSEL3(7'b0), .ODSEL4(7'b0), .ODSEL5(7'b0), .ODSEL6(7'b0),
    .DT0(4'b0), .DT1(4'b0), .DT2(4'b0), .DT3(4'b0),
    .ICPSEL(6'b0), .LPFRES(3'b0), .LPFCAP(2'b0)'''
assert old_dynamic in new
new = new.replace(old_dynamic, new_static)
new = ('// M3 offline 138K PLL primitive migration candidate, NOT GUI-generated or board-released.\n'
       '// Interface, static dividers, output enables and PLLA_inst hierarchy retained.\n' + new)
# Every original static parameter must be supported by the official PLL model.
original_parameters = re.findall(r'defparam PLLA_inst\.(\w+)\s*=\s*([^;]+);', source)
for parameter, value in original_parameters:
    assert re.search(r'parameter\s+' + parameter + r'\s*=', pll[0]), parameter
    assert f'defparam PLLA_inst.{parameter} = {value};' in new
assert len(original_parameters) > 50
assert 'defparam PLLA_inst.MDIV_SEL = 20;' in new
assert 'defparam PLLA_inst.ODIV0_SEL = 8;' in new
assert 'defparam PLLA_inst.ODIV1_SEL = 40;' in new
model_copy = HERE / 'pll_model_test/vendor_prim_sim.v'
model_copy.parent.mkdir(exist_ok=True)
if model_copy.exists() and model_copy.read_bytes() != model:
    raise ValueError('Preserve prior model evidence')
model_copy.write_bytes(model)
candidates = []
for version in ['B', 'C']:
    source_dir = HERE / f'138K_{version}_frozen_constraints'
    out = HERE / f'138K_{version}_pll_migration'
    if out.exists():
        raise ValueError('Preserve prior migration attempt')
    out.mkdir()
    source_hashes = {}
    for folder in ['sources', 'constraints', 'rom', 'include']:
        for source_file in (source_dir / folder).iterdir():
            target = out / folder / source_file.name
            target.parent.mkdir(exist_ok=True)
            data = source_file.read_bytes()
            if source_file.suffix in ('.v', '.sv'):
                data = data.replace(source_dir.as_posix().encode(), out.as_posix().encode())
            if source_file.name == 'TMDS_PLL_800_600_60.v':
                data = new.encode('utf-8')
            target.write_bytes(data)
            source_hashes[str(target.relative_to(out))] = hashlib.sha256(data).hexdigest()
    tree = ET.fromstring((source_dir / 'audio_visual_coexistence_top.gprj').read_bytes())
    for node in tree.findall('./FileList/File'):
        node.set('path', node.attrib['path'].replace(source_dir.as_posix(), out.as_posix()))
    (out / 'audio_visual_coexistence_top.gprj').write_bytes(
        ET.tostring(tree, encoding='utf-8', xml_declaration=True))
    tcl = (source_dir / 'run.tcl').read_text(encoding='utf-8').replace(source_dir.as_posix(), out.as_posix())
    (out / 'run.tcl').write_text(tcl, encoding='utf-8')
    candidates.append({'label': out.name, 'file_SHA256': source_hashes,
                       'functional_change': 'PLLA -> PLL primitive/static port interface only',
                       'parameters_and_hierarchy_preserved': True, 'CST_SDC_unchanged': True,
                       'DVI_source_unchanged': True, 'board_release': False,
                       'known_electrical_mismatch_not_fixed': True})
report = {'time': datetime.now().astimezone().isoformat(),
          'source_reference': str(vendor), 'vendor_model_SHA256': hashlib.sha256(model).hexdigest(),
          'original_PLL_SHA256': hashlib.sha256(source.encode()).hexdigest(),
          'candidate_PLL_SHA256': hashlib.sha256(new.encode()).hexdigest(),
          'original_parameters_preserved': dict(original_parameters), 'candidates': candidates,
          'scope': 'Tool-library-derived offline migration; not official GUI generation or silicon acceptance'}
(HERE / 'pll_migration_manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('PASS prepared separate B/C PLL primitive migration candidates; all static parameters retained')
print('Vendor model SHA256:', report['vendor_model_SHA256'])
