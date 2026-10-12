"""Strict synthetic trace replay from META entry state and external inputs ONLY."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from frame_reference import FrameReference, U32, integer, require  # noqa: E402

META_FIXED = dict(tag='META', schema=1, origin='SYNTHETIC_SOFTWARE_TEST',
    contract='PROPOSED_FRAME_TRANSPORT_V1', region='pre_NBA_input_then_post_state',
    voices_context=32, clipped_source='PROPOSED_ADAPTER_METADATA',
    epoch_source='SOFTWARE_LIFETIME_METADATA_NOT_EXISTING_RTL_PORT',
    readiness_gates='SOFTWARE_ENVIRONMENT_NOT_PRODUCTION_PORTS')


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'TRACE_DUPLICATE_KEY:' + key)
        result[key] = value
    return result


def parse(line):
    result = json.loads(line, object_pairs_hook=pairs,
                        parse_constant=lambda _: require(False, 'TRACE_NONFINITE'))
    require(type(result) is dict, 'TRACE_RECORD_TYPE')
    return result


def typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(typed_equal(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(typed_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def diagnostic(field, inp):
    if field in ('dispatch_valid', 'dispatch_accept', 'pending_request', 'dispatched', 'dispatch_count'):
        return 'DISPATCH_VALID_READY'
    if field == 'result_payload':
        return 'RESULT_HOLD_STABILITY'
    if field in ('commit', 'commit_payload', 'commit_count', 'committed_pending', 'clip_count'):
        return 'CLIP_COMMIT_EXACTLY_ONCE' if field == 'clip_count' else 'COMMIT_CURRENT_ONCE'
    if field in ('result_accept', 'result_count', 'received', 'pcm_record'):
        return 'FRAME_OLD_RESULT_REJECT' if inp['frame_tick'] else 'RESULT_CURRENT_EPOCH_ID'
    return 'TRANSPORT_STATE:' + field


def check(lines):
    iterator = iter(lines)
    try:
        meta = parse(next(iterator))
    except StopIteration as error:
        raise ValueError('TRACE_MISSING_META') from error
    require(set(meta) == set(META_FIXED) | {'case', 'initial'}, 'TRACE_META_FIELDS')
    require(type(meta['case']) is str and 0 < len(meta['case']) < 100, 'TRACE_CASE')
    for key, expected in META_FIXED.items():
        require(typed_equal(meta[key], expected), 'TRACE_META_VALUE:' + key)
    model = FrameReference(meta['initial'])
    cycle, resets, pending_reset, ended, edge_count = 0, 0, None, False, 0
    ledger = dict(dispatch=0, result=0, commit=0, discard=0, reset=0)
    for line in iterator:
        require(not ended, 'TRACE_AFTER_END')
        row = parse(line)
        tag = row.get('tag')
        if tag == 'RESET':
            require(set(row) == {'tag', 'cycle', 'epoch'} and pending_reset is None, 'TRACE_RESET_FIELDS')
            integer(row['cycle'], 1, U32, 'TRACE_RESET_CYCLE_TYPE')
            integer(row['epoch'], 1, U32, 'TRACE_RESET_EPOCH_TYPE')
            require(row['cycle'] == cycle + 1 and row['epoch'] == model.epoch + 1,
                    'TRACE_RESET_ORDER')
            pending_reset = row
        elif tag == 'EDGE':
            require(set(row) == {'tag', 'cycle', 'epoch', 'inputs', 'pre', 'post'}, 'TRACE_EDGE_FIELDS')
            integer(row['cycle'], 1, U32, 'TRACE_CYCLE_TYPE')
            integer(row['epoch'], 0, U32, 'TRACE_EPOCH_TYPE')
            require(row['cycle'] == cycle + 1, 'TRACE_CYCLE_CONTINUITY')
            # Model validates exact input fields/ranges; no observed state seeds it.
            expected_reset = (type(row['inputs']) is dict and row['inputs'].get('rst_n') == 0 and not model.was_reset)
            require(bool(pending_reset) == expected_reset, 'TRACE_RESET_MARKER')
            pre, post = model.edge(row['inputs'])
            require(row['epoch'] == post['epoch'], 'TRACE_EPOCH_IDENTITY')
            for region, expected in (('pre', pre), ('post', post)):
                actual = row[region]
                require(type(actual) is dict and set(actual) == set(expected), 'TRACE_OBSERVATION_FIELDS:' + region)
                for field, value in expected.items():
                    require(typed_equal(actual[field], value), diagnostic(field, row['inputs']))
            if pending_reset:
                resets += 1
                ledger['reset'] += 1
            pending_reset = None
            cycle += 1
            edge_count += 1
            for key, field in (('dispatch', 'dispatch_accept'), ('result', 'result_accept'), ('commit', 'commit'), ('discard', 'discard_result')):
                ledger[key] += pre[field]
        elif tag == 'END':
            expected = dict(tag='END', cycle=cycle, epoch=model.epoch,
                            counts=dict(EDGE=edge_count, RESET=resets), ledger=ledger)
            require(pending_reset is None and typed_equal(row, expected), 'TRACE_END_EXACT')
            require(edge_count > 0 and any(ledger[k] for k in ('dispatch', 'commit', 'discard')),
                    'TRACE_NO_TRANSACTION_EVIDENCE')
            ended = True
        else:
            raise ValueError('TRACE_UNKNOWN_TAG')
    require(ended, 'TRACE_MISSING_END')
    return dict(status='SYNTHETIC_FRAME_SOFTWARE_PASS', case=meta['case'],
        edges=edge_count, ledger=ledger, final_state=model.state(), level='L0/L1',
        origin=META_FIXED['origin'], RTL_verified=False, physical_verified=False,
        math_verified=False, admission_verified=False, t060_complete=False, t061_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.trace.open(encoding='utf-8') as stream:
            result = check(stream)
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps(dict(status='REJECT', diagnostic=str(error))), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
