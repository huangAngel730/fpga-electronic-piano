"""M2 independent control-state RTL validation. Standard-library reference.
Not MIDI/FCW/LFO validation and not a production-core build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def packed(values, width):
    return sum((value & ((1 << width) - 1)) << (width * index)
               for index, value in enumerate(values))


def event(kind, source, channel, control=0, value=0):
    return ((kind << 61) | (source << 57) | (channel << 53) |
            (control << 18) | ((value & 4095) << 6))


class Oracle:
    def __init__(self):
        self.bank = {(source, channel): [0, 0, 2]
                     for source in range(16) for channel in range(16)}
        self.snapshot = [0, 0, 0, 0, 0, 0, 0, 0, packed([2] * 4, 5)]

    def step(self, reset, valid, data, occupied, sources, channels,
             generations, capture, sample_id):
        applied = rejected = 0
        if not reset:
            self.__init__()
        else:
            source, channel = (data >> 57) & 15, (data >> 53) & 15
            kind, control, value = (data >> 61) & 7, (data >> 18) & 255, (data >> 6) & 4095
            if valid:
                if kind == 3 and control == 0:
                    self.bank[source, channel][0] = value
                    applied = 1
                elif kind == 4 and control == 1:
                    self.bank[source, channel][1] = value
                    applied = 1
                elif kind == 4 and control == 4:
                    if value <= 24:
                        self.bank[source, channel][2] = value
                        applied = 1
                    else:
                        rejected = 1
        queries = [self.bank[sources[i], channels[i]] if reset and occupied & (1 << i)
                   else [0, 0, 2] for i in range(4)]
        pitch = packed([q[0] for q in queries], 12)
        mod = packed([q[1] for q in queries], 12)
        ranges = packed([q[2] for q in queries], 5)
        if reset and capture:
            self.snapshot = [1, sample_id, occupied, packed(sources, 4),
                             packed(channels, 4), packed(generations, 32), pitch, mod, ranges]
        return [pitch, mod, ranges] + self.snapshot + [applied, rejected]


def vectors():
    oracle = Oracle()
    rows = []
    counts = {}
    def add(label, reset=1, valid=0, data=0, occupied=15,
            sources=(0, 0, 1, 1), channels=(0, 1, 0, 1),
            generations=(1, 2, 3, 4), capture=0, sample_id=0):
        counts[label] = counts.get(label, 0) + 1
        expected = oracle.step(reset, valid, data, occupied, sources, channels,
                               generations, capture, sample_id)
        row = [reset, valid, data, occupied, packed(sources, 4), packed(channels, 4),
               packed(generations, 32), capture, sample_id] + expected
        assert len(row) == 23
        rows.append(" ".join(format(value, "x") for value in row))
    add("reset", reset=0, capture=1, valid=1, data=event(3, 0, 0, value=4095))
    add("defaults", capture=1, sample_id=1)
    # Every identity, including overlapping channel numbers on different sources.
    for source in range(16):
        for channel in range(16):
            lane_sources = (source, source, source ^ 1, source)
            lane_channels = (channel, channel ^ 1, channel, channel)
            for kind, control, value in [(3, 0, (source * 257 + channel * 17) & 4095),
                                          (4, 1, (source * 131 + channel * 257) & 4095),
                                          (4, 4, (source + channel) % 25)]:
                add("all_256_identities", valid=1, data=event(kind, source, channel, control, value),
                    sources=lane_sources, channels=lane_channels, capture=1,
                    generations=(0, 0xffffffff, 7, 8), sample_id=len(rows))
            add("inactive_defaults", sources=lane_sources, channels=lane_channels, occupied=0, capture=1)
    # Raw 12-bit signed patterns: center, positive and negative endpoints included.
    for value in range(4096):
        add("all_signed_pitch_patterns", valid=1, data=event(3, 0, 0, value=value),
            capture=value % 5 == 0, sample_id=len(rows))
    for value in range(4096):
        add("all_unsigned_mod_patterns", valid=1, data=event(4, 0, 0, 1, value),
            capture=value % 7 == 0, sample_id=len(rows))
    for value in range(4096):
        add("range_legal_and_reserved", valid=1, data=event(4, 0, 0, 4, value),
            capture=1, sample_id=len(rows))
    # An unaccepted event can remain at the input for many cycles; it must not
    # write until upstream actually handshakes. accepted_valid is the tap pulse.
    for value in [-2048, -1, 0, 1, 2047]:
        for _ in range(5):
            add("unaccepted_backpressure", valid=0, data=event(3, 0, 0, value=value), capture=1)
        add("accepted_after_backpressure", valid=1, data=event(3, 0, 0, value=value), capture=1)
    # Channel controls survive NoteOff/global panic; a slot reassignment sees
    # destination identity controls and atomically carries its generation tag.
    for kind, control in [(0, 0), (1, 0), (2, 0), (5, 0), (6, 0), (7, 0),
                          (3, 1), (4, 0), (4, 6), (4, 255)]:
        add("ignored_or_note_lifecycle", valid=1, data=event(kind, 0, 0, control, 4095), capture=1)
    add("release_same_identity", sources=(0, 0, 1, 1), channels=(0, 0, 0, 0), capture=1)
    add("steal_changes_query_not_snapshot", sources=(15, 14, 13, 12), channels=(15, 14, 13, 12),
        generations=(101, 102, 103, 104), capture=0)
    add("steal_new_snapshot", sources=(15, 14, 13, 12), channels=(15, 14, 13, 12),
        generations=(101, 102, 103, 104), capture=1, sample_id=0xffffffff)
    add("generation_wrap", sources=(15, 14, 13, 12), channels=(15, 14, 13, 12),
        generations=(0, 0xffffffff, 0, 99), capture=1, sample_id=0)
    rng = random.Random(0x17C012)
    for cycle in range(4096):
        source, channel = rng.randrange(16), rng.randrange(16)
        kind, control = rng.choice([(3, 0), (4, 1), (4, 4), (4, 6), (0, 0), (5, 0)])
        value = rng.randrange(4096)
        add("random_atomic_snapshot", reset=cycle not in [511, 1535, 3071], valid=rng.randrange(2),
            data=event(kind, source, channel, control, value), occupied=rng.randrange(16),
            sources=tuple(rng.randrange(16) for _ in range(4)),
            channels=tuple(rng.randrange(16) for _ in range(4)),
            generations=tuple(rng.getrandbits(32) for _ in range(4)),
            capture=rng.randrange(2), sample_id=rng.getrandbits(32))
    add("final_reset", reset=0)
    return rows, counts


def run(command, stage, log, timeout=120):
    result = subprocess.run(command, cwd=stage, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    text = result.stdout + result.stderr
    (stage / log).write_text(text, encoding="utf-8", newline="\n")
    return result.returncode, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--negative-tests", action="store_true")
    parser.add_argument("--synth", action="store_true", help="Yosys structural synth only, not Gowin/PnR")
    args = parser.parse_args()
    stage = ROOT / "code/output/performance_control_state_20261001"
    stage.mkdir(parents=True, exist_ok=True)
    rows, coverage = vectors()
    path = stage / "vectors.txt"
    path.write_text("\n".join(rows) + "\n", encoding="ascii", newline="\n")
    package = ROOT / "code/rtl/common/audio_defs_pkg.sv"
    source = ROOT / "code/rtl/board/performance_control_state.sv"
    tb = ROOT / "code/tb/board/tb_performance_control_state.sv"
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + os.environ["PATH"]
    code, text = run([str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_performance_control_state",
                      "-o", str(stage / "tb.vvp"), str(package), str(source), str(tb)], stage, "compile.log")
    if code:
        print(text[-3000:])
        return code
    command = [str(CAD / "bin/vvp.exe"), str(stage / "tb.vvp")]
    code, text = run(command + ["+VECTORS=" + str(path)], stage, "RTL.log")
    print(text.strip())
    passed = code == 0 and "PASS performance_control_state" in text
    info = {"baseline": "30339fa", "scope": "standalone M2 control bank only; not formal top/GPRJ/FCW/LFO/MIDI",
            "vectors": len(rows), "coverage": coverage, "RTL_pass": passed,
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [package, source, tb]},
            "vector_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "formal_integration": False,
            "new_clock_or_public_interface": False, "new_bitstream": False}
    if not passed:
        return code or 1
    if args.negative_tests:
        # Mutate expected pitch only in a separate vector file. Missing writes
        # and incorrect sign bits must be observable; no accepted source rewrite.
        bad = list(rows)
        index = 10
        columns = bad[index].split()
        columns[9] = format(int(columns[9], 16) ^ 0x800, "x")
        bad[index] = " ".join(columns)
        negative = stage / "negative_vectors.txt"
        negative.write_text("\n".join(bad) + "\n", encoding="ascii", newline="\n")
        bad_code, bad_text = run(command + ["+VECTORS=" + str(negative)], stage, "negative.log")
        info["wrong_pitch_expected_rejected"] = bad_code != 0 and "live signed pitch values" in bad_text
        if not info["wrong_pitch_expected_rejected"]:
            raise RuntimeError("corrupted expected signed pitch was accepted")
        print("PASS wrong signed-pitch expectation rejected")
    if args.synth:
        script = stage / "synth.ys"
        script.write_text("read_slang --top performance_control_state " + package.as_posix() + " " + source.as_posix() +
                          "\nproc\nopt\nmemory_map\nopt\ncheck -assert\nwrite_json " +
                          (stage / "structural.json").as_posix() + "\nstat\n", encoding="ascii")
        syn_code, syn_text = run([str(CAD / "bin/yosys.exe"), "-Q", "-T", "-s", str(script)], stage, "synth.log", 180)
        if syn_code:
            print(syn_text[-3000:])
            return syn_code
        modules = json.loads((stage / "structural.json").read_text())["modules"]
        cells = modules["performance_control_state"]["cells"]
        types = {}
        sequential_bits = 0
        for cell in cells.values():
            types[cell["type"]] = types.get(cell["type"], 0) + 1
            if cell["type"] in ["$adff", "$adffe", "$dff", "$dffe", "$sdff", "$sdffe"]:
                sequential_bits += len(cell["connections"]["Q"])
        if any("latch" in name.lower() for name in types):
            raise RuntimeError("structural latch inferred")
        info["Yosys_structural_synth"] = {"passed": True, "cell_types": types,
                                            "sequential_bits": sequential_bits,
                                            "scope": "generic structural cells, not Gowin Logic/BSRAM/DSP or physical Fmax"}
        print("PASS structural no-latch synthesis; sequential bits", sequential_bits)
    info["logs_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.glob("*.log")}
    (stage / "evidence.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Evidence:", stage / "evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
