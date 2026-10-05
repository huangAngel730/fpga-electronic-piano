"""Additional fail-closed checks for full frozen reports, not hardware acceptance."""
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'preparation_20261005'))
from collect_sta_results import analyze, FROZEN_CLOCKS, normalize, ReportParser

STAGES = [
    ('u_visual/u_event_bridge', 'ack_meta', 'ack_sync'),
    ('u_visual/u_event_bridge', 'req_meta', 'req_sync'),
    ('u_visual/u_event_bridge', 'desync_meta', 'video_desync'),
    ('u_visual/u_control/u_score_mailbox', 'ack_meta', 'ack_sync'),
    ('u_visual/u_control/u_score_mailbox', 'req_meta', 'req_sync'),
    ('u_visual/u_control/u_mode_mailbox', 'ack_meta', 'ack_sync'),
    ('u_visual/u_control/u_mode_mailbox', 'req_meta', 'req_sync'),
]
BUSES = [('u_visual/u_event_bridge', 'payload_hold', 'video_data', 23),
         ('u_visual/u_control/u_score_mailbox', 'payload_hold', 'dst_data', 50)]


def parsed(text):
    parser = ReportParser()
    parser.feed(text)
    return parser.rows


def pins(text):
    rows = [r for s, r in parsed(text) if s == 'Pinout_by_Port_Name']
    headers = [r for r in rows if r and r[0] == 'Port Name']
    if len(headers) != 1 or len(set(headers[0])) != len(headers[0]):
        raise ValueError('Missing/duplicate pin table headers')
    header = headers[0]
    required = {'Port Name', 'Diff Pair', 'Loc./Bank', 'Constraint', 'Dir.',
                'IO Type', 'Drive', 'Pull Mode', 'BankVccio'}
    if not required.issubset(header):
        raise ValueError('Missing required semantic pin column')
    result = {}
    for row in rows:
        if not row or row[0] == 'Port Name':
            continue
        if len(row) != len(header) or row[0] in result:
            raise ValueError('Malformed/duplicate port row')
        result[row[0]] = dict(zip(header, row))
    if not result:
        raise ValueError('Empty pin port evidence')
    return result


def extensions(timing, pin_report, expected_pins):
    rows = parsed(timing)
    errors = []
    pulse = [r for s, r in rows if s == 'MIN_PULSE_WIDTH_TABLE'
             and len(r) >= 7 and r[0].isdigit()]
    worst_pulse = None
    try:
        values = [float(r[1]) for r in pulse]
        if not values or not all(math.isfinite(v) and v >= 0 for v in values):
            raise ValueError('missing/invalid/negative pulse')
        worst_pulse = min(values)
    except ValueError:
        errors.append('missing/nonfinite/negative minimum pulse width evidence')
    for kind in ['Recovery', 'Removal']:
        reset_paths = [r for s, r in rows if s.startswith(kind + '_Slack_Table')
                       and len(r) >= 4 and r[0].isdigit()]
        try:
            values = [float(r[1]) for r in reset_paths]
            if not values or not all(math.isfinite(v) and v >= 0 for v in values):
                raise ValueError('missing/invalid reset paths')
        except ValueError:
            errors.append('missing/nonfinite/negative ' + kind)
    commands = {
        kind: [normalize(r[2]) for s, r in rows if s == 'SDC_Report' and len(r) == 3
               and r[1] == 'Actived' and r[2].startswith('report_timing -' + kind.lower() + ' ')]
        for kind in ['Setup', 'Hold']}

    def table(kind, command):
        command = normalize(command)
        matches = [index for index, actual in enumerate(commands[kind]) if actual == command]
        if len(matches) != 1:
            errors.append('missing/duplicate dedicated CDC report: ' + command)
            return []
        section = f'{kind}_Slack_Table{matches[0] + 1}'
        return [r for s, r in rows if s == section and len(r) >= 4 and r[0].isdigit()]

    stages = {}
    for prefix, first, second in STAGES:
        for kind in ['Setup', 'Hold']:
            command = (f'report_timing -{kind.lower()} -from [get_regs {{{prefix}/{first}_s0}}] '
                       f'-to [get_regs {{{prefix}/{second}_s0}}] -max_paths 1')
            paths = table(kind, command)
            try:
                if len(paths) == 1 and math.isfinite(float(paths[0][1])):
                    stages[f'{prefix}/{first}->{second}:{kind}'] = float(paths[0][1])
                if (len(paths) != 1 or paths[0][2] != f'{prefix}/{first}_s0/Q'
                        or paths[0][3] != f'{prefix}/{second}_s0/D'
                        or not math.isfinite(float(paths[0][1])) or float(paths[0][1]) < 0):
                    raise ValueError('invalid stage path')
            except ValueError:
                errors.append('missing/invalid/negative CDC second stage: ' + command)
    buses = {}
    for prefix, source, sink, expected_count in BUSES:
        command = (f'report_timing -setup -from [get_regs {{{prefix}/{source}*}}] '
                   f'-to [get_regs {{{prefix}/{sink}*}}] -max_paths 128 -max_common_paths 1')
        paths = table('Setup', command)
        buses[prefix] = len(paths)
        try:
            if len(paths) != expected_count or len({r[3] for r in paths}) != len(paths):
                raise ValueError('payload path count changed or duplicate endpoint')
            if not all(r[2].startswith(prefix + '/' + source) and r[3].startswith(prefix + '/' + sink)
                       and math.isfinite(float(r[1])) and float(r[1]) >= 0 for r in paths):
                raise ValueError('payload bound/path changed')
        except ValueError:
            errors.append('CDC payload path set/count/slack differs from frozen surviving paths: ' + prefix)
    try:
        actual_pins = pins(pin_report)
    except ValueError as exc:
        actual_pins = {}
        errors.append('malformed pin report: ' + str(exc))
    if set(actual_pins) != set(expected_pins):
        errors.append('pin port set differs from baseline')
    # Location (including bank), differential partner, constraint, direction,
    # IO standard, drive, pull, BankVccio: no silently accepted migration.
    columns = ['Diff Pair', 'Loc./Bank', 'Constraint', 'Dir.', 'IO Type',
               'Drive', 'Pull Mode', 'BankVccio']
    for port, expected in expected_pins.items():
        if port not in actual_pins or any(actual_pins[port][i] != expected[i] for i in columns):
            errors.append('pin electrical/location mismatch: ' + port)
    return {'errors': errors, 'min_pulse_width_slack_ns': worst_pulse,
            'CDC_second_stage_slacks': stages, 'CDC_surviving_payload_path_counts': buses,
            'pins': actual_pins,
            'CDC_not_full_unoptimized_bus_coverage': True}


def normalized_options(text):
    return [normalize(line) for line in text.splitlines() if line.strip()
            and not line.startswith(('-d ', '-p ', '-pn ', '-cst ', '-cfg ', '-sdc '))]


def expected_138k_electrical_pins(original_pins):
    banks = {'sys_clk': 4, 'sys_rst_n': 5, 'key_n[0]': 5, 'key_n[1]': 5,
             'midi_rx': 4, 'i2s_bclk': 5, 'i2s_lrck': 5, 'i2s_din': 5,
             'pa_en': 5, 'uart_tx': 5, 'tmds_clk_p': 3,
             'tmds_data_p[0]': 3, 'tmds_data_p[1]': 3, 'tmds_data_p[2]': 3}
    if set(original_pins) != set(banks):
        raise ValueError('Unreviewed port set; no guessed Bank mapping')
    expected = {port: dict(row) for port, row in original_pins.items()}
    for port, row in expected.items():
        row['Loc./Bank'] = row['Loc./Bank'].rsplit('/', 1)[0] + '/' + str(banks[port])
        if port in ['sys_rst_n', 'key_n[0]', 'key_n[1]']:
            row['IO Type'], row['BankVccio'] = 'LVCMOS33', '3.3'
    return expected


def check(timing, usage, sdc, pin_report, expected_pins, expected_pn, expected_version,
          command=None, original_command=None, device_cfg=None, original_device_cfg=None,
          allowed_extra_options=(), allowed_device_cfg_changes=()):
    report = analyze(timing, usage, FROZEN_CLOCKS, True, sdc)
    extra = extensions(timing, pin_report, expected_pins)
    report['errors'].extend(extra.pop('errors'))
    report.update(extra)
    if report['metadata']['Part Number'] != expected_pn or report['metadata']['Device Version'] != expected_version:
        report['errors'].append('target part/version mismatch')
    if report['metadata']['Tool Version'] != 'V1.9.11.03 Education':
        report['errors'].append('tool version mismatch')
    if report['resources'].get('BSRAM', {}).get('used') != 20 or report['resources'].get('DSP', {}).get('used') != 46:
        report['errors'].append('frozen DSP/BSRAM footprint changed')
    if command is not None and original_command is not None:
        report['normalized_PnR_options'] = normalized_options(command)
        original_options = normalized_options(original_command)
        report['PnR_option_differences'] = {
            'added': [o for o in report['normalized_PnR_options'] if o not in original_options],
            'removed': [o for o in original_options if o not in report['normalized_PnR_options']],
            'explicit_allowed_architecture_only_extras': list(allowed_extra_options)}
        common = [o for o in report['normalized_PnR_options'] if o not in allowed_extra_options]
        if common != original_options:
            report['errors'].append('non-path PnR options changed')
    if device_cfg is not None and original_device_cfg is not None:
        report['device_cfg_matches_original'] = device_cfg == original_device_cfg
        expected_cfg = original_device_cfg
        for before, after in allowed_device_cfg_changes:
            if expected_cfg.count(before) != 1:
                raise ValueError('Ambiguous allowed device configuration adaptation')
            expected_cfg = expected_cfg.replace(before, after)
        report['device_cfg_matches_allowed_profile'] = device_cfg == expected_cfg
        report['explicit_allowed_device_cfg_changes'] = [
            {'from': before.decode(), 'to': after.decode()} for before, after in allowed_device_cfg_changes]
        if device_cfg != expected_cfg:
            report['errors'].append('device programming/options configuration changed')
    report['offline_report_gate_passed'] = not report['errors']
    report['hardware_acceptance'] = False
    report['engineering_margin_0p5ns_passed'] = (
        report['offline_report_gate_passed']
        and min(p['slack_ns'] for p in report['global_worst_paths'].values()) >= 0.5)
    return report
