"""Independent raw-token replay for the two T060 diagnostic counters only."""
import argparse
import hashlib
import json
from collections import deque
from itertools import groupby
from pathlib import Path


def replay(path):
    raw = path.read_bytes()
    rows = [line.split() for line in raw.decode("utf-8").splitlines() if line.strip()]
    ends = [row for row in rows if row[0] == "END"]
    if len(ends) != 1 or rows[-1][0] != "END":
        raise ValueError("unique terminal END required")
    queue = deque()
    full_cycles, edge_cycles = [], []
    last_frame = pushes = pops = peak = resets = same_edge = 0
    previous_cycle = -1
    for cycle, iterator in groupby(rows[:-1], key=lambda row: int(row[1])):
        if cycle < previous_cycle:
            raise ValueError("non-monotonic cycle")
        previous_cycle = cycle
        group = list(iterator)
        tags = [row[0] for row in group]
        if "R" in tags:
            if tags.count("R") != 1 or any(t in tags for t in ("P", "E", "K")):
                raise ValueError("reset/transaction collision")
            queue.clear()
            last_frame = 0
            resets += 1
            continue
        pushed = [row for row in group if row[0] == "P"]
        popped = [row for row in group if row[0] == "E"]
        if len(pushed) > 1 or len(popped) > 1:
            raise ValueError("multiple FIFO handshakes")
        if len(queue) == 32 and pushed and popped:
            full_cycles.append(cycle)
        if popped:
            if not queue or queue.popleft() != int(popped[0][2], 16):
                raise ValueError("empty pop or payload mismatch")
            pops += 1
        if pushed:
            queue.append(int(pushed[0][2], 16))
            pushes += 1
        if len(queue) > 32:
            raise ValueError("FIFO overflow")
        peak = max(peak, len(queue))
        if "E" in tags and "K" in tags:
            if tags.index("E") >= tags.index("K"):
                raise ValueError("E must precede K in the observer")
            same_edge += 1
        for row in group:
            if row[0] == "E" and cycle - last_frame < 64:
                edge_cycles.append(cycle)
            elif row[0] == "K":
                last_frame = cycle
    end = [int(token) for token in ends[0][1:]]
    if len(end) != 9:
        raise ValueError("END field count")
    matches = len(full_cycles) == end[2] and len(edge_cycles) == end[4]
    result = {
        "method": "Independent M2 raw F token replay, not closure_audit.scan or END-derived expectations",
        "full_pop_push": len(full_cycles), "edge_events": len(edge_cycles),
        "full_cycles": full_cycles, "edge_cycles": edge_cycles,
        "pushes": pushes, "pops": pops, "peak": peak, "remaining": len(queue),
        "reset_records": resets, "E_before_K_edges": same_edge,
        "END_two_fields_match": matches, "f_sha256": hashlib.sha256(raw).hexdigest(),
    }
    print(json.dumps(result, indent=2))
    return 0 if matches else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    raise SystemExit(replay(args.capture))
