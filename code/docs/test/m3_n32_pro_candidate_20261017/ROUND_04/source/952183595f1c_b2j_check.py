"""PRE-NBA public completion calendar; not a PCM math or physical STA oracle.

Scope: quiescent-router admission, normal output/hold, cancellation at HOLD
or idle, rejected injection during drain, public read suppression, whole reset.
Early in-flight cancellations and general MIDI service are deliberately absent.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from b2_clock import backend_calendar

STATUS = "B2J_PUBLIC_COMPLETION_PASS_T061_PARTIAL"
FIELDS = ("cycle rst cancel sv sr rv rr idle inject read publish launch sid rid left right er").split()


def require(test, reason):
    if not test:
        raise ValueError(reason)


class Completion:
    """Independent coupled wrapper/B1/backend transition, old-state RHS.

    The normal post-publish fence is three PRE-NBA observer edges: backend
    empties on P, B1 on P+1, wrapper on P+2, ready first observed P+3.
    HOLD cancel adds backend's DRAIN state. No arbitrary accepted time ranges.
    """
    def __init__(self, n, response):
        backend_calendar(0, n, response)  # strict integer/domain validation
        self.n, self.response = n, response
        self.mode = "idle"
        self.scheduler = self.backend = "idle"
        self.drain_age = 0
        self.expected_id = 0
        self.first = self.launch = None
        self.held = None
        self.termination = None
        self.events = []
        self.counts = dict(requests=0, first_valid=0, publishes=0, hold_cancel=0,
                           reset_active=0, read_block_edges=0, injected_drain_edges=0)

    def edge(self, row):
        c = row["cycle"]
        if not row["rst"]:
            self.counts["reset_active"] += int(self.mode != "idle")
            self.mode = self.scheduler = self.backend = "idle"
            self.expected_id, self.held, self.termination = 0, None, None
            self.first = self.launch = None
        idle = self.mode == self.scheduler == self.backend == "idle"
        ready = bool(row["rst"] and idle and not row["cancel"] and not row["read"])
        rv = self.mode == "frame" and c >= self.first
        publish = rv and row["rr"] and not row["cancel"]
        launch = self.mode == "frame" and c == self.launch
        for key, expected in (("idle", idle), ("sr", ready), ("rv", rv),
                              ("publish", publish), ("launch", launch)):
            require(row[key] == int(expected), f"COMPLETION_{key.upper()}:{c}")
        # rid changes only when RUN registers the result before its first valid.
        if rv:
            require(row["rid"] == self.expected_id, f"RESULT_ID:{c}")
            value = (row["rid"], row["left"], row["right"])
            if self.held is None:
                self.held = value
                self.counts["first_valid"] += 1
            require(value == self.held, f"HELD_RESULT_CHANGED:{c}")
        if not row["rst"]:
            return
        if idle and row["read"]:
            self.counts["read_block_edges"] += 1
        if idle and self.termination:
            kind, end = self.termination
            self.events.append(dict(kind=kind, termination=end, ready=c, delay=c-end))
            self.termination = None
        if self.mode == "frame":
            if row["cancel"]:
                require(rv, "OUTSIDE_HOLD_CANCEL_SCOPE")
                self.counts["hold_cancel"] += 1
                self.mode = self.scheduler = self.backend = "drain"
                self.drain_age = 0
                self.termination = ("hold_cancel", c)
            elif publish:
                self.counts["publishes"] += 1
                self.mode = self.scheduler = "drain"
                self.backend = "idle"
                self.drain_age = 0
                self.termination = ("publish", c)
        elif self.mode == "drain":
            old_backend, old_scheduler = self.backend, self.scheduler
            if self.backend == "drain" and not row["cancel"]:
                # HOLD only: pitch/ROM work has completed before first valid.
                self.backend = "idle"
            if self.scheduler == "drain":
                if old_backend == "idle" and not row["inject"]:
                    self.scheduler = "idle"
                    self.drain_age = 0
                else:
                    self.counts["injected_drain_edges"] += int(bool(row["inject"]))
                    require(self.drain_age < 127, "DRAIN_FAULT_OUTSIDE_NORMAL_SCOPE")
                    self.drain_age += 1
            if not row["cancel"] and old_backend == old_scheduler == "idle":
                self.mode = "idle"
            if row["cancel"] and self.termination:
                self.termination = (self.termination[0], c)
        elif row["cancel"]:
            self.mode = "drain"  # wrapper stop priority applies even at IDLE
            self.termination = ("idle_cancel", c)
        elif row["sv"] and ready:
            self.counts["requests"] += 1
            self.expected_id = row["sid"]
            self.launch = c + 12 + 6*self.n  # quiescent source frontend
            self.first = backend_calendar(self.launch, self.n, self.response).wrapper_first
            self.mode, self.held = "frame", None


def check(raw):
    lines = raw.decode("ascii").splitlines()
    # Icarus 13 emits one source-location footer after a normal $finish.
    # Recognize that exact footer only, never ignore arbitrary extra records.
    if lines and re.fullmatch(r"[^\r\n]*[/\\]tb_b2j_completion\.sv:\d+: \$finish called at \d+ \(1ps\)", lines[-1]):
        lines.pop()
    require(bool(lines), "EMPTY_CAPTURE")
    header = lines[0].split()
    require(len(header) == 3 and header[0] == "B2J", "HEADER")
    n, response = map(int, header[1:])
    model = Completion(n, response)
    end, count = None, 0
    for line in lines[1:]:
        parts = line.split()
        require(end is None, "AFTER_END")
        if parts and parts[0] == "END":
            require(len(parts) == 2, "END_SCHEMA")
            end = int(parts[1])
            continue
        require(len(parts) == len(FIELDS)+1 and parts[0] == "T", "TRACE_SCHEMA")
        row = dict(zip(FIELDS, map(int, parts[1:])))
        count += 1
        require(row["cycle"] == count, "NONCONTIGUOUS_CYCLE")
        for key in FIELDS[1:12] + ["er"]:
            require(row[key] in (0, 1), "BIT_FIELD:"+key)
        require(0 <= row["sid"] < 2**32 and 0 <= row["rid"] < 2**32, "ID_RANGE")
        require(all(-2**23 <= row[k] < 2**23 for k in ("left", "right")), "PCM_RANGE")
        model.edge(row)
    require(end == count and count > 0, "END_COUNT")
    require(model.mode == model.scheduler == model.backend == "idle", "END_NOT_IDLE")
    require(model.counts == dict(requests=13, first_valid=13, publishes=10, hold_cancel=2,
                                reset_active=2, read_block_edges=3, injected_drain_edges=9),
            "REQUIRED_COVERAGE:"+repr(model.counts))
    require(len(model.events) == 12, "TERMINATION_COVERAGE")
    return dict(status=STATUS, N=n, response=response, cycles=count,
                counts=model.counts, completion_events=model.events,
                quiescent_no_hold_first_F_minus_J=backend_calendar(12+6*n, n, response).wrapper_first,
                quiescent_no_hold_next_admission_minus_J=backend_calendar(12+6*n, n, response).wrapper_first+3,
                sha256=hashlib.sha256(raw).hexdigest(), task_complete=False,
                scope="Public quiescent frame completion/hold cancellation only",
                PCM_math_revalidated=False, general_event_service_bound=None,
                early_inflight_cancel_bound=None, physical_STA=None)


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
        print("B2J_REJECT:"+str(error))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
