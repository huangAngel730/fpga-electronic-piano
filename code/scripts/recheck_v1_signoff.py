"""Read-only numeric checks of M1 V1 signoff. No RTL/audio changes.
Not a simulator/physical test; percentages name their exact denominator.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    rom = ROOT / "code/model/generated/wavetables/piano_band_4x256_8191.mem"
    words = [int(line, 16) for line in rom.read_text().splitlines() if line.strip()]
    words = [word if word < 32768 else word - 65536 for word in words]
    if len(words) != 1024:
        raise ValueError("Incomplete V1 table")
    tables = [words[i * 256:(i + 1) * 256] for i in range(4)]
    generator = ROOT / "code/model/piano_wavetable_gen.py"
    spec = importlib.util.spec_from_file_location("v1_generator_readonly", generator)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    rebuilt = [sample for coefficients in model.TABLES for sample in model.build_table(coefficients)]
    if rebuilt != words:
        raise ValueError("V1 generator and frozen ROM differ")
    pair_jumps = []
    for before, after in [(0, 1), (1, 2), (1, 3), (0, 2), (0, 3)]:
        diffs = [abs(a - b) for a, b in zip(tables[before], tables[after])]
        pair_jumps.append({"before_table": before, "after_table": after,
            "max_same_phase_difference_LSB": max(diffs),
            "mean_same_phase_difference_LSB": sum(diffs) / 256,
            "percent_nominal_single_voice_peak8192": 100 * max(diffs) / 8192,
            "percent_PCM16_full_scale32768_before_envelope": 100 * max(diffs) / 32768})
    transitions = []
    for note in range(21, 109):
        freq = 440 * 2 ** ((note - 69) / 12)
        fcw = round(freq * (1 << 32) / 48000)
        if fcw <= 134217728:
            body, bright = 1, 0
        elif fcw <= 268435456:
            body, bright = 2, 1
        elif fcw <= 536870912:
            body, bright = 3, 2
        else:
            body, bright = 3, 3
        for velocity, duration in [(256, 480), (512, 960), (1023, 1440)]:
            phase, left, pending = 0, duration, False
            for sample in range(1, duration + math.ceil(48000 / freq) + 8):
                previous = phase
                phase = (phase + fcw) & 0xffffffff
                wraps = phase < previous
                switch = False
                if pending and wraps:
                    switch = True
                elif left:
                    left -= 1
                    if left == 0:
                        if wraps:
                            switch = True
                        else:
                            pending = True
                if switch:
                    old = tables[bright][previous >> 24]
                    continued = tables[bright][phase >> 24]
                    new = tables[body][phase >> 24]
                    transitions.append({"note": note, "velocity": velocity,
                        "nominal_attack_samples": duration, "switch_sample": sample,
                        "residual_phase_table_index": phase >> 24,
                        "natural_step_LSB": abs(continued - old),
                        "switched_step_LSB": abs(new - old),
                        "difference_vs_old_table_same_new_phase_LSB": abs(new - continued)})
                    break
            else:
                raise ValueError("Missing wrap switch")
    if len(transitions) != 264:
        raise ValueError("Incomplete key/threshold test")
    excess = [r for r in transitions if r["switched_step_LSB"] > r["natural_step_LSB"]]
    below_period = {}
    for milliseconds in [10, 20, 30]:
        notes = [note for note in range(21, 109) if 440 * 2 ** ((note - 69) / 12) * milliseconds / 1000 < 1]
        below_period[milliseconds] = {"first_note": min(notes), "last_note": max(notes),
                                      "note_count": len(notes)}
    gain_rom = ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem"
    gain = [int(line, 16) for line in gain_rom.read_text().splitlines() if line.strip()]
    report = {"date": "2026-10-02", "kind": "read-only independent numeric audit; not physical/RTL simulation",
        "ROM_generator_exact": True,
        "table_stats": [{"min": min(t), "max": max(t), "index0": t[0]} for t in tables],
        "same_phase_note_on_table_change": pair_jumps,
        "wrap_switches_checked": len(transitions),
        "wrap_switches_larger_than_old_table_natural_step": len(excess),
        "wrap_switches_not_index0": sum(r["residual_phase_table_index"] != 0 for r in transitions),
        "wrap_switches_not_same_sample_as_old_table": sum(r["difference_vs_old_table_same_new_phase_LSB"] != 0 for r in transitions),
        "transitions": transitions,
        "window_less_than_one_period": below_period,
        "A0_period_ms": 1000 / 27.5,
        "velocity200_example": {"formal_ROM_Q15": gain[200],
            "legacy_sqrt_Q15": round(math.sqrt(200 / 1023) * 32767),
            "difference_as_percent_Q15_full_scale": 100 * (round(math.sqrt(200 / 1023) * 32767) - gain[200]) / 32767},
        "brightness_threshold_gain_fractions": {v: gain[v] / 32767 for v in [256, 512, 768]},
        "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [rom, generator, gain_rom, ROOT / "code/rtl/audio/piano_dds_oscillator.sv"]},
        "limits": ["same-index table differences are not actual mixed PCM steps or measured clicks",
            "finite264 deterministic note/velocity cases not arbitrary retrigger/phase/allFCWs proof",
            "M1 proposed pending-NoteOn patch not supplied or accepted as RTL",
            "no audio/table/ADSR/new bitstream changed"]}
    stage = ROOT / "code/output/v1_M1_signoff_20261002"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "numeric_recheck.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PASS ROM regeneration matches original1024 samples")
    print("Checked264 wrap cases; step excess:", len(excess),
          "nonzero residual index:", report["wrap_switches_not_index0"])
    print("Max same-phase rich8->sine1:", pair_jumps[-1])
    print("Window<one period:", below_period)
    print("Numeric report:", stage / "numeric_recheck.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
