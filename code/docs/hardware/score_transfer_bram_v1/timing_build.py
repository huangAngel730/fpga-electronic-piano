"""User-authorized isolated timing repair; never download or program."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
TOOL = Path('E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe')
PART = 'GW5AST-LV138PG484AC1/I0'
M2_IMPORT = 'ab8f4e1b6492393fdc078668f59e3da07792788a'
SHARED_STATUS = {'code/docs/'+name+'.md' for name in
                 ('当前状态', '任务看板', '验证记录', '技术决策记录')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def review_cache_mapping(out):
    """Native hierarchy prerequisite; a declared Verilog RAM is not evidence."""
    xml = out/'project/score_ram/impl/gwsynthesis/score_ram_syn_rsc.xml'
    tree = ET.parse(xml).getroot()
    modules = {node.get('name'): node for node in tree.findall('SubModule')}
    names = [f'byte_lanes[{i}].storage' for i in range(8)] + ['request_history']
    for name in names:
        if name not in modules or modules[name].get('Bsram') != '1':
            raise ValueError('native synchronous RAM mapping missing: '+name)
    registers = int(tree.get('T_Register').split('(')[0])
    if registers >= 2000:
        raise ValueError('request-cache FF reduction not established')
    if int(tree.get('T_Latch', tree.get('Latch', '0')).split('(')[0]) != 0:
        raise ValueError('inferred latch')
    log = (out/'synthesis.stdout.bin').read_text(encoding='utf-8', errors='replace')
    if "Extracting RAM for identifier 'memory'" not in log:
        raise ValueError('native memory extraction log missing')
    return dict(hierarchy=dict(tree.attrib), total_registers=registers,
                native_xml_sha256=sha(xml),
                mapped_modules={name:dict(modules[name].attrib) for name in names})


def execute(out, label, tcl, limit):
    start = time.monotonic()
    command = [str(TOOL), str(tcl)]
    timed_out = False
    with (out/(label+'.stdout.bin')).open('xb') as stdout, (out/(label+'.stderr.bin')).open('xb') as stderr:
        process = subprocess.Popen(command, cwd=out, stdout=stdout, stderr=stderr)
        dump(out/(label+'_process.json'), dict(
            pid=process.pid, command=command, cwd=str(out),
            observed_start_utc=datetime.now(timezone.utc).isoformat(),
            timeout_seconds=limit, unlimited=limit is None,
            do_not_program=True))
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
    cli.add_argument('--unlimited-pnr', action='store_true',
                     help='Explicit user 2026-10-10 authorization: one run, no automatic PnR timeout')
    cli.add_argument('--structural-revision', action='store_true',
                     help='New T062 request-cache architecture; 1ns setup / 650ps hold protection')
    cli.add_argument('--m2-metadata-import', choices=(M2_IMPORT,),
                     help='Accept only four bookkeeping files from this exact imported M2 commit')
    cli.add_argument('--prior-timeout-receipt', type=Path)
    cli.add_argument('--restart-after-interruption', type=Path)
    args = cli.parse_args()
    if args.structural_revision and (args.unlimited_pnr or args.prior_timeout_receipt
                                    or args.restart_after_interruption):
        raise ValueError('new structural revision is not a legacy unlimited/retry authorization')
    if args.unlimited_pnr and (args.prior_timeout_receipt or args.restart_after_interruption):
        raise ValueError('unlimited authority must not masquerade as a bounded retry')
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    if args.mode=='synth':
        out.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(Path(__file__), out/'synthesis_runner.py')
        simulation = json.loads(args.simulation_receipt.read_text(encoding='utf-8'))
        if simulation['status']!='PASS_MODULE_SIMULATION_ONLY':
            raise ValueError('simulation prerequisite')
        current_inputs = {}
        metadata_changes = {}
        if args.m2_metadata_import:
            subprocess.run(['git', 'merge-base', '--is-ancestor', args.m2_metadata_import, 'HEAD'],
                           cwd=ROOT, check=True, timeout=30)
        for rel, digest in simulation['input_sha256'].items():
            current = sha(ROOT/rel)
            if current != digest:
                if rel not in SHARED_STATUS or not args.m2_metadata_import:
                    raise ValueError('simulation identity changed: '+rel)
                imported = subprocess.check_output(
                    ['git', 'show', args.m2_metadata_import+':'+rel], cwd=ROOT, timeout=30)
                if hashlib.sha256(imported).hexdigest() != current:
                    raise ValueError('metadata not exact imported M2 bytes: '+rel)
                metadata_changes[rel] = dict(historical_simulation_sha256=digest,
                                            imported_M2_sha256=current)
            current_inputs[rel] = current
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
        if args.structural_revision:
            text += 'set_clock_uncertainty -setup 1.000 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]\n'
            text += 'set_clock_uncertainty -hold 0.650 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]\n'
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
                       simulation_inputs=current_inputs,
                       historical_simulation_inputs=simulation['input_sha256'],
                       imported_M2_commit=args.m2_metadata_import,
                       shared_bookkeeping_changes=metadata_changes,
                       tool=dict(path=str(TOOL),sha256=sha(TOOL)),
                       runner_sha256=sha(Path(__file__)),
                       structural_revision=args.structural_revision,
                       minimum_setup_slack_ns=0.5 if args.structural_revision else 0,
                       desired_setup_slack_ns=1.0 if args.structural_revision else None,
                       shared_bookkeeping_before_sha256={rel:sha(ROOT/rel) for rel in SHARED_STATUS},
                       configuration_sha256={p.name:sha(p) for p in (sdc,tcl)},
                       hardware_verified=False, production_changed=False, steps=[])
        dump(out/'attempt_started.json',receipt)
        step = execute(out,'synthesis',tcl,600)
        receipt['steps'].append(step)
        receipt['status']='SYNTHESIS_COMPLETED_REVIEW_REQUIRED' if step['exit_code']==0 and not step['timed_out'] and step['elapsed']<=600 else 'FAIL_SYNTHESIS'
        if args.structural_revision and receipt['status']=='SYNTHESIS_COMPLETED_REVIEW_REQUIRED':
            try:
                receipt['cache_mapping_review']=review_cache_mapping(out)
            except (ValueError, OSError, ET.ParseError, AttributeError) as error:
                receipt['status']='FAIL_CACHE_MAPPING'
                receipt['cache_mapping_error']=str(error)
    else:
        if not args.allow_isolated_unreleased_bitstream:
            raise ValueError('explicit isolated bitstream permission required')
        receipt = json.loads((out/'receipt.json').read_text(encoding='utf-8'))
        if bool(receipt.get('structural_revision')) != args.structural_revision:
            raise ValueError('structural revision execution authority mismatch')
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
        if args.pnr_timeout==1800 and not args.unlimited_pnr:
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
        limit = None if args.unlimited_pnr else args.pnr_timeout
        if args.unlimited_pnr:
            receipt['pnr_time_authority'] = (
                'User 2026-10-10: 请帮我重新跑一下布局布线 没有时间限制; '
                'one fresh isolated run, no automatic timeout, no automatic retry')
        dump(out/'pnr_started.json',receipt)
        step = execute(out,'pnr',tcl,limit)
        receipt['steps'].append(step)
        receipt['status']='PNR_COMPLETED_STA_REVIEW_REQUIRED' if step['exit_code']==0 and not step['timed_out'] and (limit is None or step['elapsed']<=limit) else 'FAIL_PNR'
    receipt['output_sha256']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*')
                             if p.is_file() and p.name!='receipt.json'}
    for rel,digest in receipt['simulation_inputs'].items():
        if sha(ROOT/rel)!=digest:
            receipt['status']='FAIL_INPUT_CHANGED'
    receipt['shared_bookkeeping_after_sha256']={rel:sha(ROOT/rel) for rel in SHARED_STATUS}
    receipt['shared_bookkeeping_changed']=[rel for rel, digest in
        receipt['shared_bookkeeping_before_sha256'].items() if sha(ROOT/rel)!=digest]
    dump(out/'receipt.json',receipt)
    print(receipt['status'],flush=True)
    return int(receipt['status'].startswith('FAIL'))


if __name__=='__main__':
    raise SystemExit(main())
