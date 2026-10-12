"""Independent publication ledger; legacy v5 has insufficient control evidence.

Software-only proposed PRE_NBA protocol. No audio math, HDL or EDA execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


DUT_SHA = '89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb'
SCHEMA = 'T052_PUBLICATION_PRE_NBA_V1_PROPOSED'
U32 = (1 << 32) - 1


def need(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def identity(path):
    raw = Path(path).read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def integer(value, lo=0, hi=U32):
    return type(value) is int and lo <= value <= hi


def exact(row, keys, diagnostic='SCHEMA_FIELDS'):
    need(type(row) is dict and set(row) == set(keys.split()), diagnostic)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def read_rows(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    need(lines and all(lines), 'EMPTY_JSONL_ROW')
    return [json.loads(line, object_pairs_hook=unique_pairs,
                       parse_constant=lambda _: need(False, 'NONFINITE'))
            for line in lines]


def legacy(requests, capture):
    """Only shape/count/order, NEVER infer cancellation from unmatched ACC."""
    acc_re = re.compile(r'ACC (\d+) ([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) '
                        r'([0-9a-fA-F]{8}) ([0-9a-fA-F]{8}) (\d+)')
    cap_re = re.compile(r'ID=(\d+) v0=(-?\d+) v1=(-?\d+) v2=(-?\d+) '
                        r'v3=(-?\d+) ACT=(\d+) CLIP=([01])')

    def records(path, regex, end_tag):
        data, ended = [], False
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            need(not ended, 'RECORD_AFTER_END')
            end = re.fullmatch(r'END ' + end_tag + r'=(\d+)', line)
            if end:
                need(int(end[1]) == sum(row != 'RESET' for row in data), 'END_COUNT')
                ended = True
            elif line == 'RESET' and end_tag == 'requests':
                data.append('RESET')
            else:
                match = regex.fullmatch(line)
                need(match is not None, 'LEGACY_SCHEMA')
                row = list(match.groups())
                need(integer(int(row[0])), 'ID_RANGE')
                if end_tag == 'requests':
                    need(0 <= int(row[-1]) <= 15, 'MASK_RANGE')
                else:
                    need(all(-(1 << 23) <= int(v) < (1 << 23) for v in row[1:5]),
                         'PCM_RANGE')
                    need(0 <= int(row[5]) <= 4, 'ACT_RANGE')
                data.append(row)
        need(ended, 'MISSING_END')
        return data

    req = records(requests, acc_re, 'requests')
    cap = records(capture, cap_re, 'results')
    accepts = [row for row in req if row != 'RESET']
    need(accepts and cap, 'EMPTY_LEGACY_EVIDENCE')
    # Ordered membership is necessary, NOT sufficient. Repeated IDs / RESET
    # cannot provide a unique lifetime assignment from legacy bytes alone.
    cursor = 0
    for row in cap:
        while cursor < len(accepts) and int(accepts[cursor][0]) != int(row[0]):
            cursor += 1
        need(cursor < len(accepts), 'LEGACY_ORDER_OR_ORPHAN')
        cursor += 1
    return dict(status='UNKNOWN', exit_code=3,
                diagnostic='CONTROL_EVIDENCE_INSUFFICIENT',
                structure='PASS', legacy_acc_preparation_records=len(accepts),
                publication_records=len(cap),
                unmatched_preparation_count=len(accepts) - len(cap),
                inferred_cancellations=None, unique_lifetime_assignment=False,
                missing=['posedge acceptance', 'frame/cancel/reset timing',
                         'result handshake', 'complete control window'],
                audio_math='NOT_RERUN', publication_complete=False,
                T052_complete=False)


def calendar(control):
    """Derive obligations from INPUTS + frozen DUT FSM, never from results.

    CALC after accept, HOLD after next edge, valid after next HOLD edge;
    earliest PRE_NBA handshake is accept+3. Cancel/frame wins over handshake.
    Phase advances on acceptance and is not rolled back on cancellation.
    """
    need(len(control) >= 3, 'CONTROL_WINDOW_EMPTY')
    meta, rows, end = control[0], control[1:-1], control[-1]
    exact(meta, 'type schema source_sha sampling reset_scope origin')
    need(meta == dict(type='META', schema=SCHEMA, source_sha=DUT_SHA,
                     sampling='PRE_NBA', reset_scope='NO_UNOBSERVED_ASYNC_PULSE',
                     origin='HANDWRITTEN_SOFTWARE_FIXTURE'), 'PROPOSED_SCOPE_ONLY')
    exact(end, 'type last_cycle')
    need(end['type'] == 'END' and integer(end['last_cycle'])
         and end['last_cycle'] == len(rows) - 1, 'CONTROL_END')
    need(rows and rows[0].get('rst_n') == 0, 'INITIAL_RESET_REQUIRED')
    state, valid, rid, epoch, serial = 'IDLE', 0, 0, 0, 0
    low, pending = False, None
    phases, ticks = [0] * 4, 0
    accepts, cancelled, published, pins = [], [], [], []
    for cycle, row in enumerate(rows):
        exact(row, 'cycle rst_n frame cancel sample_req req_id enable mask fcw result_ready')
        need(integer(row['cycle']) and row['cycle'] == cycle, 'CONTROL_CYCLE_GAP')
        need(all(integer(row[key], 0, 1) for key in
                 ('rst_n', 'frame', 'cancel', 'sample_req', 'enable', 'result_ready')),
             'STRICT_FLAG_01')
        need(integer(row['req_id']) and integer(row['mask'], 0, 15)
             and type(row['fcw']) is list and len(row['fcw']) == 4
             and all(integer(value) for value in row['fcw']), 'REQUEST_FIELDS')
        if not row['rst_n']:
            if not low:
                if pending is not None:
                    cancelled.append(dict(key=pending, cycle=cycle, reason='reset'))
                epoch += 1
                serial = 0
            low, pending = True, None
            state, valid, rid, phases = 'IDLE', 0, 0, [0] * 4
        else:
            low = False
        pins.append(dict(cycle=cycle, calc_ready=int(state == 'IDLE'),
                         result_valid=valid, result_id=rid))
        if not row['rst_n']:
            continue
        if row['frame'] or row['cancel']:
            if pending is not None:
                cancelled.append(dict(key=pending, cycle=cycle,
                                      reason='frame' if row['frame'] else 'cancel'))
            pending, state, valid, rid = None, 'IDLE', 0, 0
        elif state == 'IDLE':
            valid = 0
            if row['sample_req']:
                serial += 1
                pending = [epoch, serial, row['req_id']]
                accepts.append(dict(key=pending, cycle=cycle,
                                    phases_before=list(phases)))
                phases = [(value + fcw) & U32 for value, fcw in zip(phases, row['fcw'])]
                ticks += 1
                state = 'CALC'
        elif state == 'CALC':
            state = 'HOLD'
        elif valid and row['result_ready']:
            published.append(dict(cycle=cycle, key=pending))
            pending, state, valid = None, 'IDLE', 0
        else:
            valid, rid = 1, pending[2]
    need(pending is None, 'OPEN_REQUEST_AT_END')
    need(len(accepts) == len(published) + len(cancelled), 'INTERNAL_LEDGER')
    return dict(pins=pins, publications=published, accepted=accepts,
                cancelled=cancelled, phase_ticks=ticks, final_phases=phases)


def controlled(controls, observations, publications):
    expected = calendar(controls)
    need(len(observations) == len(expected['pins']) + 1, 'OBS_WINDOW_INCOMPLETE')
    for actual, reference in zip(observations[:-1], expected['pins']):
        exact(actual, 'cycle calc_ready result_valid result_id')
        need(integer(actual['cycle']) and integer(actual['result_id'])
             and all(integer(actual[key], 0, 1) for key in ('calc_ready', 'result_valid')),
             'OBS_TYPES')
        need(actual == reference, 'SOURCE_CALENDAR_PINS:' + str(reference['cycle']))
    exact(observations[-1], 'type last_cycle')
    need(integer(observations[-1]['last_cycle'])
         and observations[-1] == controls[-1], 'OBS_END')
    need(publications, 'PUBLICATION_END_MISSING')
    for row in publications[:-1]:
        exact(row, 'cycle key')
        need(integer(row['cycle']) and type(row['key']) is list and len(row['key']) == 3
             and all(integer(value) for value in row['key']), 'PUBLICATION_TYPES')
    keys = [tuple(row['key']) for row in publications[:-1]]
    need(len(keys) == len(set(keys)), 'DUPLICATE_PUBLICATION')
    # Exact ordered set, derived BEFORE looking at observed records. No minimum
    # count, result_valid-derived expected set, or skipped/unmatched inference.
    need(publications[:-1] == expected['publications'], 'PUBLICATION_LEDGER_MISMATCH')
    exact(publications[-1], 'type accepted published cancelled open')
    end = dict(type='END', accepted=len(expected['accepted']),
               published=len(expected['publications']), cancelled=len(expected['cancelled']), open=0)
    need(all(integer(publications[-1][key]) for key in ('accepted', 'published', 'cancelled', 'open'))
         and publications[-1] == end, 'INDEPENDENT_END_COUNT')
    return dict(status='PASS', exit_code=0, diagnostic=None,
                scope='PROPOSED_HANDWRITTEN_SOFTWARE_ONLY', ledger=end,
                accepted=expected['accepted'], cancelled=expected['cancelled'],
                publications=expected['publications'], phase_ticks=expected['phase_ticks'],
                final_phases=expected['final_phases'], publication_complete=True,
                audio_math='NOT_RERUN', RTL_verified=False, T052_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['legacy', 'controlled'])
    parser.add_argument('--requests', type=Path)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--controls', type=Path)
    parser.add_argument('--observations', type=Path)
    parser.add_argument('--publications', type=Path)
    args = parser.parse_args()
    paths = ([args.requests, args.capture] if args.mode == 'legacy'
             else [args.controls, args.observations, args.publications])
    before = {}
    try:
        need(all(path is not None for path in paths), 'INPUT_ARGUMENTS')
        before = {str(path): identity(path) for path in paths}
        result = (legacy(*paths) if args.mode == 'legacy'
                  else controlled(*(read_rows(path) for path in paths)))
        need(before == {str(path): identity(path) for path in paths}, 'INPUT_DRIFT')
    except (ValueError, OSError, TypeError) as error:
        result = dict(status='FAIL', exit_code=1, diagnostic=str(error),
                      publication_complete=False, T052_complete=False)
    result['inputs'] = before
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
