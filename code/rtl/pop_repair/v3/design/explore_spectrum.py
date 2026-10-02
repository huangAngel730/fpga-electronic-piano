"""Diagnostic search, not a validated auditory model. All outputs in design."""
import json
import sys
import argparse
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "verification"))
from audio_metrics import bands, rms

FS = 48000
V1 = [1, .50, .28, .16, .09]
V2 = [1, .64, .45, .31, .22, .15, .10]
sys.path.insert(0, str(ROOT / "source" / "model"))
from v3_parameters import BASS_INITIAL, BASS_FLOOR, DECAY_SHIFTS
INITIAL, FLOOR, SHIFTS = BASS_INITIAL, BASS_FLOOR, DECAY_SHIFTS

def render(notes, version):
    t = np.arange(FS * 3) / FS
    y = np.zeros_like(t)
    for n in notes:
        f = 440 * 2 ** ((n - 69) / 12)
        for k, a in enumerate(V1 if version == "v1" else V2 if version == "v2" else INITIAL, 1):
            if version == "v3":
                b = FLOOR[k-1]
                a = b + (a-b)*np.exp(-t/(2**SHIFTS[k-1]/FS)) if k>1 else a
            y += a * np.sin(2*np.pi*k*f*t)
    return y / rms(y)

def score(x):
    b = bands(x, FS)
    denominator = sum(z["mean_envelope"]**2 for z in b)
    return {
        "slow_energy_proxy": sum(z["slow_0p5_30hz"]["absolute_rms"]**2 for z in b)/denominator,
        "fast_energy_proxy": sum(z["fast_30_150hz"]["absolute_rms"]**2 for z in b)/denominator,
        "fixed_65hz_band_relative_slow": b[0]["slow_0p5_30hz"]["relative_rms"],
        "total_modulation_proxy": sum((z["slow_0p5_30hz"]["absolute_rms"]**2 + z["fast_30_150hz"]["absolute_rms"]**2) for z in b)/denominator,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("conservative12", "dense24", "warm8"), default="conservative12")
    args = parser.parse_args()
    if args.variant=="dense24":
        INITIAL = [.55, .85, 1, 1, .95, .90, .85, .80, .75, .70, .65, .60,
                   .55, .50, .45, .40, .35, .30, .25, .21, .18, .15, .12, .10]
        FLOOR = [a*.80 for a in INITIAL]
        FLOOR[0] = INITIAL[0]
        SHIFTS = [0]+[18]*3+[17]*4+[16]*4+[15]*6+[14]*6
    elif args.variant=="warm8":
        INITIAL = [1, .9, .65, .35, .2, .12, .07, .03]
        FLOOR = [1, .85, .6, .32, .18, .10, .05, .02]
        SHIFTS = DECAY_SHIFTS[:8]
    result = {str(notes): {v: score(render(notes, v)) for v in ("v1", "v2", "v3")}
              for notes in ([24,25], [36,37], [48,49], [36,37,38,39], [60,61])}
    (ROOT / "design" / ("exploration_"+args.variant+".json")).write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
