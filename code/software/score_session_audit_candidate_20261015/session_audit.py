"""Offline T057 frame transcript/ACK/READ checker. Never opens a transport."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

from wire import crc, decode_frame, decode_records

MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
MAX_ATTEMPTS = 20000
FIELDS = {'schema', 'evidence_kind', 'initial_committed', 'expected_scores', 'attempts',
          'ack_timeout_us', 'max_retries', 'total_timeout_us'}


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def uint(value, upper, label):
    require(type(value) is int and 0 <= value <= upper, label)
    return value


def unhex(text, maximum, label):
    require(type(text) is str and len(text) % 2 == 0 and len(text) <= maximum * 2,
            label + '_SIZE')
    require(all(c in '0123456789abcdef' for c in text), label + '_HEX')
    return bytes.fromhex(text)


def _apply(request, state):
    """Receiver command contract, evaluated only when a response is observed."""
    command, session, seq, offset, payload = (request[key] for key in ('command', 'session', 'seq', 'offset', 'payload'))
    if not request['crc_ok']:
        return 1, b''
    if request['version'] != 1:
        return 2, b''
    if command == 1:
        if len(payload) != 14 or offset != 0:
            return 4, b''
        if session == 0:
            return 5, b''
        if seq != 0:
            return 6, b''
        sid, count, total, whole_crc, sample_hz = struct.unpack('<IHHHI', payload)
        if not 1 <= count <= 512 or total != count * 8 or sample_hz != 48000:
            return 11, b''
        state['stage'] = {'sid': sid, 'count': count, 'total': total, 'crc': whole_crc,
                          'session': session, 'next_seq': 1, 'records': bytearray()}
        state['active'], state['received'] = True, 0
    elif command == 2:
        stage = state['stage']
        if not state['active'] or session != stage['session']:
            return 5, b''
        if seq != stage['next_seq']:
            return 6, b''
        if offset != state['received']:
            return 7, b''
        if not payload or state['received'] + len(payload) > stage['total']:
            return 4, b''
        stage['records'].extend(payload)
        stage['next_seq'] += 1
        state['received'] += len(payload)
    elif command == 3:
        stage = state['stage']
        if payload or offset != 0:
            return 4, b''
        if not state['active'] or session != stage['session']:
            return 5, b''
        if seq != stage['next_seq']:
            return 6, b''
        if state['received'] != stage['total']:
            return 8, b''
        raw = bytes(stage['records'])
        # Frozen BRAM checks record legality while folding CRC, then final CRC.
        try:
            decode_records(raw)
        except ValueError:
            state['active'] = False
            state['invalidate_cache'] = True
            return 10, b''
        if crc(raw) != stage['crc']:
            state['active'] = False
            state['invalidate_cache'] = True
            return 9, b''
        if state['bank'] is not None:
            require(len(state['reads']) == len(state['bank'][1]) // 8, 'PREVIOUS_BANK_NOT_FULLY_READ')
        require(state['expected'].get(stage['sid']) == raw, 'COMMIT_EXPECTED_CONTENT_MISMATCH')
        state['bank'] = stage['sid'], raw
        state['reads'] = set()
        state['commits'] += 1
        state['published'].add(stage['sid'])
        state['active'] = False
    elif command == 4:
        if payload or offset != 0:
            return 4, b''
        state['active'], state['received'] = False, 0
        state['aborts'] += 1
    elif command == 5:
        if payload or offset != 0:
            return 4, b''
    elif command == 6:
        if payload:
            return 4, b''
        bank = state['bank']
        if bank is None or offset >= len(bank[1]) // 8:
            return 13, b''
        if offset in state['reads']:
            state['redundant_reads'] += 1
        state['reads'].add(offset)
        return 0, bank[1][offset * 8:offset * 8 + 8]
    else:
        return 3, b''
    return 0, b''


def audit_transcript(document):
    require(type(document) is dict and set(document) == FIELDS, 'TRANSCRIPT_FIELDS')
    require(type(document['schema']) is int and document['schema'] == 1, 'TRANSCRIPT_SCHEMA')
    require(document['evidence_kind'] in ('synthetic_fixture', 'recorded_frames'), 'EVIDENCE_KIND')
    require(document['initial_committed'] is None, 'INITIAL_STATE_MUST_DECLARE_RESET_EMPTY')
    ack_limit = uint(document['ack_timeout_us'], 500000, 'ACK_TIMEOUT')
    total_limit = uint(document['total_timeout_us'], 30000000, 'TOTAL_TIMEOUT')
    retries = uint(document['max_retries'], 2, 'MAX_RETRIES')
    require(0 < ack_limit <= total_limit, 'TIMEOUT_ORDER')
    targets = document['expected_scores']
    require(type(targets) is list and 1 <= len(targets) <= 64, 'EXPECTED_SCORE_CAPACITY')
    expected = {}
    for target in targets:
        require(type(target) is dict and set(target) == {'score_id', 'records_hex'}, 'EXPECTED_SCORE_FIELDS')
        sid = uint(target['score_id'], 0xffffffff, 'EXPECTED_SCORE_ID')
        require(sid not in expected, 'DUPLICATE_EXPECTED_SCORE_ID')
        raw = unhex(target['records_hex'], 4096, 'EXPECTED_RECORDS')
        decode_records(raw)
        expected[sid] = raw
    attempts = document['attempts']
    require(type(attempts) is list and 1 <= len(attempts) <= MAX_ATTEMPTS, 'ATTEMPT_CAPACITY')
    state = {'stage': None, 'active': False, 'received': 0, 'bank': None, 'reads': set(),
             'expected': expected, 'commits': 0, 'aborts': 0, 'published': set(),
             'invalidate_cache': False, 'redundant_reads': 0}
    cached_request = cached_reply = pending = None
    timeouts = retry_attempts = cache_replays = nacks = 0
    elapsed_total = session_age = pending_elapsed = 0
    error_counts = {}
    ledger = []
    for index, attempt in enumerate(attempts):
        require(type(attempt) is dict and set(attempt) == {'request_hex', 'response_hex', 'elapsed_us'}, 'ATTEMPT_FIELDS')
        elapsed = uint(attempt['elapsed_us'], total_limit, 'ATTEMPT_TIME')
        elapsed_total += elapsed
        require(elapsed_total <= total_limit, 'TOTAL_DEADLINE')
        if state['active']:
            session_age += elapsed
            require(session_age < 5000000, 'SESSION_TIMEOUT_PROFILE_UNSUPPORTED')
        raw = unhex(attempt['request_hex'], 142, 'REQUEST')
        request = decode_frame(raw)
        if pending is not None:
            require(raw == pending, 'RETRY_REQUEST_CHANGED')
            require(timeouts <= retries, 'RETRY_LIMIT')
            retry_attempts += 1
        if attempt['response_hex'] is None:
            require(elapsed == ack_limit, 'TIMEOUT_WINDOW_UNSUPPORTED')
            pending = raw
            timeouts += 1
            pending_elapsed += elapsed
            ledger.append({'attempt': index, 'kind': 'UNACKNOWLEDGED', 'command': request['command']})
            continue
        require(elapsed <= ack_limit, 'ACK_DEADLINE')
        response_raw = unhex(attempt['response_hex'], 34, 'RESPONSE')
        response = decode_frame(response_raw)
        require(response['crc_ok'] and response['version'] == 1, 'RESPONSE_CRC_VERSION')
        require(tuple(response[k] for k in ('session', 'seq', 'offset')) == tuple(request[k] for k in ('session', 'seq', 'offset')), 'RESPONSE_IDENTITY')
        if request['crc_ok'] and request['version'] == 1 and raw == cached_request:
            require(response_raw == cached_reply, 'CACHED_ACK_BYTES_CHANGED')
            cache_replays += 1
            if state['active']:
                session_age = pending_elapsed + elapsed
            pending, timeouts = None, 0
            pending_elapsed = 0
            ledger.append({'attempt': index, 'kind': 'CACHED_ACK_REPLAY', 'command': request['command']})
            continue
        payload = response['payload']
        require(len(payload) in (12, 20), 'RESPONSE_META_LENGTH')
        command, error, valid, active, count, score_id, received = struct.unpack('<BBBBHIH', payload[:12])
        require(command == request['command'], 'RESPONSE_COMMAND')
        require(response['command'] in (0x80, 0x81) and (response['command'] == 0x80) == (error == 0), 'ACK_NACK_CODE')
        require(valid in (0, 1) and active in (0, 1), 'RESPONSE_FLAGS')
        expected_error, event = _apply(request, state)
        require(error == expected_error, 'NACK_DIAGNOSIS')
        bank = state['bank']
        bank_sid, bank_count = (bank[0], len(bank[1]) // 8) if bank else (0, 0)
        require((valid, active, count, score_id, received) == (int(bank is not None), int(state['active']), bank_count, bank_sid, state['received']), 'RESPONSE_METADATA')
        require(payload[12:] == event, 'READBACK_EVENT_MISMATCH')
        if not state['active']:
            session_age = 0
        elif error == 0 and request['command'] in (1, 2):
            # Complete-frame logs cannot locate the reset within this attempt;
            # retain an upper bound including any unobserved retry windows.
            session_age = pending_elapsed + elapsed
            require(session_age < 5000000, 'SESSION_TIMEOUT_PROFILE_UNSUPPORTED')
        if error == 0:
            cached_request, cached_reply = raw, response_raw
        else:
            nacks += 1
            error_counts[str(error)] = error_counts.get(str(error), 0) + 1
            if state['invalidate_cache']:
                cached_request = cached_reply = None
                state['invalidate_cache'] = False
        pending, timeouts = None, 0
        pending_elapsed = 0
        ledger.append({'attempt': index, 'kind': 'ACK' if error == 0 else 'NACK',
                       'command': command, 'error': error, 'committed_score_id': bank_sid,
                       'unique_reads_current_generation': len(state['reads'])})
    require(pending is None, 'UNRESOLVED_TIMEOUT')
    require(not state['active'], 'OPEN_STAGING_SESSION')
    require(state['bank'] is not None and state['commits'] > 0, 'NO_SUCCESSFUL_COMMIT')
    require(len(state['reads']) == len(state['bank'][1]) // 8, 'READBACK_INCOMPLETE')
    require(state['published'] == set(expected), 'EXPECTED_SCORE_NOT_COMMITTED')
    return {'status': 'OFFLINE_SESSION_AUDIT_PASS', 'evidence_kind': document['evidence_kind'],
            'attempts': len(attempts), 'retry_attempts': retry_attempts, 'cached_ack_replays': cache_replays,
            'commits': state['commits'], 'aborts': state['aborts'], 'nacks': nacks,
            'nack_codes': error_counts, 'redundant_reads': state['redundant_reads'],
            'declared_elapsed_us': elapsed_total, 'final_score_id': state['bank'][0],
            'final_unique_reads': len(state['reads']), 'ledger': ledger,
            'trace_authenticity_verified': False, 'hardware_pass_claim': False,
            'scope': 'declared reset-empty frame trace and supplied expected content; not wire timing, FPGA, playback or audio proof'}


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'DUPLICATE_JSON_FIELD')
        value[key] = item
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f'OUTPUT_REFUSED: {exc}', file=sys.stderr)
        return 2
    receipt = {'status': 'FAIL', 'exit_code': 1, 'hardware_pass_claim': False}
    try:
        with args.trace.open('rb') as stream:
            raw = stream.read(MAX_TRANSCRIPT_BYTES + 1)
        require(len(raw) <= MAX_TRANSCRIPT_BYTES, 'TRANSCRIPT_RESOURCE_LIMIT')
        receipt['input'] = {'path': str(args.trace.resolve()), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        receipt['audit'] = audit_transcript(json.loads(raw.decode('utf-8'), object_pairs_hook=unique))
        receipt.update(status='OFFLINE_SESSION_AUDIT_PASS', exit_code=0)
    except Exception as exc:
        receipt['error'] = f'{type(exc).__name__}: {exc}'
    with (args.output / 'receipt.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))
    return receipt['exit_code']


if __name__ == '__main__':
    sys.exit(main())
