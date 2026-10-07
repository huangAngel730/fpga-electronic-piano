"""Executable C bridge / Java client tests; FPGA/GATT peers here are simulated.
Sealed T057 replies are separately replayed, never claimed as newly run RTL.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code/software/score_transfer_v1"))
import score_transfer as old

# Fixed public stimulus/reference plan, independently sealed from the C output.
# Changing capture expectations cannot make a broken implementation pass.
PLAN_SHA256="6d87ea3bef47e080a5cef49105b76ecc725b9d55b49bed5e88942102fbacb6d1"


def crc(raw):
    value = 0xffff
    for byte in raw:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 65535
    return value


def frame(cmd, session, seq, offset=0, payload=b""):
    body = struct.pack("<BBHHHH", 1, cmd, session, seq, offset, len(payload)) + payload
    return b"\xa5\x5a" + body + struct.pack("<H", crc(body))


def fragments(raw, size=20):
    return [raw[i:i+size] for i in range(0, len(raw), size)]


class Process:
    def __init__(self, command):
        self.p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
        self.trace=[]

    def command(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        answer = []
        while True:
            value = self.p.stdout.readline()
            if not value:
                raise ValueError("child ended before END " + str(self.p.poll()))
            value = value.rstrip("\r\n")
            if value == "END":
                self.trace.append({"command":line,"answer":answer.copy()})
                return answer
            answer.append(value)

    def close(self):
        self.command("Q")
        self.p.stdin.close()
        self.p.wait(timeout=5)
        errors = self.p.stderr.read()
        if self.p.returncode or errors:
            raise ValueError("child error " + errors)


def bridge_capture(exe, destination):
    child = Process([str(exe)])
    rows = []

    def check(tag, command, expected=()):
        rows.append(dict(id=len(rows), tag=tag, command=command,
                         expected=list(expected), actual=child.command(command)))

    def reset():
        check("epoch_disconnect", "D")
        check("epoch_connect", "C")

    request = frame(2, 37, 9, 128, bytes(range(128)))
    for size in (1, 2, 3, 7, 19, 20, 21, 71, 142):
        reset()
        for part in fragments(request, size):
            check("NO_PARTIAL_UART", "G 0 " + part.hex())
        check("FULL_BYTE_PRESERVATION", "P", ["UART " + request.hex()])
    reset()
    for offset in (0, 128):
        raw = frame(2, 65535, offset, offset, bytes(range(offset, offset+128)))
        check("ALL_256_BINARY", "G 0 " + raw.hex())
        check("ALL_256_BINARY", "P", ["UART " + raw.hex()])
    reset()
    a = frame(5, 37, 0)
    b = frame(4, 37, 1)
    check("COALESCED", "G 0 " + (a+b).hex())
    check("COALESCED", "P", ["UART " + a.hex(), "UART " + b.hex()])
    reset()
    check("BOUNDED_QUEUE", "G 0 " + (a+b+a).hex(), ["LOCAL 3"])
    check("BOUNDED_QUEUE", "P", ["UART " + a.hex(), "UART " + b.hex()])
    reset()
    corrupt = bytearray(request)
    corrupt[-1] ^= 128
    check("CRC_REJECT", "G 0 " + corrupt.hex(), ["LOCAL 1"])
    check("CRC_REJECT", "P")
    check("QUARANTINE", "G 1 " + a.hex())
    check("QUARANTINE", "P")
    check("QUIET_RECOVERY", "T 2001", ["LOCAL 4"])
    check("QUIET_RECOVERY", "G 2001 " + a.hex())
    check("QUIET_RECOVERY", "P", ["UART " + a.hex()])
    reset()
    long = bytearray(request[:12]); long[10:12] = b"\xff\xff"
    check("OVERLONG_REJECT", "G 0 " + (long+a).hex(), ["LOCAL 2"])
    check("OVERLONG_REJECT", "P")
    for label, damaged in (
        ("MISSING_FRAGMENT", request[:20]+request[40:]),
        ("DUPLICATE_FRAGMENT", request[:20]+request[:20]+request[20:]),
        ("OUT_OF_ORDER", request[20:40]+request[:20]+request[40:])):
        reset()
        # Incomplete/malformed streams must never emit a valid-looking whole request.
        for part in fragments(damaged):
            actual = child.command("G 0 " + part.hex())
            rows.append(dict(id=len(rows), tag=label, command="damage fragment",
                             expected=None, actual=actual))
        check(label, "P")
    reset()
    check("DISCONNECT_EPOCH", "G 0 " + request[:20].hex())
    reset()
    check("DISCONNECT_EPOCH", "G 0 " + request[20:].hex())
    check("DISCONNECT_EPOCH", "P")
    reset()
    check("FRAGMENT_DEADLINE", "G 0 " + request[:10].hex())
    check("FRAGMENT_DEADLINE", "T 2000", ["LOCAL 4"])
    check("FRAGMENT_DEADLINE", "P")
    reset()
    check("WRAP_DEADLINE", "G 4294967290 " + request[:10].hex())
    check("WRAP_DEADLINE", "T 1994", ["LOCAL 4"])
    check("WRAP_DEADLINE", "P")
    reset()
    check("NO_FAKE_ACK", "G 0 " + a.hex())
    check("NO_FAKE_ACK", "P", ["UART " + a.hex()])
    reply = frame(128, 37, 0, payload=bytes(range(20)))
    for part in fragments(reply, 3):
        check("PEER_ONLY_NOTIFY", "U 0 " + part.hex())
    check("PEER_ONLY_NOTIFY", "P", ["NOTIFY " + p.hex() for p in fragments(reply)])
    reset()
    check("UART_DEADLINE", "U 0 " + reply[:10].hex())
    check("UART_DEADLINE", "T 20", ["LOCAL 4"])
    check("UART_DEADLINE", "P")
    reset()
    check("WRONG_DIRECTION", "G 0 " + reply.hex(), ["LOCAL 2"])
    check("WRONG_DIRECTION", "P")
    # Original raw bytes and SHA from the frozen T057 run; do not rerun its RTL.
    folder = ROOT / "code/docs/hardware/score_transfer_v1/evidence/run_j_v22g6p"
    manifest = json.loads((folder / "raw_manifest.json").read_text(encoding="utf-8"))
    decoded = {}
    for name in ("expected.json.b64", "normal__capture.txt.b64"):
        raw = base64.b64decode((folder/name).read_bytes())
        if hashlib.sha256(raw).hexdigest() != manifest[name]["sha256"]:
            raise ValueError("T057_SOURCE_SHA")
        decoded[name] = raw
    replies = {int(line.split()[1]): bytes.fromhex(line.split()[2])
               for line in decoded["normal__capture.txt.b64"].decode("ascii").splitlines()
               if line.startswith("TX ")}
    cases = json.loads(decoded["expected.json.b64"])["cases"]
    replay_count = 0
    for case in cases:
        if case["id"] not in replies or case["raw"] is None:
            continue
        raw = bytes.fromhex(case["raw"])
        try:
            old.parse_frame(raw)
        except ValueError:
            continue
        if not 1 <= raw[3] <= 6:
            continue
        reset()
        for piece in fragments(raw):
            check("T057_REPLAY_REQUEST", "G 0 " + piece.hex())
        check("T057_REPLAY_REQUEST", "P", ["UART " + raw.hex()])
        response = replies[case["id"]]
        old.parse_frame(response)
        for piece in fragments(response, 5):
            check("T057_REPLAY_RESPONSE", "U 0 " + piece.hex())
        check("T057_REPLAY_RESPONSE", "P", ["NOTIFY " + p.hex() for p in fragments(response)])
        replay_count += 1
    child.close()
    if replay_count < 512:
        raise ValueError("T057_REPLAY_COVERAGE")
    with destination.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row) + "\n")
        file.write(json.dumps(dict(end=True, count=len(rows), t057_replayed=replay_count)) + "\n")
    print("CAPTURE complete", len(rows), "checks", replay_count, "sealed T057 frame pairs")


def check_capture(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows)!=8523 or rows[-1].get("end") is not True or rows[-1].get("count") != 8522 or rows[-1].get("t057_replayed")!=660:
        raise ValueError("CAPTURE_COMPLETENESS")
    plan=[{k:v for k,v in row.items() if k!="actual"} for row in rows[:-1]]
    if hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest()!=PLAN_SHA256:
        raise ValueError("PUBLIC_REFERENCE_PLAN_CHANGED")
    failures = []
    for index, row in enumerate(rows[:-1]):
        if set(row) != {"id", "tag", "command", "expected", "actual"} or row["id"]!=index or not isinstance(row["actual"],list):
            raise ValueError("CAPTURE_STRUCTURE")
        if row["expected"] is None:
            correct = all(s in ("LOCAL 1", "LOCAL 2") for s in row["actual"])
        else:
            correct = row["actual"] == row["expected"]
        if not correct:
            failures.append((row["tag"],index,row["expected"],row["actual"]))
    if failures:
        print("REJECT", json.dumps(failures[:8]))
        raise ValueError("BEHAVIOR " + failures[0][0])
    print("PASS bridge checks", len(rows)-1, "T057 sealed pairs", rows[-1]["t057_replayed"])


class Peer:
    """Independent simulated FPGA truth, not an RTL or a hardware claim."""
    def __init__(self):
        self.committed = b""; self.sid=0; self.stage=bytearray(); self.session=0
        self.last=None; self.reply=None; self.expected_seq=0; self.expected_len=0

    def answer(self, raw):
        old.parse_frame(raw)
        _,cmd,session,seq,offset,length=struct.unpack("<BBHHHH",raw[2:12])
        payload=raw[12:-2]; code=0; event=b""
        if raw==self.last:
            return self.reply
        if cmd==4:
            self.session=0; self.stage.clear()
        elif cmd==1:
            if len(payload)!=14 or seq or offset or not session: code=4
            else:
                self.pending_sid,count,self.expected_len,self.score_crc,hz=struct.unpack("<IHHHI",payload)
                if not 1<=count<=512 or self.expected_len!=count*8 or hz!=48000: code=11
                else: self.session=session; self.expected_seq=1; self.stage.clear()
        elif cmd in (2,3):
            if session!=self.session or not self.session: code=5
            elif seq!=self.expected_seq: code=6
            elif cmd==2:
                if offset!=len(self.stage): code=7
                elif not payload or len(self.stage)+len(payload)>self.expected_len: code=11
                else: self.stage.extend(payload); self.expected_seq+=1
            elif len(self.stage)!=self.expected_len: code=8
            elif crc(self.stage)!=self.score_crc: code=9
            else:
                self.committed=bytes(self.stage); self.sid=self.pending_sid
                self.expected_seq+=1; self.session=0
        elif cmd==6:
            if offset>=len(self.committed)//8: code=13
            else: event=self.committed[offset*8:offset*8+8]
        elif cmd!=5: code=3
        meta=struct.pack("<BBBBHIH",cmd,code,bool(self.committed),bool(self.session),len(self.committed)//8,self.sid,len(self.stage))
        reply=frame(129 if code else 128,session,seq,offset,meta+(event if not code else b""))
        if not code: self.last=raw; self.reply=reply
        return reply


def java_tests(java, classes, bridge_exe, trace_dir):
    child=Process([str(java),"-cp",str(classes),"Harness"])
    checks=0
    def check(value, message):
        nonlocal checks
        checks+=1
        if not value: raise ValueError(message)
    document={"schema":1,"sample_hz":48000,"score_id":0xfedcba98,"events":[
        {"tick":i//2,"type":"note_off" if i%3==0 else "note_on","channel":i%16,"note":i%128,"velocity":i%128} for i in range(512)]}
    def encode(doc): return child.command("E "+json.dumps(doc,separators=(",",":")))
    check(child.command("G 0 1")==["LOCAL_PERMISSION_DENIED"],"PERMISSION_GATE")
    check(child.command("G 1 0")==["LOCAL_BLUETOOTH_DISABLED"],"BLUETOOTH_GATE")
    check(child.command("G 1 1")==["OK"],"SCAN_GATE")
    check(child.command("I module_A module_B")==["IDENTITY false"],"TWO_MODULE_TARGET")
    check(child.command("I module_A module_A")==["IDENTITY true"],"SELECTED_MODULE")
    records=b"".join(struct.pack("<IBBBB",e["tick"],int(e["type"]=="note_off" or not e["velocity"]),e["channel"],e["note"],e["velocity"]) for e in document["events"])
    check(encode(document)==["RECORDS "+str(document["score_id"])+" "+records.hex()],"JAVA_JSON_TRUTH")
    check(old.encode_score(document)[1]==records,"PC_JSON_TRUTH")
    for key,value in (("schema",2),("schema",True),("sample_hz",44100),("events",[]),("score_id",-1),("events",document["events"]+[document["events"][-1]])):
        bad=dict(document); bad[key]=value
        check(encode(bad)[0].startswith("ERROR "),"JSON_REJECT "+key)
    for key,value in (("channel",16),("note",128),("velocity",True),("tick",1.0),("type","cc"),("extra",0)):
        bad=dict(document); bad["events"]=[dict(document["events"][0])]; bad["events"][0][key]=value
        check(encode(bad)[0].startswith("ERROR "),"EVENT_REJECT "+key)
    check(child.command('E {"schema":1,"schema":1}')[0].startswith("ERROR "),"DUPLICATE_JSON")
    wire=Process([str(bridge_exe)]); wire.command("C")
    replies=child.command("S 65535 "+json.dumps(document)); peer=Peer(); ticks=0; sent=[]; states=[]; lost=False
    def transfer(raw):
        for part in fragments(raw): check(wire.command("G 0 "+part.hex())==[],"GATT_FRAGMENT")
        out=wire.command("P"); check(out==["UART "+raw.hex()],"COMPLETE_UART")
        return peer.answer(raw)
    while any(x.startswith("SEND ") for x in replies):
        states.extend(x for x in replies if x.startswith("STATE "))
        sends=[bytes.fromhex(x[5:]) for x in replies if x.startswith("SEND ")]
        check(len(sends)==1,"STOP_WAIT")
        raw=sends[0]; sent.append(raw); response=transfer(raw)
        # A real GATT write callback is not an application response.
        check(child.command("W")==["STATE TRANSPORT_ONLY"],"NO_CALLBACK_ACK")
        if raw[3]==2 and not lost:
            lost=True; ticks+=2000; replies=child.command("T "+str(ticks)); check(replies[-1]=="SEND "+raw.hex(),"IDENTICAL_RETRY"); continue
        # Wrong identity valid-CRC peer reply cannot advance client.
        wrong=bytearray(response); wrong[4]^=1; wrong[-2:]=struct.pack("<H",crc(wrong[2:-2]))
        check(child.command("N "+str(ticks)+" "+wrong.hex())==["STATE UNRELATED"],"SESSION_MATCH")
        wrong=bytearray(response); wrong[6]^=1; wrong[-2:]=struct.pack("<H",crc(wrong[2:-2]))
        check(child.command("N "+str(ticks)+" "+wrong.hex())==["STATE UNRELATED"],"SEQ_MATCH")
        for piece in fragments(response,7): check(wire.command("U 0 "+piece.hex())==[],"UART_RESPONSE")
        notifications=wire.command("P"); check(notifications==["NOTIFY "+p.hex() for p in fragments(response)],"NOTIFY_EXACT")
        replies=[]
        for line in notifications: replies+=child.command("N "+str(ticks)+" "+line[7:])
        ticks+=1
        check(ticks<8000,"FINITE_TRANSACTION")
    states.extend(replies)
    check("STATE PASS full readback 512" in states,"FULL_512_READBACK")
    check(peer.committed==records and len(records)==4096,"ATOMIC_EXACT_4096")
    check(any(sent[i]==sent[i-1] for i in range(1,len(sent))),"DUPLICATE_RETRY_BYTES")
    child.command("D"); wire.command("D"); wire.command("C")
    small=dict(document); small["events"]=document["events"][:1]
    replies=child.command("S 19 "+json.dumps(small)); first=bytes.fromhex(next(x[5:] for x in replies if x.startswith("SEND ")))
    for _ in range(2): child.command("T "+str(2000*(_+1)))
    check(child.command("T 6000")==["STATE FAIL ACK_DEADLINE"],"BOUNDED_RETRIES")
    child.command("S 20 "+json.dumps(small)); nack=frame(129,20,0,payload=struct.pack("<BBBBHIH",4,6,1,0,512,document["score_id"],0))
    check(child.command("N 1 "+nack.hex())==["STATE FAIL FPGA_NACK 6"],"REAL_NACK_FAILURE")
    child.command("S 21 "+json.dumps(small)); response=bytearray(frame(128,21,0,payload=struct.pack("<BBBBHIH",4,0,1,0,512,document["score_id"],0))); response[-1]^=1
    check(child.command("N 1 "+response.hex())==["STATE FAIL FRAME_CRC"],"APP_CRC_REJECT")
    child.command("S 22 "+json.dumps(small)); check(child.command("D")==["STATE FAIL LOCAL_DISCONNECT"],"DISCONNECT")
    check(child.command("N 1 "+first.hex())==[],"OLD_EPOCH_NOTIFY")
    child.command("S 23 "+json.dumps(small)); cancel=child.command("X 1")
    abort=bytes.fromhex(next(x[5:] for x in cancel if x.startswith("SEND "))); check(abort[3]==4 and old.parse_frame(abort)[2]==65535,"CANCEL_ABORT")
    check(child.command("N 2 "+peer.answer(abort).hex())==["STATE CANCELLED peer ABORT ACK"],"CANCEL_PEER_ACK")
    child.command("S 24 "+json.dumps(small)); check(child.command("S 25 "+json.dumps(small))==["ERROR BUSY/session"],"SINGLE_TRANSACTION")
    long=bytearray(12); long[:4]=b"\xa5\x5a\x01\x80"; long[10:12]=b"\xff\xff"
    check(child.command("N 1 "+long.hex())==["STATE FAIL RESPONSE_LENGTH"],"APP_BOUNDED_REASSEMBLY")
    child.close(); wire.close()
    trace_dir.mkdir()
    for name,records in (("java",child.trace),("c_bridge",wire.trace)):
        with (trace_dir/(name+".jsonl")).open("w",encoding="utf-8",newline="\n") as log:
            for item in records: log.write(json.dumps(item)+"\n")
    print("PASS real Java client / compiled C / simulated FPGA", checks,"checks; 512 full readback")


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("mode",choices=("capture","check","java")); parser.add_argument("--exe",type=Path); parser.add_argument("--capture",type=Path); parser.add_argument("--java",type=Path); parser.add_argument("--classes",type=Path); parser.add_argument("--trace-dir",type=Path)
    args=parser.parse_args()
    if args.mode=="capture": bridge_capture(args.exe,args.capture)
    elif args.mode=="check": check_capture(args.capture)
    else: java_tests(args.java,args.classes,args.exe,args.trace_dir)


if __name__=="__main__":
    try: main()
    except Exception as error:
        print("FAIL",type(error).__name__,str(error),file=sys.stderr); raise SystemExit(1)
