"""PC-generated real serial vectors and explicit externally determined expectations."""
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/"code/software/score_transfer_v1"))
import score_transfer as pc


def score(sid, count):
    # Four voices same tick, repeated pitch, distinct velocity, equal-tick Off/On.
    return dict(schema=1, sample_hz=48000, score_id=sid, events=[
        dict(tick=(i//8)*24000, type="note_on" if i % 8 < 4 else "note_off",
             channel=i % 4, note=60+i % 4, velocity=(1+i*17) % 127+1 if i % 8 < 4 else 0)
        for i in range(count)])


def build(directory):
    directory = Path(directory)
    cases, lines, documents = [], [], {}
    committed, sid, pulses, active, received, last_error = b"", 0, 0, 0, 0, 0

    def add(label, raw=None, error=0, op="S", wait=0, publish=None,
            active_after=None, received_after=None, reset=False):
        nonlocal committed, sid, pulses, active, received, last_error
        if reset:
            committed, sid, pulses, active, received, last_error = b"", 0, 0, 0, 0, 0
        if publish is not None:
            sid, committed = publish
            pulses += 1
        if active_after is not None:
            active = active_after
        if received_after is not None:
            received = received_after
        if raw is not None or op=="I":
            last_error = error
        idx = len(cases)+1
        cases.append(dict(id=idx, label=label, op=op, raw=raw.hex() if raw is not None else None,
                          error=error, committed_count=len(committed)//8, score_id=sid, pulses=pulses,
                          active=active, received=received, last_error=last_error))
        lines.append(f"{op} {idx} {len(raw) if raw is not None else wait}\n")
        if raw is not None:
            lines.append(" ".join(f"{b:02x}" for b in raw)+"\n")

    def upload(document, session, chunk=128, retransmit=False):
        score_id, records = pc.encode_score(document)
        prefix = f"score{score_id}"
        documents[str(score_id)] = document
        (directory/f"{prefix}.json").write_text(json.dumps(document, indent=2)+"\n", encoding="utf-8")
        packets = list(pc.upload_frames(score_id, records, session, chunk))
        pos = 0
        for i, raw in enumerate(packets):
            if i == 0:
                add(prefix+"_begin", raw, active_after=1, received_after=0)
            elif i == len(packets)-1:
                add(prefix+"_commit", raw, publish=(score_id, records), active_after=0)
            else:
                pos += len(raw)-14
                add(prefix+f"_data{i}", raw, received_after=pos)
            if retransmit:
                # Host deliberately discards first actual decoded ACK then retries.
                add(prefix+f"_lost_ack_retry{i}", raw)
        add(prefix+"_public_read_all", op="Q")
        add(prefix+"_status", pc.frame(pc.STATUS, session, 0))
        for i in range(len(records)//8):
            add(prefix+f"_read{i}", pc.frame(pc.READ, session, i, i))
        return records

    add("power_reset", op="R", reset=True)
    add("read_without_score", pc.frame(pc.READ, 1, 0), error=13)
    old = upload(score(1, 2), 1, retransmit=True)
    # Real codec normalizes zero-velocity NoteOn without sorting equal ticks.
    document = score(2, 17)
    document["events"][8]["type"] = "note_on"
    document["events"][8]["velocity"] = 0
    document["events"][9]["note"] = 60
    document["events"][-1].update(tick=0xffffffff, channel=15, note=127, velocity=127)
    new = upload(document, 2, chunk=13)
    add("read_out_of_range", pc.frame(pc.READ, 2, 99, 17), error=13)
    good = pc.frame(pc.STATUS, 2, 40)
    bad = good[:-1] + bytes([good[-1] ^ 1])
    add("bad_frame_crc", bad, error=1)
    add("bad_version", pc.frame(pc.STATUS, 2, 41, version=2), error=2)
    add("bad_command", pc.frame(99, 2, 42), error=3)
    add("bad_status_payload", pc.frame(pc.STATUS, 2, 43, payload=b"x"), error=4)
    add("oversized_header", b"\xa5\x5a"+struct.pack("<BBHHHH", 1, 2, 2, 44, 0, 129), error=4)
    add("oversized_drain_idle", op="W", wait=840000)
    add("recovery_status", pc.frame(pc.STATUS, 2, 45))
    add("truncated_header", good[:7], error=12, op="T")
    # Truncated header retained command and only partial identity. Override exactly
    # which header fields the RTL has received; no artificial completed frame.
    cases[-1]["response_identity"] = [2, 40, 0]  # seq low byte received (=40)
    add("empty_uart_idle", op="W", wait=40000)
    add("resync_after_truncate", pc.frame(pc.ABORT, 3, 0), active_after=0, received_after=0)
    for label, count, total, sample in (("capacity513", 513, 4104, 48000),
                                       ("empty_score", 0, 0, 48000),
                                       ("bad_total_length", 2, 15, 48000),
                                       ("bad_sample_hz", 2, 16, 44100)):
        add(label, pc.frame(pc.BEGIN, 4, 0, payload=struct.pack("<IHHHI", 3, count, total,
                                                              pc.crc(old), sample)), error=11)
    add("zero_session", pc.frame(pc.BEGIN, 0, 0, payload=struct.pack("<IHHHI", 3, 2, 16,
                                                                  pc.crc(old), 48000)), error=5)

    def begin_bad(session, payload, wrong_crc=False):
        add(f"bad{session}_begin", pc.frame(pc.BEGIN, session, 0,
            payload=struct.pack("<IHHHI", session, len(payload)//8, len(payload),
                                pc.crc(payload) ^ int(wrong_crc), 48000)),
            active_after=1, received_after=0)

    begin_bad(5, old)
    add("commit_before_data", pc.frame(pc.COMMIT, 5, 1), error=8)
    add("wrong_session", pc.frame(pc.DATA, 6, 1, payload=old), error=5)
    add("reordered_sequence", pc.frame(pc.DATA, 5, 2, payload=old), error=6)
    add("wrong_offset", pc.frame(pc.DATA, 5, 1, 1, old), error=7)
    add("zero_data", pc.frame(pc.DATA, 5, 1), error=4)
    add("over_remaining", pc.frame(pc.DATA, 5, 1, payload=old+b"x"), error=4)
    add("first_half", pc.frame(pc.DATA, 5, 1, payload=old[:8]), received_after=8)
    add("first_half_duplicate", pc.frame(pc.DATA, 5, 1, payload=old[:8]))
    conflict=bytearray(old[:8]); conflict[7]^=1
    add("conflicting_duplicate", pc.frame(pc.DATA, 5, 1, payload=bytes(conflict)), error=6)
    add("missing_packet_commit", pc.frame(pc.COMMIT, 5, 2), error=8)
    add("last_half", pc.frame(pc.DATA, 5, 2, 8, old[8:]), received_after=16)
    add("old_packet_duplicate", pc.frame(pc.DATA, 5, 1, payload=old[:8]), error=6)
    add("abort_preserves_committed", pc.frame(pc.ABORT, 5, 0), active_after=0, received_after=0)
    add("after_abort_public", op="Q")
    begin_bad(7, old, wrong_crc=True)
    add("bad_score_crc_data", pc.frame(pc.DATA, 7, 1, payload=old), received_after=len(old))
    add("bad_score_crc_commit", pc.frame(pc.COMMIT, 7, 2), error=9, active_after=0)
    add("after_crc_failure_public", op="Q")
    for session, label, byte_idx, value in ((8,"illegal_channel",5,16),(9,"illegal_note",6,128),
                                           (10,"illegal_velocity",7,128),(11,"illegal_type",4,2),
                                           (12,"zero_velocity_noteon",7,0)):
        payload=bytearray(old); payload[byte_idx]=value
        begin_bad(session, bytes(payload))
        add(label+"_data", pc.frame(pc.DATA, session, 1, payload=bytes(payload)), received_after=len(old))
        add(label+"_commit", pc.frame(pc.COMMIT, session, 2), error=10, active_after=0)
        add(label+"_public_preservation",op="Q")
    payload=struct.pack("<IBBBB", 100,0,0,60,100)+struct.pack("<IBBBB", 99,1,0,60,0)
    begin_bad(13, payload)
    add("tick_descend_data",pc.frame(pc.DATA,13,1,payload=payload),received_after=16)
    add("tick_descend_commit",pc.frame(pc.COMMIT,13,2),error=10,active_after=0)
    add("tick_descend_public_preservation",op="Q")
    begin_bad(14, old)
    add("partial_score_before_reset",pc.frame(pc.DATA,14,1,payload=old[:5]),received_after=5)
    add("reset_during_receive",op="R",reset=True)
    add("stale_data_after_reset",pc.frame(pc.DATA,14,1,payload=old),error=5)
    # Cancellation/new-BEGIN and all negative errors recover to a real success.
    upload(score(15, 9), 15, chunk=7)
    add("final_preservation_public",op="Q")
    begin_bad(18, old)
    idle_request=cases[-1]["raw"]
    add("actual_5s_session_timeout",op="I",wait=200000010,error=12,active_after=0)
    cases[-1]["reply_request"]=idle_request
    add("expired_session_data",pc.frame(pc.DATA,18,1,payload=old),error=5)
    add("after_session_timeout_public",op="Q")
    maximum = upload(score(16, 512), 16, chunk=128)
    add("final_public_512",op="Q")
    (directory/"plan.txt").write_text("".join(lines),encoding="ascii")
    manifest=dict(schema=1,cases=cases,scores=documents,maximum_records=len(maximum)//8,
                  hardware_claim=False,description="PC encode -> actual RTL serial simulation")
    (directory/"expected.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest
