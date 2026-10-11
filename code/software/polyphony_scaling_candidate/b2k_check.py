"""Source-clock cancellation/drain oracle, not output-derived timing or STA.

Quiescent router, one real A4 note, no injected responses or identity changes.
The backend and scheduler are distinct owners; control output drains separately.
Persistent phase advances are never rolled back on token cancel.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from b2_clock import backend_calendar
from b2j_check import require

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "audio_math_acceptance_candidate"))
from dds_model import note_fcw  # noqa: E402

STATUS = "B2K_INFLIGHT_CANCEL_PASS_T061_PARTIAL"
FIELDS = "cycle rst cancel sv sr rv rr idle publish launch sid rid left right ev er data advance lv slot phase".split()
NOTE = (1 << 57) | (2 << 53) | (69 << 46) | (1023 << 36)


def plan(n, response):
    backend_calendar(0, n, response)
    offsets = [1, 9, 10, n+10, 3*n+14, 3*n+15, 6*n+12, 6*n+13,
               6*n+19, 6*n+20, 6*n+21, 6*n+26, 6*n+27, 6*n+27,
               6*n+27+response, 6*n+28+response, 6*n+27+2*(response+3)]
    return [(o, 0, 3 if i == 13 else 1) for i, o in enumerate(offsets)] + [
        (o, 1, 1) for o in (10, 3*n+15, 6*n+13, 6*n+27)]


class Cancellation:
    """Independent old-state transitions, with counter/valid retirement clocks."""
    def __init__(self, n, response):
        backend_calendar(0, n, response)
        self.n, self.response = n, response
        self.mode = self.backend = self.scheduler = "idle"
        self.j = self.c = self.f = self.control_clear = None
        self.pitch_clear = self.rom_clear = 0
        self.issued = False
        self.phase = 0
        self.active = False
        self.pending_lane = None
        self.held = None
        self.sid = None
        self.cancel_event = None
        self.events = []
        self.counts = dict(requests=0, cancels=0, active_resets=0, publishes=0,
                           launches=0, advances=0, lanes=0, notes=0)

    def edge(self, row):
        c, stop = row["cycle"], bool(row["cancel"])
        if not row["rst"]:
            self.counts["active_resets"] += int(self.mode == "frame")
            self.mode = self.backend = self.scheduler = "idle"
            self.j = self.c = self.f = self.control_clear = None
            self.pitch_clear = self.rom_clear = 0
            self.issued, self.active, self.phase = False, False, 0
            self.pending_lane = self.held = self.cancel_event = None
        be_empty = self.backend == "idle" and c >= max(self.pitch_clear, self.rom_clear)
        idle = self.mode == "idle" and self.scheduler == "idle" and be_empty
        ready = bool(row["rst"] and idle and not stop)
        rv = self.mode == "frame" and c >= self.f
        launch = self.mode == "frame" and c == self.c and not stop
        advance = self.backend == "run" and c == self.c+8 and not stop
        publish = rv and row["rr"] and not stop
        for key, value in (("idle", idle), ("sr", ready), ("rv", rv),
                           ("launch", launch), ("advance", advance), ("publish", publish)):
            require(row[key] == int(value), f"CANCEL_{key.upper()}:{c}")
        require(row["lv"] == int(self.pending_lane is not None), f"CANCEL_LANE_TIME:{c}")
        if self.pending_lane is not None:
            slot, phase, fcw = self.pending_lane
            require(row["slot"] == slot, f"CANCEL_SLOT:{c}")
            require(row["phase"] == phase, f"NONROLLBACK_PHASE:{c}")
            require(row["fcw"] == fcw, f"INDEPENDENT_FCW:{c}")
            self.counts["lanes"] += 1
        self.pending_lane = None
        if rv:
            require(row["rid"] == self.sid, f"RESULT_ID:{c}")
            value = (row["rid"], row["left"], row["right"])
            if self.held is None:
                self.held = value
            require(value == self.held, f"HELD_RESULT_CHANGED:{c}")
        if not row["rst"]:
            return
        if idle and self.cancel_event:
            self.events.append(dict(**self.cancel_event, ready=c))
            self.cancel_event = None
        if row["ev"] and row["er"]:
            require(idle and row["data"] == NOTE, "EVENT_OUTSIDE_A4_SCOPE")
            self.active = True
            self.counts["notes"] += 1
        old_backend, old_scheduler = self.backend, self.scheduler
        # Real accepted work determines counter ownership, never observed outputs.
        if launch:
            self.backend = "run"
            self.pitch_clear = c+8 if self.active else c
            self.counts["launches"] += 1
        if advance:
            if self.active:
                self.phase = (self.phase + note_fcw(69)) & 0xffffffff
            self.counts["advances"] += 1
        if old_backend == "run" and not stop:
            starts = [self.c+14+s*(self.response+3) for s in range(self.n)]
            if c in starts:
                self.rom_clear = c+self.response+1
            gains = backend_calendar(self.c, self.n, self.response).lanes
            if c in gains:
                slot = gains.index(c)
                self.pending_lane = (slot, self.phase if slot == 0 else 0,
                                     note_fcw(69) if slot == 0 and self.active else 0)
        if stop and not be_empty:
            self.backend = "drain"
        elif old_backend == "drain" and c >= max(self.pitch_clear, self.rom_clear):
            self.backend = "idle"
        elif publish:
            self.backend = "idle"
        # B1 cancel discards unissued work immediately; already-issued tags fence.
        if old_scheduler == "drain":
            if be_empty and not row["lv"]:
                self.scheduler, self.issued = "idle", False
        elif stop:
            self.scheduler = "drain" if self.issued else "idle"
            self.issued = False
        elif self.mode == "frame":
            if c == self.j+3*self.n+11:
                self.scheduler = "active"
            if c in range(self.j+3*self.n+14, self.j+6*self.n+12, 3):
                self.issued = True
            if publish:
                self.scheduler = "drain"
        if self.mode == "frame" and not stop and c == self.j+9:
            self.control_clear = c+self.n+2  # E+N output, PRE valid E+N+1, consume
        if stop:
            if self.mode == "frame":
                self.counts["cancels"] += 1
                self.cancel_event = dict(accepted=self.j, cancel=c, last_cancel=c,
                                         offset=c-self.j, backend_owned=old_backend != "idle")
            elif self.cancel_event:
                self.cancel_event["last_cancel"] = c
            self.mode = "drain"
        elif self.mode == "drain":
            if old_scheduler == "idle" and be_empty and (
                    self.control_clear is None or c >= self.control_clear):
                self.mode = "idle"
        elif publish:
            self.mode = "drain"
            self.counts["publishes"] += 1
        elif idle and row["sv"]:
            self.counts["requests"] += 1
            self.j, self.sid = c, row["sid"]
            self.c = c+12+6*self.n
            self.f = backend_calendar(self.c, self.n, self.response).wrapper_first
            self.mode, self.held, self.control_clear = "frame", None, None


def check(raw):
    lines = raw.decode("ascii").splitlines()
    if lines and re.fullmatch(r"[^\r\n]*[/\\]tb_b2k_cancel\.sv:\d+: \$finish called at \d+ \(1ps\)", lines[-1]):
        lines.pop()
    require(bool(lines), "EMPTY_CAPTURE")
    header = lines.pop(0).split()
    require(len(header) == 3 and header[0] == "B2K", "HEADER")
    n, response = map(int, header[1:])
    model = Cancellation(n, response)
    rows, cases, end, fcws = [], [], None, {}
    for line in lines:
        require(end is None, "AFTER_END")
        p = line.split()
        if p and p[0] == "END":
            require(len(p) == 2, "END_SCHEMA")
            end = int(p[1])
        elif p and p[0] == "CASE":
            require(len(p) == 5, "CASE_SCHEMA")
            cases.append(tuple(map(int, p[1:])))
        elif p and p[0] == "FCW":
            require(len(p) == 3, "FCW_SCHEMA")
            cycle, value = map(int, p[1:])
            require(cycle == len(rows) and cycle not in fcws and rows[-1]["lv"], "FCW_ORDER")
            require(0 <= value < 2**32, "FCW_RANGE")
            fcws[cycle] = value
        else:
            require(len(p) == len(FIELDS)+1 and p[0] == "T", "TRACE_SCHEMA")
            row = dict(zip(FIELDS, map(int, p[1:])))
            require(row["cycle"] == len(rows)+1, "NONCONTIGUOUS_CYCLE")
            for key in "rst cancel sv sr rv rr idle publish launch ev er advance lv".split():
                require(row[key] in (0, 1), "BIT_FIELD:"+key)
            require(all(0 <= row[k] < 2**32 for k in ("sid", "rid", "phase")), "UINT32_RANGE")
            require(0 <= row["data"] < 2**64 and 0 <= row["slot"] < n, "INPUT_RANGE")
            require(all(-2**23 <= row[k] < 2**23 for k in ("left", "right")), "PCM_RANGE")
            rows.append(row)
    require(end == len(rows) and end > 0, "END_COUNT")
    require([v[1:] for v in cases] == plan(n, response), "CASE_PLAN")
    accepted = []
    for row in rows:
        require(bool(row["lv"]) == (row["cycle"] in fcws), "FCW_COVERAGE")
        row["fcw"] = fcws.get(row["cycle"], 0)
        if row["sv"] and row["sr"]:
            accepted.append(row)
        model.edge(row)
    require(model.mode == model.backend == model.scheduler == "idle", "END_NOT_IDLE")
    require(model.counts["requests"] == 42 and model.counts["cancels"] == 17
            and model.counts["active_resets"] == 4 and model.counts["publishes"] == 21
            and model.counts["notes"] == 5, "REQUIRED_COVERAGE:"+repr(model.counts))
    require(len(model.events) == 17 and len(accepted) == 42, "FENCE_COVERAGE")
    for i, (sid, offset, reset, width) in enumerate(cases):
        first, recovery = accepted[2*i:2*i+2]
        require(first["sid"] == sid and recovery["sid"] == sid+1, "CASE_IDENTITY")
        transition = rows[first["cycle"]+offset-1]
        require(transition["rst"] == 1-reset and transition["cancel"] == 1-reset, "CASE_TRANSITION")
        if not reset:
            event = next(e for e in model.events if e["accepted"] == first["cycle"])
            require(event["offset"] == offset and event["last_cancel"]-event["cancel"]+1 == width,
                    "CANCEL_WIDTH")
            require(recovery["cycle"] == event["ready"], "GREEDY_ADMISSION")
    return dict(status=STATUS, N=n, response=response, cycles=len(rows), counts=model.counts,
                cancel_events=model.events, case_plan=plan(n, response),
                sha256=hashlib.sha256(raw).hexdigest(), task_complete=False,
                scope="Quiescent A4, directed source phases, explicit cancel and whole-domain reset",
                PCM_math_revalidated=False, general_event_service_bound=None,
                LFO_nonrollback_proved=False, physical_STA=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.input.read_bytes())
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(result, stream, indent=2)
                stream.write("\n")
        print(json.dumps(result))
    except (ValueError, OSError) as error:
        print("B2K_REJECT:"+str(error))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
