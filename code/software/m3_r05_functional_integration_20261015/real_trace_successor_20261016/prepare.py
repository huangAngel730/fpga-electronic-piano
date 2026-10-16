"""Read-only frozen intake and bounded synthetic schema checks. No HDL tools."""
import copy
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from contract import FIELDS, LANE, SCHEMA

ROOT = Path(__file__).resolve().parents[4]
NAME = 'real_trace_successor_20261016'
DOC = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015' / NAME
STAGE = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02/RUN_01/stage/inputs'
SEAL = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016/SEAL_CHAT9R02/M3_CHAT9_R05_PCM_REPLAY_20261016.zip'
MEMBER = 'input/M1_Failure判据修复与R05支援交接_20261015.zip'
OUTER_SHA = '842fa8f75356090440a5e8237acafc209620d114f9e3c0ce2eab5ffdf30862da'
CRITERIA = '给M3_R05冻结算法与PCM声音判据.md'
CRITERIA_SHA = 'd7a4ec69f04736fc414ab856c9e99893779e2b2192b16d2b727684fbba3e88c0'
GROUPS = {
    'clock': ('m3_r05_public_observer.sv', 'posedge clk; time in ps; monotonically numbered edge', 'PARTIAL_EXISTING'),
    'reset': ('m3_r05_public_observer.sv', 'rst_n; increment epoch on each assertion, independent of request ID', 'PARTIAL_EXISTING'),
    'frame': ('m2_fourvoice_timbre_delay_frame_core.sv', 'frame_tick', 'EXISTING'),
    'event': ('m2_fourvoice_timbre_delay_frame_core.sv', 'event_valid/event_ready/event_data', 'EXISTING_INGRESS_ONLY'),
    'request': ('premixed_frame_adapter.sv', 'request_valid/request_ready/request_id/current_req_id', 'PARTIAL_EXISTING'),
    'math': ('m1td_polyphonic_envelope_bank.sv', 'u_pitch_mod request_valid/request_ready/request_id; observe actual accept including cancelled results', 'MISSING'),
    'effect': ('m1td_stereo_delay.sv', 'input_valid/input_ready/input_id/input_left/input_right/input_clipped_left/input_clipped_right', 'MISSING'),
    'config': ('m1td_stereo_delay.sv', 'config_valid/config_ready/config_enable/config_delay_samples/config_dry_gain/config_wet_gain/config_feedback', 'MISSING_PAYLOAD_CALENDAR'),
    'result': ('m1td_stereo_delay.sv', 'output_valid/output_ready/output_id/output_left/output_right/clipped_left/clipped_right', 'MISSING'),
    'commit': ('m2_fourvoice_timbre_delay_frame_core.sv', 'commit_pulse/committed_id/committed_left/committed_right/committed_clip/clip_count', 'EXISTING'),
    'play': ('m2_fourvoice_timbre_delay_frame_core.sv', 'pending_valid/play_left/play_right/audio_underrun', 'EXISTING'),
    'serial': ('m3_r05_public_observer.sv', 'bclk/ws/din', 'EXISTING'),
}

# Explicit field-to-signal expressions; handshake is observational, not proof of
# independently correct ready or completeness. No phase/wave/env is a golden.
PORTS = {
    'cycle': 'observer edge counter', 'time_ps': 'longint\'($realtime*1000.0), timescale 1ns/1ps',
    'epoch': 'observer reset-assertion lifetime counter', 'rst_n': 'rst_n',
    'frame_tick': 'frame_tick', 'event_valid': 'event_valid',
    'event_ready_observed': 'event_ready', 'event_data': 'event_data',
    'event_accept_observed': 'event_valid && event_ready',
    'request_valid': 'candidate_sample_valid', 'request_ready_observed': 'candidate_sample_ready',
    'request_accept_observed': 'candidate_sample_valid && candidate_sample_ready',
    'request_id': 'candidate_sample_id', 'current_id': 'current_id',
    'math_valid': 'control_snapshot_valid && phase==WAIT_CONTROL && !frame_tick (export predicate, not phase)',
    'math_ready_observed': 'fcw_request_ready',
    'math_accept_observed': 'math_valid && fcw_request_ready', 'math_id': 'control_id',
    'fx_valid': 'input_valid', 'fx_ready_observed': 'input_ready',
    'fx_accept_observed': 'input_valid && input_ready', 'fx_id': 'input_id',
    'fx_left': 'input_left', 'fx_right': 'input_right',
    'fx_clip_left': 'input_clipped_left', 'fx_clip_right': 'input_clipped_right',
    'config_valid': 'config_valid', 'config_ready_observed': 'config_ready',
    'config_accept_observed': 'config_valid && config_ready',
    'config_enable': 'config_enable', 'config_delay': 'config_delay_samples',
    'config_dry': 'config_dry_gain', 'config_wet': 'config_wet_gain', 'config_feedback': 'config_feedback',
    'result_valid': 'output_valid', 'result_ready': 'output_ready', 'result_id': 'output_id',
    'result_left': 'output_left', 'result_right': 'output_right',
    'result_clip_left': 'clipped_left', 'result_clip_right': 'clipped_right',
    'commit': 'commit_pulse', 'committed_id': 'committed_id',
    'committed_left': 'committed_left', 'committed_right': 'committed_right',
    'committed_clip': 'committed_clip', 'clip_count': 'clip_count', 'pending': 'pending_valid',
    'play_left': 'play_left', 'play_right': 'play_right', 'underflow': 'audio_underrun',
    'bclk': 'i2s_bclk', 'ws': 'i2s_ws', 'din': 'i2s_din',
}
LANE_PORTS = dict(lane='generate index i', tick='lane_tick (all four lanes, occupied or not)',
    note_on='slot_note_on[i]', note_off='slot_note_off[i]', occupied='slot_occupied[i]',
    source='slot_sources[4*i+:4]', channel='slot_channels[4*i+:4]',
    note='slot_notes[8*i+:8]', generation='slot_generations[32*i+:32]',
    velocity='slot_velocity[10*i+:10]', timbre='slot_timbre[i]', fcw_observed='dds_fcw[32*i+:32]')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': sha(data)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def intake(out):
    assert identity(SEAL)['sha256'] == '832947a0a0bacb3d604a01e0bb726cf943d007f506e5b51c67d941ee55e31b12', 'CARRIER_IDENTITY'
    with zipfile.ZipFile(SEAL) as archive:
        original = archive.read(MEMBER)
    assert len(original) == 750224 and sha(original) == OUTER_SHA, 'M1_OUTER_IDENTITY'
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        criteria = archive.read(CRITERIA)
        assert sha(criteria) == CRITERIA_SHA, 'M1_CRITERIA_IDENTITY'
    (out / 'M1_CRITERIA_READONLY.md').write_bytes(criteria)
    sources = {p.name: identity(p) for p in sorted((STAGE / 'sources').glob('*.sv'))}
    receipt_path = STAGE.parent.parent / 'RUN_RECEIPT.json'
    assert identity(receipt_path)['sha256'] == '1516a35e6a5852164866aa729f8897ca5a668a4308f8e1ce60e91fa994211dbc', 'RECEIPT_IDENTITY'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    for rel, pin in receipt['stage_after'].items():
        actual = identity(STAGE / rel)
        assert actual['sha256'] == pin['sha256'], 'STAGE_IDENTITY:' + rel
    captures = {}
    pins = {'REAL_CAPTURE.jsonl': 'a2509a2b5555437ff8ee1da4799e8210ad80e95a058881a5d26111a935e5b5d3',
            'REAL_INPUTS.jsonl': 'd001cac94d1520c42b43bcb33ca079c2f1d815c1205deb4a2d87005fe143038b'}
    for name, pin in pins.items():
        captures[name] = identity(STAGE / name)
        assert captures[name]['sha256'] == pin, 'CAPTURE_IDENTITY'
        with (STAGE / name).open(encoding='utf-8') as stream:
            captures[name]['header'] = json.loads(next(stream))
            captures[name]['first_record'] = json.loads(next(stream))
    mapping = {}
    for field, (_, _, group) in FIELDS.items():
        module, pins_text, available = GROUPS[group]
        mapping[field] = {'group': group, 'source': module, 'candidate_port_set': pins_text,
                          'expression': PORTS[field],
                          'existing_capture': available, 'source_identity': sources.get(module),
                          'use': 'OBSERVATION_NOT_GOLDEN' if group in ('effect', 'result', 'commit', 'play', 'serial') else 'CONTROL_CALENDAR',
                          'missing': 'REJECT', 'sampling': 'posedge_pre_NBA',
                          'binding_state': 'PROPOSED_NOT_CONNECTED'}
    for field in LANE:
        mapping['lanes[*].' + field] = {
            'source': 'm1td_polyphonic_envelope_bank.sv',
            'source_identity': sources['m1td_polyphonic_envelope_bank.sv'],
            'expression': LANE_PORTS[field],
            'existing_capture': 'MISSING', 'missing': 'REJECT',
            'use': 'OBSERVATION_NOT_GOLDEN' if field == 'fcw_observed' else 'CONTROL_CALENDAR',
            'binding_state': 'PROPOSED_NOT_CONNECTED'}
    for field in ('applications', 'cancellations'):
        mapping[field] = {'existing_capture': 'MISSING', 'missing': 'REJECT',
                          'source': 'future public observation ports + independent control scoreboard',
                          'binding_state': 'PROPOSED_NOT_CONNECTED'}
    write(out / 'SOURCE_BINDINGS.json', mapping)
    write(out / 'INPUT_IDENTITY.json', {
        'carrier': identity(SEAL), 'nested_member': MEMBER, 'original_bytes': len(original),
        'original_sha256': sha(original), 'criteria_sha256': sha(criteria),
        'capture_lineage': 'R06 7ms successor derived from R05, plus night observer delta',
        'original_R05': '6ms watchdog FAIL; original bytes retained',
        'receipt': identity(receipt_path), 'stage_members_checked': len(receipt['stage_after']),
        'sources': sources, 'captures': captures,
        'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False})


def fixture():
    row = {key: 0 for key in FIELDS}
    row.update(lanes=[dict({key: 0 for key in LANE}, lane=i) for i in range(4)],
               applications=[], cancellations=[])
    rows = [copy.deepcopy(row) for _ in range(4)]
    for i, value in enumerate(rows):
        value.update(cycle=i, time_ps=12500 + 25000*i, rst_n=int(i in (1, 2)), epoch=int(i == 3))
    rows[2]['event_valid'] = rows[2]['event_ready_observed'] = rows[2]['event_accept_observed'] = 1
    rows[2]['lanes'][0]['tick'] = 1
    return {'schema': SCHEMA, 'origin': 'SYNTHETIC_CONTRACT_SELFTEST', 'sampling': 'posedge_pre_NBA',
            'rows': rows, 'end': {'rows': 4, 'last_cycle': 3}}


def tests():
    good = fixture()
    cases = [('synthetic_schema_only', good, 0, 'SYNTHETIC_SCHEMA_PASS_ONLY')]
    for field in FIELDS:
        bad = copy.deepcopy(good)
        del bad['rows'][1][field]
        cases.append(('missing_' + field, bad, 1, 'ROW_FIELDS'))
    for field in LANE:
        bad = copy.deepcopy(good)
        del bad['rows'][2]['lanes'][3][field]
        cases.append(('missing_lane_' + field, bad, 1, 'LANE_FIELDS'))
    for field in ('applications', 'cancellations'):
        bad = copy.deepcopy(good)
        del bad['rows'][2][field]
        cases.append(('missing_' + field, bad, 1, 'ROW_FIELDS'))
    mutations = [
        ('fake_real', lambda d: d.update(origin='REAL'), 'REAL_CAPTURE_NOT_QUALIFIED'),
        ('post_NBA', lambda d: d.update(sampling='post_NBA'), 'SAMPLING'),
        ('skip_cycle', lambda d: d['rows'][2].update(cycle=3), 'CYCLE_GAP'),
        ('bad_epoch', lambda d: d['rows'][3].update(epoch=0), 'RESET_EPOCH'),
        ('bool_flag', lambda d: d['rows'][1].update(rst_n=True), 'ROW_TYPE_RANGE'),
        ('unknown_PCM', lambda d: d['rows'][1].update(fx_left=None), 'ROW_TYPE_RANGE'),
        ('DUT_wave_golden', lambda d: d['rows'][1].update(wave=123), 'ROW_FIELDS'),
        ('DUT_env_golden', lambda d: d['rows'][1].update(env=123), 'ROW_FIELDS'),
        ('DUT_phase_golden', lambda d: d['rows'][1].update(phase=123), 'ROW_FIELDS'),
        ('missing_fourth_lane', lambda d: d['rows'][1]['lanes'].pop(), 'ALL_LANES'),
        ('tick_on_reset', lambda d: d['rows'][0]['lanes'][0].update(tick=1), 'TICK_CANCEL_RESET'),
        ('false_handshake', lambda d: d['rows'][1].update(fx_accept_observed=1), 'HANDSHAKE'),
        ('end_count', lambda d: d['end'].update(rows=3), 'END_COUNT'),
    ]
    for name, mutate, diagnostic in mutations:
        bad = copy.deepcopy(good)
        mutate(bad)
        cases.append((name, bad, 1, diagnostic))
    with (STAGE / 'REAL_CAPTURE.jsonl').open(encoding='utf-8') as stream:
        next(stream)
        old = json.loads(next(stream))
    bad = copy.deepcopy(good)
    bad['rows'] = [old]
    cases.append(('old_real_record_missing_calendar', bad, 1, 'ROW_FIELDS'))
    raw = json.dumps(good)
    cases.append(('duplicate_json_key', raw.replace('"cycle": 0', '"cycle": 0, "cycle": 0', 1), 1, 'DUPLICATE_KEY'))
    cases.append(('trailing_record', raw + '\n{}', 1, 'Extra data'))
    return cases


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isalnum():
        raise SystemExit('usage: prepare.py UNIQUE_RUN_ID')
    out = DOC / sys.argv[1]
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    src = Path(__file__).parent
    before = [identity(p) for p in sorted(src.glob('*.py'))]
    snapshot = out / 'source_snapshot'
    snapshot.mkdir()
    for item in before:
        path = Path(item['path'])
        (snapshot / path.name).write_bytes(path.read_bytes())
    command = [sys.executable, '-B', '-X', 'utf8', str(src / 'contract.py')]
    write(out / 'PLAN.json', {'machine': platform.node(), 'python': identity(Path(sys.executable)),
          'python_version': sys.version, 'source_before': before, 'cwd': str(ROOT),
          'command_prefix': command, 'total_budget_seconds': 180, 'step_budget_seconds': 5,
          'ModelSim_calls': 0, 'Gowin_calls': 0, 'all_test_inputs': 'SYNTHETIC except read-only old incomplete row'})
    calls = []
    failure = None
    try:
        intake(out)
        for index, (name, data, expected, diagnostic) in enumerate(tests()):
            path = out / (f'{index:03d}_' + name + '.json')
            if isinstance(data, str):
                path.write_text(data, encoding='utf-8')
            else:
                write(path, data)
            remaining = 180 - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError('TOTAL_BUDGET')
            argv = command + [str(path)]
            try:
                result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=min(5, remaining), check=False)
            except subprocess.TimeoutExpired as exc:
                path.with_suffix('.stdout.log').write_bytes(exc.stdout or b'')
                path.with_suffix('.stderr.log').write_bytes(exc.stderr or b'')
                calls.append({'name': name, 'argv': argv, 'exit_code': None, 'timeout': True, 'pass': False})
                raise
            path.with_suffix('.stdout.log').write_bytes(result.stdout)
            path.with_suffix('.stderr.log').write_bytes(result.stderr)
            ok = result.returncode == expected and diagnostic in result.stdout.decode('utf-8')
            calls.append({'name': name, 'argv': argv, 'exit_code': result.returncode,
                          'expected_exit': expected, 'expected_diagnostic': diagnostic, 'pass': ok,
                          'timeout': False})
            if not ok:
                raise ValueError('SELFTEST:' + name)
    except Exception as exc:
        failure = repr(exc)
    after = [identity(p) for p in sorted(src.glob('*.py'))]
    artifacts = [identity(p) for p in sorted(out.rglob('*')) if p.is_file()]
    elapsed = time.monotonic() - started
    ok = failure is None and before == after and elapsed <= 180
    write(out / 'RECEIPT.json', {'status': 'SOFTWARE_PREPARATION_PASS' if ok else 'FAIL',
          'exit_code': int(not ok), 'failure': failure, 'calls': calls, 'actual_calls': len(calls),
          'elapsed_seconds': elapsed, 'timeout': isinstance(failure, str) and 'Timeout' in failure,
          'source_after': after, 'artifacts': artifacts,
          'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False})
    print(json.dumps({'status': 'SOFTWARE_PREPARATION_PASS' if ok else 'FAIL',
                      'calls': len(calls), 'failure': failure, 'elapsed_seconds': elapsed}))
    return int(not ok)


if __name__ == '__main__':
    raise SystemExit(main())
