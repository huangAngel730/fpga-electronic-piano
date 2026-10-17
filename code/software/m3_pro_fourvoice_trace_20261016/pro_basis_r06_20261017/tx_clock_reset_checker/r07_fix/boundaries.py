"""R6-6 fixes: read the R6-5 unique plan, independently VERIFY its formula."""
import hashlib
import json

from serial_core import Pending, Reject

RULES_SHA = '3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560'
C3_FIELDS = {'tx_req_id_valid', 'tx_metadata_valid', 'tx_clip_mask', 'tx_clip_any',
             'metadata_error', 'frame_id_overflow'}
LINKS = ('frame', 'first_valid', 'accept', 'result', 'commit', 'cancel')


def need(ok, code, detail=''):
    if not ok:
        raise Reject(code, str(detail))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


def provenance(binding):
    # There is currently NO trusted executable M2 admission/authority registry.
    # R7-D also explicitly does not authenticate a producer. Never accept a
    # caller-supplied string, boolean, SHA or synthetic mixture as admission.
    if binding.get('mode') == 'REAL_PUBLIC_TRACE':
        raise Pending('PENDING_SOURCE_PROVENANCE', 'Trusted M2 source/capture/tool/finish admission is not integrated')
    if binding.get('mode') != 'SYNTHETIC_SELFTEST_ONLY':
        raise Pending('PENDING_SOURCE_PROVENANCE', 'No admissible synthetic or trusted real scope')


def verify_plan(plan, input_bytes, rules_bytes, rows):
    if plan.get('schema') != 'M3_R06_UNIQUE_FRAME_PLAN_V1':
        raise Pending('PENDING_FRAME_PLAN', 'Read R6-5 UNIQUE_FRAME_PLAN; old cycles/frame_cycles views alone are insufficient')
    rules, inputs = json.loads(rules_bytes), json.loads(input_bytes)
    need(digest(rules_bytes) == RULES_SHA and plan.get('rules_sha256') == RULES_SHA, 'FRAME_RULES_SHA')
    if inputs.get('schema') != 'M3_R06_FRAME_PLAN_GENERATOR_INPUT_V1' or inputs.get('status') != 'FROZEN_INDEPENDENT_INPUT':
        raise Pending('PENDING_FRAME_PLAN', 'Independent frozen input missing')
    need(inputs.get('independent_of_observed_trace') is True and plan.get('independent_of_trace') is True,
         'FRAME_PLAN_TRACE_DERIVED')
    need(not any(k in inputs for k in ('trace', 'trace_path', 'observed_frames', 'observed_frame_rows')), 'FRAME_PLAN_TRACE_DERIVED')
    need(plan.get('input_sha256') == digest(input_bytes) and plan.get('source_identities') == inputs.get('source_identities')
         and bool(inputs.get('source_identities')), 'FRAME_PLAN_INPUT_IDENTITY')
    parameters = {k: rules[k] for k in ('acc_bits', 'phase_step', 'core_hz_candidate',
                                      'half_bclk_toggles_per_frame', 'initial_state')}
    need(parameters == {'acc_bits': 32, 'phase_step': 659706977, 'core_hz_candidate': 40000000,
                        'half_bclk_toggles_per_frame': 128, 'initial_state': {'accumulator': 0, 'bclk': 0, 'slot_count': 0}}, 'FRAME_PARAMETERS')
    need(plan.get('parameters') == parameters and plan.get('formula') == rules['formula'], 'FRAME_PLAN_FORMULA')
    payload_keys = ('schema', 'formula', 'rules_sha256', 'input_sha256', 'source_identities', 'parameters', 'epochs', 'finish')
    payload = {key: plan.get(key) for key in payload_keys}
    identity = digest(canonical(payload))
    need(plan.get('canonical_identity_sha256') == identity and plan.get('canonical_plan_id') == 'sha256:' + identity, 'FRAME_PLAN_CANONICAL_ID')
    need(plan.get('authority') == 'CANDIDATE_INDEPENDENT_PLAN_NOT_M2_ADMITTED' and plan.get('real_authority_claimed') is False,
         'FRAME_PLAN_AUTHORITY_DECLARATION')
    need(type(inputs.get('epochs')) is list and inputs['epochs'] and len(plan.get('epochs', [])) == len(inputs['epochs']), 'FRAME_PLAN_EPOCHS')
    by_cycle = {row['cycle']: row for row in rows}
    need(len(by_cycle) == len(rows), 'DUPLICATE_CYCLE')
    for index, row in enumerate(rows):
        need(type(row.get('cycle')) is int and type(row.get('epoch')) is int and row.get('__line') == index + 1, 'TRACE_SOURCE_COORDINATE')
        if index:
            need(row['cycle'] == rows[index - 1]['cycle'] + 1 and row['time_ps'] - rows[index - 1]['time_ps'] == 25000,
                 'TRACE_CONTINUITY')
    previous_stop = None
    for index, (source, epoch) in enumerate(zip(inputs['epochs'], plan['epochs'])):
        need(source.get('epoch') == epoch.get('epoch') == index, 'FRAME_EPOCH_ID')
        for key in ('window_kind', 'reset_assert_cycle', 'release_cycle', 'stop_cycle'):
            need(source.get(key) == epoch.get(key), 'FRAME_WINDOW_BINDING', key)
        start, stop, release = epoch['reset_assert_cycle'], epoch['stop_cycle'], epoch['release_cycle']
        need(type(start) is int and type(stop) is int and 0 <= start <= stop, 'FRAME_WINDOW_ORDER')
        if previous_stop is not None:
            need(start == previous_stop + 1, 'FRAME_WINDOW_GAP')
        previous_stop = stop
        if epoch['window_kind'] == 'ACTIVE':
            if type(release) is not int:
                raise Pending('PENDING_RESET_PHASE')
            need(start <= release <= stop, 'FRAME_RELEASE_WINDOW')
            expected, k = [], 1
            # Recompute only to VERIFY the one received plan; never emit a plan.
            while True:
                n = (128 * k * (1 << 32) + 659706977 - 1) // 659706977
                frame = release + n - 1
                if frame > stop:
                    break
                expected.append(frame)
                k += 1
            if release > rows[0]['cycle']:
                need(release - 1 in by_cycle and by_cycle[release - 1]['rst_n'] == 0, 'FRAME_RELEASE_PRE_RESET')
            else:
                need(release == rows[0]['cycle'] == 0, 'FRAME_RELEASE_PRE_RESET')
        else:
            need(epoch['window_kind'] == 'RESET_ONLY' and release is None, 'FRAME_RESET_ONLY')
            expected = []
        need(epoch.get('cycles') == expected, 'FRAME_PLAN_CLOSED_FORM')
        window = [by_cycle.get(cycle) for cycle in range(start, stop + 1)]
        need(all(row is not None and row['epoch'] == index for row in window), 'FRAME_PLAN_WINDOW_COVERAGE')
        for row in window:
            need(row['rst_n'] == int(release is not None and row['cycle'] >= release), 'FRAME_RESET_PHASE')
        observed = [row['cycle'] for row in window if row['frame_tick']]
        need(observed == expected, 'FRAME_PLAN_WHOLE_WINDOW', {'expected': expected, 'observed': observed})
    need(plan.get('finish') == inputs.get('finish') == {'epoch': len(plan['epochs']) - 1, 'cycle': previous_stop}, 'FRAME_FINISH_PLAN')
    finishes = [{'epoch': row['epoch'], 'cycle': row['cycle']} for row in rows if row['finish']]
    need(finishes == [plan['finish']] and rows[-1]['cycle'] == previous_stop, 'FRAME_ACTUAL_FINISH')
    need(all(row['rst_n'] == 0 and not row['frame_tick'] for row in rows if row['cycle'] < plan['epochs'][0]['reset_assert_cycle']),
         'UNPLANNED_PREFIX')
    return {'schema': 'M3_R06_TX_FRAME_PLAN_V1', 'authority': 'SYNTHETIC_INDEPENDENT_PLAN',
            'independent_of_trace': True, 'epochs': [{'epoch': item['epoch'], 'cycles': item['cycles']} for item in plan['epochs']],
            'finish': plan['finish']}


def validate_transactions(calendar, plan, rows):
    if calendar.get('schema') != 'M3_R07_FA_TRANSACTION_CALENDAR_V1':
        raise Pending('PENDING_UNSUPPORTED_PROFILE', 'Unsupported calendar schema retained')
    need((calendar.get('authority') == 'SYNTHETIC_INDEPENDENT_CALENDAR' and calendar.get('independent_of_trace') is True)
         or (calendar.get('native_observed_only') is True and calendar.get('authority') == 'OBSERVED_R65_REPORT_NOT_AUTHORITY'
             and calendar.get('independent_of_trace') is False),
         'FA_CALENDAR_AUTHORITY')
    by_cycle = {row['cycle']: row for row in rows}
    frames = {item['epoch']: item['cycles'] for item in plan['epochs']}
    converted, report, seen = [], [], set()
    required = {'epoch', 'req_id'} | {f'{name}_cycle' for name in LINKS} | {f'{name}_source_line' for name in LINKS}
    for item in calendar.get('transactions', []):
        need(set(item) == required, 'FA_TRANSACTION_FIELDS')
        key = item['epoch'], item['req_id']
        if any(v is None or type(v) is str for v in key):
            raise Pending('PENDING_FA_LINK', 'Unknown epoch/request id')
        need(key not in seen and all(type(v) is int and v >= 0 for v in key), 'FA_TRANSACTION_ID')
        seen.add(key)
        F, V, A = [item[name + '_cycle'] for name in ('frame', 'first_valid', 'accept')]
        need(all(type(c) is int for c in (F, V, A)) and F <= V <= A, 'FA_ORDER')
        epoch_frames = frames.get(item['epoch'], [])
        need(F in epoch_frames, 'FA_ORIGIN_FRAME')
        next_frame = next((c for c in epoch_frames if c > F), None)
        if next_frame is None:
            raise Pending('PENDING_FRAME_PLAN_NEXT_BOUNDARY')
        need(A < F + 833 and A < next_frame, 'FA_ACCEPT_DEADLINE')
        for name in LINKS:
            cycle, line = item[name + '_cycle'], item[name + '_source_line']
            if cycle is None:
                need(line is None and name in ('result', 'commit', 'cancel'), 'FA_NULL_LINK')
                continue
            row = by_cycle.get(cycle)
            # Reset cleanup belongs to the next epoch; all other links stay local.
            correct_epoch = row is not None and (row['epoch'] == key[0] or (name == 'cancel' and not row['rst_n'] and row['epoch'] == key[0] + 1))
            need(correct_epoch and row.get('source_line', row['__line']) == line, 'FA_SOURCE_LINE', name)
            if name == 'frame':
                need(row['frame_tick'] == 1, 'FA_FRAME_LINK')
            elif name == 'first_valid':
                need(row['req_valid'] == 1 and row['req_id'] == key[1], 'FA_FIRST_VALID_LINK')
                need(not any(r['rst_n'] and r['epoch'] == key[0] and F < r['cycle'] < V and r['req_valid'] and r['req_id'] == key[1]
                             for r in rows), 'FA_NOT_FIRST_VALID')
            elif name == 'accept':
                need(row['req_valid'] == row['req_ready'] == 1 and row['req_id'] == key[1], 'FA_ACCEPT_LINK')
                need(all(by_cycle[c]['req_valid'] == 1 and by_cycle[c]['req_id'] == key[1]
                         and (c == A or by_cycle[c]['req_ready'] == 0) for c in range(V, A + 1)), 'FA_REQUEST_HOLD')
            elif name in ('result', 'commit', 'cancel'):
                need(type(cycle) is int and cycle >= A and cycle - F < 833 and cycle < next_frame,
                     'FRAME_BUDGET_DEADLINE', {'epoch': key[0], 'id': key[1], 'kind': name, 'F': F, 'A': A, 't': cycle, 't-F': cycle - F, 't-A': cycle - A})
                if name == 'result':
                    need(row['result_valid'] == row['result_ready'] == 1 and row['result_id'] == key[1], 'FA_RESULT_LINK')
                elif name == 'commit':
                    need(row['commit'] == 1 and row['commit_id'] == key[1], 'FA_COMMIT_LINK')
                else:
                    need(row['cancel'] == 1 or not row['rst_n'], 'FA_CANCEL_LINK')
        result, commit, cancel = [item[name + '_cycle'] for name in ('result', 'commit', 'cancel')]
        need((cancel is not None) != (commit is not None), 'FA_DISPOSITION')
        need(commit is None or (result is not None and A <= result <= commit), 'FA_RESULT_COMMIT_ORDER')
        ages = {name: {'t_minus_F': item[name + '_cycle'] - F, 't_minus_A': item[name + '_cycle'] - A}
                for name in ('result', 'commit', 'cancel') if item[name + '_cycle'] is not None}
        report.append({**item, 'ages': ages, 'next_independent_frame': next_frame})
        converted.append({'epoch': key[0], 'req_id': key[1], 'request_cycle': A,
                          'result_cycle': result, 'commit_cycle': commit, 'cancel_cycle': cancel})
    return {**calendar, 'schema': 'M3_R06_TX_TRANSACTION_CALENDAR_V1', 'transactions': converted}, report


def validate_profile(binding, rows, oracle):
    profile = binding.get('trace_profile')
    if profile not in ('LEGACY_R06_FLAT_V1', 'R06C3_TX_FLAT_V1'):
        raise Pending('PENDING_UNSUPPORTED_PROFILE', str(profile))
    golden = {(item['epoch'], item['req_id']): item for item in oracle.get('records', [])}
    held = {}
    if profile == 'R06C3_TX_FLAT_V1':
        for item in oracle.get('records', []):
            if 'clip_mask' not in item:
                raise Pending('PENDING_PCM_ORACLE_C3_PROFILE')
            need(type(item['clip_mask']) is int and 0 <= item['clip_mask'] <= 3
                 and item['clip'] == int(bool(item['clip_mask'])), 'C3_ORACLE_CLIP')
    for row in rows:
        if profile == 'LEGACY_R06_FLAT_V1':
            if C3_FIELDS & set(row):
                raise Pending('PENDING_UNSUPPORTED_PROFILE', 'C3 extensions cannot be dropped into legacy')
            continue
        if not C3_FIELDS <= set(row):
            raise Pending('PENDING_UNSUPPORTED_PROFILE', 'Missing C3 extension fields')
        for field in ('tx_sample_valid', 'tx_clip', 'tx_startup_zero', 'tx_hold', 'tx_clip_mask'):
            if row[field] is None or type(row[field]) is str:
                raise Pending('PENDING_UNSUPPORTED_PROFILE', 'Unknown TX field:' + field)
        for field in C3_FIELDS - {'tx_clip_mask'}:
            if row[field] is None or type(row[field]) is str:
                raise Pending('PENDING_UNSUPPORTED_PROFILE', 'Unknown C3 flag:' + field)
            need(type(row[field]) is int and row[field] in (0, 1), 'C3_FLAG', field)
        need(type(row['tx_clip_mask']) is int and 0 <= row['tx_clip_mask'] <= 3, 'C3_CLIP_MASK')
        need(row['tx_clip_any'] == row['tx_clip'] == int(bool(row['tx_clip_mask'])), 'C3_CLIP_OR')
        need(not row['metadata_error'], 'C3_METADATA_ERROR')
        if row['frame_id_overflow']:
            raise Pending('PENDING_C3_FRAME_OVERFLOW', 'Labels unusable; no data discarded')
        if row['tx_req_id_valid']:
            need(type(row['tx_req_id']) is int and 0 <= row['tx_req_id'] <= 0xffffffff, 'C3_REQUEST_ID')
        else:
            need(row['tx_req_id'] is None, 'C3_INVALID_ID_MUST_BE_NULL')
        if row['tx_sample_valid']:
            if not row['tx_metadata_valid']:
                raise Pending('PENDING_C3_TX_METADATA')
            need(bool(row['tx_req_id_valid']) != bool(row['tx_startup_zero']), 'C3_STARTUP_VALIDITY')
            epoch = row['epoch']
            if row['tx_startup_zero']:
                need(not row['tx_hold'] and row['tx_clip_mask'] == 0, 'C3_STARTUP_CLIP_OR_HOLD')
                held.pop(epoch, None)
            else:
                key = epoch, row['tx_req_id']
                if key not in golden:
                    raise Pending('PENDING_PCM_ORACLE_C3_PROFILE')
                need(row['tx_clip_mask'] == golden[key]['clip_mask'], 'C3_TX_CLIP_MASK')
                tuple_value = (key[1], row['tx_clip_mask'])
                if row['tx_hold']:
                    need(held.get(epoch) == tuple_value, 'C3_HOLD_CLIP_ID')
                held[epoch] = tuple_value
    return profile
