"""Independent integer reference and fail-closed T058 capture checker."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / "code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence"
BASELINE = ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sealed_samples(name):
    manifest = json.loads((RAW / "raw_manifest.json").read_text(encoding="utf-8"))
    key = name + "_capture.b64"
    data = base64.b64decode((RAW / key).read_bytes(), validate=False)
    item = manifest[key]
    if digest(data) != item["raw_sha256"] or len(data) != item["raw_bytes"]:
        raise ValueError("RAW_CAPTURE_IDENTITY")
    values = []
    for line in data.decode("utf-8").splitlines():
        if line.startswith("A "):
            parts = line.split()
            if len(parts) != 6:
                raise ValueError("RAW_A_FIELDS")
            _, time_ns, adoption, request_id, left, right = parts
            row = (int(adoption) - 1, int(left), int(right))
            if row[0] != len(values) or any(not -8388608 <= v <= 8388607 for v in row[1:]):
                raise ValueError("RAW_A_RANGE_OR_SEQUENCE")
            values.append(row)
    if len(values) != {"normal": 5849, "diagnostic": 41}[name]:
        raise ValueError("RAW_A_COUNT")
    return values, {"raw_sha256": digest(data), "raw_bytes": len(data), "adoptions": len(values)}


def baseline_identity():
    path = ROOT / "code/docs/evidence/pcm_waveform_L_baseline_20261007.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if len(evidence["files"]) != 56:
        raise ValueError("BASELINE_COUNT")
    for item in evidence["files"]:
        if digest((BASELINE / item["path"]).read_bytes()) != item["git_carrier_sha256"]:
            raise ValueError("BASELINE_SHA " + item["path"])
    return {"manifest_sha256": digest(path.read_bytes()), "verified_inputs": 56}


def prepare(out):
    normal, normal_identity = sealed_samples("normal")
    diagnostic, diagnostic_identity = sealed_samples("diagnostic")
    (out / "normal.txt").write_text("".join(f"{s} {a} {b}\n" for s, a, b in normal), encoding="ascii")
    lines = []
    coverage = []

    def tick(flags=49, x=64, y=191, seq=0, left=0, right=0):
        lines.append(f"{flags} {x} {y} {seq & 0xffffffff} {left} {right}\n")

    def reset():
        tick(0)
        tick()

    def send(rows):
        for s, a, b in rows:
            tick(57, seq=s, left=a, right=b)

    def publish():
        tick(53)
        tick()
        tick()

    def scan():
        for y in range(64, 320):
            for x in range(64, 576):
                tick(x=x, y=y)
        for x, y in [(63, 64), (576, 64), (64, 63), (64, 320), (575, 319)]:
            tick(x=x, y=y)
        tick(1, x=64, y=191)  # DE/enable off
        tick(17, x=64, y=191)  # enable off
        tick(33, x=64, y=191)  # DE off
        tick()
        tick()

    reset()
    send(diagnostic)
    publish()
    coverage.append("sealed diagnostic 41 A: asymmetric L/R, zero, underrun hold/recovery; no complete window")
    reset()
    # Include quantization boundaries, signed extrema and spikes in every one
    # of the four positions of a bin; right is deliberately inverted.
    extremes = [-8388608, -65537, -65536, -1, 0, 1, 65535, 65536, 8388607]
    rows = [(s, extremes[s % len(extremes)], -1) for s in range(2049)]
    send(rows[:2047]);publish()
    send(rows[2047:2048]);publish();scan()
    send(rows[2048:]);publish()
    coverage += ["2047/2048/2049, signed boundaries, every-column min/max, two-cycle output"]
    reset()
    send([(s, 8388607 if s % 16 in (0, 5, 10, 15) else -8388608, 0) for s in range(2048)])
    publish();scan()
    coverage.append("spike retention in all four bin positions and inclusive mapping extrema")
    # Keep an immutable front while replacing pending three times without a
    # video frame. All input packages are accepted with no ready port.
    send([(s, 0 if s < 6144 else 8388607, -8388608) for s in range(2048, 10240)])
    scan();publish();scan()
    coverage.append("back-to-back input, frozen front, pending replacement/drop count, stopped stream")
    # Gap/repeat reset only incomplete capture, retain the last front snapshot.
    send([(10242, 0, 1), (10242, -1, 1), (10243, 1, 1)])
    publish()
    tick(59, seq=8, left=8388607)  # restart wins over valid
    send([((0xfffffc00 + s) & 0xffffffff, -65536 if s % 2 else 65536, 8388607) for s in range(2048)])
    publish();scan()
    coverage += ["gap/repeat recovery, restart priority, nonzero first seq, normal u32 wrap"]
    # Publish and completion coincide: publish the OLD pending, retain NEW one.
    reset()
    send([(s, 0, 0) for s in range(4095)])
    tick(61, seq=4095, left=65536, right=0)
    tick();publish()
    tick(0);tick();send([(987, 1, 0), (988, 2, 0), (989, 3, 0)])
    tick(51);tick();send([(100, -1, 0)])
    coverage += ["simultaneous publish/completion, reset in partial bin, incomplete trailing bin"]
    (out / "vectors.txt").write_text("".join(lines), encoding="ascii")
    return {"normal": normal_identity, "diagnostic": diagnostic_identity,
            "directed_cycles": len(lines), "coverage": coverage,
            "full_scan": "8 x 800 x 525; last frame waveform_enable=0"}


def row_hash(y, values, enabled):
    bins = None
    if values is not None:
        bins = [(min(values[i:i+4]) >> 16, max(values[i:i+4]) >> 16)
                for i in range(0, 2048, 4)]
    result = 5381
    for x in range(800):
        pixel = 0
        if enabled and 64 <= x <= 575 and 64 <= y <= 319:
            color = 0x404040 if y == 191 else 0x081020
            if bins is not None:
                low, high = bins[x-64]
                if 191-high <= y <= 191-low:
                    color = 0x00e0ff
            pixel = (1 << 24) | color
        result = ((result * 33) ^ pixel) & 0xffffffff
    return result


def check_capture(path):
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or lines[0] != "HEADER T058 1" or not lines[-1].startswith("END "):
        raise ValueError("CAPTURE_HEADER_OR_END")
    current, pending, front, previous = [], None, None, None
    frames, rows = {}, set()
    gap_count = drop_count = 0
    full_samples = []
    diagnostic_packets = 0
    diagnostic_samples = []
    reset_count = 0
    previous_cycle = 0
    first_error = None
    for number, line in enumerate(lines[1:-1], 2):
        parts = line.split()
        kind = parts[0]
        if kind in ("R", "T", "V", "I"):
            cyc = int(parts[1])
            if cyc < 1 or cyc < previous_cycle:
                raise ValueError("RECORD_CYCLE")
            previous_cycle = cyc
        if kind in ("R", "T") and len(parts) == 2:
            current, pending, front, previous = [], None, None, None
            if kind == "R":
                gap_count = drop_count = 0
                reset_count += 1
        elif kind == "V" and len(parts) == 3:
            if pending is not None:
                front, pending = pending, None
            f = int(parts[2])
            if f >= 0:
                if f in frames or f != len(frames):
                    raise ValueError("FRAME_ORDER")
                frames[f] = front
        elif kind == "I" and len(parts) == 7:
            # Includes the cycle, seq, L/R and restart bit (six fields total).
            raise ValueError("INPUT_FIELD_COUNT")
        elif kind == "I" and len(parts) == 6:
            _, cyc, seq, left, right, restart = parts
            s, a, b = int(seq), int(left), int(right)
            if not 0 <= s <= 0xffffffff or any(not -8388608 <= v <= 8388607 for v in (a, b)):
                raise ValueError("INPUT_RANGE")
            if int(restart):
                continue
            if frames:
                full_samples.append((s, a, b))
            elif reset_count == 1:
                diagnostic_packets += 1
                diagnostic_samples.append((s, a, b))
            if previous is not None and s != ((previous + 1) & 0xffffffff):
                current = []
                gap_count = min(0xffffffff, gap_count + 1)
            previous = s
            current.append(a)
            if len(current) == 2048:
                if pending is not None:
                    drop_count = min(0xffffffff, drop_count + 1)
                pending, current = current, []
        elif kind == "L" and len(parts) == 5:
            f, y, actual, tb_expected = map(int, parts[1:])
            if f not in frames or not 0 <= y < 525 or (f, y) in rows:
                raise ValueError("ROW_IDENTITY")
            rows.add((f, y))
            expected = row_hash(y, frames[f], f != 7)
            if actual != expected or tb_expected != expected:
                first_error = first_error or "PIXEL_REFERENCE"
        elif kind == "ERROR_PIXEL" and len(parts) == 6:
            first_error = first_error or "PIXEL_REFERENCE"
        elif kind == "ERROR_STATE" and len(parts) == 8:
            first_error = first_error or "STATE_REFERENCE"
        else:
            raise ValueError(f"UNKNOWN_OR_MALFORMED_RECORD {number}")
    end = lines[-1].split()
    if len(end) != 8:
        raise ValueError("END_FIELDS")
    checks, pixels, states, samples, nframes, gaps, drops = map(int, end[1:])
    normal, _ = sealed_samples("normal")
    if full_samples != normal:
        raise ValueError("SEALED_NORMAL_REPLAY")
    if checks < 3360000 or samples != 5849 or nframes != 8 or len(frames) != 8 or len(rows) != 4200:
        raise ValueError("END_COVERAGE")
    if gaps != gap_count or drops != drop_count:
        raise ValueError("END_COUNTERS")
    diagnostic, _ = sealed_samples("diagnostic")
    if diagnostic_packets != 41 or diagnostic_samples != diagnostic:
        raise ValueError("DIAGNOSTIC_COVERAGE")
    if first_error or pixels or states:
        raise ValueError(first_error or "ORACLE_ERRORS")
    return {"checks": checks, "full_scan_pixels": 3360000, "rows": len(rows),
            "normal_samples": samples, "diagnostic_samples": diagnostic_packets,
            "pixel_errors": pixels, "state_errors": states, "passed": True}
