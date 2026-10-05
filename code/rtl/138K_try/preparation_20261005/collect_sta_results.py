"""Read real Gowin reports fail-closed; distinguish support probes from V0171."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'report_support'))
from check_hdmi_link_report import ReportParser

FROZEN_CLOCKS = {'sys_clk': (20.0, 50.0), 'video_pixel': (40.0, 25.0),
                 'video_serial': (8.0, 125.0)}


def normalize(command):
    return ' '.join(command.split())


def analyze(timing, usage, expected_clocks, require_async, expected_sdc=None):
    parser = ReportParser()
    parser.feed(timing)
    rows = parser.rows
    errors = []
    summary = {r[0]: r[1] for section, r in rows
               if section == 'STA_Tool_Run_Summary' and len(r) == 2}
    for key in ['Numbers of Paths Analyzed', 'Numbers of Endpoints Analyzed']:
        if not summary.get(key, '').isdigit() or int(summary[key]) < 1:
            errors.append('missing/empty analyzed evidence: ' + key)
    for key in ['Numbers of Setup Violated Endpoints', 'Numbers of Hold Violated Endpoints']:
        if summary.get(key) != '0':
            errors.append('missing/nonzero violation count: ' + key)
    global_worst = {}
    for kind in ['Setup', 'Hold']:
        paths = [r for s, r in rows if s.startswith(kind + '_Slack_Table')
                 and len(r) >= 4 and r[0].isdigit()]
        try:
            values = [float(r[1]) for r in paths]
            if not values or not all(math.isfinite(v) for v in values):
                raise ValueError('missing or nonfinite slack')
            worst = min(paths, key=lambda r: float(r[1]))
            global_worst[kind] = {'slack_ns': float(worst[1]), 'from': worst[2], 'to': worst[3]}
            if float(worst[1]) < 0:
                errors.append('negative global/cross-clock ' + kind)
        except ValueError:
            errors.append('missing/invalid global paths: ' + kind)
    clocks = {}
    fmax = {}
    per_clock = {}
    tns = {}
    for clock, (period, frequency) in expected_clocks.items():
        matches = [r for section, r in rows if section == 'Clock_Report'
                   and len(r) >= 5 and r[0].isdigit() and r[1] == clock]
        if len(matches) != 1:
            errors.append('missing/duplicate clock: ' + clock)
        else:
            try:
                clocks[clock] = {'period_ns': float(matches[0][3]), 'frequency_mhz': float(matches[0][4])}
                if clocks[clock] != {'period_ns': period, 'frequency_mhz': frequency}:
                    errors.append('clock period/frequency mismatch: ' + clock)
            except ValueError:
                errors.append('invalid clock number: ' + clock)
        maximum = [r for s, r in rows if s == 'Max_Frequency_Report'
                   and len(r) >= 4 and r[0].isdigit() and r[1] == clock]
        if len(maximum) != 1:
            errors.append('missing/duplicate Fmax: ' + clock)
        else:
            try:
                fmax[clock] = float(maximum[0][3].replace('(MHz)', ''))
                if not math.isfinite(fmax[clock]) or fmax[clock] < frequency:
                    errors.append('Fmax below constraint: ' + clock)
            except ValueError:
                errors.append('invalid Fmax: ' + clock)
        per_clock[clock] = {}
        tns[clock] = {}
        for kind in ['Setup', 'Hold']:
            paths = [r for s, r in rows if s.startswith(kind + '_Slack_Table')
                     and len(r) >= 6 and r[0].isdigit()
                     and r[4].startswith(clock + ':') and r[5].startswith(clock + ':')]
            try:
                worst = min(paths, key=lambda r: float(r[1]))
                per_clock[clock][kind] = {'slack_ns': float(worst[1]), 'from': worst[2], 'to': worst[3]}
                if not math.isfinite(float(worst[1])) or float(worst[1]) < 0:
                    errors.append('negative path: ' + clock + ' ' + kind)
            except (ValueError, IndexError):
                errors.append('missing/invalid per-clock path: ' + clock + ' ' + kind)
            totals = [r for s, r in rows if s == 'Total_Negative_Slack_Report'
                      and len(r) >= 4 and r[0] == clock and r[1] == kind]
            try:
                if len(totals) != 1:
                    raise ValueError('missing/duplicate TNS row')
                tns[clock][kind] = {'TNS_ns': float(totals[0][2]), 'violated_endpoints': int(totals[0][3])}
                if tns[clock][kind] != {'TNS_ns': 0.0, 'violated_endpoints': 0}:
                    errors.append('nonzero TNS/endpoints: ' + clock + ' ' + kind)
            except ValueError:
                errors.append('missing/invalid TNS: ' + clock + ' ' + kind)
    async_worst = {}
    for kind in ['Recovery', 'Removal']:
        paths = [r for s, r in rows if s.startswith(kind + '_Slack_Table')
                 and len(r) >= 4 and r[0].isdigit()]
        if not paths:
            async_worst[kind] = None
            if require_async:
                errors.append('missing asynchronous reset path: ' + kind)
        else:
            try:
                worst = min(paths, key=lambda r: float(r[1]))
                async_worst[kind] = {'slack_ns': float(worst[1]), 'from': worst[2], 'to': worst[3]}
                if float(worst[1]) < 0:
                    errors.append('negative ' + kind)
            except ValueError:
                errors.append('invalid ' + kind)
    active = {normalize(r[2]) for s, r in rows if s == 'SDC_Report'
              and len(r) == 3 and r[1] == 'Actived'}
    hold_command = ('set_clock_uncertainty -hold 0.550 -from [get_clocks {sys_clk}] '
                    '-to [get_clocks {sys_clk}]')
    if hold_command not in active:
        errors.append('sys Hold uncertainty 0.550 not active')
    if expected_sdc is not None:
        expected = {normalize(line) for line in expected_sdc.splitlines()
                    if line.strip() and not line.lstrip().startswith('#')}
        for command in sorted(expected - active):
            errors.append('missing/inactive frozen SDC command: ' + command)
        cuts = lambda commands: {c for c in commands if c.startswith(('set_false_path', 'set_clock_groups'))}
        if cuts(active) != cuts(expected):
            errors.append('unexpected timing exception')
    resources = {}
    for name in ['Logic', 'Register', 'DSP', 'BSRAM']:
        matches = re.findall(r'^\s*' + name + r'\s*\|\s*(\d+)/(\d+)', usage, re.M)
        if len(matches) == 1:
            resources[name] = {'used': int(matches[0][0]), 'available': int(matches[0][1])}
        elif name in ['Logic', 'Register'] or require_async:
            errors.append('missing/duplicate resource: ' + name)
    metadata = {}
    for name in ['Tool Version', 'Part Number', 'Device', 'Device Version', 'Created Time']:
        match = re.search(r'<' + name + r'>:\s*([^\r\n]+)', usage)
        metadata[name] = match[1].strip() if match else None
        if not match:
            errors.append('missing tool/target metadata: ' + name)
    return {'errors': errors, 'summary': summary, 'clocks': clocks, 'fmax_mhz': fmax,
            'per_clock_worst_paths': per_clock, 'per_clock_TNS': tns, 'global_worst_paths': global_worst,
            'recovery_removal_worst_paths': async_worst, 'resources': resources,
            'metadata': metadata, 'active_SDC': sorted(active),
            'not_a_pin_CDC_IP_or_hardware_acceptance_gate': True}


def collect_tool_probes():
    results = []
    for label, pn, version in [('60K', 'GW5AT-LV60PG484AC1/I0', 'B'),
                               ('138K_B', 'GW5AST-LV138PG484AC1/I0', 'B'),
                               ('138K_C', 'GW5AST-LV138PG484AC1/I0', 'C')]:
        folder = HERE / 'toolchain' / label
        pnr = folder / 'impl/pnr'
        timing = pnr / 'tool_probe_tr_content.html'
        usage = pnr / 'tool_probe.rpt.txt'
        result = analyze(timing.read_text(encoding='utf-8'), usage.read_text(encoding='utf-8'),
                         {'sys_clk': (20.0, 50.0)}, False,
                         (HERE / 'tool_probe.sdc').read_text(encoding='utf-8'))
        if result['metadata']['Part Number'] != pn or result['metadata']['Device Version'] != version:
            result['errors'].append('wrong target')
        if result['metadata']['Tool Version'] != 'V1.9.11.03 Education':
            result['errors'].append('wrong tool version')
        log = folder / ('build_attempt2.log' if label == '60K' else 'build.log')
        for marker in ['GowinSynthesis finish', 'Placement and routing completed',
                       'Timing analysis completed', 'Bitstream generation completed']:
            if marker not in log.read_text(encoding='utf-8'):
                result['errors'].append('missing real completion marker: ' + marker)
        files = [timing, usage, log, pnr / 'cmd.do', pnr / 'tool_probe.pin.html',
                 pnr / 'tool_probe.fs', folder / 'tool_probe.gprj', folder / 'run.tcl']
        result.update({'label': label, 'scope': '8-bit counter tool support probe only, NOT V0171',
                       'observed_cli_exit_code': 0, 'programmed': False,
                       'artifact_SHA256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
        results.append(result)
        print(('PASS' if not result['errors'] else 'FAIL'), label,
              result['per_clock_worst_paths'], 'errors=', result['errors'])
    output = {'time': datetime.now().astimezone().isoformat(),
              'scope': 'tool availability/STA probe; not full-design comparison', 'results': results,
              'frozen_V0171_PnR_executed': False, 'original_repo_written': False}
    (HERE / 'toolchain_results.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    return int(any(r['errors'] for r in results))


if __name__ == '__main__':
    raise SystemExit(collect_tool_probes())
