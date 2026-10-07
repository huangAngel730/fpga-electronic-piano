"""Independent oracle for public observer packets and actual joint raster output."""
from __future__ import annotations
import argparse
import base64
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
ROOT = Path(__file__).resolve().parents[5]
CAP = ROOT / 'code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def check_baseline():
    path = ROOT / 'code/docs/evidence/m3_night_tasks_baseline_20261007.json'
    table = json.loads(path.read_text(encoding='utf-8'))
    for name, expected in table['frozen_candidate_sha256'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError('FROZEN_SOURCE_SHA ' + name)
    return table

def prepare(out):
    check_baseline()
    manifest = json.loads((CAP / 'raw_manifest.json').read_text(encoding='utf-8'))
    info = {}
    for name in ('normal', 'diagnostic'):
        key = name + '_capture.b64'
        raw = base64.b64decode((CAP / key).read_bytes())
        if sha(raw) != manifest[key]['raw_sha256']:
            raise ValueError('SEALED_A_SHA')
        values = [line.split() for line in raw.decode('ascii').splitlines() if line.startswith('A ')]
        if len(values) != {'normal': 5849, 'diagnostic': 41}[name]:
            raise ValueError('SEALED_A_COUNT')
        rows = []
        for i, v in enumerate(values):
            if int(v[2]) != i + 1:
                raise ValueError('SEALED_A_ORDINAL')
            period = (Decimal(values[i + 1][1]) - Decimal(v[1])) / 25 if i + 1 < len(values) else Decimal(833)
            if period != int(period) or period < 1:
                raise ValueError('SEALED_A_INTERVAL')
            rows.append((i, int(v[4]), int(v[5]), int(period)))
        path = out / (name + '.txt')
        path.write_text(''.join((' '.join(map(str, row)) + '\n' for row in rows)), encoding='ascii')
        info[name] = {'count': len(rows), 'frames': 12 if name == 'normal' else 1, 'raw_sha256': sha(raw), 'vector_sha256': sha(path.read_bytes())}
    rng = random.Random(580710)
    rows = []
    extremes = (-8388608, 8388607, -65537, -65536, -1, 0, 1, 65535, 65536)
    for i in range(10500):
        left = extremes[i % len(extremes)] if i % 32 < 12 else rng.randrange(-8388608, 8388608)
        if i % 64 < 8:
            left = 0
        right = 8388607 - left if left >= 0 else -8388608 - left
        rows.append((i, left, right, 833 + (i % 3 == 2)))
    path = out / 'stress.txt'
    path.write_text(''.join((' '.join(map(str, row)) + '\n' for row in rows)), encoding='ascii')
    info['stress'] = {'count': len(rows), 'frames': 14, 'first_seq': 4294967290, 'seed': 580710, 'synthetic': True, 'vector_sha256': sha(path.read_bytes())}
    return info

def check(capture, vectors):
    raw = capture.read_text(encoding='ascii').splitlines()
    if not raw or not raw[0].startswith('HEADER JOINT 1 ') or (not raw[-1].startswith('END ')):
        raise ValueError('CAPTURE_HEADER_END')
    header = raw[0].split()
    if len(header) != 7:
        raise ValueError('HEADER_FIELDS')
    case = header[3]
    first, count, nframes = map(int, header[4:])
    if case not in ('normal', 'diagnostic', 'stress') or nframes != {'normal': 12, 'diagnostic': 1, 'stress': 14}[case]:
        raise ValueError('CASE_IDENTITY')
    stimulus = [tuple(map(int, line.split())) for line in vectors.read_text(encoding='ascii').splitlines()]
    if len(stimulus) != count:
        raise ValueError('STIMULUS_COUNT')
    rows = {}
    samples = {}
    events = {}
    frame_events = {}
    state = {}
    resets = set()
    adopts = []
    observed = []
    deliveries = []
    enqueued = []
    public_drops = 0
    peak = 0
    clocks = set()
    resets_seen = []
    ordinal = first
    bad_pixels = bad_states = 0
    final = None
    branches = 0
    source_history = {}
    accepted_packets = {}
    delivered_ids = set()
    last_delivery = {}
    last_observed = {}
    for lineno, line in enumerate(raw[1:-1], 2):
        p = line.split()
        kind = p[0]
        if kind == 'A' and len(p) == 8:
            time, branch, epoch, index, seq, l, r = map(int, p[1:])
            if index != len(adopts) or seq != ordinal or (index, l, r) != stimulus[index][:3]:
                raise ValueError('SOURCE_PCM_ORDINAL')
            ordinal = ordinal + 1 & 4294967295
            adopts.append((time, branch, epoch, seq, l, r))
            source_history[epoch, seq] = (l, r)
        elif kind == 'O' and len(p) == 12:
            time, branch, epoch, seq, l, r, accepted, drop, level, dc, source_up = map(int, p[1:])
            peak = max(peak, level)
            if source_up not in (0, 1) or accepted not in (0, 1) or drop not in (0, 1) or (accepted + drop != source_up) or (not 0 <= level <= 32):
                raise ValueError('QUEUE_PUBLIC_FLAGS')
            if source_history.get((epoch, seq)) != (l, r):
                raise ValueError('OBSERVER_PUBLIC_PCM')
            if (epoch, seq) in last_observed:
                raise ValueError('DUPLICATE_OBSERVATION')
            last_observed[epoch, seq] = time
            observed.append((branch, epoch, seq, l, r))
            public_drops += drop
            if accepted:
                packet = (branch, epoch, seq, l, r)
                accepted_packets[packet] = (time, len(enqueued))
                enqueued.append(packet)
        elif kind == 'D' and len(p) == 9:
            cycle, time, branch, epoch, seq, l, r, restart = map(int, p[1:])
            if restart or cycle in samples:
                raise ValueError('RESTART_VALID_PRIORITY')
            packet = (branch, epoch, seq, l, r)
            if packet not in accepted_packets:
                raise ValueError('DELIVERY_NOT_ENQUEUED')
            at, order = accepted_packets[packet]
            if at >= time or order <= last_delivery.get(branch, -1):
                raise ValueError('DELIVERY_ORDER')
            last_delivery[branch] = order
            if (epoch, seq) in delivered_ids:
                raise ValueError('DUPLICATE_DELIVERY')
            delivered_ids.add((epoch, seq))
            deliveries.append((cycle, branch, epoch, seq, l, r))
            samples[cycle] = (seq, l)
        elif kind == 'B' and len(p) == 4:
            _, branch, mode = map(int, p[1:])
            branches = branch
            resets_seen.append(mode)
            if mode == 2:
                ordinal = first
        elif kind == 'Z' and len(p) == 5:
            time, cycle, branch, epoch = map(int, p[1:])
            resets.add(cycle + 1)
        elif kind == 'R' and len(p) == 2:
            resets.add(int(p[1]))
        elif kind == 'T' and len(p) == 3:
            events[int(p[1])] = 'restart'
        elif kind == 'C' and len(p) == 3:
            clocks.add(p[2])
        elif kind == 'F' and len(p) == 6:
            cycle, f, en, rst, tv = map(int, p[1:])
            if cycle in frame_events or f != len(frame_events) or cycle != f * 420000 + 1 or (en != 1):
                raise ValueError('RASTER_FRAME')
            frame_events[cycle] = (f, en)
        elif kind == 'S' and len(p) == 5:
            cycle, tv, gap, drop = map(int, p[1:])
            state[cycle] = (tv, gap, drop)
        elif kind == 'L' and len(p) == 5:
            cycle, f, y, hash_value = map(int, p[1:])
            key = (f, y)
            if key in rows or cycle != f * 420000 + (y + 1) * 800:
                raise ValueError('RASTER_ROW_IDENTITY')
            rows[key] = hash_value
        elif kind == 'BAD_PIXEL' and len(p) == 6:
            bad_pixels += 1
        elif kind == 'BAD_STATE' and len(p) == 8:
            bad_states += 1
        elif kind == 'FINAL' and len(p) == 6:
            final = tuple(map(int, p[1:]))
        else:
            raise ValueError('UNKNOWN_RECORD ' + str(lineno) + ' ' + kind)
    tail = list(map(int, raw[-1].split()[1:]))
    if len(tail) != 8:
        raise ValueError('END_FIELDS')
    cycles, pixels, pixel_errors, state_errors, loads, obs, delivered, nrows = tail
    if not final or final[0] != cycles or cycles != nframes * 420000 + 1 or (pixels != cycles) or (loads != count) or (len(adopts) != count) or (obs != len(observed)) or (delivered != len(deliveries)) or (nrows != len(rows)) or (nrows != nframes * 525):
        raise ValueError('END_COVERAGE_COUNTS')
    if case != 'stress':
        if public_drops or len(deliveries) != count:
            raise ValueError('REAL_A_DROPPED')
        for i in range(count - 1):
            if adopts[i + 1][0] - adopts[i][0] != stimulus[i][3] * 25000:
                raise ValueError('REAL_A_INTERVAL_CHANGED')
    else:
        required = {'pixel_stop', 'pixel_resume', 'pixel_stop_reset', 'pixel_resume_reset', 'audio_stop', 'audio_resume'}
        if clocks != required or resets_seen != [1, 2] or (not public_drops) or (peak != 32):
            raise ValueError('STRESS_COVERAGE')
        if not any((d[3] < 8 for d in deliveries[:50])):
            raise ValueError('U32_WRAP_COVERAGE')
    buf = []
    pending = None
    front = None
    previous = None
    gap = drop = 0
    pipe = [0, 0, 0]
    pending_metadata = front_metadata = None
    frame_summaries = []
    complete_windows = 0
    published = 0
    trace_rows = 0
    mismatch = None
    row_hash = 5381
    for cycle in range(1, cycles + 1):
        idx = (cycle - 1) % 420000
        x = idx % 800
        y = idx // 800
        f = (cycle - 1) // 420000
        if cycle in resets:
            buf = []
            pending = front = previous = None
            gap = drop = 0
            pipe = [0, 0, 0]
            pending_metadata = front_metadata = None
            now = 0
        else:
            if cycle in events:
                buf = []
                pending = front = previous = None
                pending_metadata = front_metadata = None
            elif cycle in frame_events and pending is not None:
                front = pending
                pending = None
                published += 1
                front_metadata = pending_metadata
                pending_metadata = None
            if cycle in samples and cycle not in events:
                seq, left = samples[cycle]
                if previous is not None and seq != previous + 1 & 4294967295:
                    buf = []
                    gap = min(4294967295, gap + 1)
                previous = seq
                buf.append(left)
                if len(buf) == 2048:
                    if pending is not None:
                        drop = min(4294967295, drop + 1)
                    pending = [(min(buf[i:i + 4]) >> 16, max(buf[i:i + 4]) >> 16) for i in range(0, 2048, 4)]
                    pending_metadata = dict(first_seq=seq - 2047 & 4294967295, last_seq=seq, bins_sha256=sha(json.dumps(pending, separators=(',', ':')).encode()))
                    buf = []
                    complete_windows += 1
            now = 0
            if 64 <= x <= 575 and 64 <= y <= 319:
                color = 4210752 if y == 191 else 528416
                if front is not None:
                    lo, hi = front[x - 64]
                    if 191 - hi <= y <= 191 - lo:
                        color = 57599
                now = 1 << 24 | color
            pipe = [now, pipe[0], pipe[1]]
        row_hash = (row_hash * 33 ^ pipe[2]) & 4294967295
        if cycle in frame_events:
            frame_summaries.append(dict(frame=f, cycle=cycle, trace_valid=front is not None, snapshot=front_metadata, gap=gap, window_drop=drop))
        if cycle in state and state[cycle] != (int(front is not None), gap, drop):
            mismatch = mismatch or 'STATE_REFERENCE'
        if x == 799:
            if rows.get((f, y)) != row_hash:
                mismatch = mismatch or 'PIXEL_REFERENCE'
            if front is not None and 64 <= y <= 319:
                trace_rows += 1
            row_hash = 5381
    if final[1:4] != (int(front is not None), gap, drop):
        mismatch = mismatch or 'STATE_REFERENCE'
    if pixel_errors or bad_pixels:
        mismatch = mismatch or 'PIXEL_REFERENCE'
    if state_errors or bad_states:
        mismatch = mismatch or 'STATE_REFERENCE'
    if case != 'diagnostic' and (complete_windows < 2 or published < 2 or (not trace_rows)):
        raise ValueError('TRACE_WINDOW_COVERAGE')
    if case == 'stress' and front is None:
        raise ValueError('POST_RESET_WINDOW_RECOVERY')
    if mismatch:
        raise ValueError(mismatch)
    return dict(case=case, passed=True, pixel_comparisons=pixels, python_rows=len(rows), loads=loads, delivered=delivered, observed=obs, complete_windows=complete_windows, published=published, public_drop_events=public_drops, queue_peak=peak, trace_rows=trace_rows, final_gap=gap, final_window_drop=drop, frame_summaries=frame_summaries)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('capture', type=Path)
    parser.add_argument('--vectors', type=Path, required=True)
    args = parser.parse_args()
    print('PASS', json.dumps(check(args.capture, args.vectors), sort_keys=True))
if __name__ == '__main__':
    try:
        main()
    except (ValueError, IndexError, KeyError, OSError, UnicodeError) as exc:
        print('FAIL', str(exc))
        raise SystemExit(1)
