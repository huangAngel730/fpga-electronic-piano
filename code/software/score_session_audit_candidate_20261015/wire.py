"""Independent T057 wire/record primitives for offline session auditing.

Frames with an invalid CRC or version remain decodable so the session auditor
can check the corresponding rejection. Structural truncation is always fatal.
"""
from __future__ import annotations


def crc(raw: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly=0x1021 init=0xffff refin/out=false xorout=0."""
    if type(raw) is not bytes:
        raise ValueError('CRC_INPUT: bytes required')
    value = 0xffff
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xffff
    return value


def _uint(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'{label}: unsigned integer 0..{maximum} required')
    return value


def encode_frame(command, session, seq, offset=0, payload=b'', version=1):
    """Build a literal frame, permitting bad command/version test fixtures."""
    _uint(version, 255, 'VERSION')
    _uint(command, 255, 'COMMAND')
    for label, value in (('SESSION', session), ('SEQ', seq), ('OFFSET', offset)):
        _uint(value, 65535, label)
    if type(payload) is not bytes or len(payload) > 128:
        raise ValueError('PAYLOAD: 0..128 bytes required')
    body = bytes((version, command)) + b''.join(
        value.to_bytes(2, 'little') for value in (session, seq, offset, len(payload))) + payload
    return b'\xa5\x5a' + body + crc(body).to_bytes(2, 'little')


def decode_frame(raw: bytes) -> dict:
    """Decode exactly one structurally complete frame; report its CRC validity."""
    if type(raw) is not bytes:
        raise ValueError('FRAME_INPUT: bytes required')
    if len(raw) < 14 or raw[:2] != b'\xa5\x5a':
        raise ValueError('FRAME_SYNC_LENGTH: need complete A5 5A frame')
    length = int.from_bytes(raw[10:12], 'little')
    if length > 128 or len(raw) != 14 + length:
        raise ValueError('FRAME_PAYLOAD_LENGTH: declaration and frame must match, max 128')
    return {'version': raw[2], 'command': raw[3],
            'session': int.from_bytes(raw[4:6], 'little'),
            'seq': int.from_bytes(raw[6:8], 'little'),
            'offset': int.from_bytes(raw[8:10], 'little'),
            'payload': raw[12:-2],
            'crc_ok': crc(raw[2:-2]) == int.from_bytes(raw[-2:], 'little')}


def decode_records(raw: bytes) -> list[dict]:
    """Validate the frozen 1..512 monotonic eight-byte note-event contract."""
    if type(raw) is not bytes:
        raise ValueError('RECORD_INPUT: bytes required')
    if len(raw) % 8 or not 8 <= len(raw) <= 4096:
        raise ValueError('RECORD_CAPACITY: 1..512 complete records required')
    events, previous = [], 0
    for start in range(0, len(raw), 8):
        tick = int.from_bytes(raw[start:start + 4], 'little')
        kind, channel, note, velocity = raw[start + 4:start + 8]
        if tick < previous:
            raise ValueError(f'RECORD_TICK_ORDER: event {start // 8}')
        if kind not in (0, 1) or channel > 15 or note > 127 or velocity > 127:
            raise ValueError(f'RECORD_EVENT_FIELDS: event {start // 8}')
        if kind == 0 and velocity == 0:
            raise ValueError(f'RECORD_ZERO_NOTE_ON: event {start // 8}')
        events.append({'tick': tick, 'type': 'note_off' if kind else 'note_on',
                       'channel': channel, 'note': note, 'velocity': velocity})
        previous = tick
    return events
