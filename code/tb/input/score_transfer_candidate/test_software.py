"""Codec/timeout unit tests and exact PC write replay against actual RTL captures.

Unit scripted transports are explicitly software-only, never hardware evidence.
Replay assertions use independently checked physical UART RTL responses.
"""
import argparse
import copy
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/"code/software/score_transfer_v1"))
import score_transfer as pc
from vectors import score


class ScriptedTransport:
    """Explicit software-only timeout/error fixture, not FPGA model."""
    def __init__(self, replies):
        self.replies=list(replies); self.pending=bytearray(); self.now=0; self.writes=[]

    def write(self, data):
        self.writes.append(data)
        if self.replies:
            self.pending.extend(self.replies.pop(0))
        return len(data)

    def read(self,n):
        self.now+=0.01
        raw=bytes(self.pending[:min(n,3)]); del self.pending[:len(raw)]
        return raw


class SoftwareTests(unittest.TestCase):
    def test_crc_golden(self):
        self.assertEqual(pc.crc(b"123456789"),0x29b1)
        from check_capture import crc as independent_crc
        self.assertEqual(independent_crc(b"123456789"),0x29b1)

    def test_schema_strict(self):
        valid=score(1,2)
        for change in (dict(schema=2),dict(sample_hz=44100),dict(events=[]),dict(events=score(1,513)["events"]),
                       dict(extra=1),dict(score_id=True),dict(schema=True),dict(sample_hz=48000.0)):
            invalid=copy.deepcopy(valid); invalid.update(change)
            with self.subTest(change=change):
                with self.assertRaises(ValueError): pc.encode_score(invalid)
        for key,value in (("channel",16),("note",128),("velocity",128),("tick",-1),("type","control"),
                          ("tick",True),("extra",0)):
            invalid=copy.deepcopy(valid); invalid["events"][0][key]=value
            with self.assertRaises(ValueError): pc.encode_score(invalid)
        invalid=copy.deepcopy(valid); del invalid["events"][0]["note"]
        with self.assertRaises(ValueError): pc.encode_score(invalid)
        invalid=copy.deepcopy(valid); invalid["events"][0]["tick"]=2; invalid["events"][1]["tick"]=1
        with self.assertRaises(ValueError): pc.encode_score(invalid)
        with self.assertRaises(ValueError): json.loads('{"schema":1,"schema":1}',object_pairs_hook=pc.unique_object)

    def test_order_normalization(self):
        valid=score(1,3); valid["events"][0]["velocity"]=0
        valid["events"][1]["type"]="note_off"; valid["events"][2]["note"]=61
        _,records=pc.encode_score(valid)
        self.assertEqual([records[i+4] for i in (0,8,16)],[1,1,0])
        self.assertEqual([records[i+6] for i in (0,8,16)],[60,61,61])

    def test_limits(self):
        _,records=pc.encode_score(score(1,512)); self.assertEqual(len(records),4096)
        packets=list(pc.upload_frames(1,records,65535,13))
        self.assertTrue(all(pc.parse_frame(raw)[4] is not None for raw in packets))
        for raw in packets:
            with self.assertRaises(ValueError): pc.parse_frame(raw[:-1])
        with self.assertRaises(ValueError): pc.frame(1,1,0,payload=b"x"*129)

    def test_ack_loss_and_timeout_software_only(self):
        request=pc.frame(pc.STATUS,1,0)
        ack=pc.frame(pc.ACK,1,0,payload=pc.META.pack(5,0,0,0,0,0,0))
        transport=ScriptedTransport([b"",ack])
        client=pc.Client(transport,ack_timeout=0.2,clock=lambda:transport.now)
        client.exchange(request)
        self.assertEqual(client.retry_count,1); self.assertEqual(transport.writes,[request,request])
        transport=ScriptedTransport([])
        client=pc.Client(transport,ack_timeout=0.05,retries=2,total_timeout=1,clock=lambda:transport.now)
        with self.assertRaises(TimeoutError): client.exchange(request)
        self.assertEqual(len(transport.writes),3)
        transport=ScriptedTransport([])
        client=pc.Client(transport,ack_timeout=0.5,retries=99,total_timeout=0.03,clock=lambda:transport.now)
        with self.assertRaises(TimeoutError): client.exchange(request)
        self.assertEqual(len(transport.writes),1)

    def test_nack_no_retry(self):
        request=pc.frame(pc.STATUS,1,0)
        nack=pc.frame(pc.NACK,1,0,payload=pc.META.pack(5,1,0,0,0,0,0))
        transport=ScriptedTransport([nack]); client=pc.Client(transport,clock=lambda:transport.now)
        with self.assertRaises(ValueError): client.exchange(request)
        self.assertEqual(len(transport.writes),1)


def replay(capture, expected):
    cases=json.loads(expected.read_text(encoding="utf-8"))["cases"]
    responses={int(line.split()[1]):bytes.fromhex(line.split()[2])
               for line in capture.read_text(encoding="ascii").splitlines() if line.startswith("TX ")}
    class RTLReplay(ScriptedTransport):
        def __init__(self,selected):
            super().__init__([]); self.index=0; self.selected=selected

        def write(self,data):
            case=self.selected[self.index]; self.index+=1
            if data.hex()!=case["raw"]:
                raise ValueError("PC write differs from actual RTL input")
            self.writes.append(data)
            # Drop original ACKs in exactly the cases actually followed by retry.
            lost=(case["score_id"] in (0,1) and case["label"].startswith("score1_") and
                  case["label"].endswith(("begin","data1","commit")))
            if not lost:
                self.pending.extend(responses[case["id"]])
            return len(data)

        def read(self,n):
            self.now+=0.0001
            raw=bytes(self.pending[:min(n,3)]); del self.pending[:len(raw)]
            return raw

    manifest=json.loads(expected.read_text(encoding="utf-8")); compared=retries=0
    for sid,session,chunk in ((1,1,128),(2,2,13),(15,15,7),(16,16,128)):
        selected=[case for case in cases if case["label"].startswith(f"score{sid}_") and case["raw"] is not None]
        transport=RTLReplay(selected); client=pc.Client(transport,ack_timeout=0.2,clock=lambda:transport.now)
        score_id,records=pc.encode_score(manifest["scores"][str(sid)])
        count=client.upload(score_id,records,session,chunk)
        if count!=len(records)//8 or transport.index!=len(selected) or client.retry_count!=(3 if sid==1 else 0):
            raise ValueError("RTL ACK replay missing comparisons/retries")
        compared+=count; retries+=client.retry_count
    print(f"PASS PC real-RTL recorded ACK replay compares={compared} retries={retries}; not live hardware")
    for label in ("bad_command","bad_score_crc_commit"):
        case=next(case for case in cases if case["label"]==label)
        transport=RTLReplay([case]); client=pc.Client(transport,clock=lambda:transport.now)
        try:
            client.exchange(bytes.fromhex(case["raw"]))
        except ValueError as exc:
            if "NACK" not in str(exc) or client.retry_count or transport.index!=1:
                raise
        else:
            raise ValueError("actual RTL NACK accepted by PC")
    print("PASS PC refuses two actual RTL NACK records without retry; not live hardware")


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--rtl-capture",type=Path); parser.add_argument("--expected",type=Path)
    args=parser.parse_args()
    if args.rtl_capture:
        replay(args.rtl_capture,args.expected)
    else:
        unittest.main(argv=[sys.argv[0]])
