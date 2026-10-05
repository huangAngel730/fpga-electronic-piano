"""Run vendor-model PLL checks with isolated Icarus and preserve return codes."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
assert HERE == ROOT / 'reproduction_20261005'
folder = HERE / 'pll_model_test'
tool = ROOT / 'tools/icarus_oss_copy'
env = dict(os.environ)
env['PATH'] = str(tool / 'bin') + os.pathsep + env.get('PATH', '')
env['TMP'] = env['TEMP'] = str(folder / 'tmp')
(folder / 'tmp').mkdir(exist_ok=True)
sources = [folder / 'vendor_prim_sim.v', HERE / '138K_B_pll_migration/sources/TMDS_PLL_800_600_60.v',
           folder / 'tb_pll_migration.sv']
binary = folder / 'sim.vvp'
command = [str(tool / 'bin/iverilog.exe'), '-B', str(tool / 'lib/ivl'), '-g2012',
           '-s', 'tb_pll_migration', '-o', str(binary), *map(str, sources)]
process = subprocess.run(command, cwd=folder, env=env, capture_output=True, timeout=45)
(folder / 'compile.log').write_bytes(process.stdout + process.stderr)
run_code = None
passed = False
if process.returncode == 0:
    run = subprocess.run([str(tool / 'bin/vvp.exe'), str(binary)], cwd=folder,
                         env=env, capture_output=True, timeout=45)
    data = run.stdout + run.stderr
    (folder / 'run.log').write_bytes(data)
    run_code = run.returncode
    passed = run_code == 0 and b'PASS PLL migration vendor model:' in data and b'FATAL:' not in data
    print(data.decode('utf-8', errors='replace'))
else:
    print((process.stdout + process.stderr).decode('utf-8', errors='replace')[-2500:])
report = {'time': datetime.now().astimezone().isoformat(), 'command': command,
          'compile_exit': process.returncode, 'run_exit': run_code, 'passed': passed,
          'source_SHA256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
          'scope': 'Vendor digital model only; NOT real PLL startup/lock/jitter or physical mapping proof'}
(folder / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if passed else 1)
