"""Fixed-seed N32-A inputs and independent post-edge snapshots.

INJECT labels identify adversarial pre-edge state tests. They test the frozen
transition function and are not claimed reachable from reset through events.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random

from reference import Allocator, Edge, Slot


DEFAULT_SEED = 0x3261


def build_vectors(n, seed=DEFAULT_SEED, random_edges=1024):
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("SEED_RANGE")
    if type(random_edges) is not int or not 0 <= random_edges <= 100000:
        raise ValueError("RANDOM_COUNT")
    rng = random.Random(seed)
    model = Allocator(n)
    result = []

    def add(label, edge, slots=None):
        packed = None if slots is None else [s.packed(model.sw) for s in slots]
        if packed is not None:
            model.load_slots(packed)
        result.append({"index": len(result), "label": label,
                       "input": asdict(edge), "inject_slots": packed,
                       "expected": model.step(edge)})

    def reset(label):
        add(label, Edge(rst_n=0, note_on=1, note_off=1,
                        source=15, channel=15, note=255,
                        release_done=(1 << n) - 1))

    reset("RESET_initial")
    add("IDLE_outputs_hold", Edge())
    for i in range(n):
        add(f"FILL_{i}", Edge(note_on=1, source=1, channel=2, note=i))
    add("FULL_steal_oldest", Edge(note_on=1, source=3, channel=4, note=255))
    add("MATCH_active_retrigger", Edge(note_on=1, source=1, channel=2,
                                       note=n - 1))
    add("OFF_release", Edge(note_off=1, source=1, channel=2, note=n - 1))
    add("MATCH_release_retrigger", Edge(note_on=1, source=1, channel=2,
                                        note=n - 1))
    add("OFF_release_again", Edge(note_off=1, source=1, channel=2,
                                  note=n - 1))
    add("DONE_release", Edge(release_done=1 << (n - 1)))
    add("IDLE_reuse", Edge(note_on=1, source=6, channel=7, note=128))
    add("MISS_off_output_holds", Edge(note_off=1, source=15, channel=15,
                                     note=254))
    add("IDENTITY_source_isolation", Edge(note_on=1, source=7, channel=7,
                                          note=128))
    add("IDENTITY_channel_isolation", Edge(note_on=1, source=7, channel=8,
                                           note=128))

    # All eight combinations of the three enables, with old active identity in
    # slot 0 and an old release in slot 1. Each starts from a reachable reset.
    for combination in range(8):
        reset(f"RESET_combo_{combination}")
        add(f"COMBO_{combination}_active", Edge(note_on=1, source=1,
                                               channel=2, note=60))
        add(f"COMBO_{combination}_other", Edge(note_on=1, source=2,
                                              channel=3, note=61))
        add(f"COMBO_{combination}_release", Edge(note_off=1, source=2,
                                                channel=3, note=61))
        add(f"COMBO_{combination}_edge",
            Edge(note_on=combination & 1, note_off=(combination >> 1) & 1,
                 release_done=2 if combination & 4 else 0,
                 source=1, channel=2, note=60))

    # Filled reachable state: completion cannot become this edge's IDLE choice.
    reset("RESET_done_not_idle")
    for i in range(n):
        add(f"DONE_NOT_IDLE_fill_{i}", Edge(note_on=1, source=1,
                                          channel=1, note=i))
    add("DONE_NOT_IDLE_release_last", Edge(note_off=1, source=1,
                                          channel=1, note=n - 1))
    add("DONE_NOT_IDLE_same_edge", Edge(note_on=1, source=9, channel=9,
                                       note=200, release_done=1 << (n - 1)))

    # Injection tests are explicit; they do not break the normal random chain.
    reset("RESET_before_injection")
    duplicate = [Slot(active=1, source=5, channel=6, note=70, age=i)
                 for i in range(n)]
    add("INJECT_duplicate_identity_off_all_max_public",
        Edge(note_off=1, source=5, channel=6, note=70), duplicate)
    add("INJECT_duplicate_identity_match_min",
        Edge(note_on=1, source=5, channel=6, note=70), duplicate)
    add("INJECT_duplicate_on_off_done_priority",
        Edge(note_on=1, note_off=1, source=5, channel=6, note=70,
             release_done=(1 << n) - 1), duplicate)
    tied = [Slot(active=1, source=2, channel=2, note=i,
                 age=0 if i in (1, n - 1) else n - 1) for i in range(n)]
    add("INJECT_lru_tie_min_slot", Edge(note_on=1, source=8,
                                      channel=8, note=240), tied)
    match_idle = [Slot(age=i) for i in range(n)]
    match_idle[n - 1] = Slot(release=1, source=3, channel=3, note=90,
                             age=n - 1)
    add("INJECT_match_over_idle", Edge(note_on=1, source=3,
                                      channel=3, note=90), match_idle)
    reset("RESET_after_injection")

    for i in range(random_edges):
        slots = [s for s in model.slots if s.active or s.release]
        if slots and rng.randrange(3) != 0:
            identity = rng.choice(slots)
            source, channel, note = identity.source, identity.channel, identity.note
        else:
            source, channel, note = rng.randrange(16), rng.randrange(16), rng.randrange(256)
        edge = Edge(rst_n=0 if i and i % 257 == 0 else 1,
                    note_on=rng.randrange(2), note_off=rng.randrange(2),
                    source=source, channel=channel, note=note,
                    release_done=rng.getrandbits(n))
        add(f"RANDOM_{i}", edge)
    reset("RESET_final")
    add("FINAL_idle", Edge())
    return result


def jsonl_bytes(rows):
    return b"".join((json.dumps(row, sort_keys=True, separators=(",", ":"))
                     + "\n").encode("utf-8") for row in rows)


def vector_fingerprints(rows):
    inputs = [{key: row[key] for key in ("index", "label", "input", "inject_slots")}
              for row in rows]
    expected = [{"index": row["index"], **row["expected"]} for row in rows]
    return {"input_sha256": hashlib.sha256(jsonl_bytes(inputs)).hexdigest(),
            "expected_sha256": hashlib.sha256(jsonl_bytes(expected)).hexdigest(),
            "combined_sha256": hashlib.sha256(jsonl_bytes(rows)).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--seed", type=lambda s: int(s, 0), default=DEFAULT_SEED)
    parser.add_argument("--random-edges", type=int, default=1024)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = build_vectors(args.n, args.seed, args.random_edges)
    data = jsonl_bytes(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(data)
    print(json.dumps({"kind": "SOFTWARE_VECTORS_NOT_CAPTURE", "n": args.n,
                      "seed": args.seed, "rows": len(rows),
                      **vector_fingerprints(rows),
                      "injected_edges": sum(row["inject_slots"] is not None
                                            for row in rows)}))


if __name__ == "__main__":
    main()
