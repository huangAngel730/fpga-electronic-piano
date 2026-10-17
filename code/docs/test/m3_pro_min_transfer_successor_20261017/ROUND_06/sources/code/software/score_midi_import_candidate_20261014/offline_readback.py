"""Independent strict offline decoder for frozen T057 records/upload bytes.

This validates an exported upload stream, not an FPGA ACK or hardware readback.
No production encoder, serial transport or external package is imported.
"""
from __future__ import annotations

import hashlib


def crc_ccitt_false(raw: bytes) -> int:
    """Bitwise poly 0x1021, init 0xffff, no reflection/final xor."""
    value = 0xffff
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xffff
    return value


def _uint(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'DOCUMENT_{label}: invalid unsigned integer')
    return value


def _bytes(raw, label):
    if type(raw) is not bytes:
        raise ValueError(f'{label}: expected bytes')


def decode_records(raw: bytes) -> list[dict]:
    """Decode and validate the literal 8-byte little-endian event contract."""
    _bytes(raw, 'RECORD_TYPE')
    if len(raw) % 8 or not 8 <= len(raw) <= 4096:
        raise ValueError('RECORD_CAPACITY: need 1..512 complete 8-byte records')
    result, previous = [], 0
    for offset in range(0, len(raw), 8):
        tick = int.from_bytes(raw[offset:offset + 4], 'little')
        kind, channel, note, velocity = raw[offset + 4:offset + 8]
        if tick < previous:
            raise ValueError(f'RECORD_TICK_ORDER: event {offset // 8}')
        if kind not in (0, 1) or channel > 15 or note > 127 or velocity > 127:
            raise ValueError(f'RECORD_EVENT: event {offset // 8}')
        if kind == 0 and velocity == 0:
            raise ValueError(f'RECORD_ZERO_NOTE_ON: event {offset // 8}')
        result.append({'tick': tick, 'type': 'note_off' if kind else 'note_on',
                       'channel': channel, 'note': note, 'velocity': velocity})
        previous = tick
    return result


def _frames(raw):
    _bytes(raw, 'UPLOAD_TYPE')
    position = 0
    while position < len(raw):
        if len(raw) - position < 14 or raw[position:position + 2] != b'\xa5\x5a':
            raise ValueError(f'FRAME_SYNC_LENGTH: byte {position}')
        header = raw[position + 2:position + 12]
        version, command = header[:2]
        session = int.from_bytes(header[2:4], 'little')
        sequence = int.from_bytes(header[4:6], 'little')
        offset = int.from_bytes(header[6:8], 'little')
        length = int.from_bytes(header[8:10], 'little')
        end = position + 14 + length
        if version != 1 or length > 128 or end > len(raw):
            raise ValueError(f'FRAME_VERSION_LENGTH: byte {position}')
        body = raw[position + 2:end - 2]
        if crc_ccitt_false(body) != int.from_bytes(raw[end - 2:end], 'little'):
            raise ValueError(f'FRAME_CRC: byte {position}')
        yield command, session, sequence, offset, raw[position + 12:end - 2]
        position = end


def decode_upload(raw: bytes) -> tuple[int, bytes, int]:
    """Reconstruct exactly one BEGIN/DATA+/COMMIT stream; reject retries/noise."""
    state, session, expected_seq = 'begin', None, 0
    score_id = count = byte_count = expected_crc = None
    records = bytearray()
    for command, current_session, sequence, offset, payload in _frames(raw):
        if state == 'done':
            raise ValueError('UPLOAD_EXTRA_FRAME: bytes follow COMMIT')
        if state == 'begin':
            if (command, sequence, offset, len(payload)) != (1, 0, 0, 14):
                raise ValueError('UPLOAD_BEGIN: first frame must be canonical BEGIN')
            if current_session == 0:
                raise ValueError('UPLOAD_SESSION: zero session')
            session = current_session
            score_id = int.from_bytes(payload[:4], 'little')
            count = int.from_bytes(payload[4:6], 'little')
            byte_count = int.from_bytes(payload[6:8], 'little')
            expected_crc = int.from_bytes(payload[8:10], 'little')
            sample_hz = int.from_bytes(payload[10:14], 'little')
            if not 1 <= count <= 512 or byte_count != count * 8 or sample_hz != 48000:
                raise ValueError('UPLOAD_METADATA: capacity/size/sample_hz')
            expected_seq, state = 1, 'data'
            continue
        if current_session != session:
            raise ValueError('UPLOAD_SESSION: session changed')
        if sequence != expected_seq:
            raise ValueError('UPLOAD_SEQUENCE: missing/duplicate/out-of-order frame')
        if command == 2:
            if offset != len(records) or not 1 <= len(payload) <= 128:
                raise ValueError('UPLOAD_DATA: offset/empty payload')
            if len(records) + len(payload) > byte_count:
                raise ValueError('UPLOAD_OVERFLOW: DATA exceeds declared bytes')
            records.extend(payload)
            expected_seq += 1
        elif command == 3:
            if offset != 0 or payload:
                raise ValueError('UPLOAD_COMMIT: offset/payload')
            if len(records) != byte_count:
                raise ValueError('UPLOAD_INCOMPLETE: missing score bytes')
            if crc_ccitt_false(records) != expected_crc:
                raise ValueError('UPLOAD_SCORE_CRC: entire record stream differs')
            decode_records(bytes(records))
            state = 'done'
        else:
            raise ValueError('UPLOAD_COMMAND: only BEGIN/DATA/COMMIT permitted')
    if state != 'done':
        raise ValueError('UPLOAD_INCOMPLETE: missing BEGIN/DATA/COMMIT')
    return score_id, bytes(records), session


def _document_events(document):
    if type(document) is not dict or set(document) != {'schema', 'sample_hz', 'score_id', 'events'}:
        raise ValueError('DOCUMENT_FIELDS: exact T057 schema required')
    if type(document['schema']) is not int or document['schema'] != 1:
        raise ValueError('DOCUMENT_SCHEMA: require integer 1')
    if type(document['sample_hz']) is not int or document['sample_hz'] != 48000:
        raise ValueError('DOCUMENT_SAMPLE_HZ: require integer 48000')
    _uint(document['score_id'], 0xffffffff, 'SCORE_ID')
    events = document['events']
    if type(events) is not list or not 1 <= len(events) <= 512:
        raise ValueError('DOCUMENT_CAPACITY: need 1..512 events')
    expected, previous = [], 0
    for event in events:
        if type(event) is not dict or set(event) != {'tick', 'type', 'channel', 'note', 'velocity'}:
            raise ValueError('DOCUMENT_EVENT_FIELDS: exact fields required')
        tick = _uint(event['tick'], 0xffffffff, 'TICK')
        channel = _uint(event['channel'], 15, 'CHANNEL')
        note = _uint(event['note'], 127, 'NOTE')
        velocity = _uint(event['velocity'], 127, 'VELOCITY')
        if type(event['type']) is not str or event['type'] not in ('note_on', 'note_off') or tick < previous:
            raise ValueError('DOCUMENT_TYPE_ORDER: invalid type/tick order')
        expected.append({'tick': tick, 'type': 'note_off' if event['type'] == 'note_off' or velocity == 0 else 'note_on',
                         'channel': channel, 'note': note, 'velocity': velocity})
        previous = tick
    return expected


def verify_roundtrip(document, records: bytes, upload: bytes) -> dict:
    """Independently compare JSON semantics, record bytes and full upload stream."""
    expected = _document_events(document)
    decoded = decode_records(records)
    if decoded != expected:
        raise ValueError('READBACK_RECORD_MISMATCH: JSON events differ from records')
    score_id, reconstructed, session = decode_upload(upload)
    if score_id != document['score_id']:
        raise ValueError('READBACK_SCORE_ID_MISMATCH: upload identity differs')
    if reconstructed != records:
        raise ValueError('READBACK_UPLOAD_MISMATCH: uploaded bytes differ from records')
    if decode_records(reconstructed) != expected:
        raise ValueError('READBACK_EVENT_MISMATCH: uploaded events differ')
    return {'status': 'OFFLINE_READBACK_PASS', 'events_compared': len(expected),
            'score_id': score_id, 'session': session, 'sample_hz': 48000,
            'records_bytes': len(records), 'upload_bytes': len(upload),
            'records_sha256': hashlib.sha256(records).hexdigest(),
            'upload_sha256': hashlib.sha256(upload).hexdigest(),
            'score_crc16': crc_ccitt_false(records), 'hardware_pass_claim': False}
