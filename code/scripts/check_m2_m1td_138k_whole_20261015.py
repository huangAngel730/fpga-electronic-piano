"""Bounded compile-only check for one prepared M1TD/138K board candidate."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CAD = Path('D:/Gowin/oss-cad-suite')
VENDOR = Path('D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v')
PLL = ROOT / 'code/tb/board/t058_waveform_integration_20261008/clock_plan_sim.v'
DVI = ROOT / 'code/rtl/138K_try/hold_trials_20261005/dvi_sim_stub.v'
JOB = ROOT / 'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
TOP = 'm2_fourvoice_timbre_delay_board_top'


def ident(path):
    data = Path(path).read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepared', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    prepared = args.prepared.resolve()
    out = args.output.resolve()
    permitted = (ROOT / 'code/output').resolve()
    if out.exists() or out == permitted or not out.is_relative_to(permitted):
        raise ValueError('NEW_OUTPUT_REQUIRED')
    if not prepared.is_relative_to(permitted):
        raise ValueError('PREPARED_SCOPE')
    out.mkdir(parents=True)
    start = time.monotonic()
    result = {'status': 'FAIL_PARTIAL', 'error': None, 'scope': 'ICARUS_COMPILE_ONLY_NOT_EDA',
              'timeout_seconds': 90, 'total_seconds': 300, 'new_EDA_calls': 0,
              'RTL_runtime': 'NOT_RUN', 'physical_STA': 'NOT_RUN',
              'sources_before': {}, 'sources_after': {}, 'step': None}
    protected = []
    try:
        prep = prepared / 'PREPARATION_RECEIPT.json'
        receipt = json.loads(prep.read_text(encoding='utf-8'))
        if receipt['status'] != 'PREPARED_NOT_PHYSICALLY_ADMITTED' or receipt['error'] is not None:
            raise ValueError('PREPARED_NOT_VALID')
        protected.append(prep)
        gprj = prepared / (TOP + '.gprj')
        if ident(gprj)['sha256'] != receipt['project_sha256']:
            raise ValueError('PROJECT_DRIFT')
        protected.append(gprj)
        units = []
        for entry in ET.parse(gprj).getroot().iter('File'):
            path = Path(entry.attrib['path'])
            if not path.is_relative_to(prepared) or not path.is_file():
                raise ValueError('PROJECT_SOURCE_SCOPE:' + str(path))
            rel = str(path.relative_to(prepared)).replace('\\', '/')
            normalized_inputs = {k.replace('\\', '/'): v for k, v in receipt['input_files'].items()}
            if ident(path) != normalized_inputs[rel]:
                raise ValueError('INPUT_DRIFT:' + rel)
            protected.append(path)
            if entry.attrib['type'] == 'file.verilog' and path.name not in ('TMDS_PLL_800_600_60.v', 'DVI_TX_Top.v'):
                units.append(path)
        for p in (VENDOR, PLL, DVI, JOB, Path(__file__), CAD / 'bin/iverilog.exe'):
            protected.append(p)
        before = {str(p): ident(p) for p in protected}
        result['sources_before'] = before
        if ident(JOB)['sha256'] != '5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b':
            raise ValueError('JOB_SOURCE_DRIFT')
        simlib = VENDOR.read_text(encoding='utf-8')
        parts = []
        for name in ('GSR', 'pROM'):
            m = re.search(r'^module ' + name + r' \([^\n]*\);[\s\S]*?^endmodule[^\n]*', simlib, re.M)
            if not m:
                raise ValueError('SIMLIB_MODULE_MISSING:' + name)
            parts.append(m.group(0))
        vendor = out / 'vendor_GSR_pROM.v'
        vendor.write_text('`timescale 1ns/1ps\n' + '\n'.join(parts), encoding='utf-8', newline='\n')
        units.sort(key=lambda p: 0 if p.name == 'audio_defs_pkg.sv' else
                   1 if p.name == 'sustain_control_contract_pkg.sv' else 2)
        argv = [str(CAD / 'bin/iverilog.exe'), '-g2012', '-I', str(prepared / 'inputs/include'),
                '-s', TOP, '-o', str(out / 'top.vvp')]
        argv.extend(map(str, units + [vendor, PLL, DVI]))
        spec = importlib.util.spec_from_file_location('m2_winjob', JOB)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        env = os.environ.copy()
        env['YOSYSHQ_ROOT'] = str(CAD) + os.sep
        env['PATH'] = os.pathsep.join([str(CAD / 'bin'), str(CAD / 'lib'), env.get('PATH', '')])
        job = helper.WindowsJob()
        timed_out = False
        tick = time.monotonic()
        try:
            with (out / 'stdout.log').open('xb') as stdout, (out / 'stderr.log').open('xb') as stderr:
                proc = subprocess.Popen(argv, cwd=prepared / 'inputs', env=env, stdout=stdout,
                                        stderr=stderr, creationflags=4)
                job.attach_and_resume(proc)
                try:
                    proc.wait(timeout=min(90, 300 - (time.monotonic() - start)))
                except subprocess.TimeoutExpired:
                    timed_out = True
                    job.terminate()
                    proc.wait(timeout=5)
        finally:
            job.close()
        result['step'] = {'argv': argv, 'cwd': str(prepared / 'inputs'),
                          'exit_code': proc.returncode, 'timeout': timed_out,
                          'seconds': round(time.monotonic() - tick, 3),
                          'stdout': ident(out / 'stdout.log'), 'stderr': ident(out / 'stderr.log')}
        result['sources_after'] = {str(p): ident(p) for p in protected}
        if result['sources_after'] != before:
            raise ValueError('PROTECTED_INPUT_DRIFT')
        if proc.returncode != 0 or timed_out:
            raise ValueError('COMPILER_FAILED')
        if time.monotonic() - start >= 300:
            raise TimeoutError('TOTAL300')
        result['status'] = 'COMPILE_ONLY_PASS_NOT_SIMULATION_OR_STA'
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        result['sources_after'] = {str(p): ident(p) for p in protected if p.is_file()}
    result['elapsed_seconds'] = round(time.monotonic() - start, 3)
    result['exit_code'] = 0 if result['error'] is None else 1
    (out / 'RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'error', 'elapsed_seconds', 'exit_code')}))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())