"""Generate isolated, non-board Gowin support probes with known device IDs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
if HERE != Path('E:/FPGA/GAOYUNFPGA/138K_try/preparation_20261005'):
    raise ValueError('Unexpected output root')
targets = [
    ('60K', 'GW5AT-60B', 'GW5AT-LV60PG484AC1/I0', 'gw5at60b-002'),
    ('138K_B', 'GW5AST-138B', 'GW5AST-LV138PG484AC1/I0', 'gw5ast138b-011'),
    ('138K_C', 'GW5AST-138C', 'GW5AST-LV138PG484AC1/I0', 'gw5ast138c-007'),
]
records = []
for label, name, pn, device in targets:
    project_dir = HERE / 'toolchain' / label
    project_dir.mkdir(parents=True, exist_ok=True)
    project = project_dir / 'tool_probe.gprj'
    content = f'''<?xml version="1" encoding="UTF-8"?>
<!DOCTYPE gowin-fpga-project>
<Project>
  <Template>FPGA</Template><Version>5</Version>
  <Device name="{name}" pn="{pn}">{device}</Device>
  <FileList>
    <File path="../../tool_probe.v" type="file.verilog" enable="1"/>
    <File path="../../tool_probe.sdc" type="file.sdc" enable="1"/>
  </FileList>
</Project>
'''
    if project.exists() and project.read_text(encoding='utf-8') != content:
        raise ValueError('Conflicting project, preserve it')
    project.write_text(content, encoding='utf-8', newline='\n')
    tcl = project_dir / 'run.tcl'
    tcl.write_text('puts {M3 TOOLCHAIN SUPPORT PROBE ONLY; NOT V0171}\n'
                   'open_project {tool_probe.gprj}\n'
                   'set_option -top_module tool_probe\n'
                   'set_option -verilog_std v2001\n'
                   'run all\n', encoding='utf-8', newline='\n')
    records.append({'label': label, 'device': device, 'pn': pn, 'package': 'PBGA484A',
                    'speed': 'C1/I0', 'project': str(project),
                    'project_sha256': hashlib.sha256(project.read_bytes()).hexdigest(),
                    'board_pin_assignment': False, 'hardware_usable': False})
(HERE / 'toolchain_projects.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
print('Prepared 60K / 138K B / 138K C isolated tool probes; no EDA executed.')
