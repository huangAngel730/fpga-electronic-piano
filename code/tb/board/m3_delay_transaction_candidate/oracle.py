"""Independent integer recurrence and edge-level transaction reference, no M1 model."""
from __future__ import annotations

import random
from pathlib import Path


def saturate(value):
    return max(-8388608, min(8388607, value))


class Reference:
    def __init__(self, depth):
        self.depth = depth
        self.cycle = -1
        self.counts = dict(accepted=0, consumed=0, cancelled=0, raw_writes=0,
                           stalls=0, resets=0, drained=0, saturations=0, reset_drops=0)
        self.clear()

    def clear(self):
        self.history = [0] * self.depth
        self.ptr = 0
        self.work = None
        self.raw_valid = 0
        self.raw_pcm = 0
        self.state = "idle"
        self.ident = 0
        self.held = 0

    def ports(self, reset, cancel):
        return [int(reset and not cancel and self.state == "idle"),
                int(reset and not cancel and self.state == "hold"), self.ident, self.held]

    def step(self, vector):
        self.cycle += 1
        reset, cancel, valid, ident, pcm, delay, dry, wet, feedback, ready = vector
        if not reset:
            self.counts["reset_drops"] += int(self.state in ("wait", "hold"))
            self.clear()
            self.counts["resets"] += 1
        before = self.ports(reset, cancel)
        launch = int(valid and before[0])
        old_ptr = self.ptr
        old_raw = self.raw_valid
        old_pcm = self.raw_pcm
        self.raw_valid = 0
        if reset:
            if cancel:
                if self.state in ("wait", "hold"):
                    self.counts["cancelled"] += 1
                self.state = "drain" if self.state in ("wait", "drain") and not old_raw else "idle"
            elif self.state == "idle" and launch:
                self.ident = ident & 0xffffffff
                delayed = self.history[(self.ptr - delay) % self.depth]
                output = (pcm * dry >> 15) + (delayed * wet >> 15)
                write = pcm + (delayed * feedback >> 15)
                self.counts["saturations"] += int(output != saturate(output)) + int(write != saturate(write))
                self.work = (self.cycle + 2, saturate(output), saturate(write))
                self.state = "wait"
                self.counts["accepted"] += 1
            elif self.state == "wait" and old_raw:
                self.held = old_pcm
                self.state = "hold"
            elif self.state == "drain" and old_raw:
                self.state = "idle"
                self.counts["drained"] += 1
            elif self.state == "hold":
                if ready:
                    self.counts["consumed"] += 1
                    self.state = "idle"
                else:
                    self.counts["stalls"] += 1
            if self.work and self.work[0] == self.cycle:
                _, self.raw_pcm, write = self.work
                self.history[self.ptr] = write
                self.ptr = (self.ptr + 1) % self.depth
                self.raw_valid = 1
                self.work = None
                self.counts["raw_writes"] += 1
        return before + [launch] + self.ports(reset, cancel) + [
            self.raw_valid, self.raw_pcm, old_ptr, self.ptr, self.history[old_ptr]]


def vectors(depth):
    ref = Reference(depth)
    result = []

    def put(reset=1, cancel=0, valid=0, ident=0, pcm=0, delay=1,
            dry=32767, wet=32767, feedback=20000, ready=1):
        vector = [reset, cancel, valid, ident, pcm, delay, dry, wet, feedback, ready]
        result.append(vector)
        ref.step(vector)

    def idle():
        for _ in range(8):
            put()

    put(reset=0)
    put()
    # Each raw compute phase, pre-visible raw valid, and held-result cancel.
    for age in (1, 2, 3, 4, 6):
        idle()
        put(valid=1, ident=0xffffffff, pcm=8388607, delay=0, ready=0)
        for _ in range(age - 1):
            put(pcm=-8388608, delay=depth - 1, dry=0, wet=0, ready=0)
        put(cancel=1, valid=1, ident=0, ready=1)
        idle()
    # same-edge cancel/request cannot launch; keep valid and wrap identifier.
    put(cancel=1, valid=1, ident=0xffffffff)
    for ident in (0xffffffff, 0, 1):
        for _ in range(12):
            put(valid=1, ident=ident, pcm=-7654321, delay=depth - 1, ready=0)
        idle()
    # Polluting and then resetting every phase proves logical RAM zeroing.
    for age in (1, 2, 3, 5):
        idle()
        put(valid=1, pcm=8388607, delay=0, ready=0)
        for _ in range(age - 1):
            put(ready=0)
        put(reset=0, valid=1, ready=1)
        idle()
        put(valid=1, pcm=0, delay=0, dry=0, wet=32767)
        idle()
    rng = random.Random(28004 + depth)
    for index in range(max(6000, depth * 20)):
        put(reset=int(index % 2003 != 0), cancel=int(rng.randrange(31) == 0),
            valid=int(rng.randrange(5) != 0), ident=(0xffffff00 + index) & 0xffffffff,
            pcm=rng.choice([-8388608, 8388607, 0, rng.randrange(-8388608, 8388608)]),
            delay=rng.choice([0, 1, depth - 1, rng.randrange(depth)]),
            dry=rng.choice([0, 32767, rng.randrange(32768)]),
            wet=rng.choice([0, 32767, rng.randrange(32768)]),
            feedback=rng.choice([0, 32767, rng.randrange(32768)]),
            ready=int(rng.randrange(4) != 0))
    idle()
    return result


def check_capture(path: Path, stimulus, depth):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == f"G1 {depth}", "capture header"
    assert lines[-1] == f"END {len(stimulus)}", "capture incomplete"
    assert len(lines) == len(stimulus) + 2, "capture count"
    ref = Reference(depth)
    last_launch = -100
    for cycle, (line, vector) in enumerate(zip(lines[1:-1], stimulus)):
        fields = line.split()
        assert fields[:2] == ["C", str(cycle)], "capture sequence"
        actual = list(map(int, fields[2:]))
        expected = ref.step(vector)
        if not vector[0]:
            last_launch = -100
        assert actual[4] == expected[4], f"duplicate sample launch cycle={cycle}"
        assert actual[2] == expected[2] and actual[7] == expected[7], f"result id corruption cycle={cycle}"
        assert actual[0:2] == expected[0:2] and actual[5:7] == expected[5:7], f"cancel/valid admission mismatch cycle={cycle}"
        assert actual == expected, f"transaction/history mismatch cycle={cycle} got={actual} expected={expected}"
        if expected[4]:
            assert cycle - last_launch >= 4, "launch spacing"
            last_launch = cycle
    assert ref.counts["accepted"] > 500 and ref.counts["cancelled"] > 20
    assert ref.counts["stalls"] > 20 and ref.counts["raw_writes"] > 500
    assert ref.counts["saturations"] > 0
    assert ref.state == "idle" and ref.work is None, "unfinished transaction"
    assert ref.counts["accepted"] == sum(ref.counts[k] for k in ("consumed", "cancelled", "reset_drops")), "transaction conservation"
    return dict(cycles=len(stimulus), depth=depth, **ref.counts)
