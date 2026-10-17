"""Offline T057 v1 byte-stream and transaction verifier.

This tool never opens a serial port.  Direction names are PC-centric:
``tx`` is PC -> FPGA and ``rx`` is FPGA -> PC.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Iterable


MAGIC = b"\xa5\x5a"
HEADER = struct.Struct("<BBHHHH")
META = struct.Struct("<BBBBHIH")
BEGIN, DATA, COMMIT, ABORT, STATUS, READ = range(1, 7)
ACK, NACK = 0x80, 0x81
COMMAND_NAMES = {
    BEGIN: "BEGIN", DATA: "DATA", COMMIT: "COMMIT", ABORT: "ABORT",
    STATUS: "STATUS", READ: "READ", ACK: "ACK", NACK: "NACK",
}
REQUEST_COMMANDS = {BEGIN, DATA, COMMIT, ABORT, STATUS, READ}
RESPONSE_COMMANDS = {ACK, NACK}
ERROR_NAMES = {
    1: "frame_crc", 2: "version", 3: "command", 4: "length_or_parameter",
    5: "session", 6: "sequence", 7: "offset", 8: "incomplete",
    9: "score_crc", 10: "event", 11: "capacity_or_metadata",
    12: "frame_or_session_timeout", 13: "read_index", 14: "uart_stop_bit",
}
EXIT_PASS = 0
EXIT_INVALID = 2
EXIT_INCOMPLETE = 3
EXIT_NOT_VERIFIABLE = 4


class TraceError(ValueError):
    """Input or expectation cannot be interpreted safely."""


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TraceError(f"duplicate JSON field {key}")
        result[key] = value
    return result


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    direction: str | None = None
    byte_offset: int | None = None
    frame_index: int | None = None
    transaction: str | None = None
    recovery: str | None = None


@dataclass
class Frame:
    direction: str
    frame_index: int
    byte_offset: int
    raw_hex: str
    raw_sha256: str
    version: int
    command: int
    command_name: str
    session: int
    seq: int
    offset: int
    length: int
    payload_hex: str
    timestamp_us: int | None
    end_timestamp_us: int | None
    source_line: int | None

    @property
    def raw(self) -> bytes:
        return bytes.fromhex(self.raw_hex)

    @property
    def payload(self) -> bytes:
        return bytes.fromhex(self.payload_hex)

    @property
    def identity(self) -> tuple[int, int, int]:
        return self.session, self.seq, self.offset


@dataclass
class ByteMark:
    timestamp_us: int | None
    source_line: int | None


class StreamParser:
    def __init__(self, direction: str, mode: str, findings: list[Finding]):
        self.direction = direction
        self.mode = mode
        self.findings = findings
        self.buffer = bytearray()
        self.marks: list[ByteMark] = []
        self.absolute_offset = 0
        self.frames: list[Frame] = []
        self.discard_until_idle = False

    def _finding(self, code: str, severity: str, message: str,
                 offset: int | None = None) -> None:
        self.findings.append(Finding(code, severity, message, self.direction,
                                     self.absolute_offset if offset is None else offset))

    def _drop(self, count: int) -> None:
        del self.buffer[:count]
        del self.marks[:count]
        self.absolute_offset += count

    def feed(self, data: bytes, timestamp_us: int | None, source_line: int | None,
             idle_before_ms: float | None = None,
             byte_times_us: list[int] | None = None) -> list[Frame]:
        emitted: list[Frame] = []
        if self.buffer and idle_before_ms is not None and idle_before_ms >= 20.0:
            self._finding("FRAME_TIMEOUT", "error",
                          f"discarded {len(self.buffer)} partial byte(s) after documented >=20 ms idle gap")
            self._drop(len(self.buffer))
        if self.discard_until_idle:
            if idle_before_ms is None or idle_before_ms < 20.0:
                self._finding("OVERSIZE_DISCARD", "error",
                              "bytes ignored until a documented >=20 ms idle gap")
                self.absolute_offset += len(data)
                return emitted
            self.discard_until_idle = False
            self._finding("OVERSIZE_IDLE_RECOVERY", "warning",
                          "resumed sync search after documented >=20 ms idle gap")
        self.buffer.extend(data)
        if byte_times_us is None:
            self.marks.extend(ByteMark(timestamp_us, source_line) for _ in data)
        else:
            self.marks.extend(ByteMark(value, source_line) for value in byte_times_us)
        while True:
            if len(self.buffer) < 2:
                break
            if self.buffer[:2] != MAGIC:
                pos = self.buffer.find(MAGIC)
                if pos < 0:
                    keep = 1 if self.buffer[-1:] == MAGIC[:1] else 0
                    count = len(self.buffer) - keep
                else:
                    count = pos
                if count:
                    severity = "error" if self.mode == "strict" else "warning"
                    code = "UNEXPECTED_NOISE" if self.mode == "strict" else "RECOVERED_NOISE"
                    self._finding(code, severity,
                                  f"skipped {count} non-frame byte(s) while searching for sync")
                    self._drop(count)
                    continue
                break
            if len(self.buffer) < 12:
                break
            version, command, session, seq, offset, length = HEADER.unpack(self.buffer[2:12])
            if length > 128:
                self._finding("FRAME_LENGTH_OVERSIZE", "error",
                              f"declared payload length {length} exceeds 128")
                self._drop(12)
                self.discard_until_idle = True
                if self.buffer:
                    self.absolute_offset += len(self.buffer)
                    self.buffer.clear()
                    self.marks.clear()
                break
            total = 14 + length
            if len(self.buffer) < total:
                break
            raw = bytes(self.buffer[:total])
            start = self.marks[0]
            end = self.marks[total - 1]
            start_offset = self.absolute_offset
            self._drop(total)
            if crc16(raw[2:-2]) != int.from_bytes(raw[-2:], "little"):
                self.findings.append(Finding(
                    "FRAME_CRC", "error", "CRC-16/CCITT-FALSE mismatch",
                    self.direction, start_offset, len(self.frames),
                    recovery="NACK1 requires the client to stop; use ABORT or a new BEGIN before recovery.",
                ))
                continue
            if version != 1:
                self.findings.append(Finding(
                    "FRAME_VERSION", "error", f"unsupported version {version}",
                    self.direction, start_offset, len(self.frames),
                    recovery="Correct the encoder version; do not reinterpret this frame as v1.",
                ))
                continue
            frame = Frame(
                direction=self.direction,
                frame_index=len(self.frames),
                byte_offset=start_offset,
                raw_hex=raw.hex(),
                raw_sha256=sha256(raw),
                version=version,
                command=command,
                command_name=COMMAND_NAMES.get(command, f"UNKNOWN_{command}"),
                session=session,
                seq=seq,
                offset=offset,
                length=length,
                payload_hex=raw[12:-2].hex(),
                timestamp_us=start.timestamp_us,
                end_timestamp_us=end.timestamp_us,
                source_line=start.source_line,
            )
            self.frames.append(frame)
            emitted.append(frame)
        return emitted

    def finish(self) -> None:
        if self.discard_until_idle:
            self._finding("OVERSIZE_NO_IDLE", "error",
                          "trace ended before the required 20 ms idle recovery boundary")
        if self.buffer:
            prefix = "partial frame" if self.buffer[:1] == MAGIC[:1] else "trailing bytes"
            self._finding("TRUNCATED_FRAME", "incomplete",
                          f"trace ended with {len(self.buffer)} {prefix}")


@dataclass
class ActiveUpload:
    session: int
    score_id: int
    event_count: int
    total_bytes: int
    score_crc: int
    sample_hz: int
    next_seq: int = 1
    records: bytearray = field(default_factory=bytearray)


@dataclass
class Commit:
    session: int
    score_id: int
    records_hex: str
    frame_index: int
    read_indices: list[int] = field(default_factory=list)
    status_seen: bool = False

    @property
    def records(self) -> bytes:
        return bytes.fromhex(self.records_hex)


@dataclass
class Pending:
    frame: Frame
    attempts: int = 1
    first_timestamp_us: int | None = None
    last_timestamp_us: int | None = None
    replay_of_last_success: bool = False


def validate_records(records: bytes) -> str | None:
    if not records or len(records) % 8:
        return "record byte count is not a nonzero multiple of 8"
    previous = -1
    for index in range(len(records) // 8):
        tick, kind, channel, note, velocity = struct.unpack_from("<IBBBB", records, 8 * index)
        if tick < previous:
            return f"event {index} tick is not nondecreasing"
        if (kind not in (0, 1) or channel > 15 or note > 127 or velocity > 127 or
                (kind == 0 and velocity == 0)):
            return f"event {index} has invalid kind/channel/note/velocity"
        previous = tick
    return None


class TransactionChecker:
    def __init__(self, findings: list[Finding], timestamps_available: bool,
                 interleaving_available: bool):
        self.findings = findings
        self.timestamps_available = timestamps_available
        self.interleaving_available = interleaving_available
        self.active: ActiveUpload | None = None
        self.committed: Commit | None = None
        self.commits: list[Commit] = []
        self.pending: Pending | None = None
        self.last_success_request: Frame | None = None
        self.last_success_response: Frame | None = None
        self.retransmissions = 0
        self.duplicate_responses = 0
        self.nacks: list[dict[str, int]] = []
        self.nack_recovery_pending = False
        self.received_state = 0
        self.transactions: list[dict[str, Any]] = []
        self.first_timestamp_us: int | None = None
        self.last_timestamp_us: int | None = None

    def add(self, code: str, severity: str, message: str, frame: Frame | None = None,
            recovery: str | None = None) -> None:
        self.findings.append(Finding(
            code, severity, message,
            frame.direction if frame else None,
            frame.byte_offset if frame else None,
            frame.frame_index if frame else None,
            f"{frame.session}:{frame.seq}:{frame.offset}" if frame else None,
            recovery,
        ))

    def reset(self) -> None:
        self.active = None
        self.committed = None
        self.pending = None
        self.last_success_request = None
        self.last_success_response = None
        self.received_state = 0

    def consume(self, frame: Frame) -> None:
        if frame.timestamp_us is not None:
            if self.first_timestamp_us is None:
                self.first_timestamp_us = frame.timestamp_us
            if self.last_timestamp_us is not None and frame.timestamp_us < self.last_timestamp_us:
                self.add("TIME_REVERSED", "error", "timestamps are not monotonic", frame)
            self.last_timestamp_us = frame.end_timestamp_us
        if frame.direction == "tx":
            self._request(frame)
        else:
            self._response(frame)

    def _request(self, frame: Frame) -> None:
        if frame.command not in REQUEST_COMMANDS:
            self.add("TX_NOT_REQUEST", "error", "PC TX frame is not a request command", frame)
            return
        if self.pending is not None:
            if frame.raw == self.pending.frame.raw:
                if (self.timestamps_available and
                        self.pending.last_timestamp_us is not None and
                        frame.timestamp_us is not None and
                        frame.timestamp_us - self.pending.last_timestamp_us < 500_000):
                    self.add("RETRY_TOO_EARLY", "error",
                             "exact request retransmission occurred before the 0.5 s response timeout",
                             frame)
                self.pending.attempts += 1
                self.pending.last_timestamp_us = frame.end_timestamp_us
                self.retransmissions += 1
                if self.pending.attempts > 3:
                    self.add("RETRY_LIMIT", "error", "more than two retransmissions", frame)
                return
            self.add("STOP_WAIT_VIOLATION", "error",
                     "new request sent while another request has no response", frame)
        replay = (self.last_success_request is not None and
                  frame.raw == self.last_success_request.raw)
        self.pending = Pending(frame, 1, frame.end_timestamp_us, frame.end_timestamp_us, replay)
        if replay:
            self.retransmissions += 1

    def _response(self, frame: Frame) -> None:
        if frame.command not in RESPONSE_COMMANDS:
            self.add("RX_NOT_RESPONSE", "error", "FPGA RX frame is not ACK/NACK", frame)
            return
        if self.pending is None:
            if self.last_success_response is not None and frame.raw == self.last_success_response.raw:
                self.duplicate_responses += 1
                self.add("DUPLICATE_RESPONSE", "warning",
                         "exact duplicate response ignored; no transaction applied twice", frame)
                return
            self.add("UNMATCHED_RESPONSE", "error", "response has no preceding request", frame)
            return
        pending = self.pending
        request = pending.frame
        if frame.identity != request.identity:
            if (self.last_success_response is not None and
                    frame.raw == self.last_success_response.raw):
                self.duplicate_responses += 1
                self.add("LATE_DUPLICATE_RESPONSE", "warning",
                         "late byte-identical response for the previous transaction ignored; current request remains pending",
                         frame)
                return
            self.add("ACK_IDENTITY_MISMATCH", "error",
                     f"response identity {frame.identity} != request {request.identity}", frame)
            return
        if len(frame.payload) not in (META.size, META.size + 8):
            self.add("RESPONSE_SHAPE", "error", "response payload is not 12 or 20 bytes", frame)
            return
        original, error, committed_valid, session_valid, committed_count, score_id, received = \
            META.unpack(frame.payload[:META.size])
        if original != request.command:
            self.add("ACK_COMMAND_MISMATCH", "error",
                     f"response names command {original}, request was {request.command}", frame)
            return
        expected_shape = META.size + (8 if request.command == READ and frame.command == ACK else 0)
        if len(frame.payload) != expected_shape:
            self.add("RESPONSE_SHAPE", "error",
                     f"response payload has {len(frame.payload)} bytes; expected {expected_shape}", frame)
            return
        if frame.command == ACK and error != 0:
            self.add("ACK_NONZERO_ERROR", "error", "ACK carries a nonzero error code", frame)
            return
        if frame.command == NACK and error == 0:
            self.add("NACK_ZERO_ERROR", "error", "NACK carries error code zero", frame)
            return
        if self.timestamps_available and pending.last_timestamp_us is not None and frame.timestamp_us is not None:
            elapsed = frame.timestamp_us - pending.last_timestamp_us
            if elapsed < 0:
                self.add("RESPONSE_PRECEDES_REQUEST", "error", "response timestamp precedes request", frame)
            elif elapsed > 500_000:
                self.add("ACK_TIMEOUT_EXCEEDED", "error",
                         f"response latency {elapsed} us exceeds default 0.5 s", frame)
        self.pending = None
        if frame.command == NACK:
            self.nacks.append({"command": original, "error": error,
                               "session": frame.session, "seq": frame.seq, "offset": frame.offset})
            commit_nack8_divergence = request.command == COMMIT and error == 8 and session_valid
            if commit_nack8_divergence:
                self.add(
                    "CONTRACT_IMPLEMENTATION_DIVERGENCE_COMMIT_NACK8_SESSION",
                    "error",
                    "NACK8 COMMIT response retains an active session, while PROTOCOL.md requires every failed COMMIT to invalidate it",
                    frame,
                    "Use ABORT or a new BEGIN; do not continue the retained session until M2 resolves the frozen contract/RTL difference.",
                )
            if request.command == COMMIT:
                self.active = None
            if not commit_nack8_divergence:
                self._validate_meta(frame, committed_valid, session_valid,
                                    committed_count, score_id, received)
            self.add("NACK_RECEIVED", "error",
                     f"NACK{error} ({ERROR_NAMES.get(error, 'unknown')})",
                     frame, self._recovery_for(error))
            self.nack_recovery_pending = True
            self._record_transaction(pending, frame, "NACK", False, error)
            return
        if pending.replay_of_last_success:
            if self.last_success_response is None or frame.raw != self.last_success_response.raw:
                self.add("REPLAY_RESPONSE_MISMATCH", "error",
                         "exact repeated request did not receive byte-identical ACK replay", frame)
                self._record_transaction(pending, frame, "ACK_REPLAY_MISMATCH", False, 0)
            else:
                self._record_transaction(pending, frame, "ACK_REPLAY", False, 0)
            return
        errors_before = sum(item.severity == "error" for item in self.findings)
        self._apply_ack(request, frame, committed_valid, session_valid,
                        committed_count, score_id, received)
        errors_after = sum(item.severity == "error" for item in self.findings)
        accepted = errors_after == errors_before
        self._record_transaction(pending, frame,
                                 "ACK" if accepted else "ACK_REJECTED_BY_CHECKER",
                                 accepted and request.command in (BEGIN, DATA, COMMIT, ABORT), 0)
        self.last_success_request = request
        self.last_success_response = frame
        if accepted and request.command == COMMIT and self.nack_recovery_pending:
            self.add("RECOVERY_AFTER_NACK_OBSERVED", "notice",
                     "a later transaction committed successfully after an earlier NACK; the NACK remains an invalid-trace finding",
                     frame)
            self.nack_recovery_pending = False

    def _record_transaction(self, pending: Pending, response: Frame,
                            outcome: str, mutation_applied: bool,
                            error_code: int) -> None:
        elapsed = None
        if self.timestamps_available and pending.last_timestamp_us is not None and response.timestamp_us is not None:
            elapsed = response.timestamp_us - pending.last_timestamp_us
        request = pending.frame
        self.transactions.append({
            "logical_index": len(self.transactions),
            "request_frame_index": request.frame_index,
            "response_frame_index": response.frame_index,
            "command": request.command,
            "command_name": request.command_name,
            "session": request.session,
            "seq": request.seq,
            "offset": request.offset,
            "request_raw_sha256": request.raw_sha256,
            "response_raw_sha256": response.raw_sha256,
            "attempts": pending.attempts,
            "outcome": outcome,
            "error_code": error_code,
            "mutation_applied_once": mutation_applied,
            "response_latency_us": elapsed,
        })

    def _validate_meta(self, response: Frame, committed_valid: int,
                       session_valid: int, committed_count: int,
                       score_id: int, received: int) -> None:
        expected_valid = int(self.committed is not None)
        expected_count = len(self.committed.records) // 8 if self.committed else 0
        expected_score = self.committed.score_id if self.committed else 0
        expected_active = int(self.active is not None)
        expected_received = self.received_state
        actual = (committed_valid, committed_count, score_id, session_valid, received)
        expected = (expected_valid, expected_count, expected_score, expected_active, expected_received)
        if actual != expected:
            self.add("RESPONSE_META_MISMATCH", "error",
                     f"response state {actual} != reconstructed state {expected}", response)

    @staticmethod
    def _recovery_for(error: int) -> str:
        if error in (1, 9, 10, 12):
            return "Stop the failed exchange; issue ABORT or start a fresh nonzero-session BEGIN."
        if error in (5, 6, 7, 8):
            return "Do not advance state; restart with ABORT/new BEGIN and correct session/seq/offset."
        if error == 13:
            return "Keep the committed score; retry READ with an in-range event index."
        return "Correct the request according to PROTOCOL.md before starting a new transaction."

    def _apply_ack(self, request: Frame, response: Frame, committed_valid: int,
                   session_valid: int, committed_count: int, score_id: int,
                   received: int) -> None:
        payload = request.payload
        cmd = request.command
        if cmd == BEGIN:
            if request.session == 0 or request.seq != 0 or request.offset != 0 or len(payload) != 14:
                self.add("ACKED_INVALID_BEGIN", "error", "invalid BEGIN was ACKed", request)
                return
            sid, count, total, score_crc, sample_hz = struct.unpack("<IHHHI", payload)
            if not 1 <= count <= 512 or total != 8 * count or sample_hz != 48000:
                self.add("ACKED_INVALID_BEGIN", "error", "invalid BEGIN metadata was ACKed", request)
                return
            self.active = ActiveUpload(request.session, sid, count, total, score_crc, sample_hz)
            self.received_state = 0
        elif cmd == DATA:
            if (self.active is None or request.session != self.active.session or
                    request.seq != self.active.next_seq or
                    request.offset != len(self.active.records) or not 1 <= len(payload) <= 128):
                self.add("ACKED_INVALID_DATA", "error",
                         "DATA with wrong session/seq/offset/length was ACKed", request,
                         "ABORT or new BEGIN; resend from offset zero with seq one.")
                return
            self.active.records.extend(payload)
            self.active.next_seq += 1
            self.received_state = len(self.active.records)
        elif cmd == COMMIT:
            if (self.active is None or request.session != self.active.session or
                    request.seq != self.active.next_seq or request.offset != 0 or payload):
                self.add("ACKED_INVALID_COMMIT", "error", "invalid COMMIT was ACKed", request)
                return
            records = bytes(self.active.records)
            event_error = validate_records(records)
            if (len(records) != self.active.total_bytes or crc16(records) != self.active.score_crc or
                    event_error is not None):
                self.add("ACKED_BAD_SCORE", "error",
                         "COMMIT ACKed incomplete/CRC-invalid/event-invalid score", request)
                return
            commit = Commit(self.active.session, self.active.score_id, records.hex(), request.frame_index)
            self.committed = commit
            self.commits.append(commit)
            self.active = None
        elif cmd == ABORT:
            if request.offset != 0 or payload:
                self.add("ACKED_INVALID_ABORT", "error", "invalid ABORT was ACKed", request)
                return
            self.active = None
            self.received_state = 0
        elif cmd == STATUS:
            if request.offset != 0 or payload:
                self.add("ACKED_INVALID_STATUS", "error", "invalid STATUS was ACKed", request)
                return
            if self.committed is not None:
                self.committed.status_seen = True
        elif cmd == READ:
            if payload:
                self.add("ACKED_INVALID_READ", "error", "READ payload must be empty", request)
                return
            if self.committed is None or request.offset >= len(self.committed.records) // 8:
                self.add("ACKED_INVALID_READ", "error", "out-of-range READ was ACKed", request)
                return
            event = response.payload[META.size:]
            expected = self.committed.records[8 * request.offset:8 * request.offset + 8]
            if event != expected:
                self.add("READBACK_MISMATCH", "error",
                         f"READ index {request.offset} differs from committed upload", response)
            elif request.offset not in self.committed.read_indices:
                self.committed.read_indices.append(request.offset)
        self._validate_meta(response, committed_valid, session_valid,
                            committed_count, score_id, received)

    def finish(self) -> None:
        if self.pending is not None:
            self.add("MISSING_RESPONSE", "incomplete", "trace ends with an unanswered request",
                     self.pending.frame)
            self.transactions.append({
                "logical_index": len(self.transactions),
                "request_frame_index": self.pending.frame.frame_index,
                "response_frame_index": None,
                "command": self.pending.frame.command,
                "command_name": self.pending.frame.command_name,
                "session": self.pending.frame.session,
                "seq": self.pending.frame.seq,
                "offset": self.pending.frame.offset,
                "request_raw_sha256": self.pending.frame.raw_sha256,
                "response_raw_sha256": None,
                "attempts": self.pending.attempts,
                "outcome": "MISSING_RESPONSE",
                "error_code": None,
                "mutation_applied_once": False,
                "response_latency_us": None,
            })
        if self.active is not None:
            self.add("ACTIVE_UPLOAD_INCOMPLETE", "incomplete",
                     f"session {self.active.session} ends with {len(self.active.records)}/"
                     f"{self.active.total_bytes} bytes staged")
        if self.timestamps_available and self.first_timestamp_us is not None and self.last_timestamp_us is not None:
            if self.last_timestamp_us - self.first_timestamp_us > 30_000_000:
                self.add("TOTAL_TIMEOUT_EXCEEDED", "error", "trace exceeds the default 30 s transaction deadline")


def integer(value: Any, upper: int, label: str) -> int:
    if type(value) is not int or not 0 <= value <= upper:
        raise TraceError(f"invalid {label}")
    return value


def nonzero_integer(value: Any, upper: int, label: str) -> int:
    result = integer(value, upper, label)
    if result == 0:
        raise TraceError(f"invalid {label}")
    return result


def encode_score_document(document: Any) -> tuple[int, bytes]:
    if type(document) is not dict or set(document) != {"schema", "sample_hz", "score_id", "events"}:
        raise TraceError("expected score fields")
    if document["schema"] != 1 or type(document["schema"]) is not int:
        raise TraceError("expected score schema")
    if document["sample_hz"] != 48000 or type(document["sample_hz"]) is not int:
        raise TraceError("expected sample_hz")
    score_id = integer(document["score_id"], 0xFFFFFFFF, "score_id")
    events = document["events"]
    if type(events) is not list or not 1 <= len(events) <= 512:
        raise TraceError("expected capacity 1..512")
    result = bytearray()
    previous = 0
    for index, event in enumerate(events):
        if type(event) is not dict or set(event) != {"tick", "type", "channel", "note", "velocity"}:
            raise TraceError(f"expected event {index} fields")
        tick = integer(event["tick"], 0xFFFFFFFF, "tick")
        channel = integer(event["channel"], 15, "channel")
        note = integer(event["note"], 127, "note")
        velocity = integer(event["velocity"], 127, "velocity")
        if event["type"] not in ("note_on", "note_off") or tick < previous:
            raise TraceError(f"expected event {index} type/tick")
        kind = int(event["type"] == "note_off" or velocity == 0)
        result.extend(struct.pack("<IBBBB", tick, kind, channel, note, velocity))
        previous = tick
    return score_id, bytes(result)


def load_expected(path: Path | None, records_path: Path | None,
                  score_id_arg: int | None, session_arg: int | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    identities: list[dict[str, Any]] = []
    expected: list[dict[str, Any]] = []
    if path is not None:
        raw = path.read_bytes()
        identities.append({"role": "expected_json", "path": str(path), "bytes": len(raw), "sha256": sha256(raw)})
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        if type(document) is dict and set(document) == {"schema", "transactions"}:
            if document["schema"] != 1 or type(document["transactions"]) is not list:
                raise TraceError("expected transaction bundle schema")
            for index, item in enumerate(document["transactions"]):
                if type(item) is not dict or set(item) != {"session", "score"}:
                    raise TraceError(f"expected transaction {index} fields")
                session = nonzero_integer(item["session"], 0xFFFF, "expected session")
                sid, records = encode_score_document(item["score"])
                expected.append({"session": session, "score_id": sid, "records": records})
        else:
            sid, records = encode_score_document(document)
            session = None if session_arg is None else nonzero_integer(
                session_arg, 0xFFFF, "expected session"
            )
            expected.append({"session": session, "score_id": sid, "records": records})
    if records_path is not None:
        raw = records_path.read_bytes()
        identities.append({"role": "expected_records", "path": str(records_path), "bytes": len(raw), "sha256": sha256(raw)})
        if score_id_arg is None:
            raise TraceError("--score-id is required with --expected-records")
        error = validate_records(raw)
        if error:
            raise TraceError(f"expected records: {error}")
        if len(raw) > 4096:
            raise TraceError("expected records exceed 4096-byte/512-event capacity")
        session = None if session_arg is None else nonzero_integer(
            session_arg, 0xFFFF, "expected session"
        )
        expected.append({"session": session,
                         "score_id": integer(score_id_arg, 0xFFFFFFFF, "score_id"),
                         "records": raw})
    return expected, identities


def read_binary(path: Path, b64: bool, role: str) -> tuple[bytes, list[dict[str, Any]]]:
    container = path.read_bytes()
    identities = [{"role": role + ("_base64" if b64 else ""), "path": str(path),
                   "bytes": len(container), "sha256": sha256(container)}]
    if not b64:
        return container, identities
    try:
        compact = b"".join(container.split())
        decoded = base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise TraceError(f"invalid base64 {path}: {exc}") from exc
    identities.append({"role": role + "_decoded", "path": str(path),
                       "bytes": len(decoded), "sha256": sha256(decoded)})
    return decoded, identities


def parse_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw = path.read_bytes()
    chunks: list[dict[str, Any]] = []
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line, object_pairs_hook=unique_object)
        allowed = {"direction", "data_hex", "timestamp_us", "byte_times_us",
                   "idle_before_ms", "label"}
        if type(item) is not dict or not {"direction", "data_hex"} <= set(item) or set(item) - allowed:
            raise TraceError(f"JSONL line {line_no} fields")
        if item["direction"] not in ("tx", "rx") or type(item["data_hex"]) is not str:
            raise TraceError(f"JSONL line {line_no} direction/data")
        try:
            data = bytes.fromhex(item["data_hex"])
        except ValueError as exc:
            raise TraceError(f"JSONL line {line_no} hex") from exc
        if not data:
            raise TraceError(f"JSONL line {line_no} empty chunk")
        timestamp = item.get("timestamp_us")
        if timestamp is not None and (type(timestamp) is not int or timestamp < 0):
            raise TraceError(f"JSONL line {line_no} timestamp_us")
        byte_times = item.get("byte_times_us")
        if byte_times is not None:
            if (type(byte_times) is not list or len(byte_times) != len(data) or
                    any(type(value) is not int or value < 0 for value in byte_times) or
                    any(left > right for left, right in zip(byte_times, byte_times[1:]))):
                raise TraceError(f"JSONL line {line_no} byte_times_us")
            if timestamp is not None and byte_times[0] != timestamp:
                raise TraceError(f"JSONL line {line_no} timestamp_us != first byte_times_us")
        idle = item.get("idle_before_ms")
        if idle is not None and (not isinstance(idle, (int, float)) or isinstance(idle, bool) or idle < 0):
            raise TraceError(f"JSONL line {line_no} idle_before_ms")
        chunks.append({"direction": item["direction"], "data": data,
                       "timestamp_us": timestamp, "idle_before_ms": idle,
                       "byte_times_us": byte_times,
                       "source_line": line_no, "reset": False})
    if not chunks:
        raise TraceError("empty JSONL trace")
    return chunks, [{"role": "interleaved_jsonl", "path": str(path),
                     "bytes": len(raw), "sha256": sha256(raw)}]


def parse_legacy_capture(path: Path, b64: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Finding]]:
    raw, identities = read_binary(path, b64, "legacy_rtl_capture")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise TraceError("legacy capture is not ASCII") from exc
    if not lines or lines[0] != "START 40000000 115200" or not lines[-1].startswith("END "):
        raise TraceError("legacy capture START/END missing")
    chunks: list[dict[str, Any]] = []
    notices = [Finding(
        "LEGACY_RTL_CAPTURE", "notice",
        "RX records are mapped to PC tx and TX records to PC rx; this is simulator evidence, not hardware UART evidence.",
    )]
    case_timestamp: int | None = None
    tx_stream_end_us: int | None = None
    for line_no, line in enumerate(lines[1:-1], 2):
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "CASE":
            if len(parts) != 4:
                raise TraceError(f"legacy CASE line {line_no}")
            case_timestamp = int(parts[3]) // 40
            if parts[2] == "R":
                chunks.append({"reset": True, "direction": None, "data": b"",
                               "timestamp_us": case_timestamp, "idle_before_ms": None,
                               "source_line": line_no})
        elif parts[0] == "RX":
            raw_frame = bytes.fromhex(parts[2])
            idle_before = None
            if case_timestamp is not None and tx_stream_end_us is not None:
                idle_before = max(0, case_timestamp - tx_stream_end_us) / 1000.0
            chunks.append({"reset": False, "direction": "tx", "data": bytes.fromhex(parts[2]),
                           "timestamp_us": case_timestamp, "idle_before_ms": idle_before,
                           "source_line": line_no})
            if case_timestamp is not None:
                duration_us = (len(raw_frame) * 10_000_000 + 115199) // 115200
                tx_stream_end_us = case_timestamp + duration_us
        elif parts[0] == "TX":
            if len(parts) != 4:
                raise TraceError(f"legacy TX line {line_no}")
            chunks.append({"reset": False, "direction": "rx", "data": bytes.fromhex(parts[2]),
                           "timestamp_us": int(parts[3]) // 40, "idle_before_ms": None,
                           "source_line": line_no})
        elif parts[0] not in ("META", "EVENT"):
            raise TraceError(f"legacy record {parts[0]} at line {line_no}")
    return chunks, identities, notices


def compare_expected(commits: list[Commit], expected: list[dict[str, Any]], findings: list[Finding]) -> None:
    if not expected:
        findings.append(Finding(
            "EXPECTED_MISSING", "not_verifiable",
            "no independent expected score/records supplied; content correctness is NOT_VERIFIABLE",
        ))
        return
    if len(commits) != len(expected):
        findings.append(Finding(
            "COMMIT_COUNT_MISMATCH", "error",
            f"observed {len(commits)} commit(s), expected {len(expected)}",
        ))
    for index, pair in enumerate(zip(commits, expected)):
        actual, wanted = pair
        if wanted["session"] is not None and actual.session != wanted["session"]:
            findings.append(Finding("EXPECTED_SESSION_MISMATCH", "error",
                                    f"commit {index} session {actual.session} != {wanted['session']}"))
        if actual.score_id != wanted["score_id"]:
            findings.append(Finding("EXPECTED_SCORE_ID_MISMATCH", "error",
                                    f"commit {index} score_id {actual.score_id} != {wanted['score_id']}"))
        if actual.records != wanted["records"]:
            findings.append(Finding("UPLOAD_CONTENT_MISMATCH", "error",
                                    f"commit {index} uploaded bytes differ from independent expected records"))
        if not actual.status_seen:
            findings.append(Finding("STATUS_MISSING", "incomplete",
                                    f"commit {index} has no successful STATUS evidence"))
        wanted_indices = set(range(len(wanted["records"]) // 8))
        actual_indices = set(actual.read_indices)
        if actual_indices != wanted_indices:
            missing = sorted(wanted_indices - actual_indices)
            findings.append(Finding("READBACK_INCOMPLETE", "incomplete",
                                    f"commit {index} missing READ indices {missing[:16]}"
                                    + ("..." if len(missing) > 16 else "")))


def report_text(report: dict[str, Any]) -> str:
    lines = [
        f"T057 offline trace result: {report['status']}",
        f"exit_code: {report['exit_code']}",
        f"input_mode: {report['input_mode']}",
        f"frames: {report['summary']['frames']} (tx={report['summary']['tx_frames']}, rx={report['summary']['rx_frames']})",
        f"transactions: {report['summary']['transactions']}; commits: {report['summary']['commits']}; retransmissions: {report['summary']['retransmissions']}; duplicate_responses: {report['summary']['duplicate_responses']}",
        "",
        "Evidence limits:",
    ]
    for item in report["evidence_limits"]:
        lines.append(f"- {item['name']}: {item['status']} - {item['detail']}")
    lines.extend(["", "Findings:"])
    if not report["findings"]:
        lines.append("- none")
    for item in report["findings"]:
        location = ""
        if item.get("direction") is not None:
            location = f" [{item['direction']}@{item.get('byte_offset')}]"
        lines.append(f"- {item['severity']} {item['code']}{location}: {item['message']}")
        if item.get("recovery"):
            lines.append(f"  recovery: {item['recovery']}")
    lines.extend([
        "",
        "Claim boundary:",
        "- This result is offline software evidence only.",
        "- It does not prove FPGA UART hardware, playback, audible output, BLE, or real-time timing.",
    ])
    return "\n".join(lines) + "\n"


def verify(args: argparse.Namespace) -> int:
    output: Path = args.output
    if output.exists():
        raise TraceError("output already exists; refuse overwrite")
    output.mkdir(parents=True)
    findings: list[Finding] = []
    identities: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    input_mode: str
    interleaving_available = False
    if args.trace is not None:
        chunks, ids = parse_jsonl(args.trace)
        identities.extend(ids)
        input_mode = "interleaved_jsonl"
        interleaving_available = True
    elif args.legacy_capture is not None:
        chunks, ids, notices = parse_legacy_capture(args.legacy_capture, args.base64)
        identities.extend(ids)
        findings.extend(notices)
        input_mode = "legacy_rtl_capture"
        interleaving_available = True
    else:
        if args.tx is None or args.rx is None:
            raise TraceError("provide --trace, --legacy-capture, or both --tx and --rx")
        tx, ids = read_binary(args.tx, args.base64, "tx_stream")
        identities.extend(ids)
        rx, ids = read_binary(args.rx, args.base64, "rx_stream")
        identities.extend(ids)
        chunks = [
            {"direction": "tx", "data": tx, "timestamp_us": None, "byte_times_us": None,
             "idle_before_ms": None, "source_line": None, "reset": False},
            {"direction": "rx", "data": rx, "timestamp_us": None, "byte_times_us": None,
             "idle_before_ms": None, "source_line": None, "reset": False},
        ]
        input_mode = "separate_streams"
    expected, expected_ids = load_expected(args.expected_json, args.expected_records,
                                           args.score_id, args.session)
    identities.extend(expected_ids)
    parsers = {name: StreamParser(name, args.mode, findings) for name in ("tx", "rx")}
    timestamps_available = bool(chunks) and all(
        item.get("reset") or item.get("byte_times_us") is not None for item in chunks
    )
    ordered: list[tuple[int, Frame]] = []
    serial = 0
    checker = TransactionChecker(findings, timestamps_available, interleaving_available)
    for item in chunks:
        if item.get("reset"):
            checker.reset()
            continue
        emitted = parsers[item["direction"]].feed(
            item["data"], item["timestamp_us"], item["source_line"], item["idle_before_ms"],
            item.get("byte_times_us")
        )
        for frame in emitted:
            frame.frame_index = serial
            ordered.append((serial, frame))
            serial += 1
            if interleaving_available:
                checker.consume(frame)
    for parser in parsers.values():
        parser.finish()
    if not interleaving_available:
        findings.append(Finding(
            "INTERLEAVING_NOT_VERIFIABLE", "not_verifiable",
            "separate TX/RX streams cannot prove response order, stop-and-wait, retries, or latency",
        ))
        # Parse and expose both directions, but never invent a global order.
        ordered = [(i, frame) for i, frame in enumerate(parsers["tx"].frames + parsers["rx"].frames)]
    else:
        checker.finish()
    if not timestamps_available:
        findings.append(Finding(
            "TIMING_NOT_VERIFIABLE", "not_verifiable",
            "exact per-byte timestamps are absent; response latency and total deadline are NOT_VERIFIABLE",
        ))
    if interleaving_available:
        compare_expected(checker.commits, expected, findings)
    else:
        findings.append(Finding(
            "TRANSACTION_RECONSTRUCTION_NOT_VERIFIABLE", "not_verifiable",
            "upload/readback reconstruction requires an interleaved direction trace",
        ))
    errors = [item for item in findings if item.severity == "error"]
    incompletes = [item for item in findings if item.severity == "incomplete"]
    not_verifiable = [item for item in findings if item.severity == "not_verifiable"]
    warnings = [item for item in findings if item.severity == "warning"]
    if errors:
        status, exit_code = "INVALID", EXIT_INVALID
    elif incompletes:
        status, exit_code = "INCOMPLETE", EXIT_INCOMPLETE
    elif not_verifiable:
        status, exit_code = "NOT_VERIFIABLE", EXIT_NOT_VERIFIABLE
    elif warnings:
        status, exit_code = "RECOVERED", EXIT_PASS
    else:
        status, exit_code = "PASS", EXIT_PASS
    frames = [frame for _, frame in ordered]
    evidence_limits = [
        {"name": "independent_expected", "status": "VERIFIED" if expected else "NOT_VERIFIABLE",
         "detail": "expected data came from an external JSON/records input" if expected else "not supplied"},
        {"name": "global_order", "status": "VERIFIED" if interleaving_available else "NOT_VERIFIABLE",
         "detail": "direction records preserve one global order" if interleaving_available else "TX/RX stored separately"},
        {"name": "timing", "status": "VERIFIED" if timestamps_available else "NOT_VERIFIABLE",
         "detail": "exact timestamp present for every captured byte" if timestamps_available else "exact per-byte timestamps absent"},
        {"name": "hardware_uart", "status": "NOT_VERIFIABLE",
         "detail": "offline logs do not prove electrical or live FPGA UART behavior"},
        {"name": "playback_audio", "status": "NOT_VERIFIABLE",
         "detail": "ACK/COMMIT/READ do not prove scheduling, playback, or audible output"},
    ]
    report = {
        "schema": 1,
        "status": status,
        "exit_code": exit_code,
        "validation_level": "offline_software_only",
        "input_mode": input_mode,
        "parser_mode": args.mode,
        "file_identities": identities,
        "summary": {
            "frames": len(frames),
            "tx_frames": len(parsers["tx"].frames),
            "rx_frames": len(parsers["rx"].frames),
            "commits": len(checker.commits) if interleaving_available else None,
            "expected_commits": len(expected),
            "retransmissions": checker.retransmissions if interleaving_available else None,
            "duplicate_responses": checker.duplicate_responses if interleaving_available else None,
            "nacks": checker.nacks if interleaving_available else None,
            "transactions": len(checker.transactions) if interleaving_available else None,
        },
        "evidence_limits": evidence_limits,
        "commits": [asdict(item) for item in checker.commits] if interleaving_available else [],
        "transactions": checker.transactions if interleaving_available else [],
        "findings": [asdict(item) for item in findings],
        "hardware_pass_claim": False,
        "playback_pass_claim": False,
    }
    frame_rows = []
    for frame in frames:
        row = asdict(frame)
        row["diagnostics"] = [
            {"code": item.code, "severity": item.severity, "message": item.message}
            for item in findings
            if item.frame_index == frame.frame_index and item.direction == frame.direction
        ]
        frame_rows.append(row)
    (output / "frames.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_rows), encoding="utf-8"
    )
    (output / "transactions.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in checker.transactions),
        encoding="utf-8",
    )
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "report.txt").write_text(report_text(report), encoding="utf-8")
    print(json.dumps({"status": status, "exit_code": exit_code,
                      "report": str(output / "report.json")}, sort_keys=True))
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path,
                        help="interleaved JSONL chunks (PC-centric tx/rx)")
    parser.add_argument("--legacy-capture", type=Path,
                        help="historical RTL START/CASE/RX/TX capture")
    parser.add_argument("--tx", type=Path, help="separate raw PC->FPGA byte stream")
    parser.add_argument("--rx", type=Path, help="separate raw FPGA->PC byte stream")
    parser.add_argument("--base64", action="store_true",
                        help="decode --tx/--rx/--legacy-capture from strict Base64")
    parser.add_argument("--expected-json", type=Path,
                        help="independent score JSON or transaction bundle")
    parser.add_argument("--expected-records", type=Path,
                        help="independent raw 8-byte records")
    parser.add_argument("--score-id", type=int,
                        help="score id required with --expected-records")
    parser.add_argument("--session", type=int,
                        help="optional expected session for a single score/records input")
    parser.add_argument("--mode", choices=("strict", "recover"), default="strict")
    parser.add_argument("--output", type=Path, required=True,
                        help="new, nonexisting evidence directory")
    return parser


def write_input_failure(args: argparse.Namespace, exc: Exception) -> None:
    """Persist a machine-readable rejection when parsing fails after output creation."""
    output: Path = args.output
    if not output.is_dir() or (output / "report.json").exists():
        return
    identities: list[dict[str, Any]] = []
    for role, path in (
        ("interleaved_jsonl", args.trace),
        ("legacy_rtl_capture", args.legacy_capture),
        ("tx_stream", args.tx),
        ("rx_stream", args.rx),
        ("expected_json", args.expected_json),
        ("expected_records", args.expected_records),
    ):
        if path is not None and path.is_file():
            raw = path.read_bytes()
            identities.append({"role": role, "path": str(path),
                               "bytes": len(raw), "sha256": sha256(raw)})
    finding = Finding("INPUT_FORMAT_ERROR", "error", str(exc))
    report = {
        "schema": 1,
        "status": "INVALID",
        "exit_code": EXIT_INVALID,
        "validation_level": "offline_software_only",
        "input_mode": "unresolved_due_to_input_error",
        "parser_mode": args.mode,
        "file_identities": identities,
        "summary": {"frames": 0, "tx_frames": 0, "rx_frames": 0,
                    "commits": 0, "expected_commits": None,
                    "retransmissions": 0, "duplicate_responses": 0,
                    "nacks": [], "transactions": 0},
        "evidence_limits": [
            {"name": "input_parse", "status": "REJECTED", "detail": str(exc)},
            {"name": "hardware_uart", "status": "NOT_VERIFIABLE",
             "detail": "offline malformed input cannot prove hardware behavior"},
        ],
        "commits": [],
        "transactions": [],
        "findings": [asdict(finding)],
        "hardware_pass_claim": False,
        "playback_pass_claim": False,
    }
    (output / "frames.jsonl").write_text("", encoding="utf-8")
    (output / "transactions.jsonl").write_text("", encoding="utf-8")
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.txt").write_text(report_text(report), encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    choices = sum(value is not None for value in (args.trace, args.legacy_capture))
    if choices > 1 or (choices and (args.tx is not None or args.rx is not None)):
        parser.error("input modes are mutually exclusive")
    if (args.tx is None) != (args.rx is None):
        parser.error("--tx and --rx must be provided together")
    if args.base64 and args.trace is not None:
        parser.error("--base64 does not apply to JSONL --trace")
    if args.expected_json is not None and args.expected_records is not None:
        parser.error("choose one independent expected input")
    try:
        return verify(args)
    except (TraceError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        try:
            write_input_failure(args, exc)
        except OSError:
            pass
        print(f"FAIL: {exc}", file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
