"""Independent public pre-NBA buffer ledger and physical PT8211 decoder.

No hierarchy probes, no DUT max-cycle summary and no golden from serial output.
The diagnostic producer is not the R05 MIDI/voice chain.
"""
import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
from pathlib import Path

FIELDS = "cycle epoch rst_n tick frame_tick request req_id pcm_valid pcm_ready pcm_id left right clip pending play_l play_r frames requests commits underflow bclk ws din".split()
FLAGS = "rst_n tick frame_tick request pcm_valid pcm_ready clip pending bclk ws din".split()
HEADER = "C_PCM_SERIAL_PUBLIC_V1,NEW_MODULE_RTL_FIXTURE,40000000,PRE_NBA,PT8211_LSBJ"


def require(value, diagnostic):
    if not value:
        raise ValueError(diagnostic)


def signed16(word):
    return word - 65536 if word >= 32768 else word


def quantize(value):
    require(type(value) is int and -(1 << 23) <= value < (1 << 23), "PCM24_RANGE")
    return max(-32768, min(32767, (value + 128) // 256))


def vector(index):
    return [0, 8388607, -8388608, 127, 128, 129, -127, -128, -129,
            8388480, 8388479, -8388481, 1234567, -2345678, 7654321,
            -6543210][index % 16]


def digital_latency(request_cycle, serial_complete_cycle):
    require(type(request_cycle) is int and type(serial_complete_cycle) is int
            and 0 <= request_cycle <= serial_complete_cycle, "LATENCY_CALENDAR")
    elapsed=serial_complete_cycle-request_cycle
    require(elapsed<=400000,"DIGITAL_LATENCY_EXCEEDS_10MS")
    return elapsed


def check(path, *, fixture_inputs=True, expected_underflows=2):
    raw = Path(path).read_bytes()
    lines = raw.decode("ascii").splitlines()
    require(lines and lines[0] == HEADER, "CAPTURE_HEADER_OR_EVIDENCE_KIND")
    require(len(lines) > 2 and lines[-1].startswith("END,"), "MISSING_END")
    end = lines[-1].split(",")
    require(len(end) == 2 and end[1].isdigit(), "END_FORMAT")
    rows = []
    for number, line in enumerate(lines[1:-1], 2):
        values = line.split(",")
        require(len(values) == len(FIELDS), f"ROW_FIELD_COUNT:{number}")
        try:
            nums = list(map(int, values))
        except ValueError as exc:
            raise ValueError(f"UNKNOWN_OR_NONINTEGER:{number}") from exc
        row = dict(zip(FIELDS, nums))
        require(row["cycle"] == len(rows)+1, "MISSING_OR_DUPLICATE_CYCLE")
        require(all(row[k] in (0, 1) for k in FLAGS), "FLAG_RANGE")
        require(all(-(1<<23) <= row[k] < (1<<23) for k in ("left", "right", "play_l", "play_r")), "PCM24_RANGE")
        require(all(0 <= row[k] < (1<<32) for k in ("req_id", "pcm_id", "frames", "requests", "commits", "underflow")), "COUNTER_ID_RANGE")
        require(0 <= row["epoch"] <= 2, "EPOCH_RANGE")
        rows.append(row)
    require(rows and int(end[1]) == len(rows), "END_COUNT")
    epochs = {}
    state = None
    last_epoch = 0
    prior_rst = 0
    prior_row = None
    pending = None
    held = (0, 0)
    held_id = None
    held_clip = 0
    ever = False
    active = False
    counter = [0, 0, 0, 0]  # frames requests commits underflow
    req_id = req_pulse = phase = tick_value = 0
    ledger = {}
    adoptions = {}
    frame_cycles = {}
    tick_cycles = {}
    underflows = stale_rejects = holds = clip_commits = 0
    normal_stereo = set()
    for row in rows:
        cycle, epoch, reset = row["cycle"], row["epoch"], row["rst_n"]
        require(epoch >= last_epoch and epoch <= last_epoch+1, "EPOCH_SEQUENCE")
        if epoch != last_epoch:
            require(reset and not prior_rst and epoch != 0, "EPOCH_REQUIRES_RESET_RELEASE")
        last_epoch = epoch
        if not reset:
            require(not any(row[k] for k in ("tick", "frame_tick", "request", "req_id", "pcm_ready", "pending", "play_l", "play_r", "frames", "requests", "commits", "underflow", "bclk", "ws", "din")), "RESET_OUTPUT_NOT_ZERO")
            pending=None; held=(0,0); held_id=None; held_clip=0; ever=False; active=False
            counter=[0,0,0,0]; req_id=req_pulse=phase=tick_value=0
            prior_rst=0; prior_row=row
            continue
        require(epoch in (1,2), "ACTIVE_EPOCH")
        epochs.setdefault(epoch, 0)
        epochs[epoch] += 1
        require(row["tick"] == tick_value, "SAMPLE_TICK_PHASE")
        phase += 5153961
        tick_value = int(phase >= (1<<32)); phase %= 1<<32
        if row["tick"]:
            tick_cycles.setdefault(epoch, []).append(cycle)
        require(row["request"] == req_pulse and row["req_id"] == req_id, "REQUEST_CALENDAR")
        require([row[k] for k in ("frames", "requests", "commits", "underflow")] == counter, "PUBLIC_COUNTER_LEDGER")
        expected_play = pending[1:3] if pending else held
        require((row["play_l"],row["play_r"]) == tuple(expected_play), "BUFFER_PENDING_HELD_MAPPING")
        require(row["pending"] == int(pending is not None), "PENDING_MAPPING")
        ready = active and not row["frame_tick"] and pending is None and row["pcm_id"] == req_id
        require(row["pcm_ready"] == int(ready), "ID_READY_QUALIFICATION")
        if row["pcm_valid"] and row["pcm_id"] != req_id:
            require(not row["pcm_ready"], "OLD_ID_ACCEPTED")
            stale_rejects += 1
        if row["pcm_valid"] and pending:
            require(not row["pcm_ready"], "DUPLICATE_COMMIT")
            holds += 1
        if row["request"]:
            key = (epoch,req_id)
            require(key not in ledger, "DUPLICATE_REQUEST")
            ledger[key] = {"epoch":epoch,"id":req_id,"request_cycle":cycle,"status":"IN_FLIGHT"}
        req_pulse=0
        if row["frame_tick"]:
            frame_cycles.setdefault(epoch, []).append(cycle)
            if pending:
                held_id, held_l, held_r, held_clip = pending
                held=(held_l,held_r); pending=None; ever=True
                ledger[(epoch,held_id)].update(adoption_cycle=cycle,status="ADOPTED")
            elif ever:
                counter[3] += 1; underflows += 1
            if (epoch, req_id) in ledger and ledger[(epoch,req_id)]["status"] == "IN_FLIGHT":
                ledger[(epoch,req_id)]["status"]="EXPIRED_UNCOMMITTED"
            counter[0] += 1; counter[1] += 1
            adoptions.setdefault(epoch, []).append({"cycle":cycle,"pcm":held,"id":held_id,"clip":held_clip,"frame":counter[0]})
            req_id += 1; req_pulse=1; active=True
        elif row["pcm_valid"] and ready:
            require((epoch,req_id) in ledger, "COMMIT_WITHOUT_REQUEST")
            if fixture_inputs:
                require((row["left"],row["right"],row["clip"]) == (vector(req_id+epoch),vector(req_id+epoch+7),int(req_id%17==0)), "FIXTURE_INPUT_CALENDAR")
            pending=(req_id,row["left"],row["right"],row["clip"])
            active=False; counter[2]+=1; clip_commits+=row["clip"]
            ledger[(epoch,req_id)].update(commit_cycle=cycle,left=row["left"],right=row["right"],clip=row["clip"],status="COMMITTED")
            normal_stereo.add((row["left"],row["right"]))
        prior_rst=reset; prior_row=row
    require(set(epochs)=={1,2}, "TWO_RESET_LIFETIMES_REQUIRED")
    frame_distributions={}; tick_distributions={}
    for epoch in epochs:
        for name, src, result in (("FRAME",frame_cycles,frame_distributions),("TICK",tick_cycles,tick_distributions)):
            gaps = [b-a for a,b in zip(src[epoch],src[epoch][1:])]
            require(len(gaps)>=60 and set(gaps)=={833,834}, f"{name}_833_834_DISTRIBUTION")
            require(abs(sum(gaps)-len(gaps)*40000000/48000) <= 1.01, f"{name}_48KHZ_MEAN")
            result[str(epoch)] = {"intervals":len(gaps),"distribution":dict(Counter(gaps)),"average_hz":40000000*len(gaps)/sum(gaps)}
    require(underflows==expected_underflows, "UNEXPECTED_UNDERFLOW")
    require(stale_rejects>=30 and holds>=500 and clip_commits>=8, "IDENTITY_HOLD_CLIP_COVERAGE")
    require(any(l!=r for l,r in normal_stereo) and any(l<0 for l,r in normal_stereo) and any(r>0 for l,r in normal_stereo), "SIGNED_STEREO_COVERAGE")
    # Reconstruct solely from external BCLK rising edges / physical WS boundaries.
    synchronized=False; prior_ws=0; bits=[]; right_half=None
    decoded=[]; transition_gaps=[]; previous_rise=None; previous_toggle=None
    current_epoch=0
    for previous,row in zip(rows,rows[1:]):
        if not row["rst_n"] or current_epoch != row["epoch"]:
            synchronized=False; prior_ws=row["ws"]; bits=[]; right_half=None
            previous_rise=previous_toggle=None; current_epoch=row["epoch"]
        if not row["rst_n"]:
            continue
        if previous["bclk"]!=row["bclk"]:
            if previous_toggle is not None:
                require(row["cycle"]-previous_toggle in (6,7), "BCLK_HALF_PERIOD")
            previous_toggle=row["cycle"]
        if previous["bclk"]==0 and row["bclk"]==1:
            cycle=row["cycle"]
            if previous_rise is not None:
                require(cycle-previous_rise in (13,14), "BCLK_PERIOD")
            previous_rise=cycle
            if row["ws"]!=prior_ws:
                if synchronized:
                    require(len(bits)==32, "PHYSICAL_WS_32_SLOTS")
                    word=sum(value << (31-i) for i,(_,value) in enumerate(bits))
                    require(word>>16==0,"LSBJ_PADDING_PHASE")
                    first=bits[0][0]
                    choices=adoptions[row["epoch"]]
                    pos=bisect_right([a["cycle"] for a in choices],first)-1
                    # The first complete WS-high half precedes the first full
                    # frame_tick. It is reset silence, not a manufactured PCM.
                    adoption=choices[pos] if pos>=0 else {"cycle":0,"pcm":(0,0),"id":None,"clip":0,"frame":0}
                    value=signed16(word&65535)
                    expected=quantize(adoption["pcm"][0 if prior_ws else 1])
                    require(value==expected,"SERIAL_PCM_LSBJ_OR_STEREO")
                    if prior_ws==0:
                        right_half=(adoption,value,first)
                    elif right_half:
                        adopt,right_value,start=right_half
                        require(adopt["frame"]==adoption["frame"],"STEREO_FRAME_MIX")
                        key=(row["epoch"],adopt["id"])
                        if key in ledger and ledger[key].get("adoption_cycle")==adopt["cycle"]:
                            elapsed=digital_latency(ledger[key]["request_cycle"],cycle)
                            ledger[key].update(serial_complete_cycle=cycle,digital_cycles=elapsed,status="SERIAL_OBSERVED")
                        decoded.append({"epoch":row["epoch"],"frame":adopt["frame"],"id":adopt["id"],"left":value,"right":right_value,"clip_metadata":adopt["clip"],"start":start,"end":cycle})
                        right_half=None
                synchronized=True; prior_ws=row["ws"]; bits=[]
            if synchronized:
                bits.append((cycle,row["din"]))
    for epoch in epochs:
        observed=[d for d in decoded if d["epoch"]==epoch]
        require(len(observed)>=68,"MISSING_STEREO_FRAMES")
        require(all(b["frame"]==a["frame"]+1 for a,b in zip(observed,observed[1:])),"DROPPED_STEREO_FRAME")
        require(observed[0]["left"]==observed[0]["right"]==0,"STARTUP_NOT_SILENT")
    latencies=[e["digital_cycles"] for e in ledger.values() if "digital_cycles" in e]
    require(latencies and max(latencies)<=400000,"DIGITAL_LATENCY_EXCEEDS_10MS")
    return {"passed":True,"evidence_kind":"NEW_MODULE_RTL_FIXTURE","scope":"PUBLIC_BUFFER_AND_PT8211_MODULE_ONLY","level":"L2_MODULE_FIXTURE_L1_INDEPENDENT_CHECKER","capture_sha256":hashlib.sha256(raw).hexdigest(),"cycles":len(rows),"clock_hz":40000000,"frame_distribution":frame_distributions,"sample_tick_distribution":tick_distributions,"decoded_stereo_frames":len(decoded),"observed_clip_commits":clip_commits,"clip_transport":"SOURCE_METADATA_ONLY_NO_CLIP_PORT_ON_FROZEN_BUFFER_OR_TX","stale_id_rejected_cycles":stale_rejects,"postcommit_valid_hold_cycles":holds,"expected_diagnostic_underflows":underflows,"request_ledger":list(ledger.values()),"serial_frames":decoded,"max_digital_request_to_serial_cycles":max(latencies),"max_digital_request_to_serial_us":max(latencies)/40,"r05_true_chain":"UNKNOWN_NOT_RUN_BY_THIS_PACKAGE","analog_end_to_end_10ms":"UNKNOWN_NOT_MEASURED","board_release_allowed":False,"physical_sta":"NOT_EXECUTED"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("capture",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--expected-underflows",type=int,default=2)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit("REFUSE_OVERWRITE")
    try:
        result=check(args.capture,expected_underflows=args.expected_underflows)
        code=0
    except (ValueError,OSError,UnicodeError) as exc:
        result={"passed":False,"diagnostic":str(exc),"board_release_allowed":False}
        code=1
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("request_ledger","serial_frames")}))
    return code


if __name__=="__main__":
    raise SystemExit(main())
