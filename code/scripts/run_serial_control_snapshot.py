"""M2 serialized control snapshot transaction oracle + parallel RTL reference.
Standard library only. Original state module and formal audio remain untouched.
"""
from pathlib import Path
import hashlib
import json
import os
import random
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def packed(values, width):
    return sum((value & ((1 << width) - 1)) << (width * i) for i, value in enumerate(values))


def control(kind, source, channel, item=0, value=0):
    return (kind << 61) | (source << 57) | (channel << 53) | (item << 18) | ((value & 4095) << 6)


def snapshot(bank, request):
    ident, occupied, sources, channels, generations = request
    values = [bank[sources[i], channels[i]] if occupied & (1 << i) else [0, 0, 2] for i in range(4)]
    fields = [(ident, 32), (occupied, 4), (packed(sources, 4), 16), (packed(channels, 4), 16),
              (packed(generations, 32), 128), (packed([v[0] for v in values], 12), 48),
              (packed([v[1] for v in values], 12), 48), (packed([v[2] for v in values], 5), 20)]
    out = 0
    for value, width in fields:
        out = (out << width) | value
    return out


class Oracle:
    def __init__(self):
        self.bank = {(s, c): [0, 0, 2] for s in range(16) for c in range(16)}
        self.busy = 0
        self.valid = 0
        self.payload = packed([2] * 4, 5)
        self.pending = None

    def ready(self, output_ready):
        return not self.busy, not self.busy and (not self.valid or output_ready)

    def step(self, reset, event_valid, data, request_valid, req, output_ready):
        applied = invalid = 0
        accepted_event = accepted_request = False
        if not reset:
            self.__init__()
        else:
            event_ready, req_ready = self.ready(output_ready)
            accepted_event = bool(event_valid and event_ready)
            accepted_request = bool(request_valid and req_ready)
            if accepted_event:
                kind, source, channel = (data >> 61) & 7, (data >> 57) & 15, (data >> 53) & 15
                item, value = (data >> 18) & 255, (data >> 6) & 4095
                if kind == 3 and item == 0:
                    self.bank[source, channel][0] = value
                    applied = 1
                elif kind == 4 and item == 1:
                    self.bank[source, channel][1] = value
                    applied = 1
                elif kind == 4 and item == 4:
                    if value <= 24:
                        self.bank[source, channel][2] = value
                        applied = 1
                    else:
                        invalid = 1
            if self.valid and output_ready:
                self.valid = 0
            if accepted_request:
                self.pending = snapshot(self.bank, req)
                self.busy = 4
                self.valid = 0
            elif self.busy:
                self.busy -= 1
                if not self.busy:
                    self.payload = self.pending
                    self.valid = 1
        event_ready, req_ready = self.ready(output_ready)
        return [int(reset and event_ready), int(reset and req_ready), self.valid,
                self.payload, applied, invalid], accepted_event, accepted_request


def make_vectors():
    model, rows, coverage = Oracle(), [], {}
    rng = random.Random(0xC01740)
    req = (0, 15, (0, 0, 1, 0), (0, 1, 0, 0), (1, 2, 3, 4))
    def add(label, reset=1, event_valid=0, data=0, request_valid=0, request=req, ready=1):
        coverage[label] = coverage.get(label, 0) + 1
        expected, ev, rq = model.step(reset, event_valid, data, request_valid, request, ready)
        ident, occupied, sources, channels, generations = request
        fields = [reset, event_valid, data, request_valid, ident, occupied,
                  packed(sources, 4), packed(channels, 4), packed(generations, 32), ready] + expected
        rows.append(" ".join(format(value, "x") for value in fields))
        return ev, rq
    def capture(label, request, data=None):
        assert not model.busy and not model.valid
        add(label, event_valid=data is not None, data=data or 0, request_valid=1, request=request)
        for _ in range(4):
            # Tag bus changes without a new request cannot tear captured identities.
            add("input_tags_change_during_scan", request=(0xffffffff, 0, (15,) * 4, (15,) * 4, (0,) * 4))
        add("result_ack")
    add("reset", reset=0, event_valid=1, data=control(3, 0, 0, value=4095), request_valid=1)
    capture("reset_defaults", req)
    for source in range(16):
        for channel in range(16):
            query = (len(rows), 15, (source, source, source ^ 1, source),
                     (channel, channel ^ 1, channel, channel), (0, 0xffffffff, 7, 8))
            for kind, item, value in [(3, 0, (source * 257 + channel * 31) & 4095),
                                      (4, 1, (source * 113 + channel * 257) & 4095),
                                      (4, 4, (source + channel) % 25)]:
                capture("all_identities_same_edge_write_snapshot", query,
                        control(kind, source, channel, item, value))
    for label, kind, item in [("all_4096_pitch_bitpatterns", 3, 0), ("all_4096_mod_values", 4, 1),
                              ("all_4096_range_legal_invalid", 4, 4)]:
        for value in range(4096):
            data = control(kind, 0, 0, item, value)
            add(label, event_valid=1, data=data)
            if value % 32 == 0:
                capture("pattern_snapshot", (len(rows), 15, req[2], req[3], req[4]))
    # Pending control remains unacknowledged during4 reads and is accepted only
    # afterwards. Updates while result is held must not change that old snapshot.
    capture("initial_lifecycle", req, control(3, 0, 0, value=-2048))
    add("begin_held_snapshot", request_valid=1, request=req, ready=0)
    blocked = control(3, 0, 0, value=2047)
    for _ in range(4):
        ev, _ = add("event_backpressure_during_reads", event_valid=1, data=blocked, ready=0)
        assert not ev
    ev, _ = add("deferred_event_accepted_after_reads", event_valid=1, data=blocked, ready=0)
    assert ev
    for _ in range(12):
        add("stalled_output_immutable", event_valid=1, data=control(4, 0, 0, 1, rng.randrange(4096)), ready=0)
    add("held_result_ack")
    capture("later_snapshot_sees_updates", req)
    for kind, item in [(0, 0), (1, 0), (4, 6), (5, 0), (6, 0), (7, 0), (3, 1), (4, 255)]:
        capture("ignored_events_noteoff_panic", req, control(kind, 0, 0, item, 4095))
    capture("inactive_neutral", (len(rows), 0, req[2], req[3], req[4]))
    capture("steal_rebind_and_generation_wrap", (0, 15, (15, 14, 13, 12), (15, 14, 13, 12), (0, 0xffffffff, 91, 92)))
    # Reset must hide uncleared RAM, even after a nonzero control was written.
    add("reset_during_scan_request", event_valid=1, data=control(3, 0, 0, value=2047), request_valid=1)
    add("reset_cancels_inflight", reset=0)
    capture("logical_RAM_reset_defaults", req)
    capture("first_partial_write_after_reset", req, control(4, 0, 0, 1, 55))
    add("reset_stalled_result_begin", request_valid=1)
    for _ in range(4):
        add("reset_stalled_result_wait", ready=0)
    add("reset_cancels_held", reset=0)
    capture("defaults_after_stalled_reset", req)
    # Genuine producers retain valid/data across backpressure. Random events
    # and requests advance independently only after successful handshakes.
    event_pending, req_pending = None, None
    for cycle in range(8192):
        if event_pending is None and rng.randrange(3):
            kind, item = rng.choice([(3, 0), (4, 1), (4, 4), (4, 6), (0, 0), (5, 0)])
            event_pending = control(kind, rng.randrange(16), rng.randrange(16), item, rng.randrange(4096))
        if req_pending is None and rng.randrange(4) == 0:
            req_pending = (rng.getrandbits(32), rng.randrange(16),
                           tuple(rng.randrange(16) for _ in range(4)),
                           tuple(rng.randrange(16) for _ in range(4)),
                           tuple(rng.getrandbits(32) for _ in range(4)))
        reset = cycle not in [2047, 4095, 6143]
        ev, rq = add("random_two_handshake_streams", reset=reset,
                     event_valid=event_pending is not None, data=event_pending or 0,
                     request_valid=req_pending is not None, request=req_pending or req,
                     ready=rng.randrange(3) != 0)
        if ev or not reset:
            event_pending = None
        if rq or not reset:
            req_pending = None
    for _ in range(8):
        add("drain_results")
    add("final_reset", reset=0)
    return rows, coverage


def run(command, stage, label):
    result = subprocess.run(command, cwd=stage, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    text = result.stdout + result.stderr
    (stage / (label + ".log")).write_text(text, encoding="utf-8", newline="\n")
    return result.returncode, text


def main():
    stage = ROOT / "code/output/control_snapshot_optimization_20261002"
    stage.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + os.environ["PATH"]
    rows, coverage = make_vectors()
    path = stage / "vectors.txt"
    path.write_text("\n".join(rows) + "\n", encoding="ascii", newline="\n")
    sources = [ROOT / rel for rel in ["code/rtl/common/audio_defs_pkg.sv",
        "code/rtl/board/performance_control_state.sv", "code/rtl/board/performance_control_snapshot.sv",
        "code/tb/board/tb_performance_control_snapshot.sv"]]
    code, text = run([str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_performance_control_snapshot",
                      "-o", str(stage / "tb.vvp")] + list(map(str, sources)), stage, "compile")
    if code:
        print(text[-3000:]);return code
    command = [str(CAD / "bin/vvp.exe"), str(stage / "tb.vvp")]
    code, text = run(command + ["+VECTORS=" + str(path)], stage, "RTL")
    print(text.strip())
    results = [l for l in text.splitlines() if l.startswith("PASS performance_control_snapshot")]
    if code or len(results) != 1:
        return code or 1
    # Mutate expected output payload only, not input/source/accepted original.
    mutated = list(rows)
    index = next(i for i, row in enumerate(rows) if int(row.split()[12], 16) == 1)
    fields = mutated[index].split();fields[13] = format(int(fields[13], 16) ^ (1 << 68), "x")
    mutated[index] = " ".join(fields)
    bad = stage / "bad_vectors.txt"
    bad.write_text("\n".join(mutated) + "\n", encoding="ascii", newline="\n")
    bad_code, bad_text = run(command + ["+VECTORS=" + str(bad)], stage, "negative_payload")
    if bad_code == 0 or "independent transactional reference" not in bad_text:
        raise RuntimeError("wrong snapshot pitch bit accepted")
    print("PASS negative payload rejected")
    # The RAM is intentionally not reset. Removing its initialized guard
    # must fail even when the storage happens to contain old/unknown values.
    mutant = stage / "unguarded_ram.sv"
    original = sources[2].read_text(encoding="utf-8")
    before = "initialized[read_identity] ? raw_word : DEFAULT_WORD"
    if original.count(before) != 1:
        raise RuntimeError("reset guard mutation anchor absent")
    mutant.write_text(original.replace(before, "raw_word"), encoding="utf-8", newline="\n")
    mut_sources = sources[:2] + [mutant, sources[3]]
    mut_code, mut_text = run([str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_performance_control_snapshot",
                            "-o", str(stage / "unguarded.vvp")] + list(map(str, mut_sources)), stage, "negative_reset_compile")
    if mut_code:
        raise RuntimeError("reset guard mutant compile failed; not behavioral proof")
    mut_code, mut_text = run([str(CAD / "bin/vvp.exe"), str(stage / "unguarded.vvp"), "+VECTORS=" + str(path)],
                             stage, "negative_reset")
    if mut_code == 0 or "independent transactional reference" not in mut_text:
        raise RuntimeError("uninitialized/old RAM data was not rejected")
    print("PASS missing logical RAM reset guard rejected")
    info = {"date": "2026-10-02", "baseline": "251cd8d", "scope": "standalone optimized handshaking candidate, not formal replacement",
            "vectors": len(rows), "coverage": coverage, "results": results,
            "exact_request_to_valid_clocks": 4, "max_event_ready_low_clocks_per_request": 4,
            "reference": "original performance_control_state exact snapshot at accepted request",
            "negative_payload_rejected": True, "negative_reset_guard_rejected": True,
            "sources_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            "vectors_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "logs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.glob("*.log")}}
    (stage / "simulation_evidence.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Evidence:", stage / "simulation_evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
