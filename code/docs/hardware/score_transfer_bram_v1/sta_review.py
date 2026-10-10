"""Read the exact isolated Gowin reports; never invoke FPGA tools/devices."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
PARSER = ROOT/'code/scripts/check_hdmi_link_report.py'
spec = importlib.util.spec_from_file_location('gowin_report_parser', PARSER)
parser_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser_module)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path):
    parser = parser_module.ReportParser()
    parser.feed(path.read_text(encoding='utf-8'))
    return parser.rows


def timing_facts(rows):
    """Reject global and reported local violations independently."""
    summary = {r[0]: r[1] for s, r in rows
               if s == 'STA_Tool_Run_Summary' and len(r) == 2}
    errors = []
    for key in ('Numbers of Setup Violated Endpoints',
                'Numbers of Hold Violated Endpoints'):
        if summary.get(key) != '0':
            errors.append('VIOLATED_ENDPOINTS:'+key)
    for key in ('Numbers of Paths Analyzed', 'Numbers of Endpoints Analyzed'):
        if not summary.get(key, '').isdigit() or int(summary[key]) <= 0:
            errors.append('NO_ANALYSIS:'+key)
    for key, value in summary.items():
        if 'unconstrain' in key.lower() and value != '0':
            errors.append('UNCONSTRAINED_SUMMARY:'+key)
    if any('unconstrain' in s.lower() and r and r[0].isdigit() for s, r in rows):
        errors.append('UNCONSTRAINED_PATH_ROW')
    clocks = [r for s, r in rows if s == 'Clock_Report' and r and r[0].isdigit()]
    if len(clocks) != 1 or clocks[0][1:5] != ['sys_clk', 'Base', '25.000', '40.000']:
        errors.append('CLOCK_CONTRACT')
    paths = {}
    for kind in ('Setup', 'Hold', 'Recovery', 'Removal'):
        actual = [r for s, r in rows if s.startswith(kind+'_Slack_Table')
                  and len(r) >= 4 and r[0].isdigit()]
        paths[kind] = actual
        values = [float(r[1]) for r in actual]
        if any(not math.isfinite(v) or v < 0 for v in values):
            errors.append('NEGATIVE_OR_NONFINITE:'+kind)
        if kind in ('Setup', 'Hold') and not actual:
            errors.append('MISSING_PATH:'+kind)
    tns = [r for s, r in rows if s == 'Total_Negative_Slack_Report'
           and len(r) == 4 and r[0] != 'Clock Name']
    if not {('sys_clk', 'Setup'), ('sys_clk', 'Hold')} <= {(r[0], r[1]) for r in tns}:
        errors.append('MISSING_TNS')
    for r in tns:
        if not math.isfinite(float(r[2])) or float(r[2]) != 0 or int(r[3]) != 0:
            errors.append('NONZERO_TNS_OR_ENDPOINTS')
    active = [r[2] for s, r in rows if s == 'SDC_Report'
              and len(r) == 3 and r[1] == 'Actived']
    if any(x.startswith(('set_false_path', 'set_multicycle_path', 'set_clock_groups')) for x in active):
        errors.append('UNAUTHORIZED_EXCEPTION')
    pulse = [float(r[1]) for s, r in rows if s == 'MIN_PULSE_WIDTH_TABLE'
             and len(r) >= 7 and r[0].isdigit()]
    if not pulse or any(not math.isfinite(v) or v < 0 for v in pulse):
        errors.append('MIN_PULSE')
    return dict(summary=summary, clocks=clocks, paths=paths, TNS=tns,
                active_SDC=active, minimum_pulse_ns=min(pulse) if pulse else None,
                errors=errors)


def mapping(build):
    syn = build/'project/score_ram/impl/gwsynthesis'
    tree = ET.parse(syn/'score_ram_syn_rsc.xml').getroot()
    lanes = {n.get('name'): n for n in tree.findall('SubModule')
             if n.get('name', '').startswith('byte_lanes[')}
    if set(lanes) != {f'byte_lanes[{i}].storage' for i in range(8)}:
        raise ValueError('MISSING_BODY_LANE')
    if any(n.get('Bsram') != '1' or n.get('T_Bsram') != '1(1)' for n in lanes.values()):
        raise ValueError('BODY_NOT_BSRAM')
    log = (build/'synthesis.stdout.bin').read_text(encoding='utf-8', errors='replace')
    if not re.search(r"Extracting RAM for identifier 'memory'\([^\n]*score_byte_lane\.sv", log):
        raise ValueError('MISSING_NATIVE_MEMORY_LOG')
    return dict(hierarchy=dict(tree.attrib), body_bsram=8,
                lanes={k: dict(v.attrib) for k, v in lanes.items()})


def review_unit_tests(build):
    """Parser self-tests are not native timing evidence; retain their raw logs."""
    command = [sys.executable, '-B', str(Path(__file__).with_name('test_sta_review.py'))]
    started = time.monotonic()
    test = subprocess.run(command, capture_output=True, timeout=30)
    stdout = build/'review_tests.stdout.bin'
    stderr = build/'review_tests.stderr.bin'
    stdout.write_bytes(test.stdout)
    stderr.write_bytes(test.stderr)
    return dict(command=command, exit_code=test.returncode,
                elapsed_seconds=time.monotonic()-started, timeout_seconds=30,
                stdout_sha256=sha(stdout), stderr_sha256=sha(stderr),
                proves_native_sta=False)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('build', type=Path)
    cli.add_argument('--inspect', action='store_true')
    args = cli.parse_args()
    build = args.build.resolve()
    build.relative_to(ROOT/'code/output')
    path = build/'project/score_ram/impl/pnr/score_ram_tr_content.html'
    if args.inspect:
        rows = tables(path)
        selected = [(s, r) for s, r in rows if 'Analysis' not in s]
        print(json.dumps(selected, ensure_ascii=False, indent=2))
        return
    receipt = json.loads((build/'receipt.json').read_text(encoding='utf-8'))
    if receipt['status']=='FAIL_PNR' and receipt['steps'][-1]['timed_out']:
        for name, digest in receipt['output_sha256'].items():
            if sha(build/name)!=digest:
                raise ValueError('timeout artifact identity: '+name)
        for name, digest in receipt['simulation_inputs'].items():
            if sha(ROOT/name)!=digest:
                raise ValueError('timeout input identity: '+name)
        first=receipt['steps'][0]
        if first['exit_code'] or first['timed_out'] or first['elapsed']>first['timeout']:
            raise ValueError('synthesis prerequisite for partial delivery')
        test = review_unit_tests(build)
        if test['exit_code']:
            raise ValueError('review unit tests failed; partial audit not sealed')
        shutil.copyfile(Path(__file__),build/'reviewer_snapshot.py')
        result=dict(status='INCOMPLETE_PHYSICAL_STA', physical_complete=False,
                    timing_passed=False, reason='bounded routing timed out; no physical STA verdict',
                    partial_report_present=path.is_file(), mapping=mapping(build),
                    actual_steps=receipt['steps'], build_receipt_sha256=sha(build/'receipt.json'),
                    reviewer_sha256=sha(Path(__file__)), hardware_verified=False,
                    unit_tests=test,
                    board_timing_verified=False, do_not_program=True,
                    complete_system=False)
        (build/'sta_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',
                                           encoding='utf-8',newline='\n')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2
    if receipt['status'] != 'PNR_COMPLETED_STA_REVIEW_REQUIRED':
        raise ValueError('native PnR completion prerequisite')
    rows = tables(path)
    for step in receipt['steps']:
        if step['exit_code'] or step['timed_out'] or step['elapsed'] > step['timeout']:
            raise ValueError('bounded native execution prerequisite')
    for name, digest in receipt['output_sha256'].items():
        if sha(build/name) != digest:
            raise ValueError('native output identity: '+name)
    for name, digest in receipt['simulation_inputs'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('executed input identity: '+name)
    log = (build/'pnr.stdout.bin').read_text(encoding='utf-8', errors='replace')
    for marker in ('Placement and routing completed', 'Timing analysis completed',
                   'Bitstream generation completed'):
        if marker not in log:
            raise ValueError('missing native marker: '+marker)
    facts = timing_facts(rows)
    normalized = lambda x: re.sub(r'\s+', ' ', x.strip())
    requested = {normalized(x) for x in (build/'module.sdc').read_text().splitlines() if x.strip()}
    active = {normalized(x) for x in facts['active_SDC']}
    if not requested <= active:
        facts['errors'].append('INACTIVE_SDC')
    fmax = [r for s, r in rows if s == 'Max_Frequency_Report' and r and r[0].isdigit()]
    if len(fmax) != 1 or fmax[0][1] != 'sys_clk':
        facts['errors'].append('MISSING_FMAX')
    elif not math.isfinite(float(fmax[0][3].replace('(MHz)', ''))) or float(fmax[0][3].replace('(MHz)', '')) < 40:
        facts['errors'].append('FMAX_BELOW_40')
    facts['Fmax_rows'] = fmax
    facts['unconstrained_rows'] = [(s, r) for s, r in rows if 'unconstrain' in s.lower()]
    facts['recovery_removal_empty'] = [k for k in ('Recovery', 'Removal') if not facts['paths'][k]]
    # Empty recovery/removal tables need explicit native/source review; do not
    # silently convert missing data into zero slack or claim asynchronous safety.
    if facts['recovery_removal_empty']:
        facts['errors'].append('EMPTY_RECOVERY_REMOVAL_REQUIRES_CLASSIFICATION')
    if not facts['unconstrained_rows']:
        facts['errors'].append('UNCONSTRAINED_COVERAGE_REQUIRES_REVIEW')
    test = review_unit_tests(build)
    if test['exit_code']:
        facts['errors'].append('REVIEW_UNIT_TESTS')
    shutil.copyfile(Path(__file__),build/'reviewer_snapshot.py')
    result = dict(status='STA_REVIEW_NOT_PASSED' if facts['errors'] else 'PASS_ISOLATED_MODULE_40MHZ_STA',
                  facts=facts, mapping=mapping(build), board_timing_verified=False,
                  hardware_verified=False, production_changed=False, do_not_program=True,
                  build_receipt_sha256=sha(build/'receipt.json'), parser_sha256=sha(PARSER),
                  reviewer_sha256=sha(Path(__file__)), unit_test_exit_code=test['exit_code'],
                  unit_tests=test,
                  output_sha256={p.relative_to(build).as_posix(): sha(p)
                                 for p in build.rglob('*') if p.is_file() and p.name != 'sta_review.json'})
    (build/'sta_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                                       encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(facts['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
