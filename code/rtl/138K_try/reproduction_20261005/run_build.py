"""Run one authorized isolated project, retaining actual CLI exit and raw log."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
label = sys.argv[1]
if label not in ['60K_control', '138K_B_frozen_constraints', '138K_C_frozen_constraints',
                 '138K_B_pll_migration', '138K_C_pll_migration',
                 '138K_B_electrical_migration', '138K_C_electrical_migration']:
    raise ValueError('Unapproved project label')
folder = HERE / label
log = folder / 'build.log'
receipt = folder / 'build_receipt.json'
if log.exists() or receipt.exists():
    raise ValueError('Preserve prior run; prepare a separately named attempt')
tool = ROOT / 'tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe'
assert (folder / 'run.tcl').is_file()
env = dict(os.environ)
env['TMP'] = env['TEMP'] = str(folder / 'tmp')
(folder / 'tmp').mkdir(exist_ok=True)
command = [str(tool), 'run.tcl']
start = datetime.now().astimezone().isoformat()
record = {'label': label, 'started': start, 'command': command, 'cwd': str(folder),
          'state': 'running', 'programmed': False, 'original_repo_written': False}
receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print('START', label, start, flush=True)
with log.open('wb') as output:
    process = subprocess.Popen(command, cwd=folder, env=env, stdout=output, stderr=subprocess.STDOUT)
    record['pid'] = process.pid
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    code = process.wait()
record.update({'state': 'finished', 'finished': datetime.now().astimezone().isoformat(),
               'exit_code': code, 'build_log_SHA256': hashlib.sha256(log.read_bytes()).hexdigest()})
receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print('FINISH', label, 'exit=', code, record['finished'], flush=True)
print(log.read_bytes().decode('utf-8', errors='replace')[-3500:], flush=True)
raise SystemExit(code)
