"""New RAM candidate only: bounded UART regression and two compiled mutants."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
RTL = ROOT / 'code/rtl/input/score_transfer_bram_candidate'
TB = ROOT / 'code/tb/input/score_transfer_bram_candidate'
SW = ROOT / 'code/software/score_transfer_bram_test_candidate'
sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    out = args.output.resolve()
    if ROOT / 'code/output' not in out.parents or out.exists():
        parser.error('new directory within code/output required')
    out.mkdir(parents=True)
    shutil.copyfile(Path(__file__), out / 'simulation_runner.py')
    started = time.monotonic()
    receipt = dict(status='FAIL', synthesis_executed=False, hardware_verified=False,
                   argv=sys.argv, cwd=str(ROOT), python=str(Path(sys.executable)), steps=[])
    readonly = [ROOT / 'code/rtl/input/score_transfer_candidate/score_transfer_candidate.sv',
                ROOT / 'code/rtl/common/uart_rx.sv', ROOT / 'code/rtl/common/uart_tx.sv',
                ROOT / 'code/tb/input/score_transfer_candidate/vectors.py',
                ROOT / 'code/tb/input/score_transfer_candidate/check_capture.py',
                ROOT / 'code/software/score_transfer_v1/score_transfer.py',
                ROOT / 'code/docs/hardware/score_transfer_v1/PROTOCOL.md']
    protected = ['code/rtl/board/electronic_piano_top.sv', 'code/rtl/common/audio_defs_pkg.sv',
                 'code/constraints/electronic_piano.cst', 'code/docs/模块接口规范.md',
                 'code/docs/当前状态.md', 'code/docs/任务看板.md',
                 'code/docs/验证记录.md', 'code/docs/技术决策记录.md']
    bookkeeping = {relative: sha(ROOT / relative) for relative in protected[4:]}
    # Shared registration changes are audited separately, never bound as
    # executable inputs. Source/interface protections remain mandatory.
    readonly += [ROOT / relative for relative in protected[:4]]
    inputs = readonly + list(RTL.glob('*.sv')) + list(TB.glob('*.sv')) + list(SW.glob('*.py')) + [Path(__file__)]
    identity = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    receipt['input_sha256'] = identity
    receipt['shared_bookkeeping_before_sha256'] = bookkeeping
    snapshots = out / 'executed_inputs'
    for rel in identity:
        target = snapshots / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    receipt['python_sha256'] = sha(Path(sys.executable))
    receipt['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()

    def run(label, cmd, cwd=out, limit=900):
        remaining = args.timeout - (time.monotonic()-started)
        if remaining <= 0:
            raise ValueError('total deadline')
        limit = min(limit, remaining)
        begin = time.monotonic()
        cmd = [str(x) for x in cmd]
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=15)
            stdout, stderr = proc.communicate(timeout=15)
        elapsed = time.monotonic()-begin
        (out / (label+'.stdout.bin')).write_bytes(stdout)
        (out / (label+'.stderr.bin')).write_bytes(stderr)
        step = dict(label=label, command=cmd, cwd=str(cwd), exit_code=proc.returncode,
                    elapsed=elapsed, timeout=limit, timed_out=timed_out)
        receipt['steps'].append(step)
        dump(out / 'receipt.json', receipt)
        print(label, proc.returncode, round(elapsed, 3), flush=True)
        if timed_out or elapsed > limit:
            raise ValueError(label+': deadline exceeded')
        return proc.returncode, (stdout+stderr).decode('utf-8', errors='replace')

    try:
        spec = importlib.util.spec_from_file_location('ram_vectors', SW / 'vectors.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.build(out)
        tools = Path('E:/FPGA/Bpan/modelsim/modelsim1/win64')
        receipt['tools'] = {name: dict(path=str(tools / (name+'.exe')), sha256=sha(tools / (name+'.exe')))
                            for name in ('vlib', 'vlog', 'vsim')}
        run('version', [tools / 'vsim.exe', '-version'], limit=30)
        sources = readonly[1:3] + [RTL / 'score_byte_lane.sv', RTL / 'score_transfer_bram_candidate.sv',
                                  TB / 'tb_score_transfer_bram.sv']
        for label, define in (('normal', None), ('ram_read_mutant', 'MUTANT_RAM_READ'),
                              ('bank_mutant', 'MUTANT_BANK_SWITCH'),
                              ('reply_crc_mutant', 'MUTANT_RESPONSE_CRC')):
            folder = out / label
            folder.mkdir()
            if run(label+'_vlib', [tools / 'vlib.exe', 'work'], folder, 30)[0]:
                raise ValueError('vlib failed')
            cmd = [tools / 'vlog.exe', '-sv']
            if define:
                cmd += ['+define+'+define]
            if run(label+'_compile', cmd+sources, folder, 60)[0]:
                raise ValueError('compile failure is not a negative PASS')
            capture = folder / 'capture.txt'
            code, log = run(label+'_simulate', [tools / 'vsim.exe', '-c', '-wlf', 'simulation.wlf',
                'work.tb_score_transfer_bram', '+PLAN='+str(out / 'plan.txt'),
                '+CAPTURE='+str(capture), '+ORACLE='+str(out / 'public_oracle.txt'), '-do',
                'onerror {quit -code 2}; onbreak {quit -code 3}; run -all; quit -code 0'], folder)
            if define:
                marker = 'UART_REPLY_CRC_MISMATCH' if define=='MUTANT_RESPONSE_CRC' else 'RAM_PUBLIC_DATA_OR_BANK'
                if marker not in log or 'HARNESS COMPLETE' in log:
                    raise ValueError(label+': designated behavioral assertion missing')
            else:
                if code or 'HARNESS COMPLETE' not in log or 'RAM_CHECKS' not in log:
                    raise ValueError('normal simulation incomplete')
                code, log = run('protocol_oracle', [sys.executable, '-B', '-X', 'utf8', readonly[4],
                                                     capture, out / 'expected.json'], limit=30)
                if code or not log.startswith('PASS '):
                    raise ValueError(log)
                receipt['protocol'] = json.loads(log[5:])
        code, log = run('reset_boundaries', [sys.executable, '-B', '-X', 'utf8',
            SW / 'boundaries.py', '--output', out / 'reset_boundaries'], limit=210)
        if code or 'PASS_RESET_RAM_RECOVERY' not in log:
            raise ValueError('reset boundaries failed')
        receipt['status'] = 'PASS_MODULE_SIMULATION_ONLY'
    except Exception as exc:
        receipt['error'] = str(exc)
    for rel, digest in identity.items():
        if sha(ROOT / rel) != digest:
            receipt.update(status='FAIL', error='input changed: '+rel)
    receipt['shared_bookkeeping_after_sha256'] = {
        rel: sha(ROOT / rel) for rel in bookkeeping}
    receipt['shared_bookkeeping_changed'] = [rel for rel, digest in bookkeeping.items()
        if sha(ROOT / rel) != digest]
    receipt['elapsed'] = time.monotonic()-started
    receipt['output_sha256'] = {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*')
                               if p.is_file() and p.name!='receipt.json' and 'work' not in p.parts
                               and p.suffix not in ('.wlf',)}
    dump(out / 'receipt.json', receipt)
    print(receipt['status'], receipt.get('error', ''), flush=True)
    return int(receipt['status']!='PASS_MODULE_SIMULATION_ONLY')


if __name__ == '__main__':
    raise SystemExit(main())
