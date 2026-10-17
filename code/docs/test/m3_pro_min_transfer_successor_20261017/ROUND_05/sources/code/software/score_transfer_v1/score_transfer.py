"""T057 v1 PC codec and bounded stop-and-wait uploader; no audio synthesis."""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

MAGIC = b"\xa5\x5a"
HEADER = struct.Struct("<BBHHHH")
META = struct.Struct("<BBBBHIH")
BEGIN, DATA, COMMIT, ABORT, STATUS, READ = range(1, 7)
ACK, NACK = 0x80, 0x81
CAPACITY, CHUNK = 512, 128


def crc(data):
    """C-backed CCITT-FALSE, independently implemented bitwise in RTL/checker."""
    return binascii.crc_hqx(data, 0xffff)


def integer(value, upper, label):
    if type(value) is not int or not 0 <= value <= upper:
        raise ValueError(f"invalid {label}")
    return value


def encode_score(document):
    if type(document) is not dict or set(document) != {"schema", "sample_hz", "score_id", "events"}:
        raise ValueError("score fields")
    if type(document["schema"]) is not int or document["schema"] != 1:
        raise ValueError("schema")
    if type(document["sample_hz"]) is not int or document["sample_hz"] != 48000:
        raise ValueError("sample_hz")
    sid = integer(document["score_id"], 0xffffffff, "score_id")
    events = document["events"]
    if type(events) is not list or not 1 <= len(events) <= CAPACITY:
        raise ValueError("capacity 1..512")
    result, previous = bytearray(), 0
    for event in events:
        if type(event) is not dict or set(event) != {"tick", "type", "channel", "note", "velocity"}:
            raise ValueError("event fields")
        tick = integer(event["tick"], 0xffffffff, "tick")
        channel = integer(event["channel"], 15, "channel")
        note = integer(event["note"], 127, "note")
        velocity = integer(event["velocity"], 127, "velocity")
        if event["type"] not in ("note_on", "note_off") or tick < previous:
            raise ValueError("type/tick order")
        kind = int(event["type"] == "note_off" or velocity == 0)
        result.extend(struct.pack("<IBBBB", tick, kind, channel, note, velocity))
        previous = tick
    return sid, bytes(result)


def frame(command, session, seq, offset=0, payload=b"", version=1):
    if len(payload) > CHUNK:
        raise ValueError("payload exceeds 128")
    body = HEADER.pack(version, command, session, seq, offset, len(payload)) + payload
    return MAGIC + body + struct.pack("<H", crc(body))


def parse_frame(raw):
    if len(raw) < 14 or raw[:2] != MAGIC:
        raise ValueError("frame sync/length")
    version, cmd, session, seq, offset, length = HEADER.unpack(raw[2:12])
    if version != 1 or length > CHUNK or len(raw) != 14 + length:
        raise ValueError("frame version/length")
    if crc(raw[2:-2]) != int.from_bytes(raw[-2:], "little"):
        raise ValueError("frame CRC")
    return cmd, session, seq, offset, raw[12:-2]


def upload_frames(score_id, records, session, chunk=CHUNK):
    if not 1 <= session <= 65535 or not 1 <= chunk <= CHUNK:
        raise ValueError("session/chunk")
    yield frame(BEGIN, session, 0, payload=struct.pack("<IHHHI", score_id, len(records)//8,
                                                    len(records), crc(records), 48000))
    seq = 1
    for offset in range(0, len(records), chunk):
        yield frame(DATA, session, seq, offset, records[offset:offset+chunk])
        seq += 1
    yield frame(COMMIT, session, seq)


class Client:
    """Transport must expose write(bytes) and read(n)->bytes with finite timeout."""

    def __init__(self, transport, ack_timeout=0.5, retries=2, total_timeout=30,
                 clock=time.monotonic):
        if ack_timeout <= 0 or retries < 0 or total_timeout <= 0:
            raise ValueError("timeout/retry options")
        self.transport, self.clock = transport, clock
        self.ack_timeout, self.retries = ack_timeout, retries
        self.deadline = clock() + total_timeout
        self.sent, self.received, self.buffer = bytearray(), bytearray(), bytearray()
        self.retry_count = 0

    def receive(self, until):
        while self.clock() < min(until, self.deadline):
            # Stream buffering tolerates leading noise and partial reads.
            while len(self.buffer) >= 2 and self.buffer[:2] != MAGIC:
                del self.buffer[0]
            if len(self.buffer) >= 12:
                size = int.from_bytes(self.buffer[10:12], "little")
                if size > CHUNK:
                    del self.buffer[0]
                    continue
                if len(self.buffer) >= 14 + size:
                    raw = bytes(self.buffer[:14+size])
                    del self.buffer[:14+size]
                    return parse_frame(raw)
            piece = self.transport.read(256)
            self.received.extend(piece)
            self.buffer.extend(piece)
        raise TimeoutError("ACK/total deadline")

    def exchange(self, raw):
        cmd, session, seq, offset, _ = parse_frame(raw)
        for attempt in range(self.retries+1):
            if self.clock() >= self.deadline:
                raise TimeoutError("total deadline")
            count = self.transport.write(raw)
            self.sent.extend(raw[:count])
            if count != len(raw):
                raise IOError("short serial write")
            until = self.clock() + self.ack_timeout
            try:
                while True:
                    response, rs, rq, ro, payload = self.receive(until)
                    if (rs, rq, ro) != (session, seq, offset):
                        continue  # late unrelated reply; still finite deadline
                    if response not in (ACK, NACK) or len(payload) not in (META.size, META.size+8):
                        raise ValueError("response shape")
                    meta = META.unpack(payload[:META.size])
                    if meta[0] != cmd:
                        raise ValueError("response command")
                    if response == NACK or meta[1] != 0:
                        raise ValueError(f"NACK command={cmd} code={meta[1]}")
                    return meta, payload[META.size:]
            except TimeoutError:
                if attempt == self.retries:
                    raise
                self.retry_count += 1
        raise AssertionError("unreachable")

    def upload(self, score_id, records, session=1, chunk=CHUNK):
        for raw in upload_frames(score_id, records, session, chunk):
            self.exchange(raw)
        meta, _ = self.exchange(frame(STATUS, session, 0))
        if (meta[2], meta[4], meta[5]) != (1, len(records)//8, score_id):
            raise ValueError("committed metadata")
        compared = 0
        for index in range(len(records)//8):
            read_meta, event = self.exchange(frame(READ, session, index, index))
            if (read_meta[2], read_meta[4], read_meta[5]) != (1, len(records)//8, score_id):
                raise ValueError("readback score identity changed")
            if event != records[8*index:8*index+8]:
                raise ValueError(f"readback mismatch at {index}")
            compared += 1
        return compared


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key}")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("encode", "upload", "abort"))
    parser.add_argument("--score", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new nonexisting evidence directory")
    parser.add_argument("--port", help="explicit USB-TTL port, never MIDI/STAT/JTAG")
    parser.add_argument("--confirm-independent-uart", action="store_true")
    parser.add_argument("--session", type=int, default=1)
    parser.add_argument("--ack-timeout", type=float, default=0.5)
    parser.add_argument("--total-timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; refuse overwrite")
    sid, records = 0, b""
    if args.command != "abort":
        if not args.score:
            parser.error("--score required")
        sid, records = encode_score(json.loads(args.score.read_text(encoding="utf-8"),
                                               object_pairs_hook=unique_object))
    if args.command != "encode" and (not args.port or not args.confirm_independent_uart):
        parser.error("explicit --port and --confirm-independent-uart required before opening serial")
    args.output.mkdir(parents=True)
    client, error, compared, serial_port = None, None, 0, None
    try:
        if args.command == "encode":
            (args.output/"records.bin").write_bytes(records)
            (args.output/"upload.bin").write_bytes(b"".join(upload_frames(sid, records, args.session)))
        else:
            import serial  # optional hardware dependency, not needed for codec/RTL tests
            serial_port = serial.Serial(args.port, 115200, timeout=0.02, write_timeout=0.5)
            client = Client(serial_port, args.ack_timeout, args.retries, args.total_timeout)
            if args.command == "abort":
                client.exchange(frame(ABORT, args.session, 0))
            else:
                compared = client.upload(sid, records, args.session)
    except Exception as exc:
        error = str(exc)
    finally:
        if serial_port is not None:
            serial_port.close()
        if client is not None:
            (args.output/"tx.bin").write_bytes(client.sent)
            (args.output/"rx.bin").write_bytes(client.received)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in args.output.iterdir() if p.is_file()}
        receipt = dict(schema=1, command=args.command, error=error, exit_code=int(error is not None),
                       compared=compared, retries=client.retry_count if client else 0,
                       hashes=hashes, hardware_pass_claim=False)
        (args.output/"receipt.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(receipt))
    return receipt["exit_code"]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
