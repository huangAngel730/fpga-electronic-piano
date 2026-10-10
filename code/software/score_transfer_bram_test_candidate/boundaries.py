"""Produce a separate reset plan and run real-UART reset/recovery probes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from vectors import load, ROOT, LEGACY


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', required=True, type=Path)
    args = cli.parse_args()
    out = args.output.resolve()
    if out.exists() or ROOT / 'code/output' not in out.parents:
        cli.error('new code/output directory required')
    out.mkdir(parents=True)
    old = load(LEGACY / 'vectors.py', 'boundary_original_vectors')
    base = list(old.pc.upload_frames(*old.pc.encode_score(old.score(70, 2)), 70))
    stage = list(old.pc.upload_frames(*old.pc.encode_score(old.score(71, 32)), 71))
    # Golden records independently assembled, not imported encoder output.
    doc = old.score(70, 2)
    records = [event['tick'].to_bytes(4, 'little') + bytes((int(event['type']=='note_off'),
               event['channel'], event['note'], event['velocity'])) for event in doc['events']]
    text = ' '.join(f'{int.from_bytes(x,"little"):016x}' for x in records)+'\n'
    for phase in range(8):
        frames = base + [stage[0]]
        frames += [stage[1]] if phase in (0,6,7) else [old.pc.frame(6, 71, 9, 0)] if phase in (2,4,5) else stage[1:]
        frames += base
        for frame in frames:
            text += str(len(frame))+' '+' '.join(f'{x:02x}' for x in frame)+'\n'
    plan = out / 'plan.txt'
    plan.write_text(text, encoding='ascii')
    tools = Path('E:/FPGA/Bpan/modelsim/modelsim1/win64')
    receipt = dict(status='FAIL', steps=[])

    def run(label, cmd, limit):
        begin = time.monotonic()
        result = subprocess.run([str(x) for x in cmd], cwd=out, capture_output=True, timeout=limit)
        elapsed = time.monotonic()-begin
        (out / (label+'.stdout.bin')).write_bytes(result.stdout)
        (out / (label+'.stderr.bin')).write_bytes(result.stderr)
        receipt['steps'].append(dict(label=label, command=[str(x) for x in cmd],
                                     exit_code=result.returncode, elapsed=elapsed, limit=limit))
        if elapsed>limit:
            raise ValueError('elapsed deadline')
        return result.returncode, (result.stdout+result.stderr).decode('utf-8',errors='replace')
    try:
        if run('vlib', [tools/'vlib.exe','work'], 30)[0]:
            raise ValueError('vlib')
        sources = [ROOT/'code/rtl/common'/name for name in ('uart_rx.sv','uart_tx.sv')]
        sources += [ROOT/'code/rtl/input/score_transfer_bram_candidate'/name for name in (
            'score_byte_lane.sv','score_transfer_bram_candidate.sv')]
        sources += [ROOT/'code/tb/input/score_transfer_bram_candidate/tb_score_bram_reset.sv']
        if run('compile', [tools/'vlog.exe','-sv']+sources, 60)[0]:
            raise ValueError('compile')
        code, log = run('simulate', [tools/'vsim.exe','-c','-wlf','simulation.wlf',
            'work.tb_score_bram_reset','+PLAN='+str(plan),'-do',
            'onerror {quit -code 2}; onbreak {quit -code 3}; run -all; quit -code 0'], 180)
        if code or 'RESET_RECOVERY_COMPLETE checks=24' not in log or 'Fatal:' in log:
            raise ValueError('reset simulation incomplete')
        receipt['status']='PASS_RESET_RAM_RECOVERY'
    except Exception as exc:
        receipt['error']=str(exc)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n', encoding='utf-8')
    print(receipt['status'],receipt.get('error',''),flush=True)
    return int(receipt['status']!='PASS_RESET_RAM_RECOVERY')


if __name__=='__main__':
    raise SystemExit(main())
