"""ONE bounded new repair group. No old twenty-case or producer execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import checker
import serial_core as core
from boundaries import canonical, digest, verify_plan
from crosspack import A_SCHEMA, CAL_SCHEMA, adapt_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
RULES = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017/FRAME_PLAN_RULES.json'
DECODER = ROOT / 'code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py'
DECODER_SHA = 'da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb'


def write(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, separators=(',', ':'))
        stream.write('\n')


def base():
    plan = json.loads((HERE / 'fixtures/UNIQUE_FRAME_PLAN.json').read_text(encoding='utf-8'))
    inputs = (HERE / 'fixtures/FRAME_INPUT.json').read_bytes()
    rows = []
    for cycle in range(2502):
        row = dict.fromkeys(core.CANONICAL_FIELDS, 0)
        row.update(cycle=cycle, epoch=0, time_ps=cycle * 25000,
                   rst_n=int(cycle > 0), pll_locked=int(cycle > 0), audio_stable=int(cycle > 0),
                   cancel_reason='NONE', config_payload={}, tx_req_id=None,
                   tx_req_id_valid=0, tx_metadata_valid=int(cycle > 0), tx_clip_mask=0,
                   tx_clip_any=0, metadata_error=0, frame_id_overflow=0,
                   source_line=10000 + cycle, __line=cycle + 1)
        rows.append(row)
    for ordinal, cycle in enumerate((834, 1667, 2500)):
        rows[cycle].update(frame_tick=1, tx_sample_valid=1, tx_frame_id=ordinal + 1,
                           tx_startup_zero=int(ordinal == 0), tx_hold=int(ordinal == 2))
        if ordinal:
            rows[cycle].update(tx_req_id_valid=1, tx_req_id=0, tx_left=256, tx_right=512,
                               tx_clip=1, tx_clip_any=1, tx_clip_mask=1)
    rows[835].update(req_valid=1, req_ready=1, req_id=0)
    rows[1200].update(result_valid=1, result_ready=1, result_id=0, result_left=256, result_right=512, result_clip_mask=1)
    rows[1666].update(commit=1, commit_id=0, commit_left=256, commit_right=512, commit_clip=1)
    rows[2501]['finish'] = 1
    item = {'epoch': 0, 'req_id': 0}
    for name, cycle in dict(frame=834, first_valid=835, accept=835, result=1200, commit=1666, cancel=None).items():
        item[name + '_cycle'], item[name + '_source_line'] = cycle, None if cycle is None else rows[cycle]['source_line']
    calendar = {'schema': 'M3_R07_FA_TRANSACTION_CALENDAR_V1',
                'authority': 'SYNTHETIC_INDEPENDENT_CALENDAR', 'independent_of_trace': True,
                'canonical_plan_id': plan['canonical_plan_id'], 'transactions': [item],
                'tx_selection_plan_authoritative': True,
                'tx_expectations': [{'epoch': 0, 'cycle': c, 'kind': k, 'req_id': rid}
                                    for c, k, rid in ((834, 'STARTUP', None), (1667, 'NEW', 0), (2500, 'HOLD', 0))]}
    oracle = {'schema': 'M3_R06_PCM24_ORACLE_V1', 'authority': 'SYNTHETIC_INDEPENDENT_ORACLE',
              'records': [{'epoch': 0, 'req_id': 0, 'left': 256, 'right': 512, 'clip': 1, 'clip_mask': 1}]}
    binding = {'schema': 'M3_R06_TX_CLOCK_RESET_BINDING_V1', 'mode': 'SYNTHETIC_SELFTEST_ONLY',
               'trace_profile': 'R06C3_TX_FLAT_V1', 'trace_authority': 'SYNTHETIC_FIXTURE',
               'tx_sidecar_authority': 'SYNTHETIC_EXPLICIT_SIDECAR', 'pins_authority': 'SYNTHETIC_PIN_STREAM',
               'timebase_authority': 'SYNTHETIC_40MHZ_TIMEBASE', 'finish_authority': 'SYNTHETIC_EXPLICIT_FINISH',
               'clock_hz': 40000000, 'sample_phase': 'SYS_POSEDGE_PRE_NBA',
               'serial_format': 'PT8211_32BIT_SLOT_LSBJ16_WS_LOW_RIGHT_HIGH_LEFT',
               'pcm24_to_pcm16': 'SATURATE((PCM24+128)//256)'}
    return dict(binding=binding, calendar=calendar, plan=plan, oracle=oracle, rows=rows, inputs=inputs.decode('utf-8'))


def native(data):
    """Hand-authored SAME-contract synthetic fixture; never imports A/R6-3/5."""
    originals = []
    for row in data['rows']:
        fields = {key: row[key] for key in core.CANONICAL_FIELDS}
        cycle = row['cycle']
        ext = {'schema': 'M3_R7A_TX_EXTENSION_V1', 'obs_core_clk': 1, 'obs_polyphonic_valid': 1,
               'obs_tx_metadata_valid': row['tx_metadata_valid'], 'obs_tx_req_id_valid': row['tx_req_id_valid'],
               'obs_tx_clip_mask': row['tx_clip_mask'], 'obs_metadata_error': row['metadata_error'],
               'obs_frame_id_overflow': row['frame_id_overflow'], 'uart_tx': 1,
               'raw_tx_req_id_bits': '0' * 32}
        events = []
        if row['rst_n']:
            events = [name for name, active in (('FRAME_F', row['frame_tick']),
                      ('ACCEPT_A', row['req_valid'] and row['req_ready']),
                      ('RESULT_TRANSFER', row['result_valid'] and row['result_ready']),
                      ('COMMIT', row['commit']), ('TX_ADOPT', row['tx_sample_valid'])) if active]
        if row['finish']:
            events.append('FINISH')
        originals.append({'schema': A_SCHEMA, 'capture_id': 'SYNTHETIC_R66_R07', 'origin': 'SYNTHETIC_SCHEMA_FIXTURE',
                          'source': {'raw_sha256': '1' * 64, 'reset_edges_sha256': '2' * 64, 'line': cycle + 1,
                                     'cycle': cycle, 'epoch': row['epoch'], 'time_ps': row['time_ps'],
                                     'sampling_phase': 'POSEDGE_PRE_NBA'}, 'fields': fields, 'extensions': ext,
                          'missing_reasons': {'tx_req_id': 'NO_KNOWN_VALID_TX_REQUEST_ID_RAW_BITS_RETAINED'} if row['tx_req_id'] is None else {},
                          'events': events})
    old = data['calendar']['transactions'][0]
    item = {'epoch': 0, 'req_id': 0, 'frame_ordinal': 1, 'state': 'ADOPTED_HELD'}
    for dst, src in {'F': 'frame', 'first_valid': 'first_valid', 'A': 'accept', 'result': 'result', 'commit': 'commit'}.items():
        item[dst] = {'cycle': old[src + '_cycle'], 'source_line': old[src + '_cycle'] + 1}
    item['tx_adoption'] = {'cycle': 1667, 'source_line': 1668}
    data['calendar'] = {'schema': CAL_SCHEMA, 'status': 'PENDING_FRAME_PLAN_ADMISSION', 'capture_id': 'SYNTHETIC_R66_R07',
                        'frame_plan_id': data['plan']['canonical_plan_id'], 'frames': [], 'transactions': [item],
                        'tx_samples': [{'kind': kind, 'epoch': 0, 'cycle': c, 'source_line': c + 1,
                                        'req_id': rid, 'consumes_pending': kind == 'ADOPTION'}
                                       for c, kind, rid in ((834, 'STARTUP', None), (1667, 'ADOPTION', 0), (2500, 'HOLD', 0))],
                        'raw_frame_cancels': [], 'business_cancels': [], 'legacy_d3_projection_status': 'PENDING_UNSUPPORTED_PROFILE',
                        'pending_reasons': ['PENDING_FRAME_PLAN_ADMISSION', 'PENDING_M1_ADVANCE'],
                        'real_pro_calendar_pass': False, 'board_release_allowed': False}
    data['binding']['trace_profile'] = A_SCHEMA
    data['originals'] = originals
    data['rows'] = adapt_rows(originals)


def move(data, kind, cycle):
    item = data['calendar']['transactions'][0]
    old = item[kind + '_cycle']
    fields = {'result': ('result_valid', 'result_ready'), 'commit': ('commit',), 'cancel': ('cancel',)}[kind]
    if old is not None:
        for field in fields:
            data['rows'][old][field] = 0
    for field in fields:
        data['rows'][cycle][field] = 1
    item[kind + '_cycle'], item[kind + '_source_line'] = cycle, data['rows'][cycle]['source_line']


def mutate(data, action):
    if action.startswith('late_'):
        move(data, action[5:], 1667)
    elif action == 'legal_cancel':
        item = data['calendar']['transactions'][0]
        item['commit_cycle'] = item['commit_source_line'] = None
        data['rows'][1666]['commit'] = 0
        move(data, 'cancel', 1666)
    elif action == 'delay_A':
        item = data['calendar']['transactions'][0]
        data['rows'][835]['req_ready'] = 0
        data['rows'][836].update(req_valid=1, req_ready=1, req_id=0)
        item['accept_cycle'], item['accept_source_line'] = 836, 10836
    elif action == 'line_wrong':
        data['calendar']['transactions'][0]['accept_source_line'] += 1
    elif action == 'missing_idle_frame':
        data['rows'][2500]['frame_tick'] = 0
    elif action == 'missing_finish':
        data['rows'][-1]['finish'] = 0
    elif action == 'shift_plan_and_trace':
        data['plan']['epochs'][0]['cycles'] = [835, 1668, 2501]
        keys = ('schema', 'formula', 'rules_sha256', 'input_sha256', 'source_identities', 'parameters', 'epochs', 'finish')
        sha = digest(canonical({k: data['plan'][k] for k in keys}))
        data['plan'].update(canonical_identity_sha256=sha, canonical_plan_id='sha256:' + sha)
        for a, b in ((834, 835), (1667, 1668), (2500, 2501)):
            data['rows'][a]['frame_tick'], data['rows'][b]['frame_tick'] = 0, 1
    elif action.startswith('real_'):
        data['binding'].update(mode='REAL_PUBLIC_TRACE', approved=True, authenticated=True, executor_pid=123,
                               trace_authority='REAL_PUBLIC_TRACE', registry_id='SELF_REPORTED_' + action)
    elif action == 'startup_numeric_zero':
        data['rows'][834]['tx_req_id'] = 0
    elif action == 'metadata_unknown':
        data['rows'][1667]['tx_metadata_valid'] = 0
    elif action == 'clip_swap':
        data['rows'][2500]['tx_clip_mask'] = 2
    elif action == 'metadata_error':
        data['rows'][1667]['metadata_error'] = 1
    elif action == 'overflow':
        data['rows'][2500]['frame_id_overflow'] = 1
    elif action == 'unknown_profile':
        data['binding']['trace_profile'] = 'FUTURE_UNKNOWN'
    elif action == 'missing_clip_oracle':
        del data['oracle']['records'][0]['clip_mask']
    elif action == 'legacy_plus_c3':
        data['binding']['trace_profile'] = 'LEGACY_R06_FLAT_V1'
    elif action.startswith('native'):
        native(data)
        if action == 'native_unknown_M1':
            for row in data['originals']:
                row['fields']['advance_mask'] = None
                row['missing_reasons']['advance_mask'] = 'NOT_PUBLIC_PENDING_M1'
            data['rows'] = adapt_rows(data['originals'])
        elif action == 'native_null_reset':
            data['originals'][0]['fields']['rst_n'] = None
            data['rows'] = adapt_rows(data['originals'])
        elif action == 'native_changed_event':
            data['originals'][2500]['events'].remove('TX_ADOPT')
            data['rows'] = adapt_rows(data['originals'])
    elif action == 'release_zero':
        inputs = json.loads(data['inputs'])
        inputs['epochs'][0]['release_cycle'] = 0
        data['inputs'] = canonical(inputs).decode('utf-8')
        data['plan']['input_sha256'] = digest(data['inputs'].encode('utf-8'))
        data['plan']['epochs'][0].update(release_cycle=0, cycles=[833, 1666, 2499])
        keys = ('schema', 'formula', 'rules_sha256', 'input_sha256', 'source_identities', 'parameters', 'epochs', 'finish')
        sha = digest(canonical({k: data['plan'][k] for k in keys}))
        data['plan'].update(canonical_identity_sha256=sha, canonical_plan_id='sha256:' + sha)
        data['rows'][0]['rst_n'] = 1
        for a, b in ((834, 833), (1667, 1666), (2500, 2499)):
            data['rows'][a]['frame_tick'], data['rows'][b]['frame_tick'] = 0, 1


CASES = [
    ('valid_F834_A835_ID0_null_HOLD', 'none', 'BOUNDARY_OK'),
    ('late_result_F833_A832', 'late_result', 'FRAME_BUDGET_DEADLINE'),
    ('late_commit_F833_A832', 'late_commit', 'FRAME_BUDGET_DEADLINE'),
    ('late_cancel_F833_A832', 'late_cancel', 'FRAME_BUDGET_DEADLINE'),
    ('legal_cancel_F832', 'legal_cancel', 'BOUNDARY_OK'),
    ('delayed_accept_hold_request', 'delay_A', 'BOUNDARY_OK'),
    ('original_source_line_mismatch', 'line_wrong', 'FA_SOURCE_LINE'),
    ('full_window_idle_frame_missing', 'missing_idle_frame', 'FRAME_PLAN_WHOLE_WINDOW'),
    ('unique_plan_shift_not_input_shift', 'shift_plan_and_trace', 'FRAME_PLAN_CLOSED_FORM'),
    ('finish_not_eof', 'missing_finish', 'FRAME_ACTUAL_FINISH'),
    ('real_with_synthetic_mixture', 'real_mixed', 'PENDING_SOURCE_PROVENANCE'),
    ('real_self_approved_pid_registry', 'real_claims', 'PENDING_SOURCE_PROVENANCE'),
    ('invalid_startup_numeric0', 'startup_numeric_zero', 'C3_INVALID_ID_MUST_BE_NULL'),
    ('metadata_not_valid', 'metadata_unknown', 'PENDING_C3_TX_METADATA'),
    ('dual_clip01_to10_sameOR', 'clip_swap', 'C3_TX_CLIP_MASK'),
    ('metadata_error', 'metadata_error', 'C3_METADATA_ERROR'),
    ('frame_id_overflow', 'overflow', 'PENDING_C3_FRAME_OVERFLOW'),
    ('unknown_profile', 'unknown_profile', 'PENDING_UNSUPPORTED_PROFILE'),
    ('oracle_missing_dual_clip', 'missing_clip_oracle', 'PENDING_PCM_ORACLE_C3_PROFILE'),
    ('legacy_cannot_drop_extensions', 'legacy_plus_c3', 'PENDING_UNSUPPORTED_PROFILE'),
    ('actual_A_R65_contract_mechanics', 'native', 'BOUNDARY_OK_NATIVE_PENDING'),
    ('actual_A_missing_M1_preserved', 'native_unknown_M1', 'BOUNDARY_OK_NATIVE_PENDING'),
    ('actual_A_null_reset', 'native_null_reset', 'PENDING_UNSUPPORTED_PROFILE'),
    ('actual_A_HOLD_event_is_sample', 'native_changed_event', 'R7A_EVENT_FLAGS'),
    ('global_zero_first_functional_n1', 'release_zero', 'PLAN_OK'),
    ('flat_CLI_dead_pins_fail_closed', 'none', 'PIN_BCLK_STALLED_OR_MISSING_EDGE'),
    ('actual_A_R65_CLI_retains_pending', 'native', 'PENDING_TX_SELECTION_PLAN'),
    ('real_CLI_before_missing_paths', 'real_claims', 'PENDING_SOURCE_PROVENANCE'),
]


def cli_case(data, folder, real=False):
    paths = {k: folder / (k + ('.jsonl' if k == 'trace' else '.json'))
             for k in ('binding', 'calendar', 'frame_plan', 'oracle', 'trace', 'frame_input', 'frame_rules')}
    if not real:
        for role, key in (('calendar', 'calendar'), ('frame_plan', 'plan'), ('oracle', 'oracle')):
            write(paths[role], data[key])
        paths['frame_input'].write_bytes(data['inputs'].encode('utf-8'))
        paths['frame_rules'].write_bytes(RULES.read_bytes())
        trace = data.get('originals', [{k: v for k, v in r.items() if k != '__line'} for r in data['rows']])
        with paths['trace'].open('x', encoding='utf-8', newline='\n') as stream:
            for row in trace:
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        data['binding']['inputs_sha256'] = {k: core.sha256(v) for k, v in paths.items() if k != 'binding'}
    write(paths['binding'], data['binding'])
    code, report = checker.run_files(paths, core.sha256(paths['binding']), DECODER, DECODER_SHA, folder / 'CLI_REPORT.json')
    if data['binding']['trace_profile'] == A_SCHEMA and not real:
        assert report['crosspack_preservation']['r7a_rows'] == data['originals']
        assert report['crosspack_preservation']['r65_calendar'] == data['calendar']
        assert report['frame_first_valid_accept_ledger'][0]['frame_cycle'] == 834
        assert report['frame_first_valid_accept_ledger'][0]['accept_cycle'] == 835
        assert 'PENDING_M1_ADVANCE' in report['pending_reasons']
    assert report['real_pro_tx_pass'] is False and report['board_release_allowed'] is False
    return report.get('error') if code == 2 else report['status']


def main():
    output = Path(sys.argv[1])
    output.mkdir(exist_ok=False, parents=True)
    write(output / 'TARGETS_BEFORE_CASES.json', {'cases': CASES, 'old_twenty_cases_run': False,
          'R63_R65_producers_imported_or_executed': False, 'HDL_EDA_hardware_calls': 0})
    pristine = base()
    write(output / 'SYNTHETIC_BASE_INPUT.json', pristine)
    results = []
    for index, (name, action, expected) in enumerate(CASES, 1):
        folder = output / ('%02d_' % index + name)
        folder.mkdir()
        data = copy.deepcopy(pristine)
        # Case mutation itself is frozen in selftest.py. No production plan is
        # generated: explicit hand fixture cycles only, plus tamper cases.
        write(folder / 'EXPECTATION_BEFORE_CALL.json', {'action': action, 'expected': expected})
        try:
            mutate(data, action)
            write(folder / 'INPUT.json', data)
            if index >= 26:
                actual = cli_case(data, folder, real=index == 28)
            elif action == 'release_zero':
                verify_plan(data['plan'], data['inputs'].encode('utf-8'), RULES.read_bytes(), data['rows'])
                actual = 'PLAN_OK'
            else:
                prepared = checker.prepare(data['binding'], data['calendar'], data['plan'], data['oracle'],
                                           data['rows'], data['inputs'].encode('utf-8'), RULES.read_bytes())
                profile, frame, cal, ledger, pending = prepared
                assert ledger[0]['frame_cycle'] == 834 and ledger[0]['first_valid_cycle'] == 835
                assert ledger[0]['accept_cycle'] == (836 if action == 'delay_A' else 835)
                assert ledger[0]['ages']['result']['t_minus_F'] == 366
                assert cal['transactions'][0]['request_cycle'] == ledger[0]['accept_cycle']
                if action.startswith('native'):
                    assert 'PENDING_TX_SELECTION_PLAN' in pending
                    assert data['originals'][834]['fields']['tx_req_id'] is None
                    assert 'TX_ADOPT' in data['originals'][2500]['events']
                    actual = 'BOUNDARY_OK_NATIVE_PENDING'
                else:
                    assert not pending
                    actual = 'BOUNDARY_OK'
                write(folder / 'BOUNDARY_LEDGER.json', {'ledger': ledger, 'pending': pending,
                                                       'serial_not_run': True, 'real_pro_tx_pass': False})
        except (core.Pending, core.Reject) as error:
            # Retain the actual fully materialized case even on adapter failure.
            if not (folder / 'INPUT.json').exists():
                write(folder / 'INPUT.json', data)
            actual = error.code
            write(folder / 'DIAGNOSTIC.json', {'code': error.code, 'detail': error.detail})
        ok = actual == expected
        item = {'name': name, 'action': action, 'expected': expected, 'actual': actual, 'pass': ok,
                'input_sha256': hashlib.sha256((folder / 'INPUT.json').read_bytes()).hexdigest()}
        write(folder / 'RESULT.json', item)
        print(json.dumps(item), flush=True)
        results.append(item)
        if not ok:
            break
    write(output / 'RESULT.json', {'cases': results, 'passed': sum(i['pass'] for i in results),
          'expected_cases': len(CASES), 'all_pass': len(results) == len(CASES) and all(i['pass'] for i in results),
          'scope': 'NEW_SYNTHETIC_BOUNDARIES_ONLY_NOT_FULL_SERIAL_REGRESSION', 'real_pro_tx_pass': False})
    return 0 if len(results) == len(CASES) and all(i['pass'] for i in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
