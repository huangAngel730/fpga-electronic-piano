"""Read-only chat8 delta: decode actual controls; never invent missing lane math.

This is NOT a DDS/ADSR/gain/delay oracle or a rerun of the C digital checker.
Exit 0 means a limited evidence inventory was produced, not full R05 PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
A = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02'
C = ROOT / 'code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02'
STAGE = A / 'RUN_01/stage/inputs'
PINS = {
    A / 'RUN_01/RUN_RECEIPT.json': '1516a35e6a5852164866aa729f8897ca5a668a4308f8e1ce60e91fa994211dbc',
    STAGE / 'REAL_CAPTURE.jsonl': 'a2509a2b5555437ff8ee1da4799e8210ad80e95a058881a5d26111a935e5b5d3',
    STAGE / 'REAL_INPUTS.jsonl': 'd001cac94d1520c42b43bcb33ca079c2f1d815c1205deb4a2d87005fe143038b',
    C / 'EVENT_CALENDAR.json': 'b90f2c477f52a0423ee2aeaa8e1e3a910e8536d95f52cff3b335f75347822231',
    C / 'DIGITAL_SUMMARY.json': 'd70f2dda0b58585609ed5ca5f6a2e769537bdebe4ddb9f233d858fc24ed523fc',
    Path('E:/FPGA/GAOYUNFPGA/Callback3/chat8/给M3_R05冻结算法与PCM声音判据.md'):
        'd7a4ec69f04736fc414ab856c9e99893779e2b2192b16d2b727684fbba3e88c0',
}
FIELDS = [('event_type', 3), ('source_id', 4), ('channel', 4),
          ('note_number', 7), ('velocity', 10), ('expression', 10),
          ('control_id', 8), ('control_value', 12), ('reserved', 6)]
# Proposed observations, not new public ports and not permission to collect RTL.
REQUIRED = {
    'four_independent_voices': ['slot_identity', 'slot_generation', 'slot_note',
        'slot_fcw', 'lane_tick', 'lane_phase', 'lane_wave', 'lane_envelope'],
    'program_lock': ['slot_identity', 'slot_generation', 'slot_timbre', 'slot_note_on'],
    'q15_mix': ['bank_result_id', 'bank_result_valid', 'bank_result_ready',
        'bank_occupied', 'bank_waves', 'bank_envelopes', 'mixed_pcm', 'mixed_clip'],
    'effect_history': ['effect_input_valid', 'effect_input_ready', 'effect_input_id',
        'effect_input_left', 'effect_input_right', 'effect_config_values',
        'effect_output_valid', 'effect_output_ready', 'effect_output_id'],
    'clip_math': ['upstream_clip_left', 'upstream_clip_right',
        'effect_clip_left', 'effect_clip_right', 'unsaturated_mix', 'unsaturated_effect'],
}


def identity(path: Path) -> dict:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def no_duplicate(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_KEY:' + key)
        result[key] = value
    return result


def parse(text):
    return json.loads(text, object_pairs_hook=no_duplicate)


def decode_event(text):
    if not isinstance(text, str) or not re.fullmatch('[0-9a-fA-F]{16}', text):
        raise ValueError('EVENT_HEX_WIDTH_OR_UNKNOWN')
    value = int(text, 16)
    shift = 64
    decoded = {}
    for name, width in FIELDS:
        shift -= width
        decoded[name] = (value >> shift) & ((1 << width) - 1)
    if decoded['reserved']:
        raise ValueError('RESERVED_NONZERO')
    return decoded


def program_predictions(events):
    """Input-contract predictions ONLY; no guessed slot or DSP phase assigned."""
    selections = {}
    output = []
    for event in events:
        row = dict(event)
        d = decode_event(row['event_data_hex'])
        key = (row['epoch'], d['source_id'], d['channel'])
        row['decoded'] = d
        row['scope'] = 'INPUT_OBSERVED_ALLOCATION_AND_SOUND_NOT_PROVEN'
        if d['event_type'] == 4 and d['control_id'] == 5:
            row['meaning'] = 'PROGRAM_SELECT' if d['control_value'] <= 1 else 'IGNORED_PROGRAM'
            if d['control_value'] <= 1:
                selections[key] = d['control_value']
        elif d['event_type'] == 0 and d['velocity'] != 0:
            row['meaning'] = 'NOTE_ON'
            row['program_if_successfully_allocated'] = selections.get(key, 0)
            row['program_observed_in_slot'] = None
            row['slot_identity'] = None
        else:
            row['meaning'] = 'OTHER_OR_ZERO_VELOCITY_OFF'
        output.append(row)
    return output


def missing_observations(fields):
    # Even a complete header is not a mathematical comparison or signed proof.
    return {name: {'status': 'UNKNOWN_NOT_MATHEMATICALLY_COMPARED',
                   'missing_proposed_observations': sorted(set(required) - set(fields))}
            for name, required in REQUIRED.items()}


def require_integer_bit(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError('NON_BINARY_FLAG')


def analyze():
    pins = []
    for path, expected in PINS.items():
        record = identity(path)
        if record['sha256'] != expected:
            raise ValueError('INPUT_IDENTITY:' + str(path))
        pins.append(record)
    receipt = parse((A / 'RUN_01/RUN_RECEIPT.json').read_text(encoding='utf-8'))
    sources = []
    names = ['audio_defs_pkg.sv', 'm1td_polyphonic_event_router.sv',
             'm1td_polyphonic_envelope_bank.sv', 'm1td_piano_triangle_voice.sv',
             'm1td_audio_candidate.sv', 'm1td_voice_gain_q15_candidate.sv',
             'm1td_pcm_mixer_4voice.sv', 'm1td_timbre_delay_chain.sv',
             'm1td_stereo_delay.sv', 'm1td_delay_effect.sv',
             'm2_fourvoice_timbre_delay_board_top.sv']
    for key in ['sources/' + n for n in names] + sorted(
            k for k in receipt['stage_before'] if k.startswith('rom/')):
        item = identity(STAGE / key)
        for section in ('stage_before', 'stage_after'):
            if any(item[k] != receipt[section][key][k] for k in ('bytes', 'sha256')):
                raise ValueError('STAGE_IDENTITY:' + key)
        sources.append(item)
    observed = []
    configurations = []
    fields = set()
    epoch = 0
    with (STAGE / 'REAL_INPUTS.jsonl').open(encoding='utf-8') as stream:
        for line_number, text in enumerate(stream, 1):
            row = parse(text)
            if row['kind'] == 'RESET':
                epoch = row['epoch']
            if row['kind'] != 'TICK':
                continue
            fields.update(row)
            for name in ('rst_n', 'event_valid', 'event_ready', 'config_valid', 'config_ready'):
                require_integer_bit(row[name])
            if row['rst_n'] and row['event_valid'] and row['event_ready']:
                observed.append({k: row[k] for k in ('cycle', 'time_ns', 'event_data_hex')}
                                | {'epoch': epoch, 'source_line': line_number})
            if row['rst_n'] and row['config_valid'] and row['config_ready']:
                configurations.append({'cycle': row['cycle'], 'epoch': epoch,
                                       'source_line': line_number,
                                       'payload_observed': None})
    prior = parse((C / 'EVENT_CALENDAR.json').read_text(encoding='utf-8'))
    keys = ('epoch', 'cycle', 'time_ns', 'event_data_hex')
    if [[r[k] for k in keys] for r in observed] != [[r[k] for k in keys] for r in prior]:
        raise ValueError('PRIOR_CALENDAR_DISAGREES')
    # Inspect only the pinned header/first record to inventory exported fields.
    # Do not repeat the already completed full C deadline/serial analysis.
    with (STAGE / 'REAL_CAPTURE.jsonl').open(encoding='utf-8') as stream:
        header = parse(next(stream))
        fields.update(parse(next(stream)))
    summary = parse((C / 'DIGITAL_SUMMARY.json').read_text(encoding='utf-8'))
    output = {
        'status': 'PARTIAL_MISSING_M1_CLOSURE_AND_LANE_EFFECT_OBSERVATIONS',
        'level': 'L0_IDENTITY_AND_L1_SOFTWARE_INPUT_DELTA_ONLY',
        'inputs': pins, 'stage_sources_and_roms': sources,
        'events': program_predictions(observed), 'config_handshakes': configurations,
        'observed_field_names': sorted(fields), 'math_scope': missing_observations(fields),
        'source_tied_config_not_exported_payload': {
            'enable': 1, 'delay_samples': 1, 'dry_q15': 32767, 'wet_q15': 16384, 'feedback_q15': 0},
        'reused_not_rerun': {k: summary[k] for k in (
            'accepted_requests', 'committed_requests', 'commits_with_proven_next_frame_deadline',
            'serial_stereo_frames', 'equal_channels_all_commits', 'actual_clip_commits')},
        'first_valid_observable': header['first_valid_observable'],
        'M1_full_archive_received': False,
        'M1_required_sha256': '842fa8f75356090440a5e8237acafc209620d114f9e3c0ce2eab5ffdf30862da',
        'math_model_executions': 0, 'rtl_executions': 0, 'eda_executions': 0,
        'four_frequency_pcm_verified': False, 'board_release_allowed': False,
    }
    # Identity check after analysis; readonly by construction, no source mutation.
    for item in pins + sources:
        if identity(Path(item['path'])) != item:
            raise ValueError('INPUT_CHANGED_DURING_ANALYSIS')
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = analyze()
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(result['status'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
