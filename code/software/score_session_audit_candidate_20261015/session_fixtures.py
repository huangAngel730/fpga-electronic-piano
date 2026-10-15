"""Independent synthetic T057 transcripts; never a hardware capture claim."""
from __future__ import annotations

import binascii
import struct


def checksum(raw):
    return binascii.crc_hqx(raw, 0xFFFF)


def frame(command, session, seq, offset=0, payload=b"", version=1):
    body = struct.pack("<BBHHHH", version, command, session, seq, offset,
                       len(payload)) + payload
    return b"\xa5\x5a" + body + struct.pack("<H", checksum(body))


def record(tick, kind, channel, note, velocity):
    return struct.pack("<IBBBB", tick, kind, channel, note, velocity)


RECORDS_A = record(0, 0, 0, 60, 100) + record(24000, 1, 0, 60, 0)
RECORDS_B = record(120, 0, 9, 127, 127) + record(48000, 1, 9, 127, 31)


def begin(score_id, records, session=1, crc_override=None):
    whole = checksum(records) if crc_override is None else crc_override
    return frame(1, session, 0, payload=struct.pack(
        "<IHHHI", score_id, len(records) // 8, len(records), whole, 48000))


def response(request, *, error=0, bank=None, active=False, received=0,
             event=b""):
    _, command, session, seq, offset, _ = struct.unpack("<BBHHHH", request[2:12])
    score_id, records = bank if bank else (0, b"")
    metadata = struct.pack("<BBBBHIH", command, error, int(bank is not None),
                           int(active), len(records) // 8, score_id, received)
    return frame(0x81 if error else 0x80, session, seq, offset, metadata + event)


def attempt(request, reply, elapsed_us=1000):
    return {"request_hex": request.hex(),
            "response_hex": reply.hex() if reply is not None else None,
            "elapsed_us": elapsed_us}


def document(targets):
    return {"schema": 1, "evidence_kind": "synthetic_fixture",
            "initial_committed": None,
            "expected_scores": [{"score_id": sid, "records_hex": raw.hex()}
                                for sid, raw in targets],
            "attempts": [], "ack_timeout_us": 500000,
            "max_retries": 2, "total_timeout_us": 30000000}


def _publish(steps, sid, records, session, old=None, lose_commit_ack=False):
    req = begin(sid, records, session)
    steps.append(attempt(req, response(req, bank=old, active=True)))
    # Deliberately non-record-aligned DATA split: 7 + 9 bytes.
    req = frame(2, session, 1, payload=records[:7])
    steps.append(attempt(req, response(req, bank=old, active=True, received=7)))
    req = frame(2, session, 2, 7, records[7:])
    steps.append(attempt(req, response(req, bank=old, active=True, received=len(records))))
    req = frame(3, session, 3)
    reply = response(req, bank=(sid, records), received=len(records))
    if lose_commit_ack:
        steps.append(attempt(req, None, 500000))
    steps.append(attempt(req, reply))
    if lose_commit_ack:
        # Same last successful command must replay ACK without recommitting.
        steps.append(attempt(req, reply))
    _read_all(steps, (sid, records), session, received=len(records))


def _read_all(steps, bank, session, *, active=False, received=0):
    req = frame(5, session, 99)
    steps.append(attempt(req, response(req, bank=bank, active=active, received=received)))
    for index in range(len(bank[1]) // 8):
        req = frame(6, session, index, index)
        steps.append(attempt(req, response(
            req, bank=bank, active=active, received=received,
            event=bank[1][index * 8:index * 8 + 8])))


def build_success():
    result = document([(101, RECORDS_A)])
    _publish(result["attempts"], 101, RECORDS_A, 1)
    return result


def build_recovery():
    result = document([(101, RECORDS_A), (202, RECORDS_B)])
    steps = result["attempts"]
    old = (101, RECORDS_A)
    _publish(steps, 101, RECORDS_A, 1, lose_commit_ack=True)
    # Partial new upload: old committed bank must survive ABORT.
    req = begin(202, RECORDS_B, 2)
    steps.append(attempt(req, response(req, bank=old, active=True)))
    req = frame(2, 2, 1, payload=RECORDS_B[:7])
    steps.append(attempt(req, response(req, bank=old, active=True, received=7)))
    _read_all(steps, old, 2, active=True, received=7)
    req = frame(4, 42, 17)
    steps.append(attempt(req, response(req, bank=old)))
    # All records legal, wrong whole-score CRC: NACK9 retains receive count.
    req = begin(202, RECORDS_B, 3, checksum(RECORDS_B) ^ 1)
    steps.append(attempt(req, response(req, bank=old, active=True)))
    req = frame(2, 3, 1, payload=RECORDS_B)
    steps.append(attempt(req, response(req, bank=old, active=True, received=16)))
    req = frame(3, 3, 2)
    steps.append(attempt(req, response(req, error=9, bank=old, received=16)))
    req = frame(5, 3, 71)
    steps.append(attempt(req, response(req, bank=old, received=16)))
    req = frame(4, 3, 72)
    steps.append(attempt(req, response(req, bank=old)))
    _publish(steps, 202, RECORDS_B, 4, old=old)
    return result
