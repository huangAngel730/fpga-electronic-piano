"""Independent physical report gate for the exact staged M1TD 138K successor.

Retains all old pin, CDC, clock, timing and PnR checks. Only the two old audio
LOC identities and frozen DSP/BSRAM equality have different meanings here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_platform_timing as original

TOP = 'm2_fourvoice_timbre_delay_board_top'
EXPECTED_OLD_LOC = {
    'actual fixed FF location mismatch/missing g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s1_18_s0',
    'actual fixed FF location mismatch/missing g_polyphonic.u_audio_core/u_bank/u_pitch_mod/g_lane[2].u_control/base_s2_18_s0',
}
EXPECTED_OLD_FOOTPRINT = {'frozen resource footprint changed DSP',
                          'frozen resource footprint changed BSRAM'}
EXPECTED_DELTAS = EXPECTED_OLD_LOC | EXPECTED_OLD_FOOTPRINT
MARKERS = ('GowinSynthesis finish', 'Placement and routing completed',
           'Timing analysis completed', 'Bitstream generation completed')


def digest(path):
    b = path.read_bytes()
    return {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


def assess(stage, run):
    errors = []
    build = json.loads((run / 'receipt.json').read_text(encoding='utf-8'))
    prep = json.loads((stage / 'PREPARATION_RECEIPT.json').read_text(encoding='utf-8'))
    pnr = stage / 'impl/pnr'
    files = [pnr / (TOP + ext) for ext in ('_tr_content.html', '.rpt.txt', '.pin.html')]
    files += [stage / 'inputs/constraints/audio_visual_hold055.sdc', pnr / 'cmd.do', pnr / 'device.cfg']
    bitstream = pnr / (TOP + '.fs')
    if not all(x.is_file() for x in [*files, bitstream]):
        return {'status': 'FAIL_MISSING_REPORT', 'errors': ['missing physical report/bitstream'],
                'missing': [str(x) for x in [*files, bitstream] if not x.is_file()],
                'board_release_allowed': False}
    result = original.review('138k_c40_hold065', *(x.read_text(encoding='utf-8') for x in files))
    observed = set(result['errors'])
    if observed != EXPECTED_DELTAS or len(result['errors']) != len(EXPECTED_DELTAS):
        errors.append('baseline_gate_unexpected_differences: ' + repr(result['errors']))
    if prep['status'] != 'PREPARED_NOT_PHYSICALLY_ADMITTED' or prep['error'] is not None:
        errors.append('preparation_failed')
    if build['status'] != 'TOOL_EXIT0_REPORTS_REQUIRE_INDEPENDENT_REVIEW' or build['exit_code'] != 0 or build['timed_out']:
        errors.append('build_failed_or_timed_out')
    if build['tool_calls'] != 1 or not build['input_unchanged']:
        errors.append('execution_or_identity_contract_failed')
    if build['preparation_receipt'] != digest(stage / 'PREPARATION_RECEIPT.json'):
        errors.append('preparation_receipt_sha_changed')
    if build['project'] != digest(stage / (TOP + '.gprj')):
        errors.append('project_sha_changed')
    for name, identity in build['log_sha256'].items():
        if identity != digest(run / name):
            errors.append('build_log_sha_changed:' + name)
    for name, identity in build['pnr_artifacts'].items():
        if identity != digest(pnr / name):
            errors.append('physical_artifact_sha_changed:' + name)
    if build['pnr_artifacts'].get(bitstream.name) != digest(bitstream):
        errors.append('bitstream_sha_missing_or_changed')
    log = (run / 'stdout.log').read_text(encoding='utf-8', errors='replace')
    for marker in MARKERS:
        if marker not in log:
            errors.append('incomplete_build:' + marker)
    sdc = files[3].read_text(encoding='utf-8')
    cst = (stage / 'inputs/constraints/audio_visual.cst').read_text(encoding='utf-8')
    if sdc.count('# M1TD NEW NETLIST ENDPOINT REQUIRED:') != 2 or cst.count('// M1TD NEW NETLIST ENDPOINT REQUIRED: INS_LOC') != 2:
        errors.append('retired_audio_path_scope_changed')
    if result['resources']['BSRAM']['used'] <= 20 or result['resources']['DSP']['used'] <= 46:
        errors.append('new_audio_resource_not_detected')
    if result['slacks']['Setup'] < 0.5:
        errors.append('setup_engineering_floor_below_0p5ns')
    rows = original.parsed(files[0].read_text(encoding='utf-8'))
    audio = [(section, float(row[1]), row[2], row[3]) for section, row in rows
             if section.startswith(('Setup_Slack_Table', 'Hold_Slack_Table'))
             and len(row) > 3 and row[0].isdigit()
             and ('g_polyphonic.u_audio_core/' in row[2] or 'g_polyphonic.u_audio_core/' in row[3])]
    if not any(x[0].startswith('Setup') for x in audio) or not any(x[0].startswith('Hold') for x in audio):
        errors.append('new_audio_timing_paths_unobserved')
    return {'status': 'PHYSICAL_REPORT_PASS_FUNCTIONAL_PENDING' if not errors else 'FAIL_PARTIAL',
            'errors': errors, 'expected_new_combo_differences': sorted(EXPECTED_DELTAS),
            'slacks_ns': result['slacks'], 'fmax_MHz': result['fmax_MHz'],
            'resources': result['resources'], 'TNS': result['TNS'],
            'visual_CDC_gate': result['visual_CDC_gate'],
            'actual_pins': result['actual_pins'],
            'reset_and_diagnostic_LOC': result['reset_and_diagnostic_LOC'],
            'minimum_pulse_ns': result['minimum_pulse_ns'],
            'audio_timing_paths': sorted(audio, key=lambda x:x[1])[:12],
            'artifact_sha256': {x.name: digest(x) for x in [*files, bitstream]},
            'board_release_allowed': False,
            'new_board_functional_RTL': 'NOT_RUN',
            'old_L5_transfer': False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepared', type=Path, required=True)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('REFUSE_OVERWRITE_ASSESSMENT')
    result = assess(args.prepared.resolve(), args.run.resolve())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: result.get(key) for key in ('status', 'errors', 'slacks_ns', 'resources')}, ensure_ascii=False))
    return 0 if result['status'].startswith('PHYSICAL_REPORT_PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
