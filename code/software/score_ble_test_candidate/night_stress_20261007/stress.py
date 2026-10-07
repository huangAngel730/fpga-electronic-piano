"""Compiled C/Java public-API stress, with explicitly synthetic score storage.

No device, radio, UART port or Android system is touched. Each child response
has a five-second deadline. Full transcripts are streamed rather than retained
in unbounded RAM. The peer below is a test oracle, not an FPGA implementation.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import queue
import random
import struct
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SEED = 590710


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def crc(raw):
    value = 65535
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 32768 else 0)) & 65535
    return value


def frame(cmd, session, seq, offset=0, payload=b""):
    body = struct.pack("<BBHHHH", 1, cmd, session, seq, offset, len(payload)) + payload
    return b"\xa5\x5a" + body + struct.pack("<H", crc(body))


def parse(raw):
    if not 14 <= len(raw) <= 142 or raw[:3] != b"\xa5\x5a\x01":
        raise ValueError("PEER_FORMAT")
    _, cmd, session, seq, offset, length = struct.unpack("<BBHHHH", raw[2:12])
    if length > 128 or length + 14 != len(raw) or crc(raw[2:-2]) != int.from_bytes(raw[-2:], "little"):
        raise ValueError("PEER_CRC_LENGTH")
    return cmd, session, seq, offset, raw[12:-2]


class Host:
    def __init__(self, command, name, output, log):
        self.name, self.log = name, log
        self.errors = (output / (name + ".stderr.log")).open("wb")
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.errors, text=True, encoding="utf-8", bufsize=1)
        self.answers = queue.Queue()

        def reader():
            for line in self.process.stdout:
                self.answers.put(line.rstrip("\r\n"))
            self.answers.put(None)

        threading.Thread(target=reader, daemon=True).start()

    def call(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        values = []
        deadline = time.monotonic() + 5
        while True:
            try:
                line = self.answers.get(timeout=max(0.001, deadline - time.monotonic()))
            except queue.Empty as error:
                raise ValueError("HOST_STEP_TIMEOUT " + self.name) from error
            if line is None:
                raise ValueError("HOST_EOF " + self.name)
            if line == "END":
                break
            values.append(line)
        self.log.write(canonical(dict(host=self.name, command=command, answer=values)) + "\n")
        return values

    def close(self):
        self.call("Q")
        self.process.stdin.close()
        code = self.process.wait(timeout=5)
        self.errors.close()
        return code


class SimPeer:
    """Independent synthetic atomic score storage, persistent across disconnects."""
    def __init__(self):
        self.committed = b""
        self.identity = 0
        self.session = 0
        self.stage = bytearray()
        self.last = self.reply = None
        self.expected_seq = self.expected_length = 0

    def answer(self, raw):
        cmd, session, seq, offset, payload = parse(raw)
        if raw == self.last:
            return self.reply
        code, record = 0, b""
        if cmd == 4:
            self.session = 0
            self.stage.clear()
        elif cmd == 1:
            if len(payload) != 14 or seq or offset or not session:
                code = 4
            else:
                self.pending_id, count, length, self.score_crc, hz = struct.unpack("<IHHHI", payload)
                if not 1 <= count <= 512 or length != count * 8 or hz != 48000:
                    code = 11
                else:
                    self.session, self.expected_seq, self.expected_length = session, 1, length
                    self.stage.clear()
        elif cmd in (2, 3):
            if session != self.session or not self.session:
                code = 5
            elif seq != self.expected_seq:
                code = 6
            elif cmd == 2:
                if offset != len(self.stage):
                    code = 7
                elif not payload or len(self.stage) + len(payload) > self.expected_length:
                    code = 11
                else:
                    self.stage.extend(payload)
                    self.expected_seq += 1
            elif len(self.stage) != self.expected_length:
                code = 8
            elif crc(self.stage) != self.score_crc:
                code = 9
            else:
                self.committed, self.identity = bytes(self.stage), self.pending_id
                self.session = 0
                self.expected_seq += 1
        elif cmd == 6:
            if offset >= len(self.committed) // 8:
                code = 13
            else:
                record = self.committed[offset * 8:offset * 8 + 8]
        elif cmd != 5:
            code = 3
        meta = struct.pack("<BBBBHIH", cmd, code, bool(self.committed), bool(self.session),
                           len(self.committed) // 8, self.identity, len(self.stage))
        response = frame(129 if code else 128, session, seq, offset, meta + (record if not code else b""))
        if not code:
            self.last, self.reply = raw, response
        return response


def document(identity, count):
    events = [dict(tick=i // 2, type="note_off" if i % 3 == 0 else "note_on",
                   channel=i % 16, note=(i * 17) % 128, velocity=i % 128)
              for i in range(count)]
    doc = dict(schema=1, sample_hz=48000, score_id=identity, events=events)
    records = b"".join(struct.pack("<IBBBB", e["tick"], int(e["type"] == "note_off" or e["velocity"] == 0),
                                   e["channel"], e["note"], e["velocity"]) for e in events)
    return canonical(doc), records


def plan():
    result = []
    # 1056 separate bounded transactions, including every capacity category.
    for i in range(1056):
        count = (511 if i % 16 == 0 else 512 if i % 16 == 1 else 1 + i % 2)
        action = ("success", "cancel", "disconnect", "success", "timeout", "success")[i % 6]
        result.append(dict(id=i, count=count, action=action, boundary=i % ((count + 15) // 16), after=bool(i % 2)))
    # All 32 DATA boundaries for a full 512-event score, before AND after reply.
    for boundary in range(32):
        for after in (False, True):
            result.append(dict(id=len(result), count=512, action="disconnect", boundary=boundary, after=after))
    # Explicit cancellation around BEGIN/DATA/COMMIT/READ response.
    for cmd in (1, 2, 3, 6):
        for after in (False, True):
            result.append(dict(id=len(result), count=2, action="cancel_cmd", command=cmd, after=after, boundary=0))
    return result


class Stress:
    def __init__(self, wire, java, output, checks):
        self.wire, self.java, self.output, self.checks = wire, java, output, checks
        self.rng = random.Random(SEED)
        self.check_count = self.byte_count = self.queue_peak = self.requests = self.readbacks = 0
        self.histogram = {}
        self.plan_hash = hashlib.sha256()
        self.transactions = []
        self.peer = SimPeer()

    def check(self, tag, actual, expected):
        row = dict(id=self.check_count, tag=tag, expected=expected, actual=actual)
        self.checks.write(canonical(row) + "\n")
        self.plan_hash.update((canonical({k: v for k, v in row.items() if k != "actual"}) + "\n").encode())
        self.check_count += 1
        self.histogram[tag] = self.histogram.get(tag, 0) + 1
        if actual != expected:
            raise ValueError("SEMANTIC " + tag + " expected=" + str(expected)[:200] + " actual=" + str(actual)[:200])

    def equal_bytes(self, tag, actual, expected):
        self.check(tag, actual.hex(), expected.hex())
        self.byte_count += len(expected)

    def fragments(self, raw, direction, now, random_split=True):
        start = 0
        while start < len(raw):
            size = self.rng.randint(1, 20) if random_split else 20
            self.check("FRAGMENT_ACCEPTED", self.wire.call(direction + " " + str(now & 0xffffffff) + " " + raw[start:start + size].hex()), [])
            start += size

    def request(self, raw, now):
        self.fragments(raw, "G", now)
        self.check("QUEUED_REQUEST", self.wire.call("S")[0].split()[2:4], ["1", "0"])
        self.queue_peak = max(1, self.queue_peak)
        result = self.wire.call("P")
        self.check("UART_COMPLETE_FRAME", result, ["UART " + raw.hex()])
        self.byte_count += len(raw)
        self.requests += 1
        # Counterexample host modifications are never supplied to the peer.
        return self.peer.answer(raw)

    def response(self, response, now):
        self.fragments(response, "U", now)
        self.check("PEER_REPLY_BYTE_EXACT", self.wire.call("P"), ["REPLY " + response.hex()])
        self.byte_count += len(response)
        lines = []
        for start in range(0, len(response), 20):
            lines += self.java.call("N " + str(now) + " " + response[start:start + 20].hex())
        return lines

    @staticmethod
    def send(lines):
        values = [bytes.fromhex(line[5:]) for line in lines if line.startswith("SEND ")]
        if len(values) != 1:
            raise ValueError("CLIENT_STOP_WAIT " + str(lines))
        return values[0]

    def reset(self):
        self.java.call("D")
        self.check("BRIDGE_DISCONNECT", self.wire.call("D"), [])
        self.check("BRIDGE_CONNECT", self.wire.call("C"), [])

    def transaction(self, item):
        self.reset()
        identity, session = 100000 + item["id"], item["id"] + 1
        doc, records = document(identity, item["count"])
        self.check("JAVA_SCORE_RECORDS", self.java.call("E " + doc), ["RECORDS " + str(identity) + " " + records.hex()])
        self.byte_count += len(records)
        lines = self.java.call("S " + str(session) + " " + doc)
        old, now, data_index, lost = self.peer.committed, 0, 0, False
        action = item["action"]
        if action == "timeout":
            raw = self.send(lines)
            self.check("CALLBACK_NOT_APP_ACK", self.java.call("W"), ["STATE TRANSPORT_ONLY"])
            for now in (2000, 4000):
                retry = self.java.call("T " + str(now))
                self.equal_bytes("BOUNDED_IDENTICAL_RETRY", self.send(retry), raw)
            self.check("ACK_DEADLINE", self.java.call("T 6000"), ["STATE FAIL ACK_DEADLINE"])
            self.equal_bytes("OLD_SCORE_PRESERVED", self.peer.committed, old)
            return dict(**item, terminal="ACK_DEADLINE", requests=0, steps=3)
        terminal = None
        for step in range(560):
            raw = self.send(lines)
            cmd, _, _, _, _ = parse(raw)
            target = ((action == "disconnect" and cmd == 2 and data_index == item["boundary"]) or
                      (action == "cancel" and cmd == 2 and data_index == item["boundary"]) or
                      (action == "cancel_cmd" and cmd == item["command"]))
            response = self.request(raw, now)
            self.check("CALLBACK_NOT_APP_ACK", self.java.call("W"), ["STATE TRANSPORT_ONLY"])
            # Correct CRC but unrelated identity/seq/offset must not advance.
            if step == 0 or (cmd == 2 and data_index == 0):
                for field in (4, 6, 8):
                    wrong = bytearray(response)
                    wrong[field] ^= 1
                    wrong[-2:] = struct.pack("<H", crc(wrong[2:-2]))
                    self.check("UNRELATED_REPLY", self.java.call("N " + str(now) + " " + wrong.hex()), ["STATE UNRELATED"])
            if target:
                if item["after"]:
                    self.response(response, now)
                if action == "disconnect":
                    self.check("DISCONNECTED_TRANSACTION", self.java.call("D"), ["STATE FAIL LOCAL_DISCONNECT"])
                    self.wire.call("D")
                    self.check("NO_OLD_NOTIFY", self.java.call("N " + str(now) + " " + response.hex()), [])
                    terminal = "DISCONNECT"
                else:
                    abort = self.send(self.java.call("X " + str(now)))
                    self.check("CANCEL_ABORT_SEQ", parse(abort)[:4], (4, session, 65535, 0))
                    answer = self.request(abort, now)
                    self.check("CANCEL_PEER_ACK", self.response(answer, now), ["STATE CANCELLED peer ABORT ACK"])
                    terminal = "CANCELLED"
                # READ cancellation occurs after commit, earlier cancellations do not.
                expected = records if cmd == 6 or (cmd == 3) else old
                self.equal_bytes("ATOMIC_FAILURE_OR_COMMIT", self.peer.committed, expected)
                break
            if action == "success" and cmd == 2 and not lost:
                # Peer applied DATA; first ACK lost; duplicate must be idempotent.
                lost = True
                now += 2000
                retry = self.send(self.java.call("T " + str(now)))
                self.equal_bytes("LOST_ACK_IDENTICAL_RETRY", retry, raw)
                self.equal_bytes("PEER_DUPLICATE_REPLY", self.request(retry, now), response)
            lines = self.response(response, now)
            if cmd == 6:
                self.readbacks += 1
            if any(line.startswith("STATE PASS full readback") for line in lines):
                self.check("FULL_READBACK_COUNT", lines[-1], "STATE PASS full readback " + str(item["count"]))
                self.equal_bytes("ATOMIC_SUCCESS_RECORDS", self.peer.committed, records)
                terminal = "PASS"
                break
            if cmd == 2:
                data_index += 1
            now += 1
        if terminal is None:
            raise ValueError("TRANSACTION_STEP_BOUND")
        return dict(**item, terminal=terminal, requests=step + 1, steps=step + 1)

    def edges(self):
        self.reset()
        a, b = frame(5, 60000, 0), frame(4, 60000, 1)
        self.check("COALESCED_TWO", self.wire.call("G 0 " + (a + b).hex()), [])
        self.check("QUEUE_CAPACITY_TWO", self.wire.call("S")[0].split()[2:4], ["2", "0"])
        self.queue_peak = 2
        self.check("QUEUE_BUSY", self.wire.call("G 0 " + a.hex()), ["LOCAL 3"])
        self.check("QUEUE_FIFO", self.wire.call("P"), ["UART " + a.hex(), "UART " + b.hex()])
        self.byte_count += len(a) + len(b)
        for offset in (0, 128):
            raw = frame(2, 60000, offset, offset, bytes(range(offset, offset + 128)))
            self.fragments(raw, "G", 0, False)
            self.check("ALL_256_PAYLOAD_BYTES", self.wire.call("P"), ["UART " + raw.hex()])
            self.byte_count += len(raw)
        reply = frame(128, 60000, 0, payload=bytes(range(128)))
        self.check("NOTIFY_UNAVAILABLE_QUEUE", self.wire.call("U 0 " + (reply + reply).hex()), [])
        self.check("NOTIFY_LONG_BUSY", self.wire.call("U 501 " + reply.hex()), ["LOCAL 3"])
        self.check("NOTIFY_QUEUE_BOUNDED", self.wire.call("S")[0].split()[2:4], ["0", "2"])
        self.check("NOTIFY_PRESERVE_REPLY", self.wire.call("P"), ["REPLY " + reply.hex()] * 2)
        self.byte_count += len(reply) * 2
        for source, limit in (("G", 2000), ("U", 20)):
            self.reset()
            raw = a if source == "G" else reply
            self.check("U32_PARTIAL", self.wire.call(source + " 4294967290 " + raw[:10].hex()), [])
            self.check("U32_BEFORE_DEADLINE", self.wire.call("T " + str((4294967290 + limit - 1) & 0xffffffff)), [])
            self.check("U32_TIMEOUT", self.wire.call("T " + str((4294967290 + limit) & 0xffffffff)), ["LOCAL 4"])
            self.check("TIMEOUT_NO_FRAME", self.wire.call("P"), [])
        for source in ("G", "U"):
            for damage in ("crc", "length", "direction"):
                self.reset()
                raw = bytearray(a if source == "G" else reply)
                error = 2
                if damage == "crc":
                    raw[-1] ^= 128
                    error = 1
                elif damage == "length":
                    raw = raw[:12]
                    raw[10:12] = b"\xff\xff"
                else:
                    raw = bytearray(reply if source == "G" else a)
                self.check("MALFORMED_" + damage, self.wire.call(source + " 0 " + raw.hex()), ["LOCAL " + str(error)])
                self.check("MALFORMED_NO_FRAME", self.wire.call("P"), [])
                self.check("POISON_ISOLATION", self.wire.call(source + " 1 " + (a if source == "G" else reply).hex()), [])
                self.check("POISON_NO_FRAME", self.wire.call("P"), [])
                self.check("POISON_QUIET_RECOVERY", self.wire.call("T " + str(2001 if source == "G" else 21)), ["LOCAL 4"])
        self.reset()
        self.check("PARTIAL_OLD_EPOCH", self.wire.call("G 0 " + a[:10].hex()), [])
        self.wire.call("D")
        self.wire.call("C")
        self.check("RECONNECTED_SUFFIX_ONLY", self.wire.call("G 0 " + a[10:].hex()), [])
        self.check("NO_CROSS_EPOCH_FRAME", self.wire.call("P"), [])
        self.check("TWO_TARGET_MISMATCH", self.java.call("I module_A module_B"), ["IDENTITY false"])
        self.check("TWO_TARGET_SELECTED", self.java.call("I module_B module_B"), ["IDENTITY true"])
        doc, _ = document(800000, 2)
        self.java.call("S 62000 " + doc)
        self.check("SINGLE_CLIENT_BUSY", self.java.call("S 62001 " + doc), ["ERROR BUSY/session"])
        self.java.call("D")
        # CRC, NACK, overlength, fragment timeout and silent transport-only.
        for case in ("crc", "nack", "length", "partial"):
            self.reset()
            lines = self.java.call("S 62000 " + doc)
            request = self.send(lines)
            response = bytearray(self.request(request, 0))
            if case == "crc":
                response[-1] ^= 1
                expected = ["STATE FAIL FRAME_CRC"]
            elif case == "nack":
                response[3], response[13] = 129, 6
                response[-2:] = struct.pack("<H", crc(response[2:-2]))
                expected = ["STATE FAIL FPGA_NACK 6"]
            elif case == "length":
                response = response[:12]
                response[10:12] = b"\xff\xff"
                expected = ["STATE FAIL RESPONSE_LENGTH"]
            else:
                self.check("APP_PARTIAL_REPLY", self.java.call("N 1 " + response[:10].hex()), [])
                retry = self.java.call("T 2001")
                self.equal_bytes("APP_FRAGMENT_EXPIRED_RETRY", self.send(retry), request)
                self.check("NO_CROSS_FRAGMENT_REPLY", self.java.call("N 2002 " + response[10:].hex()), [])
                self.check("NEW_WHOLE_REPLY_RECOVERS", bool(self.java.call("N 2003 " + response.hex())[-1].startswith("SEND ")), True)
                continue
            self.check("APP_REJECT_" + case, self.java.call("N 1 " + response.hex()), expected)


def capture(args):
    output = args.output
    with gzip.open(output / "hosts.jsonl.gz", "wt", encoding="utf-8", newline="\n") as hosts, \
            gzip.open(output / "checks.jsonl.gz", "wt", encoding="utf-8", newline="\n") as checks:
        wire = Host([str(args.exe)], "c", output, hosts)
        java = Host([str(args.java), "-cp", str(args.classes), "NightClient"], "java", output, hosts)
        stress = Stress(wire, java, output, checks)
        findings = []
        started = time.monotonic()
        try:
            stress.edges()
            for item in plan():
                if time.monotonic() - started >= 1700:
                    raise ValueError("TOTAL_STRESS_DEADLINE")
                result = stress.transaction(item)
                stress.transactions.append(result)
                checks.flush()
                if len(stress.transactions) % 100 == 0:
                    print("PROGRESS transactions=" + str(len(stress.transactions)), flush=True)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            findings.append(str(error))
        finally:
            codes = {}
            for name, child in (("c", wire), ("java", java)):
                try:
                    codes[name] = child.close()
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    child.process.kill()
                    codes[name] = -1
                    findings.append(str(error))
            summary = dict(end=True, seed=SEED, synthetic_peer=True,
                           plan_sha256=hashlib.sha256(canonical(plan()).encode()).hexdigest(),
                           reference_plan_sha256=stress.plan_hash.hexdigest(),
                           check_count=stress.check_count, byte_comparisons=stress.byte_count,
                           requests=stress.requests, readbacks=stress.readbacks,
                           queue_peak=stress.queue_peak, histogram=stress.histogram,
                           transactions=stress.transactions, child_exit_codes=codes, findings=findings)
            checks.write(canonical(summary) + "\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("CAPTURE_COMPLETE transactions=" + str(len(stress.transactions)), flush=True)
    # Semantic mismatches are rejected by a separate checker, not exit(compile).
    return 0


def check_capture(path, reference_hash=None, minimum=1000):
    reference = hashlib.sha256()
    count, first_error, summary = 0, None, None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("end") is True:
                if summary is not None:
                    raise ValueError("DUPLICATE_END")
                summary = row
                continue
            if summary is not None or set(row) != {"id", "tag", "expected", "actual"} or row["id"] != count:
                raise ValueError("CAPTURE_STRUCTURE")
            reference.update((canonical({k: v for k, v in row.items() if k != "actual"}) + "\n").encode())
            if row["actual"] != row["expected"] and first_error is None:
                first_error = "SEMANTIC " + row["tag"]
            count += 1
    if summary is None or count != summary["check_count"]:
        raise ValueError("CAPTURE_COMPLETENESS")
    if reference.hexdigest() != summary["reference_plan_sha256"] or (reference_hash and reference.hexdigest() != reference_hash):
        raise ValueError("REFERENCE_PLAN_SHA")
    if first_error:
        raise ValueError(first_error)
    if summary["findings"]:
        raise ValueError("RUNTIME_FINDING " + str(summary["findings"]))
    if len(summary["transactions"]) < minimum:
        raise ValueError("TRANSACTION_COVERAGE")
    if minimum:
        expected = plan()
        if len(summary["transactions"]) != len(expected) or summary["plan_sha256"] != hashlib.sha256(canonical(expected).encode()).hexdigest():
            raise ValueError("STIMULUS_PLAN_SHA")
        for actual, planned in zip(summary["transactions"], expected):
            if any(actual[key] != value for key, value in planned.items()):
                raise ValueError("TRANSACTION_IDENTITY")
        if summary["queue_peak"] != 2 or summary["child_exit_codes"] != {"c": 0, "java": 0} or summary["byte_comparisons"] < 100000:
            raise ValueError("COVERAGE_COUNTS")
    print("PASS", canonical({k: summary[k] for k in ("check_count", "byte_comparisons", "queue_peak", "readbacks")}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "check"))
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--java", type=Path)
    parser.add_argument("--classes", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--reference-hash")
    parser.add_argument("--minimum", type=int, default=1000)
    args = parser.parse_args()
    if args.mode == "capture":
        return capture(args)
    check_capture(args.capture, args.reference_hash, args.minimum)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, EOFError, TypeError) as error:
        print("FAIL", str(error))
        raise SystemExit(1)
