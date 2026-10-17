"""Independent real-MIDI expected bytes vs external UART and public RAM capture."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct

from common import MIDI_SHA, OLD_PY, identity, load, save


class Difference(ValueError):
    def __init__(self, code, case=0, expected=None, actual=None):
        self.detail = {"code": code, "case": case, "expected": expected, "actual": actual}
        super().__init__(json.dumps(self.detail))


def need(ok, code, case=0, expected=None, actual=None):
    if not ok:
        raise Difference(code, case, expected, actual)


def crc(raw):
    value = 65535
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 65535
    return value


def response(raw, case):
    need(len(raw) in (26, 34) and raw[:2] == b"\xa5\x5a", "RESPONSE_SHAPE", case)
    version, cmd, session, seq, offset, length = struct.unpack("<BBHHHH", raw[2:12])
    need(version == 1 and length == len(raw) - 14, "RESPONSE_LENGTH_VERSION", case)
    need(crc(raw[2:-2]) == int.from_bytes(raw[-2:], "little"), "RESPONSE_CRC", case)
    return (cmd, session, seq, offset), raw[12:-2]


def check(capture, input_dir, out, clean_only):
    before = identity(capture)
    expected = json.loads((input_dir / "EXPECTED.json").read_text(encoding="utf-8"))
    midi = (input_dir / "original.mid").read_bytes()
    need(hashlib.sha256(midi).hexdigest() == MIDI_SHA, "REAL_MIDI_IDENTITY")
    oracle = load("e3_readonly_oracle", OLD_PY[2])
    notes, origins, _ = oracle.expected_notes(oracle.smf_inventory(midi))
    golden = b"".join(struct.pack("<IBBBB", e["tick"], int(e["type"] == "note_off"),
                                  e["channel"], e["note"], e["velocity"]) for e in notes)
    need(len(golden) == 352 and golden == (input_dir / "records.bin").read_bytes(), "INDEPENDENT_GOLDEN_BYTES")
    cases = expected["cases"][:expected["clean_last_case"]] if clean_only else expected["cases"]
    actual = defaultdict(lambda: {"in": [], "out": [], "events": [], "tx": []})
    byte_records = []
    active = 0
    last_cycle = 0
    ended = False
    starts = []
    with capture.open(encoding="ascii") as stream:
        need(stream.readline().strip() == "START 40000000 115200 800000 2000000", "CAPTURE_HEADER")
        for line in stream:
            need(not ended, "AFTER_END")
            p = line.split()
            if p[0] == "CASE":
                need(len(p) == 4, "CASE_SHAPE")
                active = int(p[1])
                starts.append(active)
                need(active == len(starts) and active <= len(cases), "CASE_ORDER", active)
                need(p[2] == cases[active - 1]["op"], "CASE_OPERATION", active)
                actual[active]["start_cycle"] = int(p[3])
            elif p[0] == "BYTE":
                need(len(p) == 5 and p[1] in ("IN", "OUT") and int(p[2]) == active, "BYTE_SHAPE", active)
                cycle, value = int(p[3]), int(p[4], 16)
                need(cycle >= last_cycle and 0 <= value <= 255 and len(p[4]) == 2, "BYTE_ORDER_RANGE", active)
                last_cycle = cycle
                actual[active][p[1].lower()].append((cycle, value))
                byte_records.append((active, p[1], cycle, value))
            elif p[0] == "TX":
                need(len(p) == 4 and int(p[1]) == active, "TX_SHAPE", active)
                actual[active]["tx"].append(bytes.fromhex(p[2]))
                need(int(p[3]) == last_cycle, "TX_BOUNDARY_CYCLE", active)
            elif p[0] == "META":
                need(len(p) == 7 and int(p[1]) == active and "meta" not in actual[active], "META_SHAPE", active)
                actual[active]["meta"] = [int(v) for v in p[2:]]
            elif p[0] == "EVENT":
                need(len(p) == 4 and int(p[1]) == active and len(p[3]) == 16, "EVENT_SHAPE", active)
                actual[active]["events"].append((int(p[2]), int(p[3], 16).to_bytes(8, "little")))
            elif p[0] == "END":
                need(len(p) == 4 and int(p[1]) == len(cases) and int(p[3]) >= last_cycle, "END_SHAPE")
                end_packets, end_cycle = int(p[2]), int(p[3])
                ended = True
            else:
                raise Difference("UNKNOWN_CAPTURE_ROW", active, actual=line.strip())
    need(ended and starts == list(range(1, len(cases) + 1)), "INCOMPLETE_CAPTURE")
    proofs = []
    last_input_cycle = 0
    replay = {}
    packet_count = 0
    read_indices = []
    for case in cases:
        cid = case["id"]
        got = actual[cid]
        sent = bytes(v for _, v in got["in"])
        need(sent.hex() == (case["raw"] or ""), "ACTUAL_INPUT_BYTES", cid)
        if got["in"]:
            last_input_cycle = got["in"][-1][0]
        want_reply = case["op"] in ("S", "T", "I")
        need(len(got["tx"]) == int(want_reply), "MISSING_DUPLICATE_REPLY", cid)
        if want_reply:
            packet_count += 1
            reply = got["tx"][0]
            need(reply == bytes(v for _, v in got["out"]), "PIN_BYTE_FRAME_MISMATCH", cid)
            hdr, payload = response(reply, cid)
            meta = struct.unpack("<BBBBHIH", payload[:12])
            cmd, session, seq, offset = case["response_header"]
            need(hdr[1:] == (session, seq, offset), "RESPONSE_IDENTITY", cid)
            need(meta[:2] == (cmd, case["error"]), "RESPONSE_ERROR", cid,
                 [cmd, case["error"]], list(meta[:2]))
            need(hdr[0] == (0x81 if case["error"] else 0x80), "ACK_NACK_KIND", cid)
            state = case["state"]
            need(meta[2:] == tuple(state[k] for k in ("valid", "active", "count", "score_id", "received")),
                 "RESPONSE_METADATA", cid, state, list(meta))
            is_read = cmd == 6 and not case["error"]
            need(len(payload) == (20 if is_read else 12), "READ_RESPONSE_LENGTH", cid)
            if is_read:
                need(payload[12:] == golden[8 * offset:8 * offset + 8], "UART_READ_RECORD", cid)
                if cid <= expected["clean_last_case"]:
                    read_indices.append(offset)
            if case["label"].startswith("exact_ack_replay_"):
                need(sent in replay and replay[sent] == reply, "ACK_REPLAY_NOT_IDENTICAL", cid)
            if not case["error"] and sent:
                replay[sent] = reply
            if case["op"] in ("T", "I"):
                limit = expected["frame_timeout_cycles"] if case["op"] == "T" else expected["session_timeout_cycles"]
                need(got["out"][0][0] - last_input_cycle >= limit, "TIMEOUT_BEFORE_BOUND", cid)
            proofs.append({"case": cid, "label": case["label"], "error": case["error"],
                           "reply_sha256": hashlib.sha256(reply).hexdigest(), "first_reply_cycle": got["out"][0][0],
                           "last_reply_cycle": got["out"][-1][0], "metadata": list(meta)})
        else:
            need(not got["out"], "UNEXPECTED_OUTPUT_BYTES", cid)
        state = case["state"]
        need(got.get("meta") == [state[k] for k in ("valid", "count", "score_id", "pulses", "last_error")],
             "PUBLIC_METADATA", cid, state, got.get("meta"))
        if case["op"] == "Q":
            want_count = state["count"] if state["valid"] else 0
            need([i for i, _ in got["events"]] == list(range(want_count)), "PUBLIC_READ_COVERAGE", cid)
            need(b"".join(v for _, v in got["events"]) == (golden if want_count else b""), "PUBLIC_RAM_BYTES", cid)
        else:
            need(not got["events"], "UNEXPECTED_PUBLIC_EVENT", cid)
    need(packet_count == end_packets and read_indices == list(range(44)), "COMPLETE_UART_READ_COVERAGE")
    need(identity(capture) == before, "CAPTURE_DRIFT")
    with (out / "CLEAN_INTERLEAVED.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for cid, direction, cycle, value in byte_records:
            if cid <= expected["clean_last_case"]:
                item = {"direction": "tx" if direction == "IN" else "rx", "data_hex": f"{value:02x}",
                        "timestamp_us": cycle // 40, "byte_times_us": [cycle // 40], "label": f"case_{cid}"}
                stream.write(json.dumps(item) + "\n")
    return {"passed": True, "level": "L2_ISOLATED_RTL_UART_RAM", "midi_sha256": MIDI_SHA,
            "events": 44, "records_bytes": 352, "cases": len(cases), "packets": packet_count,
            "capture_cycles": end_cycle, "clean_full_read_indices": read_indices,
            "public_ram_full_snapshots": sum(c["op"] == "Q" and c["state"]["valid"] for c in cases),
            "negative_responses": [p for p in proofs if p["error"]], "reply_proofs": proofs,
            "source_map_events": len(origins), "byte_timestamp_phase": "both directions midpoint of stop bit, sys_clk cycles",
            "session_timeout": "50ms isolated parameter, default5s not reexecuted",
            "NACK8_contract_divergence": "KNOWN_UNRESOLVED_NOT_EXERCISED", "capture": before,
            "hardware_UART_ACK_READ": "PENDING", "playback_PCM": "NOT_CLAIMED", "board_release_allowed": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", required=True, type=Path)
    ap.add_argument("--inputs", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--clean-only", action="store_true")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        result = check(args.capture, args.inputs, args.output, args.clean_only)
        code = 0
    except (Difference, ValueError, KeyError, TypeError, OSError) as exc:
        result = {"passed": False, "first_difference": exc.detail if isinstance(exc, Difference) else {"code": str(exc)},
                  "board_release_allowed": False}
        code = 1
    save(args.output / "RESULT.json", result)
    print(json.dumps({"passed": result["passed"], "first_difference": result.get("first_difference")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
