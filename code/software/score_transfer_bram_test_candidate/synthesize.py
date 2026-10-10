"""One authorized RAM-module synthesis, no PnR/STA/download or auto retry."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TOOL = Path('D:/program/gaoyunFPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/GowinSynthesis.exe')
PART = 'GW5AST-LV138PG484AC1/I0'
DEVICE = 'GW5AST-138C'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', required=True, type=Path)
    cli.add_argument('--simulation-receipt', required=True, type=Path)
    cli.add_argument('--reset-receipt', required=True, type=Path)
    cli.add_argument('--execute-once', action='store_true')
    args = cli.parse_args()
    out = args.output.resolve()
    output_root = ROOT / 'code/output'
    if out.exists() or output_root not in out.parents:
        cli.error('new directory in code/output required')
    if args.execute_once and list(output_root.glob('m3_score_bram_syn*/attempt_started.json')):
        cli.error('one-shot already consumed; preserve reports and request new authority')
    simulation = json.loads(args.simulation_receipt.read_text(encoding='utf-8'))
    resets = json.loads(args.reset_receipt.read_text(encoding='utf-8'))
    if simulation['status']!='PASS_MODULE_SIMULATION_ONLY' or resets['status']!='PASS_RESET_RAM_RECOVERY':
        cli.error('positive, both compiled mutants, and reset probes must pass first')
    for relative, expected in simulation['input_sha256'].items():
        if sha(ROOT/relative)!=expected:
            cli.error('simulation source changed: '+relative)
    out.mkdir(parents=True)
    sources = [ROOT/'code/rtl/common'/name for name in ('uart_rx.sv','uart_tx.sv')]
    sources += [ROOT/'code/rtl/input/score_transfer_bram_candidate'/name for name in (
        'score_byte_lane.sv','score_transfer_bram_candidate.sv')]
    staged = []
    for source in sources:
        local = out / source.name
        shutil.copyfile(source, local)
        if sha(source)!=sha(local):
            raise ValueError('staged source identity')
        staged.append(local)
    sdc = out / 'module.sdc'
    sdc.write_text('create_clock -name sys_clk -period 25.000 [get_ports {clk}]\n', encoding='ascii')
    netlist = out / 'score_ram.vg'
    command = [TOOL, '-p', DEVICE, '-pn', PART, '-i', *staged,
               '-top', 'score_transfer_bram_candidate', '-verilog_language', 'sysv-2017',
               '-sdc', sdc, '-global_freq', '40', '-disable_insert_pad', '1', '-o', netlist]
    receipt = dict(status='PREPARED_NOT_RUN', synthesis_executed=False,
        target=dict(device=DEVICE, part=PART, clock_ns=25), timeout=600,
        command=[str(x) for x in command], tool_sha256=sha(TOOL),
        simulation_receipt=dict(path=str(args.simulation_receipt), sha256=sha(args.simulation_receipt)),
        reset_receipt=dict(path=str(args.reset_receipt), sha256=sha(args.reset_receipt)),
        source_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in sources},
        configuration_sha256={sdc.name:sha(sdc)}, pnr=False, hardware_verified=False)
    for label, flag in (('version','-version'),('help','-help')):
        result = subprocess.run([str(TOOL),flag], cwd=out, capture_output=True, timeout=30)
        (out/(label+'.stdout.bin')).write_bytes(result.stdout)
        (out/(label+'.stderr.bin')).write_bytes(result.stderr)
        receipt[label+'_exit']=result.returncode
    if args.execute_once:
        dump(out/'attempt_started.json', receipt)
        receipt['synthesis_executed']=True
        start = time.monotonic()
        timed_out=False
        with (out/'synthesis.stdout.bin').open('wb') as stdout, (out/'synthesis.stderr.bin').open('wb') as stderr:
            process=subprocess.Popen([str(x) for x in command],cwd=out,stdout=stdout,stderr=stderr)
            try:
                process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                timed_out=True
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                process.wait(timeout=15)
        receipt.update(exit_code=process.returncode, elapsed=time.monotonic()-start,timed_out=timed_out)
        receipt['status']='FAIL_SYNTHESIS_OR_MAPPING'
        log=(out/'synthesis.stdout.bin').read_text(encoding='utf-8',errors='replace')
        receipt['memory_mapping_log_lines']=[line for line in log.splitlines()
            if re.search(r'memory|bsram|ssram|\bDPB\b|\bSDPB\b',line,re.I)]
        xmls=list(out.glob('*_syn_rsc.xml'))
        if len(xmls)==1:
            element=ET.parse(xmls[0]).getroot()
            receipt['hierarchy_xml']=dict(path=xmls[0].name,sha256=sha(xmls[0]),
                root_attributes=element.attrib,
                children=[child.attrib for child in element.iter() if child is not element])
        # Never equate module-level BSRAM total with evidence for the song body.
        receipt['body_ram_mapping_review']='PENDING_ACTUAL_HIERARCHY_AND_NATIVE_MEMORY_REVIEW'
        if not timed_out and receipt['elapsed']<=600 and process.returncode==0 and netlist.is_file() and xmls:
            receipt['status']='SYNTHESIS_COMPLETED_MAPPING_REVIEW_REQUIRED'
    receipt['output_sha256']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*')
                             if p.is_file() and p.name!='receipt.json'}
    for source in sources:
        if sha(source)!=receipt['source_sha256'][source.relative_to(ROOT).as_posix()]:
            receipt.update(status='FAIL_SOURCE_CHANGED')
    dump(out/'receipt.json',receipt)
    print(receipt['status'],flush=True)
    return int(receipt['status'] not in ('PREPARED_NOT_RUN','SYNTHESIS_COMPLETED_MAPPING_REVIEW_REQUIRED'))


if __name__=='__main__':
    raise SystemExit(main())
