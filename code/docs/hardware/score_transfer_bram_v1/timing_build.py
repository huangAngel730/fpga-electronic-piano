"""User-authorized isolated timing repair: bounded synthesis/PnR, never program."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
TOOL = Path('E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe')
PART = 'GW5AST-LV138PG484AC1/I0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def execute(out, label, tcl, limit):
    start = time.monotonic()
    command = [str(TOOL), str(tcl)]
    timed_out = False
    with (out/(label+'.stdout.bin')).open('xb') as stdout, (out/(label+'.stderr.bin')).open('xb') as stderr:
        process = subprocess.Popen(command, cwd=out, stdout=stdout, stderr=stderr)
        try:
            process.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], capture_output=True, timeout=20)
            process.wait(timeout=20)
    return dict(command=command, cwd=str(out), exit_code=process.returncode,
                timed_out=timed_out, elapsed=time.monotonic()-start, timeout=limit)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=('synth','pnr'))
    cli.add_argument('--output', required=True, type=Path)
    cli.add_argument('--simulation-receipt', type=Path)
    cli.add_argument('--allow-isolated-unreleased-bitstream', action='store_true')
    cli.add_argument('--pnr-timeout', type=int, choices=(900, 1800), default=900)
    cli.add_argument('--prior-timeout-receipt', type=Path)
    cli.add_argument('--restart-after-interruption', type=Path)
    args = cli.parse_args()
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    if args.mode=='synth':
        out.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(Path(__file__), out/'synthesis_runner.py')
        simulation = json.loads(args.simulation_receipt.read_text(encoding='utf-8'))
        if simulation['status']!='PASS_MODULE_SIMULATION_ONLY':
            raise ValueError('simulation prerequisite')
        for rel, digest in simulation['input_sha256'].items():
            if sha(ROOT/rel)!=digest:
                raise ValueError('simulation identity changed: '+rel)
        sources = [ROOT/'code/rtl/common'/name for name in ('uart_rx.sv','uart_tx.sv')]
        sources += [ROOT/'code/rtl/input/score_transfer_bram_candidate'/name for name in (
            'score_byte_lane.sv','score_transfer_bram_candidate.sv')]
        staged = out/'sources'
        staged.mkdir()
        for path in sources:
            shutil.copyfile(path,staged/path.name)
            assert sha(path)==sha(staged/path.name)
        # Zero-delay virtual environment for standalone port-to-register and
        # register-to-port checks; NOT a board I/O timing specification.
        sdc = out/'module.sdc'
        inputs = '{rst_n uart_rx_i rd_req rd_index[*]}'
        outputs = '{uart_tx_o rd_valid rd_event[*] committed_valid committed_count[*] committed_score_id[*] commit_pulse last_error[*]}'
        text = 'create_clock -name sys_clk -period 25.000 [get_ports {clk}]\n'
        for kind, ports in (('input',inputs),('output',outputs)):
            for bound in ('max','min'):
                text += f'set_{kind}_delay -{bound} 0.000 -clock sys_clk [get_ports {ports}]\n'
        sdc.write_text(text, encoding='ascii', newline='\n')
        project = out/'project'
        lines = [f'create_project -name score_ram -dir {{{project.as_posix()}}} -pn {PART} -device_version C',
                 'set_device -name GW5AST-138 -device_version C '+PART]
        lines += [f'add_file {{{(staged/p.name).as_posix()}}}' for p in sources]
        lines += [f'add_file {{{sdc.as_posix()}}}',
                  'set_option -top_module score_transfer_bram_candidate',
                  'set_option -verilog_std sysv2017',
                  'set_option -global_freq 40',
                  'set_option -frequency 40',
                  'set_option -timing_driven 1',
                  'set_option -correct_hold_violation 1',
                  'set_option -gen_text_timing_rpt 1',
                  'set_option -gen_posp 1',
                  'run syn', 'exit']
        tcl = out/'synth.tcl'
        tcl.write_text('\n'.join(lines)+'\n',encoding='ascii',newline='\n')
        receipt = dict(status='STARTED', authority='User 2026-10-10 timing repair and isolated PnR/STA',
                       part=PART, device_version='C', period_ns=25, board_timing_verified=False,
                       source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in sources},
                       simulation_receipt_sha256=sha(args.simulation_receipt),
                       simulation_inputs=simulation['input_sha256'],
                       tool=dict(path=str(TOOL),sha256=sha(TOOL)),
                       runner_sha256=sha(Path(__file__)),
                       configuration_sha256={p.name:sha(p) for p in (sdc,tcl)},
                       hardware_verified=False, production_changed=False, steps=[])
        dump(out/'attempt_started.json',receipt)
        step = execute(out,'synthesis',tcl,600)
        receipt['steps'].append(step)
        receipt['status']='SYNTHESIS_COMPLETED_REVIEW_REQUIRED' if step['exit_code']==0 and not step['timed_out'] and step['elapsed']<=600 else 'FAIL_SYNTHESIS'
    else:
        if not args.allow_isolated_unreleased_bitstream:
            raise ValueError('explicit isolated bitstream permission required')
        receipt = json.loads((out/'receipt.json').read_text(encoding='utf-8'))
        if receipt['status']!='SYNTHESIS_COMPLETED_REVIEW_REQUIRED' or (out/'pnr_started.json').exists():
            raise ValueError('fresh successful synthesis required, no implicit PnR retry')
        for rel,digest in receipt['simulation_inputs'].items():
            if sha(ROOT/rel)!=digest:
                raise ValueError('post-simulation input changed: '+rel)
        for name,digest in receipt['configuration_sha256'].items():
            assert sha(out/name)==digest, name
        for name,digest in receipt['output_sha256'].items():
            if sha(out/name)!=digest:
                raise ValueError('synthesis artifact changed: '+name)
        if sha(TOOL)!=receipt['tool']['sha256']:
            raise ValueError('tool identity changed')
        if args.pnr_timeout==1800:
            if args.prior_timeout_receipt is None:
                raise ValueError('user-approved extension requires prior timeout receipt')
            prior_path=args.prior_timeout_receipt.resolve()
            prior_path.relative_to(ROOT/'code/output')
            prior=json.loads(prior_path.read_text(encoding='utf-8'))
            if prior['status']!='FAIL_PNR' or not prior['steps'][-1]['timed_out'] or prior['steps'][-1]['timeout']!=900:
                raise ValueError('extension only after actual 900-second timeout')
            if prior['source_sha256']!=receipt['source_sha256'] or prior['tool']!=receipt['tool']:
                raise ValueError('extension source/tool identity')
            if prior['configuration_sha256']['module.sdc']!=sha(out/'module.sdc'):
                raise ValueError('extension SDC changed')
            old_tcl=(prior_path.parent/'synth.tcl').read_text(encoding='ascii')
            new_tcl=(out/'synth.tcl').read_text(encoding='ascii')
            if old_tcl.replace(prior_path.parent.as_posix(),out.as_posix())!=new_tcl:
                raise ValueError('extension synthesis options changed')
            receipt['extension_authority']='User explicitly allowed exactly one same-source/config 1800-second isolated retry after timeout'
            receipt['prior_timeout_receipt_sha256']=sha(prior_path)
        if args.restart_after_interruption:
            observation_path = args.restart_after_interruption.resolve()
            observation_path.relative_to(ROOT/'code/output')
            observation = json.loads(observation_path.read_text(encoding='utf-8'))
            if observation['status'] != 'INTERRUPTED_OR_TERMINATED_NO_FINAL_PNR_RECEIPT':
                raise ValueError('interrupted attempt observation required')
            interrupted = observation_path.parent
            for name, key in (('receipt.json', 'receipt_json_sha256'),
                              ('pnr_started.json', 'pnr_started_json_sha256'),
                              ('pnr.stdout.bin', 'pnr_stdout_bin_sha256')):
                if sha(interrupted/name) != observation[key]:
                    raise ValueError('interrupted evidence changed: '+name)
            started = json.loads((interrupted/'pnr_started.json').read_text(encoding='utf-8'))
            if started['source_sha256'] != receipt['source_sha256'] or started['tool'] != receipt['tool']:
                raise ValueError('restart source/tool identity')
            if started['configuration_sha256']['module.sdc'] != sha(out/'module.sdc'):
                raise ValueError('restart SDC changed')
            old_tcl = (interrupted/'synth.tcl').read_text(encoding='ascii')
            if old_tcl.replace(interrupted.as_posix(), out.as_posix()) != (out/'synth.tcl').read_text(encoding='ascii'):
                raise ValueError('restart configuration changed')
            if args.pnr_timeout != 1800:
                raise ValueError('restart remains bounded at 1800 seconds')
            receipt['extension_authority'] = ('User confirmed continue after explicit restart question '
                'on 2026-10-10; one additional same-source/config 1800-second isolated attempt')
            receipt['interrupted_observation_sha256'] = sha(observation_path)
        shutil.copyfile(Path(__file__), out/'pnr_runner.py')
        tcl = out/'pnr.tcl'
        tcl.write_text(f'open_project {{{(out/"project/score_ram/score_ram.gprj").as_posix()}}}\nrun pnr\nexit\n',
                       encoding='ascii',newline='\n')
        receipt['pnr_runner_sha256']=sha(Path(__file__))
        receipt['configuration_sha256'][tcl.name]=sha(tcl)
        receipt['bitstream_authority']='User explicitly allowed isolated generation only; NEVER download or burn'
        dump(out/'pnr_started.json',receipt)
        step = execute(out,'pnr',tcl,args.pnr_timeout)
        receipt['steps'].append(step)
        receipt['status']='PNR_COMPLETED_STA_REVIEW_REQUIRED' if step['exit_code']==0 and not step['timed_out'] and step['elapsed']<=args.pnr_timeout else 'FAIL_PNR'
    receipt['output_sha256']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*')
                             if p.is_file() and p.name!='receipt.json'}
    for rel,digest in receipt['simulation_inputs'].items():
        if sha(ROOT/rel)!=digest:
            receipt['status']='FAIL_INPUT_CHANGED'
    dump(out/'receipt.json',receipt)
    print(receipt['status'],flush=True)
    return int(receipt['status'].startswith('FAIL'))


if __name__=='__main__':
    raise SystemExit(main())
