"""Independent capture adjudicator: does not import PC codec or DUT internals."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def crc(data):
    value = 65535
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 65535
    return value


def decode(raw):
    if len(raw) < 14 or raw[:2] != b"\xa5\x5a":
        raise ValueError("reply sync/size")
    version, command, session, seq, offset, length = struct.unpack("<BBHHHH", raw[2:12])
    if version != 1 or length > 128 or length+14 != len(raw) or crc(raw[2:-2]) != int.from_bytes(raw[-2:],"little"):
        raise ValueError("reply CRC/version/length")
    return command,session,seq,offset,raw[12:-2]


def check(capture, expectation):
    expected=json.loads(Path(expectation).read_text(encoding="utf-8"))
    if expected.get("schema")!=1 or not expected.get("cases"):
        raise ValueError("empty/invalid expectations")
    # Independently derive records from the original JSON document, never use
    # the PC encoder output as the only expected event truth.
    golden_scores={}
    for sid,document in expected["scores"].items():
        if document["schema"]!=1 or document["sample_hz"]!=48000 or str(document["score_id"])!=sid:
            raise ValueError("JSON source identity")
        golden=bytearray(); previous=-1
        for event in document["events"]:
            tick=event["tick"]; vel=event["velocity"]; kind=event["type"]
            if tick<previous or not 0<=tick<=0xffffffff or not 0<=event["channel"]<=15 or not 0<=event["note"]<=127 or not 0<=vel<=127:
                raise ValueError("JSON source event")
            golden.extend(tick.to_bytes(4,"little"))
            golden.extend((int(kind=="note_off" or vel==0),event["channel"],event["note"],vel))
            previous=tick
        if not 1<=len(golden)//8<=512:
            raise ValueError("JSON source capacity")
        golden_scores[int(sid)]=bytes(golden)
    lines=Path(capture).read_text(encoding="ascii").splitlines()
    if not lines or lines[0]!="START 40000000 115200" or not lines[-1].startswith("END "):
        raise ValueError("capture start/end missing")
    buckets={}
    order=[]
    for line in lines[1:-1]:
        parts=line.split()
        if len(parts)<3 or parts[0] not in ("CASE","RX","TX","META","EVENT"):
            raise ValueError("unknown/truncated capture record")
        kind,case_id=parts[0],int(parts[1])
        if kind=="CASE":
            if case_id in buckets:
                raise ValueError("duplicate CASE")
            if len(parts)!=4:
                raise ValueError("missing system-cycle timestamp")
            buckets[case_id]=dict(CASE=parts[2:],RX=[],TX=[],META=[],EVENT=[])
            order.append(case_id)
        else:
            if case_id not in buckets or order[-1]!=case_id:
                raise ValueError("out-of-order capture identity")
            buckets[case_id][kind].append(parts[2:])
    if order!=[c["id"] for c in expected["cases"]]:
        raise ValueError("missing/duplicate/reordered cases")
    packets=reads=public_reads=negative=commits=0
    previous_cycle=-1; timeout_cycles=[]
    for case in expected["cases"]:
        identity=case["id"]; bucket=buckets[identity]; label=case["label"]
        if bucket["CASE"][0]!=case["op"]:
            raise ValueError(f"{label}: operation")
        begin_cycle=int(bucket["CASE"][1])
        if begin_cycle<=previous_cycle:
            raise ValueError("nonmonotonic case timestamp")
        previous_cycle=begin_cycle
        records=(bytes.fromhex(case["committed"]) if "committed" in case else
                 golden_scores[case["score_id"]] if case["committed_count"] else b"")
        if "committed_count" in case and case["committed_count"]!=len(records)//8:
            raise ValueError("invalid declared committed count")
        if records and records!=golden_scores[case["score_id"]]:
            raise ValueError("expected records differ from independent JSON truth")
        meta_expected=[int(bool(records)),len(records)//8,case["score_id"],case["pulses"],case["last_error"]]
        if bucket["META"]!=[[str(n) for n in meta_expected]]:
            raise ValueError(f"{label}: publication/error mismatch {bucket['META']} vs {meta_expected}")
        public_expected=[[str(i),f"{int.from_bytes(records[i*8:i*8+8],'little'):016x}"]
                         for i in range(len(records)//8)] if case["op"]=="Q" else []
        if bucket["EVENT"]!=public_expected:
            raise ValueError(f"{label}: public readback mismatch/zero/duplicates")
        public_reads+=len(public_expected)
        if case["raw"] is None and case["op"]!="I":
            if bucket["RX"] or bucket["TX"]:
                raise ValueError(f"{label}: unexpected serial traffic")
            continue
        expected_rx=[[case["raw"]]] if case["raw"] is not None else []
        if bucket["RX"]!=expected_rx or len(bucket["TX"])!=1 or len(bucket["TX"][0])!=2:
            raise ValueError(f"{label}: input identity/reply count")
        request=bytes.fromhex(case["raw"] or case["reply_request"])
        reply=bytes.fromhex(bucket["TX"][0][0])
        tx_cycle=int(bucket["TX"][0][1]); elapsed=tx_cycle-begin_cycle
        if tx_cycle<=begin_cycle:
            raise ValueError("reply predates request")
        previous_cycle=tx_cycle
        if case["op"]=="I":
            if not 199990000<=elapsed<=200010000:
                raise ValueError("5s session timeout not observed at physical UART")
            timeout_cycles.append(elapsed)
        if case["op"]=="T":
            expected_cycles=len(request)*40000000*10/115200+800000+len(reply)*347*10
            if abs(elapsed-expected_cycles)>2000:
                raise ValueError("20ms frame timeout not observed at physical UART")
        cmd,rs,rq,ro,payload=decode(reply)
        identity_expected=case.get("response_identity",[
            int.from_bytes(request[4:6],"little"),int.from_bytes(request[6:8],"little"),
            int.from_bytes(request[8:10],"little")])
        if [rs,rq,ro]!=identity_expected or cmd!=(0x81 if case["error"] else 0x80):
            raise ValueError(f"{label}: response identity/ACK/NACK")
        expected_payload=struct.pack("<BBBBHIH",request[3],case["error"],int(bool(records)),
                                     case["active"],len(records)//8,case["score_id"],case["received"])
        if request[3]==6 and not case["error"]:
            idx=int.from_bytes(request[8:10],"little")
            expected_payload+=records[idx*8:idx*8+8]
            reads+=1
        if payload!=expected_payload:
            raise ValueError(f"{label}: reply payload {payload.hex()} != {expected_payload.hex()}")
        negative+=int(case["error"]!=0); commits+=int(request[3]==3 and case["error"]==0)
        packets+=1
    if lines[-1]!=f"END {len(order)} {packets}" or not (reads>=512 and public_reads>=512 and negative>=20 and commits>=4):
        raise ValueError("end counts/zero or insufficient coverage")
    return dict(cases=len(order),packets=packets,serial_event_compares=reads,
                public_event_compares=public_reads,negative_transactions=negative,
                successful_commit_acks=commits,capture_sha256=hashlib.sha256(Path(capture).read_bytes()).hexdigest(),
                physical_timeout_elapsed_cycles=timeout_cycles,
                hardware_verified=False)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture",type=Path); parser.add_argument("expected",type=Path)
    args=parser.parse_args()
    try:
        print("PASS "+json.dumps(check(args.capture,args.expected),sort_keys=True))
    except (ValueError,KeyError,IndexError,OSError) as exc:
        print("FAIL "+str(exc)); sys.exit(1)
