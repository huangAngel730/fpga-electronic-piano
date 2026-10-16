"""One unchanged real file through frozen MIDI importer/encoder, new RTL plan."""
import argparse
import json
from pathlib import Path
import struct

from common import MIDI, MIDI_SHA, OLD_PY, identity, load, save

SESSION_TIMEOUT = 2000000  # 50ms isolated parameter, not the production 5s claim.
FRAME_TIMEOUT = 800000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    raw = MIDI.read_bytes()
    assert identity(MIDI)["sha256"] == MIDI_SHA
    importer = load("e3_frozen_importer", OLD_PY[0])
    pc = load("e3_frozen_codec", OLD_PY[1])
    oracle = load("e3_independent_midi", OLD_PY[2])
    doc, provenance = importer.convert_midi(raw, score_id=20180321)
    sid, records = pc.encode_score(doc)
    frames = list(pc.upload_frames(sid, records, 1510))
    checked = oracle.check(raw, doc, records, b"".join(frames))
    assert len(records) == 352 and len(doc["events"]) == 44
    save(out / "score.json", doc)
    save(out / "IMPORT_SOURCE_MAP.json", provenance)
    save(out / "MIDI_ORACLE.json", checked)
    (out / "original.mid").write_bytes(raw)
    (out / "records.bin").write_bytes(records)
    (out / "upload.bin").write_bytes(b"".join(frames))
    cases = []
    state = {"valid": 0, "count": 0, "score_id": 0, "pulses": 0,
             "active": 0, "received": 0, "last_error": 0}

    def add(label, packet=None, *, op="S", wait=0, error=0, active=None, received=None,
            publish=False, reset=False, header=None):
        if reset:
            state.update(valid=0, count=0, score_id=0, pulses=0, active=0, received=0, last_error=0)
        if publish:
            state.update(valid=1, count=44, score_id=sid, pulses=state["pulses"] + 1)
        if active is not None:
            state["active"] = active
        if received is not None:
            state["received"] = received
        if packet is not None or op == "I":
            state["last_error"] = error
        if packet is not None and header is None:
            _, cmd, session, seq, offset, _ = struct.unpack("<BBHHHH", packet[2:12])
            header = [cmd, session, seq, offset]
        cases.append({"id": len(cases) + 1, "label": label, "op": op,
                      "raw": packet.hex() if packet is not None else None,
                      "wait": wait, "error": error, "response_header": header, "state": dict(state)})

    add("power_reset", op="R", reset=True)
    received = 0
    for index, frame in enumerate(frames):
        if index == 0:
            add("real_begin", frame, active=1, received=0)
        elif index == len(frames) - 1:
            add("real_commit", frame, active=0, publish=True)
        else:
            received += len(frame) - 14
            add(f"real_data{index}", frame, received=received)
        if index in (0, 1, len(frames) - 1):
            add(f"exact_ack_replay_{index}", frame)
    add("real_public_read_all", op="Q")
    add("real_status", pc.frame(pc.STATUS, 1510, 0))
    for index in range(44):
        add(f"real_full_read_{index}", pc.frame(pc.READ, 1510, index, index))
    clean_last = len(cases)

    def begin(session, wrong_score_crc=False):
        payload = struct.pack("<IHHHI", sid, 44, len(records), pc.crc(records) ^ int(wrong_score_crc), 48000)
        add(f"session_{session}_begin", pc.frame(pc.BEGIN, session, 0, payload=payload), active=1, received=0)

    def retained(label, session):
        add(label + "_public_old_score", op="Q")
        for index in (0, 43):
            add(label + f"_uart_old_read_{index}", pc.frame(pc.READ, session, index, index))

    begin(1511)
    add("drop_frame_data1", pc.frame(pc.DATA, 1511, 1, 0, records[:128]), received=128)
    add("drop_frame_no_wire_packet", op="W", wait=40000)
    add("drop_frame_next_seq_rejected", pc.frame(pc.DATA, 1511, 3, 256, records[256:]), error=6)
    add("drop_frame_abort", pc.frame(pc.ABORT, 1511, 0), active=0, received=0)
    retained("drop_frame", 1511)
    begin(1512)
    bad = pc.frame(pc.DATA, 1512, 1, 0, records[:128])
    bad = bad[:-1] + bytes([bad[-1] ^ 1])
    add("frame_crc_rejected", bad, error=1)
    add("frame_crc_abort", pc.frame(pc.ABORT, 1512, 0), active=0, received=0)
    retained("frame_crc", 1512)
    begin(1513)
    partial = pc.frame(pc.DATA, 1513, 1, 0, records[:128])[:20]
    add("truncated_frame_timeout", partial, op="T", error=12)
    add("truncated_frame_abort", pc.frame(pc.ABORT, 1513, 0), active=0, received=0)
    retained("truncated_frame", 1513)
    begin(1514)
    add("session_timeout_data1", pc.frame(pc.DATA, 1514, 1, 0, records[:128]), received=128)
    add("session_timeout_parameter_50ms", op="I", wait=SESSION_TIMEOUT + 100,
        error=12, active=0, header=[2, 1514, 1, 0])
    retained("session_timeout", 1514)
    begin(1515, wrong_score_crc=True)
    received = 0
    for seq, offset in enumerate(range(0, len(records), 128), 1):
        payload = records[offset:offset + 128]
        received += len(payload)
        add(f"score_crc_data{seq}", pc.frame(pc.DATA, 1515, seq, offset, payload), received=received)
    add("score_crc_rejected", pc.frame(pc.COMMIT, 1515, 4), error=9, active=0)
    retained("score_crc", 1515)
    # New v1 COMMIT lifecycle fix, with cache replay and old-bank controls.
    begin(1517)
    first_data = pc.frame(pc.DATA, 1517, 1, 0, records[:128])
    add("incomplete_commit_data1", first_data, received=128)
    add("incomplete_commit_nack8_invalidates", pc.frame(pc.COMMIT, 1517, 2), error=8, active=0)
    add("after_nack8_exact_cached_data_must_not_ack", first_data, error=5)
    add("after_nack8_next_data_rejected", pc.frame(pc.DATA, 1517, 2, 128, records[128:256]), error=5)
    retained("incomplete_commit", 1517)
    for session, error in ((1520, 4), (1521, 5), (1522, 6)):
        begin(session)
        packet = pc.frame(pc.COMMIT, session + int(error == 5), 2 if error == 6 else 1,
                          payload=b"x" if error == 4 else b"")
        add(f"commit_semantic_nack{error}_invalidates", packet, error=error, active=0)
        add(f"after_nack{error}_data_rejected", pc.frame(pc.DATA, session, 1, 0, records[:128]), error=5)
        retained(f"commit_error{error}", session)
    # Fresh BEGIN recovery still publishes exactly once, same one real file.
    begin(1518)
    received = 0
    for seq, offset in enumerate(range(0, len(records), 128), 1):
        payload = records[offset:offset + 128]
        received += len(payload)
        add(f"fresh_recovery_data{seq}", pc.frame(pc.DATA, 1518, seq, offset, payload), received=received)
    recovery_commit = pc.frame(pc.COMMIT, 1518, 4)
    add("fresh_recovery_commit", recovery_commit, active=0, publish=True)
    add("fresh_recovery_commit_ack_replay", recovery_commit)
    retained("fresh_recovery", 1518)
    add("post_transfer_reset", op="R", reset=True)
    add("post_reset_status", pc.frame(pc.STATUS, 1516, 0))
    add("post_reset_public_empty", op="Q")
    for filename, subset in (("PLAN.txt", cases), ("PLAN_MUTANT.txt", cases[:clean_last])):
        with (out / filename).open("x", encoding="ascii", newline="\n") as stream:
            for case in subset:
                data = bytes.fromhex(case["raw"]) if case["raw"] is not None else b""
                stream.write(f"{case['op']} {case['id']} {len(data) if data else case['wait']}\n")
                if data:
                    stream.write(" ".join(f"{b:02x}" for b in data) + "\n")
    save(out / "EXPECTED.json", {"schema": "E3_REAL_FILE_UART_EXPECTED_V1", "midi": identity(MIDI),
         "score_id": sid, "record_bytes": len(records), "events": 44, "clean_last_case": clean_last,
         "frame_timeout_cycles": FRAME_TIMEOUT, "session_timeout_cycles": SESSION_TIMEOUT,
         "session_timeout_scope": "50ms parameterized isolated test, not new verification of default5s",
         "mutant_expected_exit": 1, "mutant_expected_first_difference": "RESPONSE_ERROR",
         "cases": cases, "NACK8_contract_status": "SUCCESSOR_FIX_WITH_OLD_SOURCE_PRESERVED",
         "commit_error_scope": "v1 semantic4/5/6/8; VERIFY9/10 retained; framing/version policy unchanged",
         "board_release_allowed": False})
    print(json.dumps({"events": 44, "cases": len(cases), "clean_last_case": clean_last, "original_midi_sha": MIDI_SHA}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
