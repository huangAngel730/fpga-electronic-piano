"""Independent public-observation/FIFO-order checker; no DUT-private state."""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path


def check(capture: Path, vectors: Path | None = None) -> dict:
    raw = capture.read_bytes()
    lines = raw.decode("ascii").splitlines()
    if not lines or not lines[0].startswith("META ") or not lines[-1].startswith("END "):
        raise ValueError("missing META/END or empty capture")
    meta = lines[0].split()
    if len(meta) != 6 or meta[1] != "1" or meta[2] not in ("replay", "isolation"):
        raise ValueError("META schema")
    depth, first, target = map(int, meta[3:])
    if not 2 <= depth <= 32767 or not 0 <= first < 2**32 or target < 1:
        raise ValueError("META limits")
    kind = meta[2]
    # TB prints schema + kind + depth + first + target: exactly SIX fields.
    return _rows(raw, lines, kind, depth, first, target, vectors)


def _rows(raw, lines, kind, depth, first, target, vectors):
    branch = audio_epoch = -1
    next_seq = first
    adopted = {}
    adoption_time = {}
    observed = set()
    pending = deque()
    expected_vectors = None
    if vectors is not None:
        expected_vectors = [tuple(map(int, row.split())) for row in vectors.read_text(encoding="ascii").splitlines()]
        if not expected_vectors or len(expected_vectors) != target:
            raise ValueError("vectors count")
    counts = dict(A=0, O=0, D=0, R=0, I=0, Z=0, C=0, AUDIO=0, STAT=0)
    drops = gaps = resets = accepted = 0
    branch_drops = 0
    last_output_seq = None
    restarted = False
    seen_end = False
    audio_result = None
    t_by_tag = {}
    for line_number, line in enumerate(lines[1:], 2):
        words = line.split()
        if not words or seen_end:
            raise ValueError("blank/records after END")
        tag = words[0]
        if tag == "END":
            if len(words) != 5 or list(map(int, words[1:])) != [counts[x] for x in ("A", "O", "D", "R")]:
                raise ValueError("END counts")
            seen_end = True
            continue
        sizes = dict(Z=5, A=7, O=9, D=7, R=4, I=6, C=3, AUDIO=7, STAT=5)
        if tag not in sizes or len(words) != sizes[tag]:
            raise ValueError(f"unknown/malformed record at {line_number}")
        counts[tag] += 1
        if tag == "AUDIO":
            audio_result = list(map(int, words[1:]))
            continue
        timestamp = int(words[1])
        if timestamp < t_by_tag.get(tag, -1):
            raise ValueError("nonmonotonic timestamp")
        t_by_tag[tag] = timestamp
        if tag == "Z":
            b, a, reset_kind = map(int, words[2:])
            if b != branch + 1 or reset_kind not in (0, 1, 2):
                raise ValueError("reset branch epoch")
            if reset_kind in (0, 2):
                if a != audio_epoch + 1:
                    raise ValueError("audio epoch")
                next_seq = first
                audio_epoch = a
            elif a != audio_epoch:
                raise ValueError("display reset changed audio epoch")
            branch = b
            pending.clear()
            branch_drops = 0
            restarted = False
            last_output_seq = None
            resets += 1
        elif tag == "I":
            idx, left, right, cycles = map(int, words[2:])
            if idx != counts["I"] - 1 or cycles < 1:
                raise ValueError("input sequence/cycles")
            if expected_vectors is not None and (idx, left, right, cycles) != expected_vectors[idx]:
                raise ValueError("input not original vectors")
        elif tag == "C":
            if words[2] not in ("pixel_stop", "pixel_resume", "audio_stop", "audio_resume"):
                raise ValueError("control")
        elif tag == "STAT":
            b, level, reported_drops = map(int, words[2:])
            if b != branch or not 0 <= level <= depth or reported_drops != branch_drops:
                raise ValueError("queue/drop stats")
        else:
            b, a = map(int, words[2:4])
            if (b, a) != (branch, audio_epoch):
                raise ValueError("stale/reset payload epoch")
            if tag == "R":
                if restarted:
                    raise ValueError("duplicate stream_restart")
                restarted = True
                continue
            seq, left, right = map(int, words[4:7])
            if not 0 <= seq < 2**32 or not all(-(2**23) <= x < 2**23 for x in (left, right)):
                raise ValueError("PCM/seq range")
            key = (audio_epoch, seq)
            if tag == "A":
                if seq != next_seq or key in adopted:
                    raise ValueError("adoption ordinal/drop/reset")
                next_seq = (next_seq + 1) % 2**32
                adopted[key] = (left, right)
                adoption_time[key] = timestamp
                if expected_vectors is not None:
                    idx = counts["A"] - 1
                    if (left, right) != expected_vectors[idx][1:3]:
                        raise ValueError("adoption not real input PCM")
            elif tag == "O":
                if key not in adopted or adopted[key] != (left, right) or key in observed:
                    raise ValueError("OBSERVATION_PCM_OR_ORDINAL")
                if timestamp - adoption_time[key] != 25000:
                    raise ValueError("observer not exactly one audio cycle after pre-NBA capture")
                observed.add(key)
                enqueue, drop = map(int, words[7:9])
                if enqueue not in (0, 1) or drop not in (0, 1) or enqueue + drop > 1:
                    raise ValueError("enqueue/drop flags")
                if enqueue:
                    pending.append((seq, left, right))
                    accepted += 1
                elif drop:
                    branch_drops += 1
                    drops += 1
            elif tag == "D":
                if not restarted or not pending or pending.popleft() != (seq, left, right):
                    raise ValueError("DELIVERY_PCM_ORDER_OR_STALE")
                if last_output_seq is not None and seq != (last_output_seq + 1) % 2**32:
                    gaps += 1
                last_output_seq = seq
    if not seen_end or counts["Z"] < 1 or counts["A"] < 1 or counts["O"] < 1 or counts["D"] < 1:
        raise ValueError("empty coverage")
    if kind == "replay":
        if counts["A"] != target or counts["O"] != target or counts["I"] != target or pending:
            raise ValueError("replay count/drain")
        if target > 300 and (drops < 1 or gaps < 1 or counts["Z"] != 3 or counts["R"] != 3):
            raise ValueError("missing reset/full/gap coverage")
    elif (audio_result is None or counts["AUDIO"] != 1 or audio_result[0] < 100000
          or audio_result[1] < target or audio_result[4] < 6 or audio_result[5] < 6
          or drops < 1 or counts["Z"] != 3 or counts["R"] != 3):
        # Display reset with clock stopped delays restart until resumed.
        raise ValueError("missing real audio isolation/underrun/reset/full coverage")
    if abs(counts["A"] - counts["O"]) > 1 or len(pending) > depth + 1:
        raise ValueError("observation tail/capacity")
    return dict(passed=True, capture_sha256=hashlib.sha256(raw).hexdigest(), kind=kind,
                counts=counts, accepted=accepted, dropped=drops, visible_sequence_gaps=gaps,
                queued_tail=len(pending), audio_equivalence=audio_result,
                physical_cdc_verified=False, sta_verified=False, hardware_verified=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--vectors", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.capture, args.vectors)
    except (OSError, ValueError, IndexError, UnicodeError, KeyError) as error:
        print("FAIL", error)
        return 1
    print("PASS", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
