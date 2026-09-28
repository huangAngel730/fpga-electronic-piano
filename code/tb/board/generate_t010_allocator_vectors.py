#!/usr/bin/env python3
"""Independent four-slot recency oracle for T010 external-port vector testing."""
import argparse
from collections import Counter
from pathlib import Path
import random


class Oracle:
    def __init__(self):
        self.reset()

    def reset(self):
        self.slots = [None] * 4
        self.order = list(range(4))  # oldest -> newest; no modulo timestamps

    def step(self, rst, on, off, source, channel, note, done):
        if not rst:
            self.reset()
            return 0, 0, 0, 0, "reset"
        before = self.slots.copy()
        matches = [i for i, slot in enumerate(before)
                   if slot is not None and slot[:3] == (source, channel, note)]
        active_off = [i for i in matches if before[i][3] == "active"]
        idle = [i for i, slot in enumerate(before) if slot is None]
        kind = "idle"
        alloc = matches[0] if matches else (idle[0] if idle else self.order[0])
        if on:
            kind = "retrigger" if matches else ("new" if idle else "steal")
        for i in range(4):
            if done & (1 << i) and before[i] is not None and before[i][3] == "release":
                self.slots[i] = None
        if on:
            self.slots[alloc] = (source, channel, note, "active")
            self.order.remove(alloc)
            self.order.append(alloc)
        if off:
            for i in active_off:
                self.slots[i] = (source, channel, note, "release")
        return int(on), alloc if on else 0, int(off and bool(active_off)), (active_off[-1] if active_off else 0), kind


def generate(path, seed, random_count):
    oracle = Oracle()
    rnd = random.Random(seed)
    steps = []
    # Many wraps on each slot, then release/steal; include all four identities.
    directed = [(0, 0, 0, 0, 0, 0, 0)]
    directed += [(1, 1, 0, 0, 0, 60 + i, 0) for i in range(4)]
    directed += [(1, 1, 0, 0, 0, 60, 0)] * 25
    directed += [(1, 1, 0, 0, 0, 64, 0), (1, 0, 1, 0, 0, 63, 0),
                 (1, 1, 0, 0, 0, 63, 0), (1, 1, 0, 1, 1, 63, 0),
                 (1, 0, 1, 1, 1, 63, 0), (1, 0, 0, 0, 0, 0, 8),
                 (1, 1, 0, 1, 1, 63, 0)]
    directed += [(1, 1, 0, 0, 0, 65 + i % 4, 0) for i in range(64)]
    # Completion coincident with retrigger must not erase the new attack.
    directed += [(0, 0, 0, 0, 0, 0, 0),
                 (1, 1, 0, 0, 0, 60, 0),
                 (1, 0, 1, 0, 0, 60, 0),
                 (1, 1, 0, 0, 0, 60, 1),
                 (1, 0, 1, 0, 0, 60, 0),
                 (1, 0, 0, 0, 0, 0, 1),
                 (1, 1, 0, 0, 0, 61, 0)]
    directed += [(0, 0, 0, 0, 0, 0, 0)]
    coverage = Counter()

    def record(event):
        rst, on, off, src, ch, note, done = event
        av, aslot, rv, rslot, kind = oracle.step(*event)
        coverage[kind] += 1
        steps.append((*event, av, aslot, rv, rslot))

    for event in directed:
        record(event)
    for index in range(random_count):
        if index % 173 == 0:
            record((0, 0, 0, 0, 0, 0, 0))
        used = [(i, slot) for i, slot in enumerate(oracle.slots) if slot is not None]
        pending = [i for i, slot in used if slot[3] == "release"]
        action = rnd.randrange(100)
        src = rnd.randrange(3)
        ch = rnd.randrange(3)
        note = rnd.randrange(21, 109)
        on = off = 0
        done = 0
        if action < 47:
            on = 1
            if used and rnd.randrange(3) != 0:
                _, slot = rnd.choice(used)
                src, ch, note, _ = slot
        elif action < 76:
            off = 1
            active = [slot for _, slot in used if slot[3] == "active"]
            if active and rnd.randrange(4) != 0:
                src, ch, note, _ = rnd.choice(active)
        elif pending:
            done = 1 << rnd.choice(pending)
            if action > 90:
                on = 1
                slot = oracle.slots[done.bit_length() - 1]
                src, ch, note, _ = slot
        else:
            on = 1
        record((1, on, off, src, ch, note, done))
    expected = {"reset", "new", "steal", "retrigger"}
    if len(steps) < 1000 or not expected <= coverage.keys() or not coverage["steal"] > 40:
        raise ValueError(f"Insufficient T010 scenario coverage: {coverage}")
    path.write_text("\n".join(" ".join(map(str, row)) for row in steps) + "\n", encoding="ascii")
    return len(steps), dict(coverage)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("out", type=Path)
    cli.add_argument("--seed", type=int, default=20260928)
    cli.add_argument("--random-count", type=int, default=2000)
    args = cli.parse_args()
    count, coverage = generate(args.out, args.seed, args.random_count)
    print(f"T010 oracle vectors={count} coverage={coverage}")


if __name__ == "__main__":
    main()
