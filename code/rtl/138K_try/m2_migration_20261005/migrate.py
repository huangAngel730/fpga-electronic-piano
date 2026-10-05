"""138K-C 50MHz baseline reproduction; no production changes or board download."""
import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCOPE = HERE.parent
ORIGINAL = ROOT / 'code/output/138k_migration_20261005/original_C50_evidence/C_reset_route1'
OLD_PATH = 'E:/FPGA/GAOYUNFPGA/138K_try/optimization_20261005/C_reset_route1'
OUT = HERE / 'output/C50_baseline'
TOOL = SCOPE / 'tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe'
STEM = 'audio_visual_coexistence_top'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p, data):
    p.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def prepare():
    assert not OUT.exists(), 'Preserve old runs; new source build only once'
    if not ORIGINAL.exists():
        archive=SCOPE/'optimization_20261005/M3_138K_C_optimization_L5_evidence_20261005.zip'
        extraction=ORIGINAL.parent
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if member.is_dir() or not member.filename.startswith('C_reset_route1/'):
                    continue
                relative=Path(member.filename)
                assert not relative.is_absolute() and '..' not in relative.parts and ':' not in member.filename
                target=(extraction/relative).resolve()
                assert target.is_relative_to(extraction.resolve()) and not target.exists()
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(z.read(member))
    manifest = json.loads((ORIGINAL / 'input_manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['inputs']) == 56
    tree = ET.parse(ORIGINAL / (STEM + '.gprj'))
    assert tree.getroot().find('Device').text == 'gw5ast138c-007'
    assert len(tree.getroot().find('FileList')) == 47
    OUT.mkdir(parents=True)
    records = []
    for item in manifest['inputs']:
        old = ORIGINAL / item['path']
        assert sha(old) == item['candidate_SHA256'], item['path']
        data = old.read_bytes()
        relocated = data.replace(OLD_PATH.encode(), OUT.as_posix().encode())
        assert relocated.replace(OUT.as_posix().encode(), OLD_PATH.encode()) == data
        p = OUT / item['path']
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(relocated)
        records.append({'path': item['path'], 'original_sha': sha(old), 'actual_sha': sha(p)})
    for item in tree.getroot().find('FileList'):
        assert item.attrib['path'].startswith(OLD_PATH + '/')
        item.attrib['path'] = item.attrib['path'].replace(OLD_PATH, OUT.as_posix(), 1)
        assert Path(item.attrib['path']).is_file()
    tree.write(OUT / (STEM + '.gprj'), encoding='utf-8', xml_declaration=True)
    tcl = (ORIGINAL / 'run.tcl').read_text(encoding='utf-8').replace(OLD_PATH, OUT.as_posix())
    (OUT / 'run.tcl').write_text(tcl, encoding='ascii')
    write_json(OUT / 'migration_manifest.json', {
        'date': '2026-10-05', 'git_baseline': '546c075', 'part': 'GW5AST-LV138PG484AC1/I0',
        'device_version': 'C', 'clocks_MHz': [50, 25, 125], 'inputs': records,
        'project_sha': sha(OUT / (STEM + '.gprj')), 'tcl_sha': sha(OUT / 'run.tcl'),
        'tool_sha': sha(TOOL), 'changes': 'exact path relocation only',
        'prior_138K_adapters_preserved': ['PLLA->PLL', 'Bank5 reset/key 3.3V', 'R44C168 serial reset', 'route1'],
        'contains_frozen_V0171_PitchMod': True, 'adds_T027_panel_effects': False,
        'physical_board_B_C_confirmed': False, '60k_changed': False, 'download_allowed': False})
    print('Prepared C50: 47 enabled entries +7 ROM+2 headers; path-only changes')


def verify():
    m = json.loads((OUT / 'migration_manifest.json').read_text(encoding='utf-8'))
    for item in m['inputs']:
        assert sha(OUT / item['path']) == item['actual_sha'], item['path']
    assert sha(OUT / (STEM + '.gprj')) == m['project_sha']
    assert sha(OUT / 'run.tcl') == m['tcl_sha']
    assert sha(TOOL) == m['tool_sha']


def build():
    verify()
    assert not (OUT / 'build_receipt.json').exists() and not (OUT / 'impl').exists()
    env = os.environ.copy()
    env['TEMP'] = env['TMP'] = str(OUT / 'tmp')
    (OUT / 'tmp').mkdir()
    r = {'started': datetime.now().astimezone().isoformat(), 'limit_seconds': 1800,
         'command': [str(TOOL), 'run.tcl'], 'cwd': str(OUT), 'programmed': False}
    start = time.monotonic()
    with (OUT / 'build.log').open('wb') as log:
        p = subprocess.Popen(r['command'], cwd=OUT, env=env, stdout=log, stderr=subprocess.STDOUT)
        r['pid'] = p.pid
        write_json(OUT / 'build_receipt.json', r)
        print('START C50', p.pid, r['started'], flush=True)
        try:
            code = p.wait(timeout=1800)
            r['timed_out'] = False
        except subprocess.TimeoutExpired:
            r['timed_out'] = True
            command = '$all=Get-CimInstance Win32_Process; $ids=@(' + str(p.pid) + '); for($r=0;$r -lt 8;$r++){ $more=@($all | Where-Object { $_.ParentProcessId -in $ids } | Select-Object -ExpandProperty ProcessId); $ids=@($ids+$more | Select-Object -Unique) }; foreach($taskId in ($ids | Sort-Object -Descending)){ Stop-Process -Id $taskId -Force -ErrorAction Continue }'
            stopped = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, timeout=30)
            (OUT / 'process_stop.log').write_bytes(stopped.stdout + stopped.stderr)
            if stopped.returncode != 0:
                p.kill()
            code = p.wait(timeout=10)
    r.update(exit_code=code, finished=datetime.now().astimezone().isoformat(),
             elapsed_seconds=time.monotonic()-start, log_sha=sha(OUT / 'build.log'))
    write_json(OUT / 'build_receipt.json', r)
    verify()
    print(json.dumps(r, indent=2), flush=True)
    return code


def normalize_options(text):
    return [s.split(' ', 1)[0]+' <path>' if s.startswith(('-d ', '-cst ', '-cfg ', '-sdc ')) else s for s in text.splitlines()]


def assess():
    verify()
    sys.path.insert(0, str(ROOT / 'code/scripts'))
    from check_audio_visual_probe import check as original_gate
    from check_hdmi_link_report import ReportParser
    r = json.loads((OUT / 'build_receipt.json').read_text(encoding='utf-8'))
    assert r.get('exit_code') == 0 and not r['timed_out'] and sha(OUT / 'build.log') == r['log_sha']
    raw, facts = original_gate(OUT)
    allowed = {'tool/device mismatch', 'formal audio clock uncertainty missing: hold',
               'audio ROM footprint is not 8 BSRAM', 'audio pin mismatch: sys_rst_n',
               'audio pin mismatch: key_n[0]', 'audio pin mismatch: key_n[1]'}
    # 138K pin reports have a different column order. Replace only old fixed-
    # column pin checks with the complete header-driven checks below.
    errors = [e for e in raw if e not in allowed
              and not e.startswith('Pin mismatch: ')
              and not e.startswith('audio pin mismatch: ')]
    timing = OUT / ('impl/pnr/'+STEM+'_tr_content.html')
    parser = ReportParser()
    parser.feed(timing.read_text(encoding='utf-8'))
    usage = (OUT / ('impl/pnr/'+STEM+'.rpt.txt')).read_text(encoding='utf-8')
    if ('<Part Number>: GW5AST-LV138PG484AC1/I0' not in usage
            or '<Device Version>: C' not in usage
            or '<Tool Version>: V1.9.11.03 Education' not in usage):
        errors.append('exact 138K part/tool mismatch')
    if facts['resources']['DSP'] != 46 or facts['resources']['BSRAM'] != 20:
        errors.append('frozen audio resource footprint mismatch')
    def pins(path):
        p = ReportParser()
        p.feed(path.read_text(encoding='utf-8'))
        rows = [r for s,r in p.rows if s == 'Pinout_by_Port_Name']
        header = next(r for r in rows if r[0] == 'Port Name')
        keys = ['Diff Pair', 'Loc./Bank', 'Constraint', 'Dir.', 'IO Type', 'BankVccio', 'Pull Mode']
        assert len(set(header)) == len(header) and all(k in header for k in keys)
        result = {r[0]: {k:r[header.index(k)] for k in keys} for r in rows if len(r)==len(header) and r[0]!='Port Name'}
        assert len(result) == 14, 'missing/extra 138K physical ports'
        assert all(v['Constraint'] == 'Y' for v in result.values())
        return result
    actual_pins = pins(OUT / ('impl/pnr/'+STEM+'.pin.html'))
    original_pins = pins(ORIGINAL / ('impl/pnr/'+STEM+'.pin.html'))
    if actual_pins != original_pins:
        errors.append('138K pins/Bank/electrical changed')
    required = {'sys_clk': ('V22/4', 'LVCMOS33', '3.3'),
                'sys_rst_n': ('AA13/5', 'LVCMOS33', '3.3'),
                'key_n[0]': ('AB13/5', 'LVCMOS33', '3.3'),
                'key_n[1]': ('Y12/5', 'LVCMOS33', '3.3'),
                'midi_rx': ('R17/4', 'LVCMOS33', '3.3'),
                'uart_tx': ('U15/5', 'LVCMOS33', '3.3'),
                'i2s_bclk': ('Y17/5', 'LVCMOS33', '3.3'),
                'i2s_lrck': ('AB17/5', 'LVCMOS33', '3.3'),
                'i2s_din': ('AA16/5', 'LVCMOS33', '3.3'),
                'pa_en': ('AB16/5', 'LVCMOS33', '3.3')}
    for port, expected in required.items():
        row = actual_pins[port]
        if (row['Loc./Bank'], row['IO Type'], row['BankVccio']) != expected:
            errors.append('explicit 138K pin specification failed: ' + port)
    if normalize_options((OUT/'impl/pnr/cmd.do').read_text()) != normalize_options((ORIGINAL/'impl/pnr/cmd.do').read_text()):
        errors.append('nonpath PnR option changed')
    if (OUT/'impl/pnr/device.cfg').read_bytes() != (ORIGINAL/'impl/pnr/device.cfg').read_bytes():
        errors.append('138K device.cfg or vccx changed')
    locations = {}
    for stage,suffix in [(0,'A'),(1,'B')]:
        cell=f'u_visual/u_serial_reset/sync_chain_{stage}_s0/'
        loc=f'R44C168[1][{suffix}]'
        rows=[r for s,r in parser.rows if 'Analysis' in s and any(cell in v for v in r) and loc in r]
        locations[str(stage)]={'expected':loc,'actual_rows':len(rows)}
        if not rows:
            errors.append('actual reset LOC absent')
    tns=[r for s,r in parser.rows if s=='Total_Negative_Slack_Report' and len(r)==4 and r[0] in ['sys_clk','video_pixel','video_serial']]
    if len(tns)!=6 or any(float(r[2])<0 or r[3]!='0' for r in tns):
        errors.append('TNS or endpoints negative/missing')
    active={r[2] for s,r in parser.rows if s=='SDC_Report' and len(r)==3 and r[1]=='Actived'}
    old_parser=ReportParser()
    old_parser.feed((ORIGINAL/('impl/pnr/'+STEM+'_tr_content.html')).read_text(encoding='utf-8'))
    old_active={r[2] for s,r in old_parser.rows if s=='SDC_Report' and len(r)==3 and r[1]=='Actived'}
    if active != old_active:
        errors.append('original effective SDC command set changed')
    if 'set_clock_uncertainty -hold 0.550 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]' not in active:
        errors.append('exact hold uncertainty missing')
    pulse=[float(r[1]) for s,r in parser.rows if s=='MIN_PULSE_WIDTH_TABLE' and len(r)>=7 and r[0].isdigit()]
    if not pulse or min(pulse)<0:
        errors.append('minimum pulse missing/negative')
    for kind in ['Setup','Hold','Recovery','Removal']:
        values=[float(r[1]) for s,r in parser.rows if s.startswith(kind+'_Slack_Table') and len(r)>=4 and r[0].isdigit()]
        if not values or any(not math.isfinite(x) or x<0 for x in values):
            errors.append('nonfinite/missing/negative '+kind)
    log=(OUT/'build.log').read_text(encoding='utf-8', errors='replace')
    for marker in ['GowinSynthesis finish','Placement and routing completed','Timing analysis completed','Bitstream generation completed']:
        if marker not in log:
            errors.append('missing completion '+marker)
    result={'date':'2026-10-05','part':'GW5AST-LV138PG484AC1/I0','device_version':'C',
            'offline_STA_pass':not errors,'errors':errors,'raw_60k_gate_differences':raw,'facts':facts,
            'actual_reset_LOC':locations,'actual_pins':actual_pins,
            'TNS':tns,'minimum_pulse_ns':min(pulse) if pulse else None,
            'setup_goal_0p5':facts['exported_min_slack_ns']['Setup']>=.5,
            'download_allowed':False,'board_version_and_Dock_pending':True,'60k_preserved':True,
            'new_T027_panel_effects_not_added':True,'new_board_validation':False,
            'artifacts':{str(p.relative_to(OUT)):sha(p) for p in [timing,OUT/'build.log',OUT/'impl/pnr/cmd.do',OUT/'impl/pnr/device.cfg']}}
    write_json(OUT/'assessment.json',result)
    print(json.dumps(result,indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','verify','build','assess'])
    a=p.parse_args()
    if a.action=='prepare':
        prepare()
    elif a.action=='verify':
        verify()
        print('PASS C50 input hashes')
    else:
        raise SystemExit(build() if a.action=='build' else assess())
