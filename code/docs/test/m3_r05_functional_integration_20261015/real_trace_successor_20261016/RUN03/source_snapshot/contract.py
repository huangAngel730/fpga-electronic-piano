"""P1 proposed calendar schema, not a PCM oracle or real-capture signer."""
import argparse
import json
from pathlib import Path

SCHEMA = 'R06_DERIVED_PRE_NBA_CALENDAR_PROPOSAL_V1'
# All groups are sampled every rising edge, including idle/cancelled work.
# Each value maps to a source category; no DUT math state is a golden input.
FIELDS = {
    'cycle': (0, 2**63-1, 'clock'),
    'time_ps': (0, 2**63-1, 'clock'),
    'epoch': (0, 2**32-1, 'reset'),
    'rst_n': (0, 1, 'reset'),
    'frame_tick': (0, 1, 'frame'),
    'event_valid': (0, 1, 'event'),
    'event_ready_observed': (0, 1, 'event'),
    'event_data': (0, 2**64-1, 'event'),
    'event_accept_observed': (0, 1, 'event'),
    'request_valid': (0, 1, 'request'),
    'request_ready_observed': (0, 1, 'request'),
    'request_accept_observed': (0, 1, 'request'),
    'request_id': (0, 2**32-1, 'request'),
    'current_id': (0, 2**32-1, 'request'),
    'math_valid': (0, 1, 'math'),
    'math_ready_observed': (0, 1, 'math'),
    'math_accept_observed': (0, 1, 'math'),
    'math_id': (0, 2**32-1, 'math'),
    'fx_valid': (0, 1, 'effect'),
    'fx_ready_observed': (0, 1, 'effect'),
    'fx_accept_observed': (0, 1, 'effect'),
    'fx_id': (0, 2**32-1, 'effect'),
    'fx_left': (-2**23, 2**23-1, 'effect'),
    'fx_right': (-2**23, 2**23-1, 'effect'),
    'fx_clip_left': (0, 1, 'effect'),
    'fx_clip_right': (0, 1, 'effect'),
    'config_valid': (0, 1, 'config'),
    'config_ready_observed': (0, 1, 'config'),
    'config_accept_observed': (0, 1, 'config'),
    'config_enable': (0, 1, 'config'),
    'config_delay': (0, 65535, 'config'),
    'config_dry': (0, 32767, 'config'),
    'config_wet': (0, 32767, 'config'),
    'config_feedback': (0, 32767, 'config'),
    'result_valid': (0, 1, 'result'),
    'result_ready': (0, 1, 'result'),
    'result_id': (0, 2**32-1, 'result'),
    'result_left': (-2**23, 2**23-1, 'result'),
    'result_right': (-2**23, 2**23-1, 'result'),
    'result_clip_left': (0, 1, 'result'),
    'result_clip_right': (0, 1, 'result'),
    'commit': (0, 1, 'commit'),
    'committed_id': (0, 2**32-1, 'commit'),
    'committed_left': (-2**23, 2**23-1, 'commit'),
    'committed_right': (-2**23, 2**23-1, 'commit'),
    'committed_clip': (0, 1, 'commit'),
    'clip_count': (0, 2**32-1, 'commit'),
    'pending': (0, 1, 'play'),
    'play_left': (-2**23, 2**23-1, 'play'),
    'play_right': (-2**23, 2**23-1, 'play'),
    'underflow': (0, 2**32-1, 'play'),
    'bclk': (0, 1, 'serial'), 'ws': (0, 1, 'serial'),
    'din': (0, 1, 'serial'),
}
LANE = {
    'lane': (0, 3), 'tick': (0, 1), 'note_on': (0, 1),
    'note_off': (0, 1), 'occupied': (0, 1), 'source': (0, 15),
    'channel': (0, 15), 'note': (0, 127), 'generation': (0, 2**32-1),
    'velocity': (0, 1023), 'timbre': (0, 1), 'fcw_observed': (0, 2**32-1),
}
# Application is distinct from ingress acceptance. These records require future
# public simulation observation ports; never infer application as accept+4.
APPLICATION = {'event_seq': (0, 2**32-1), 'lane_mask': (0, 15),
               'event_data': (0, 2**64-1), 'kind': (0, 7)}
CANCEL = {'request_id': (0, 2**32-1)}


def require(ok, diagnostic):
    if not ok:
        raise ValueError(diagnostic)


def numbers(obj, spec, name):
    require(isinstance(obj, dict) and set(obj) == set(spec), name + '_FIELDS')
    for key, limits in spec.items():
        require(type(obj[key]) is int and limits[0] <= obj[key] <= limits[1],
                name + '_TYPE_RANGE:' + key)


def unique(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, 'DUPLICATE_KEY:' + key)
        obj[key] = value
    return obj


def validate(data):
    require(set(data) == {'schema', 'origin', 'sampling', 'rows', 'end'}, 'HEADER_FIELDS')
    require(data['schema'] == SCHEMA, 'SCHEMA')
    # No live origin accepted before source binding + new observer permission.
    require(data['origin'] == 'SYNTHETIC_CONTRACT_SELFTEST', 'REAL_CAPTURE_NOT_QUALIFIED')
    require(data['sampling'] == 'posedge_pre_NBA', 'SAMPLING')
    require(isinstance(data['rows'], list) and bool(data['rows']), 'EMPTY_ROWS')
    previous = None
    row_keys = set(FIELDS) | {'lanes', 'applications', 'cancellations'}
    for row in data['rows']:
        require(isinstance(row, dict) and set(row) == row_keys, 'ROW_FIELDS')
        numbers({k: row[k] for k in FIELDS}, FIELDS, 'ROW')
        require(isinstance(row['lanes'], list) and len(row['lanes']) == 4, 'ALL_LANES')
        for index, lane in enumerate(row['lanes']):
            numbers(lane, LANE, 'LANE')
            require(lane['lane'] == index, 'LANE_ORDER')
            require(not lane['tick'] or (row['rst_n'] and not row['frame_tick']), 'TICK_CANCEL_RESET')
        for field, spec in [('applications', APPLICATION), ('cancellations', CANCEL)]:
            require(isinstance(row[field], list), 'LIST:' + field)
            for item in row[field]:
                numbers(item, spec, field.upper())
            require(len({json.dumps(x, sort_keys=True) for x in row[field]}) == len(row[field]),
                    'DUPLICATE:' + field)
        for prefix in ('event', 'request', 'math', 'fx', 'config'):
            require(row[prefix + '_accept_observed'] ==
                    (row[prefix + '_valid'] & row[prefix + '_ready_observed']),
                    'HANDSHAKE:' + prefix)
        if previous is None:
            require(row['cycle'] == 0 and row['epoch'] == 0 and row['rst_n'] == 0, 'RESET_ANCHOR')
        else:
            require(row['cycle'] == previous['cycle'] + 1, 'CYCLE_GAP')
            require(row['time_ps'] - previous['time_ps'] == 25000, 'CLOCK_INTERVAL')
            require(row['epoch'] == previous['epoch'] +
                    int(previous['rst_n'] == 1 and row['rst_n'] == 0), 'RESET_EPOCH')
        previous = row
    numbers(data['end'], {'rows': (1, 2**63-1), 'last_cycle': (0, 2**63-1)}, 'END')
    require(data['end'] == {'rows': len(data['rows']), 'last_cycle': previous['cycle']}, 'END_COUNT')
    return {'status': 'SYNTHETIC_SCHEMA_PASS_ONLY', 'rows': len(data['rows']),
            'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False,
            'acceptance_qualification': 'NOT_PROVEN_BY_READY_HANDSHAKE_CHECK',
            'math_result': 'NOT_RUN'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding='utf-8'), object_pairs_hook=unique)
        result = validate(data)
    except (ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'REJECT', 'diagnostic': str(exc),
                          'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
