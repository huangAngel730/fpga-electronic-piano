"""Streaming C9 public TX/pin checks. File consistency never authenticates RTL.

No file reads or candidate loading at import. Coordinator alone executes this
new successor; old consumers, PinDecoder and FRAME_PLAN producer stay frozen.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
SOFT = ROOT / 'code/software/m3_pro_fourvoice_trace_20261016'
COMMON = SOFT / 'pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py'
COMMON_SHA = '55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca'
DECODER = ROOT / 'code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py'
DECODER_SHA = 'da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb'
LEGACY13 = SOFT / 'pro_basis_r08_20261017/i2s_serial_compare/r08c13_serial.py'
LEGACY13_SHA = '58b08fd25d6d52d1684a421d1843a94ee19cd3753badbb4a43587100c1b01123'
LEGACY66 = SOFT / 'pro_basis_r06_20261017/tx_clock_reset_checker/r07_fix/serial_core.py'
LEGACY66_SHA = 'd7fcbe2008ba87e82835faaecfc67ef9b9e864533fc82ad12b2a9517f6242a76'
PLAN_CHECKER = SOFT / 'pro_basis_r06_20261017/event_calendar/r07_fix/calendar_r07_fix_candidate.py'
PLAN_CHECKER_SHA = '9af7022b0a228e0f8e180fd6a3c58646757cb407dfb132726c8ae0ace28413a5'
ADDED_FIELDS = ('tx_metadata_valid tx_req_id_valid tx_clip_mask metadata_error frame_id_overflow '
                'apply_kind apply_mask router_apply_seq router_apply_seq_valid config_take '
                'upstream_clip_mask effect_clip_mask feedback_clip_mask').split()
MAX_INPUT = 64 * 1024**3
MAX_OUTPUT = 16 * 1024**3
MAX_FRAMES = 200000
_COMMON = None


def shared():
    """Bootstrap only the pinned coordinator helper, never a pyc loader."""
    global _COMMON
    raw = COMMON.read_bytes()
    if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
        raise ValueError('COMMON_SOURCE_SHA')
    if _COMMON is None:
        module = ModuleType('_c9_serial_completion_common')
        module.__file__ = str(COMMON)
        exec(compile(raw, str(COMMON), 'exec', dont_inherit=True), module.__dict__)
        _COMMON = module
    return _COMMON


def resolve_file(value, c):
    return c.checked_descriptor(value, allow_external=True) if isinstance(value, dict) else c.no_alias(value)


class JsonLines:
    def __init__(self, path, budget):
        self.stream = Path(path).open('xb')
        self.budget = budget

    def emit(self, value):
        raw = (json.dumps(value, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False) + '\n').encode('utf-8')
        self.budget[0] += len(raw)
        if self.budget[0] > MAX_OUTPUT:
            raise ValueError('SERIAL_OUTPUT_BOUND')
        self.stream.write(raw)

    def close(self):
        self.stream.close()


def analyze_files(public_rows_path, frame_plan_path, output_dir, expected_scenario_ref=None):
    c = shared()
    public = resolve_file(public_rows_path, c)
    plan_path = resolve_file(frame_plan_path, c)
    before = {'public_rows': c.artifact(public), 'frame_plan': c.artifact(plan_path)}
    expected_path = None
    if expected_scenario_ref is not None:
        expected_path = resolve_file(expected_scenario_ref, c)
        before['expected_scenario'] = c.artifact(expected_path)
    c.require(before['public_rows']['bytes'] <= MAX_INPUT, 'SERIAL_INPUT_BOUND')
    out = c.output_directory(output_dir)
    c.write_json(out / 'INPUTS.json', before)
    budget, writers = [0], {}
    names = {'serial_frames': 'SERIAL_FRAMES.jsonl', 'serial_halves': 'SERIAL_HALVES.jsonl',
             'row_index': 'ROW_INDEX.jsonl', 'transactions': 'TRANSACTIONS.jsonl'}
    try:
        old13 = c.load_source(LEGACY13, LEGACY13_SHA)
        old66 = c.load_source(LEGACY66, LEGACY66_SHA)
        decoder = c.load_source(DECODER, DECODER_SHA)
        verifier = c.load_source(PLAN_CHECKER, PLAN_CHECKER_SHA)
        plan = c.read_json(plan_path)  # Bounded metadata, never the public window.
        frame_cycles, window_ends = verifier._expected_cycles(plan)
        c.require(sum(map(len, frame_cycles.values())) <= MAX_FRAMES, 'FRAME_METADATA_BOUND')
        fields74 = set(old66.CANONICAL_FIELDS) | set(ADDED_FIELDS)
        c.require(len(fields74) == 74, 'LEGACY_C9_FIELD_BINDING')
        expectations = None
        if expected_path is not None:
            scenario = c.read_json(expected_path)
            c.require(scenario.get('schema') == 'M3_R08_TX_SCENARIO_V1'
                      and scenario.get('FRAME_PLAN_generated') is False, 'TX_SCENARIO_SCHEMA')
            expectations = {(r['epoch'], r['cycle']): r for r in scenario['rows']}
            c.require(len(expectations) == len(scenario['rows']), 'DUPLICATE_TX_EXPECTATION')
            c.require(len(expectations) <= MAX_FRAMES, 'TX_EXPECTATION_BOUND')
            for epoch, cycle in expectations:
                c.require(type(epoch) is int and type(cycle) is int and epoch in frame_cycles,
                          'TX_EXPECTATION_COORDINATE')
                frames = frame_cycles[epoch]
                index = bisect_left(frames, cycle)
                c.require(index < len(frames) and frames[index] == cycle,
                          'TX_EXPECTATION_OUTSIDE_FRAME_PLAN')
        writers = {key: JsonLines(out / name, budget) for key, name in names.items()}
        ledger, seen, outstanding, pending, held, waiting = {}, set(), None, None, None, None
        pins = decoder.PinDecoder(ledger)
        counts = {'rows': 0, 'frames': 0, 'halves': 0, 'FRAME_F': 0, 'accepted': 0,
                  'new_tx': 0, 'hold_tx': 0, 'startup_tx': 0, 'result': 0, 'commit': 0,
                  'unknown_rows': 0, 'reset_truncations': 0}
        unknown = set()
        policy = {'PENDING_REAL_EXECUTION_AUTHORITY', 'PENDING_M1_PCM_GOLDEN',
                  'PENDING_INDEPENDENT_APPLY_MAPPING', 'PENDING_AUDIO_STABLE_POLICY'}
        if expectations is None:
            policy.add('PENDING_TX_SELECTION_PLAN')
        indices = {epoch: 0 for epoch in frame_cycles}
        previous = capture_id = raw_sha = None
        reset_sha = capture_origin = None
        finished = False
        last_frame = None
        previous_frame = None
        gaps = []
        decoder_enabled = True
        result_hold = None
        tx_state_known = True
        chain_unknown = False
        last_finish = None
        public_digest, public_bytes = hashlib.sha256(), 0

        def public_rows():
            nonlocal public_bytes
            with public.open('rb') as stream:
                for line_number in range(1, MAX_INPUT + 1):
                    raw = stream.readline(c.MAX_JSON_LINE + 1)
                    if not raw:
                        return
                    c.require(len(raw) <= c.MAX_JSON_LINE, 'JSONL_LINE_BOUND:' + str(line_number))
                    c.require(bool(raw.strip()), 'EMPTY_JSONL_LINE:' + str(line_number))
                    public_bytes += len(raw)
                    c.require(public_bytes <= MAX_INPUT, 'SERIAL_INPUT_BOUND')
                    public_digest.update(raw)
                    value = c.loads(raw)
                    c.require(isinstance(value, dict), 'JSONL_ROW_NOT_OBJECT:' + str(line_number))
                    yield value

        def bit(row, name):
            value = row[name]
            if type(value) is not int:
                unknown.add('UNKNOWN_' + name.upper())
                return None
            c.require(value in (0, 1), 'BIT_RANGE:' + name)
            return value

        def integer(row, name, width=32, signed=False):
            value = row[name]
            if type(value) is not int:
                unknown.add('UNKNOWN_' + name.upper())
                return None
            low = -(1 << (width - 1)) if signed else 0
            high = (1 << (width - int(signed))) - 1
            c.require(low <= value <= high, 'INTEGER_RANGE:' + name)
            return value

        def complete_values(values):
            return all(value is not None for value in values)

        def deadline(entry, at, kind):
            frames = frame_cycles[entry['epoch']]
            index = bisect_right(frames, entry['F'])
            next_f = frames[index] if index < len(frames) else None
            c.require(at >= entry['A'] and at - entry['F'] < 833
                      and (next_f is None or at < next_f), 'FRAME_BUDGET_DEADLINE:' + kind)

        for input_line, original in enumerate(public_rows(), 1):
            c.require(not finished, 'ROW_AFTER_FINISH')
            c.require(original.get('schema') == 'M3_R7A_C9_PUBLIC_ROW_V1', 'C9_PUBLIC_SCHEMA')
            row, source = original.get('fields', {}), original.get('source', {})
            c.require(set(row) == fields74, 'CANONICAL_FIELDS_74_NO_FILL')
            cycle, epoch, at = row['cycle'], row['epoch'], source.get('time_ps')
            c.require(type(cycle) is int and cycle >= 0 and type(at) is int and at >= 0,
                      'SOURCE_TIME_COORDINATE')
            c.require(source.get('cycle') == cycle and source.get('epoch') == epoch
                      and source.get('line') == input_line, 'SOURCE_LINE_BINDING')
            c.require(cycle == input_line - 1, 'C9_ZERO_BASED_FULL_WINDOW')
            if previous is not None:
                c.require(cycle == previous['cycle'] + 1 and at == previous['time_ps'] + 25000,
                          'SERIAL_TIME_GAP')
            else:
                capture_id, raw_sha = original.get('capture_id'), source.get('raw_sha256')
                reset_sha, capture_origin = source.get('reset_edges_sha256'), original.get('origin')
                c.require(isinstance(capture_id, str) and capture_id and isinstance(raw_sha, str)
                          and len(raw_sha) == 64, 'CAPTURE_SOURCE_BINDING')
            c.require(original.get('capture_id') == capture_id and source.get('raw_sha256') == raw_sha,
                      'CAPTURE_SOURCE_CHANGED')
            c.require(source.get('reset_edges_sha256') == reset_sha and original.get('origin') == capture_origin,
                      'CAPTURE_RESET_ORIGIN_CHANGED')
            previous = {'cycle': cycle, 'time_ps': at}
            counts['rows'] += 1
            coordinate = {'input_line': input_line, 'source_line': source['line'],
                          'cycle': cycle, 'epoch': epoch, 'time_ps': at}
            writers['row_index'].emit({**coordinate, 'source_raw_sha256': raw_sha,
                                       'canonical_input': before['public_rows']['sha256']})
            rst, frame, finish = [bit(row, name) for name in ('rst_n', 'frame_tick', 'finish')]
            last_finish = finish
            phase_known = source.get('sampling_phase') == 'POSEDGE_PRE_NBA'
            if not phase_known:
                unknown.add('UNKNOWN_SERIAL_FIRST_PHASE')
            pll, pa = bit(row, 'pll_locked'), bit(row, 'pa_en')
            if pa == 1:
                c.require(rst != 0 and pll != 0 and row['audio_stable'] != 0, 'PA_UNSAFE_STATE')
                if row['audio_stable'] is None or isinstance(row['audio_stable'], str):
                    unknown.add('PA_AUDIO_STABLE_NOT_PROVEN')
            qualified = original.get('raw_ports', {}).get('obs_polyphonic_valid') in ('1', 1)
            if type(epoch) is not int or epoch not in frame_cycles or rst is None or frame is None or not qualified:
                unknown.add('UNKNOWN_FRAME_RESET_EPOCH')
                if not qualified:
                    unknown.add('PENDING_PUBLIC_OBSERVER_QUALIFICATION')
                counts['unknown_rows'] += 1
                decoder_enabled = False
                chain_unknown = True
                tx_state_known = False
                outstanding = waiting = pending = held = result_hold = None
                ledger.clear()
                if finish == 1:
                    c.require(plan['finish'] == {'epoch': epoch, 'cycle': cycle}, 'FINISH_PLAN_MISMATCH')
                    finished = True
                continue
            window = plan['epochs'][epoch]
            prefix = epoch == 0 and cycle < window['reset_assert_cycle'] and rst == frame == 0
            c.require(prefix or window['reset_assert_cycle'] <= cycle <= window['stop_cycle'], 'FRAME_WINDOW')
            release = window['release_cycle']
            c.require(rst == int(release is not None and cycle >= release), 'FRAME_RESET_PHASE')
            expected = frame_cycles[epoch]
            index = bisect_left(expected, cycle)
            is_expected = index < len(expected) and expected[index] == cycle
            c.require(frame == int(is_expected), 'FRAME_PLAN_WHOLE_WINDOW')
            if is_expected:
                indices[epoch] += 1
                counts['FRAME_F'] += 1
                if outstanding is not None:
                    raise ValueError('REQUEST_OPEN_AT_NEXT_FRAME')
                c.require(waiting is None, 'REQUEST_HELD_AT_NEXT_FRAME')
                if previous_frame is not None and previous_frame[0] == epoch:
                    gap = cycle - previous_frame[1]
                    if index == bisect_left(expected, previous_frame[1]) + 1:
                        c.require(gap in (833, 834), 'FRAME_INTERVAL')
                        gaps.append(gap)
                        gaps = gaps[-3:]
                        if len(gaps) == 3:
                            c.require(sum(gaps) == 2500, 'FRAME_48K_DISTRIBUTION')
                    else:
                        gaps.clear()
                        unknown.add('FRAME_INTERVAL_COVERAGE_GAP')
                previous_frame, last_frame = (epoch, cycle), cycle
            if not rst:
                if outstanding is not None:
                    deadline(ledger[outstanding], cycle, 'RESET_CLEANUP')
                    writers['transactions'].emit({**coordinate, 'kind': 'RESET_CANCEL',
                                                   'entry': ledger[outstanding]})
                pending = held = outstanding = waiting = result_hold = None
                last_frame = previous_frame = None
                gaps.clear()
                if pins.bits or pins.right_half:
                    unknown.add('RESET_TRUNCATED_HALF_OR_FRAME')
                    counts['reset_truncations'] += 1
                pins.reset()
                ledger.clear()
                decoder_enabled = True
                tx_state_known = True
                chain_unknown = False
            else:
                critical = ('req_valid req_ready result_valid result_ready commit cancel '
                            'tx_sample_valid bclk ws din').split()
                missing = [name for name in critical if bit(row, name) is None]
                for flag, names_to_check in [
                        ('req_valid', ['req_id']),
                        ('result_valid', ['result_id', 'result_left', 'result_right', 'result_clip_mask']),
                        ('commit', ['commit_id', 'commit_left', 'commit_right', 'commit_clip']),
                        ('tx_sample_valid', ['tx_metadata_valid', 'tx_req_id_valid', 'tx_startup_zero',
                                             'tx_hold', 'metadata_error', 'frame_id_overflow',
                                             'tx_left', 'tx_right', 'tx_clip_mask', 'tx_clip'])]:
                    if row[flag] == 1:
                        missing.extend(name for name in names_to_check if type(row[name]) is not int)
                if row['tx_sample_valid'] == 1:
                    c.require(row['metadata_error'] != 1, 'C3_METADATA_ERROR')
                    if row['tx_req_id_valid'] == 1 and type(row['tx_req_id']) is not int:
                        missing.append('tx_req_id')
                    if row['tx_metadata_valid'] != 1 or row['frame_id_overflow'] == 1:
                        missing.append('UNQUALIFIED_TX_METADATA')
                if not phase_known:
                    missing.append('sampling_phase')
                if missing:
                    unknown.update('UNKNOWN_' + name.upper() for name in missing)
                    counts['unknown_rows'] += 1
                    writers['transactions'].emit({**coordinate, 'kind': 'UNKNOWN_CHAIN_BREAK',
                                                   'fields': sorted(set(missing)),
                                                   'outstanding': list(outstanding) if outstanding else None,
                                                   'pending': pending, 'held': held})
                    chain_unknown, decoder_enabled, tx_state_known = True, False, False
                    outstanding = waiting = pending = held = result_hold = None
                    ledger.clear()
                if chain_unknown:
                    unknown.add('CHAIN_COVERAGE_UNKNOWN_UNTIL_RESET')
                    if finish == 1:
                        c.require(plan['finish'] == {'epoch': epoch, 'cycle': cycle}, 'FINISH_PLAN_MISMATCH')
                        finished = True
                    continue
                pvalues = [bit(row, name) for name in ('bclk', 'ws', 'din')]
                if complete_values(pvalues) and decoder_enabled:
                    view = {**coordinate, 'rst_n': rst, 'frame_tick': frame,
                            'bclk': pvalues[0], 'ws': pvalues[1], 'din': pvalues[2]}
                    try:
                        pins.observe(view)  # PRE_NBA old word, before TX current_sample update.
                    except (ValueError, KeyError) as error:
                        raise ValueError('PIN_' + str(error)) from error
                    for half in pins.halves:
                        writers['serial_halves'].emit(half)
                        counts['halves'] += 1
                    for decoded in pins.frames:
                        writers['serial_frames'].emit(decoded)
                        counts['frames'] += 1
                    pins.halves.clear()
                    pins.frames.clear()
                else:
                    unknown.add('UNKNOWN_SERIAL_PIN_COVERAGE')
                    decoder_enabled = False
                txvalid = bit(row, 'tx_sample_valid')
                if frame and txvalid != 1:
                    unknown.add('PENDING_TX_SAMPLE')
                    decoder_enabled = False
                    tx_state_known = False
                if txvalid == 1:
                    c.require(frame == 1, 'TX_NOT_ACTIVE_FRAME')
                    flags = [bit(row, name) for name in ('tx_metadata_valid', 'tx_req_id_valid',
                                                        'tx_startup_zero', 'tx_hold', 'metadata_error',
                                                        'frame_id_overflow')]
                    left, right = [integer(row, name, 24, True) for name in ('tx_left', 'tx_right')]
                    clip = integer(row, 'tx_clip_mask', 2)
                    if complete_values(flags + [left, right, clip]):
                        meta, idvalid, startup, hold, error, overflow = flags
                        c.require(error == 0, 'C3_METADATA_ERROR')
                        if meta != 1 or overflow:
                            unknown.add('PENDING_C3_TX_METADATA_OR_OVERFLOW')
                            decoder_enabled = False
                            tx_state_known = False
                        else:
                            rid = row['tx_req_id']
                            c.require(bit(row, 'tx_clip') == int(bool(clip)), 'C3_TX_CLIP_ANY')
                            if startup:
                                c.require(rid is None and idvalid == 0 and hold == 0 and
                                          left == right == clip == 0 and held is None and pending is None,
                                          'STARTUP_NULL_ID_OR_PCM')
                                counts['startup_tx'] += 1
                            else:
                                c.require(type(rid) is int and 0 <= rid <= 0xffffffff and idvalid == 1,
                                          'TX_VALID_ID_0_DISTINCT_FROM_NULL')
                                actual = (rid, left, right, clip)
                                if hold:
                                    if tx_state_known:
                                        c.require(held == actual, 'HOLD_ID_PCM_CLIP_CHANGED_OR_RESET')
                                    else:
                                        unknown.add('PENDING_HELD_IDENTITY_AFTER_UNKNOWN_TX')
                                    counts['hold_tx'] += 1
                                else:
                                    if tx_state_known or pending is not None:
                                        c.require(pending == actual, 'TX_NOT_OBSERVED_PENDING_ID_PCM_CLIP')
                                        tx_state_known = True
                                    else:
                                        unknown.add('PENDING_PENDING_IDENTITY_AFTER_UNKNOWN_TX')
                                    held, pending = actual, None
                                    counts['new_tx'] += 1
                            if expectations is not None:
                                expectation = expectations.pop((epoch, cycle), None)
                                c.require(expectation is not None, 'TX_EXPECTATION_MISSING')
                                for name in ('tx_req_id', 'tx_left', 'tx_right', 'tx_clip_mask',
                                             'tx_startup_zero', 'tx_hold'):
                                    c.require(row[name] == expectation.get(name), 'TX_SELECTION_DIFFERENCE:' + name)
                            pins.current_sample = {'cycle': cycle, 'epoch': epoch, 'id': rid,
                                                   'left': left, 'right': right, 'frame': row['tx_frame_id']}
                    else:
                        unknown.add('PENDING_TX_METADATA')
                        decoder_enabled = False
                        tx_state_known = False
                rv, ready = bit(row, 'req_valid'), bit(row, 'req_ready')
                if rv == 1:
                    rid = integer(row, 'req_id')
                    if rid is not None:
                        c.require(last_frame is not None, 'ACCEPT_BEFORE_FRAME_F')
                        if waiting is None:
                            waiting = {'id': rid, 'F': last_frame, 'V': cycle}
                        c.require(waiting['id'] == rid, 'REQUEST_HOLD_ID_CHANGED')
                        if ready == 1:
                            key = epoch, rid
                            c.require(key not in seen and outstanding is None, 'DUPLICATE_OR_OVERLAPPED_REQUEST')
                            c.require(cycle - waiting['F'] < 833, 'FA_ACCEPT_DEADLINE')
                            seen.add(key)
                            c.require(len(seen) <= MAX_FRAMES, 'REQUEST_METADATA_BOUND')
                            ledger[key] = {'epoch': epoch, 'id': rid, 'F': waiting['F'],
                                           'V': waiting['V'], 'A': cycle, 'request_cycle': cycle,
                                           'accept_source_line': input_line}
                            outstanding, waiting = key, None
                            counts['accepted'] += 1
                elif rv == 0:
                    c.require(waiting is None, 'REQUEST_VALID_WITHDRAWN')
                valid, ready = bit(row, 'result_valid'), bit(row, 'result_ready')
                if valid == 1:
                    payload = (integer(row, 'result_id'), integer(row, 'result_left', 24, True),
                               integer(row, 'result_right', 24, True), integer(row, 'result_clip_mask', 2))
                    if complete_values(payload):
                        c.require(result_hold is None or result_hold == payload, 'RESULT_BACKPRESSURE_CHANGED')
                        result_hold = payload if ready != 1 else None
                        if ready == 1:
                            key = epoch, payload[0]
                            c.require(outstanding == key, 'RESULT_NOT_ACCEPTED_REQUEST')
                            c.require('result' not in ledger[key], 'DUPLICATE_RESULT_HANDSHAKE')
                            deadline(ledger[key], cycle, 'RESULT')
                            ledger[key].update(result_cycle=cycle, result=payload,
                                               result_source_line=input_line)
                            counts['result'] += 1
                elif valid == 0:
                    c.require(result_hold is None, 'RESULT_VALID_WITHDRAWN')
                if bit(row, 'commit') == 1:
                    rid = integer(row, 'commit_id')
                    key = epoch, rid
                    c.require(outstanding == key, 'COMMIT_NOT_ACCEPTED_REQUEST')
                    entry = ledger[key]
                    deadline(entry, cycle, 'COMMIT')
                    payload = (rid, integer(row, 'commit_left', 24, True),
                               integer(row, 'commit_right', 24, True))
                    result = entry.get('result')
                    c.require(result is not None and complete_values(payload), 'COMMIT_WITHOUT_KNOWN_RESULT')
                    c.require(payload == tuple(result[:3]) and bit(row, 'commit_clip') == int(bool(result[3])),
                              'COMMIT_RESULT_ID_PCM_CLIP')
                    c.require(pending is None, 'COMMIT_WHILE_PENDING')
                    pending = result
                    entry.update(commit_cycle=cycle, commit_source_line=input_line)
                    writers['transactions'].emit({**coordinate, 'kind': 'COMMIT', 'entry': entry})
                    outstanding = None
                    counts['commit'] += 1
                if bit(row, 'cancel') == 1:
                    if outstanding is not None:
                        deadline(ledger[outstanding], cycle, 'CANCEL')
                        writers['transactions'].emit({**coordinate, 'kind': 'CANCEL',
                                                       'raw_reason': row['cancel_reason'],
                                                       'entry': ledger[outstanding]})
                        outstanding = None
                    else:
                        writers['transactions'].emit({**coordinate, 'kind': 'RAW_IDLE_CANCEL',
                                                       'raw_reason': row['cancel_reason']})
            if finish == 1:
                c.require(plan['finish'] == {'epoch': epoch, 'cycle': cycle}, 'FINISH_PLAN_MISMATCH')
                c.require(outstanding is None and (pending is None or not tx_state_known) and waiting is None,
                          'FINISH_WITH_UNCOMPLETED_TRANSACTION')
                finished = True
            # Keep only entries referenced by an active/held/serial word; seen IDs
            # have a separate explicit metadata bound. No per-cycle RAM index.
            keep = {key for key in (outstanding, (epoch, held[0]) if held else None,
                                    (epoch, pending[0]) if pending else None) if key is not None}
            for sample in (pins.current_sample, pins.word_sample, pins.right_half):
                if sample is not None:
                    rid = sample.get('id', sample.get('request_id'))
                    if rid is not None:
                        keep.add((sample.get('epoch'), rid))
            for key in list(ledger):
                if key not in keep:
                    del ledger[key]
        c.require(counts['rows'] > 0, 'EMPTY_PUBLIC_CAPTURE')
        c.require({'bytes': public_bytes, 'sha256': public_digest.hexdigest()} ==
                  {key: before['public_rows'][key] for key in ('bytes', 'sha256')},
                  'SERIAL_READ_IDENTITY')
        if not finished and last_finish is None:
            unknown.add('PENDING_FINISH_FLAG_UNKNOWN')
        else:
            c.require(finished, 'ACTUAL_FINISH_REQUIRED')
        if 'UNKNOWN_FRAME_RESET_EPOCH' not in unknown:
            c.require(all(indices[e] == len(frame_cycles[e]) for e in indices), 'FRAME_PLAN_WHOLE_WINDOW')
        if expectations is not None:
            if expectations and unknown:
                unknown.add('TX_EXPECTATIONS_UNCHECKED_DUE_TO_UNKNOWN')
            else:
                c.require(not expectations, 'UNCONSUMED_TX_EXPECTATION')
        if pins.bits or pins.right_half:
            unknown.add('SERIAL_TAIL_INCOMPLETE')
        if pins.partial_resets:
            unknown.add('RESET_TRUNCATED_HALF_OR_FRAME')
        if not counts['frames']:
            unknown.add('NO_COMPLETE_SERIAL_FRAME')
        for name, descriptor in before.items():
            file = resolve_file(descriptor, c)
            c.require(c.artifact(file) == descriptor, 'READ_AFTER_INPUT_CHANGED:' + name)
        status = 'UNKNOWN_SERIAL_PARTIAL' if unknown else 'OBSERVED_TX_SERIAL_CONSISTENT_POLICY_PENDING'
        result = {'schema': 'M3_C9_STREAM_TX_SERIAL_REPORT_V1', 'status': status,
                  'counts': counts, 'unknown': sorted(unknown), 'pending': sorted(policy),
                  'inputs': before, 'protocol': old13.PROTOCOL,
                  'quantization': 'SATURATE((PCM24+128)//256)', 'clock_hz': 40000000,
                  'decoder': c.artifact(DECODER), 'frame_verifier': c.artifact(PLAN_CHECKER),
                  'finish': plan['finish'], 'FRAME_PLAN_produced': False,
                  'finish_observed': finished,
                  'read_after_identity_equal': True,
                  'unchecked_tx_expectations': len(expectations or {}),
                  'original_74_fields_preserved_in_input': True, 'raw_canonical_not_rewritten': True,
                  'source_authenticity': 'NOT_AUTHENTICATED', 'real_pass': False,
                  'board_release_allowed': False}
    except Exception as error:
        c.write_json(out / 'FAILURE.json', {'status': 'REJECT', 'reason': str(error),
                                          'inputs': before, 'partial_outputs_retained': True,
                                          'real_pass': False, 'board_release_allowed': False})
        raise
    finally:
        for writer in writers.values():
            writer.close()
    result['artifacts'] = {key: c.artifact(out / name) for key, name in names.items()}
    c.write_json(out / 'REPORT.json', result)
    result['artifacts']['report'] = c.artifact(out / 'REPORT.json')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--public-rows', required=True, type=Path)
    parser.add_argument('--frame-plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-scenario', type=Path)
    args = parser.parse_args()
    result = analyze_files(args.public_rows, args.frame_plan, args.output, args.expected_scenario)
    print(json.dumps({'status': result['status'], 'real_pass': False}))
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
