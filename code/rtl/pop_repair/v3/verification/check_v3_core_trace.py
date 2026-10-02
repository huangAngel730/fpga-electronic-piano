"""Independent bass/phase replay plus unchanged formal ADSR model reference."""
import argparse
import json
from pathlib import Path
import re
import sys


def read_signed(path):
    return [v if v < 32768 else v-65536 for v in
            (int(word, 16) for word in path.read_text().split())]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("trace", type=Path)
    p.add_argument("--snapshot", type=Path, required=True)
    args = p.parse_args()
    snapshot = args.snapshot.resolve()
    root = Path(__file__).resolve().parents[1]
    if not snapshot.is_relative_to(root / "build"):
        p.error("owned snapshot only")
    sys.path.insert(0, str(snapshot / "code/model"))
    sys.path.insert(0, str(snapshot / "code/tb/board"))
    from adsr_piano import PianoADSREnvelope
    from check_polyphonic_audio_trace import PianoV1Lane
    text = (snapshot / "source/rtl/v3_constants.svh").read_text()
    def coefficients(name, width):
        field = re.search(name+r"\s*=\s*\{([^}]+)\}", text)
        return list(reversed([int(v) for v in re.findall(str(width)+r"'d(\d+)", field[1])]))
    initial = coefficients("BASS_INITIAL", 16)
    floor = coefficients("BASS_FLOOR", 16)
    shifts = coefficients("PARTIAL_SHIFT", 5)
    sine = read_signed(snapshot / "source/rom/sine_v3_1024_32767.mem")
    piano = read_signed(snapshot / "source/baseline/piano_band_4x256_8191.mem")
    def reset():
        return ([PianoADSREnvelope() for _ in range(4)], [PianoV1Lane() for _ in range(4)],
                [0]*4, [0]*4, [[a<<16 for a in floor] for _ in range(4)],
                [[a<<16 for a in floor] for _ in range(4)])
    env, legacy, phase, note_steps, amplitude, target = reset()
    samples = 0
    max_env = max_pcm = 0
    bass_samples = high_samples = resets = 0
    for line_number, line in enumerate(args.trace.read_text().splitlines(), 1):
        words = line.split()
        if words == ["R"]:
            env, legacy, phase, note_steps, amplitude, target = reset()
            resets += 1
        elif words[0] == "N" and len(words) == 4:
            lane, velocity, fcw = map(int, words[1:])
            env[lane].note_on(velocity)
            legacy[lane].note_on(velocity, fcw)
            note_steps[lane] = fcw
            target[lane] = [(b + ((a-b)//2 if velocity < 256 else
                           3*(a-b)//4 if velocity < 768 else a-b)) << 16
                            for a, b in zip(initial, floor)]
        elif words[0] == "F" and len(words) == 2:
            env[int(words[1])].note_off()
        elif words[0] == "D" and len(words) == 15:
            values = list(map(int, words[1:]))
            mixed = 0
            for lane in range(4):
                fcw = values[8+lane]
                if values[13] & (1 << lane) and fcw != note_steps[lane]:
                    raise ValueError(f"row{line_number}: occupied lane FCW changed without NoteOn")
                envelope = env[lane].step()
                max_env = max(max_env, abs(envelope-values[lane]))
                if abs(envelope-values[lane]) > 2:
                    raise ValueError(f"row{line_number}: lane{lane} envelope model{envelope} RTL{values[lane]}")
                phase[lane] = (phase[lane]+fcw) % (1 << 32)
                for k in range(12):
                    delta = target[lane][k]-amplitude[lane][k]
                    amplitude[lane][k] += ((delta+63)//64 if delta >= 0 else -((-delta+63)//64))
                    tail = target[lane][k]-(floor[k] << 16)
                    if shifts[k]:
                        target[lane][k] -= (tail+(1 << shifts[k])-1)//(1 << shifts[k])
                legacy[lane].fcw = fcw
                legacy_wave = legacy[lane].step(piano)
                if fcw <= 19685267:
                    total = sum(sine[((phase[lane]*(k+1)) % (1 << 32)) >> 22] *
                                (amplitude[lane][k] >> 16) for k in range(12)
                                if fcw*(k+1) <= 1789569706)
                    wave = max(-8192, min(8191, (total+16384)//32768))
                    bass_samples += 1
                else:
                    wave = legacy_wave
                    high_samples += 1
                if wave != values[4+lane]:
                    raise ValueError(f"row{line_number}: lane{lane} wave model{wave} RTL{values[4+lane]}")
                mixed += ((wave*envelope)//32768)*256
            mixed = min(8388607, max(-8388608, mixed))
            max_pcm = max(max_pcm, abs(mixed-values[12]))
            if abs(mixed-values[12]) > 1024:
                raise ValueError(f"row{line_number}: PCM delta{abs(mixed-values[12])}")
            samples += 1
        else:
            raise ValueError(f"bad row{line_number}: {line[:60]}")
    if samples < 45000 or resets < 10 or not high_samples or not bass_samples:
        raise ValueError("incomplete lifecycle trace")
    report = {"status":"PASS", "frames":samples, "resets":resets,
              "bass_lane_samples":bass_samples, "high_lane_samples":high_samples,
              "envelope_max_delta":max_env, "PCM24_max_delta":max_pcm,
              "wave_max_delta":0, "PCM24_limit":1024}
    (args.trace.parent / "v3_golden.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print("PASS independent V3 core golden", json.dumps(report))


if __name__ == "__main__":
    main()
