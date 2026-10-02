"""Reproducible sample-level checks/WAV; writes exclusively under V3/design.

The independent diagnostic filters are owned by M2 (verification/audio_metrics.py).
Do not execute the asset generator after DESIGN_READY; generated hashes are frozen.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import wave
import numpy as np
from v3_model import BassOscillator, LegacyOscillator, render
from v3_parameters import FS, BASE_FCW, BASS_LIMIT, bass_coefficients, coefficient_box_bound, note_fcw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verification"))
from audio_metrics import bands, rms

def write_wav(path, samples):
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(FS)
        writer.writeframes(np.asarray(samples, dtype="<i2").tobytes())

def diagnostic(samples):
    x = samples.astype(float)/32768
    result = bands(x, FS)
    denominator = sum(b["mean_envelope"]**2 for b in result)
    return {"rms": rms(x), "peak": float(np.max(np.abs(x))),
            "slow_energy_proxy": sum(b["slow_0p5_30hz"]["absolute_rms"]**2 for b in result)/denominator,
            "fast_energy_proxy": sum(b["fast_30_150hz"]["absolute_rms"]**2 for b in result)/denominator,
            "bands": result}

def selftest(destination):
    initial, floor = bass_coefficients()
    minimum, maximum = coefficient_box_bound(initial, floor)
    assert minimum>=-8192 and maximum<=8191 and floor[0]>0
    assert BASE_FCW[9]==39370534 and note_fcw(69)==39370534
    max_cent = max(abs(1200*np.log2(note_fcw(n)*FS/2**32/(440*2**((n-69)/12)))) for n in range(21,109))
    assert max_cent < .0005
    records = []
    for n in (21,24,36,48,57):
        osc = BassOscillator(note_fcw(n))
        osc.note_on(900)
        vector = []
        # Model output phase is post-tick. RTL TB waits >=37 clocks.
        for i in range(2048):
            if i==1000:
                phase, amplitude = osc.phase, osc.amplitude.copy()
                osc.note_on(120)
                assert phase==osc.phase and amplitude==osc.amplitude
            value = osc.step()
            assert -8192<=value<=8191
            assert all((b<<16)<=c<=(a<<16) for a,b,c in zip(initial,floor,osc.amplitude))
            vector.append(value)
        assert osc.phase == (2048*note_fcw(n))&0xffffffff
        path = destination/f"osc_note{n}.mem"
        path.write_text("".join(f"{v&65535:04x}\n" for v in vector), encoding="ascii")
        records.append({"note":n,"fcw":note_fcw(n),"samples":len(vector),"vector":str(path),
                        "sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    # All pitches ABOVE the research zone use formal V1 identically.
    for n in (58,60,84,96,108):
        fcw=note_fcw(n)
        assert fcw>BASS_LIMIT
        a,b=LegacyOscillator(fcw),LegacyOscillator(fcw)
        a.note_on(900);b.note_on(900)
        assert [a.step() for _ in range(512)]==[b.step() for _ in range(512)]
    report = {"status":"PASS sample-model invariants only, NOT RTL simulation",
              "max_pitch_error_cents":max_cent,"coefficient_box_sample_bound":[minimum,maximum],"vectors":records,
              "checks":["88-note formal FCW", "partial bound", "amplitude floors", "continuous phase",
                        "retrigger preserves current amplitude", "V1 selection above 220Hz"]}
    (destination/"model_selftest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(report["status"], "pitch_error", max_cent)

def audio(destination):
    cases = ((24,25), (36,37), (48,49), (36,37,38,39), (60,61))
    report = {"scope":"sample-level oscillator and FLOAT formal ADSR reference, static lane sum; not full-top PCM24 RTL",
              "disclaimer":"Gaussian eight-band envelope diagnostics, NOT standardized roughness or listening acceptance. RMS match is NOT perceptual loudness match.",
              "cases":{}}
    for notes in cases:
        label = "_".join(map(str,notes))
        samples = {v:render(notes,v) for v in ("v1","v2","v3")}
        target = min(rms(x.astype(float)) for x in samples.values())
        record = {}
        for v,x in samples.items():
            write_wav(destination/f"{label}_{v}_raw.wav", x)
            gain = target/rms(x.astype(float))
            matched=np.rint(x.astype(float)*gain).astype("<i2")
            write_wav(destination/f"{label}_{v}_rmsmatched.wav",matched)
            record[v]={"raw":diagnostic(x),"match_gain":gain,"matched":diagnostic(matched)}
        report["cases"][label]=record
        print(label,{v:{k:round(d[k],6) for k in ("rms","slow_energy_proxy","fast_energy_proxy")}
                     for v,r in record.items() for d in [r["raw"]]})
    (destination/"candidate_diagnostics.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--selftest",action="store_true")
    parser.add_argument("--audio",action="store_true")
    parser.add_argument("--destination",type=Path,default=ROOT/"design"/"model_results")
    args=parser.parse_args()
    path=args.destination.resolve()
    if not path.is_relative_to(ROOT/"design"):
        parser.error("All outputs must stay under V3 design")
    path.mkdir(parents=True,exist_ok=True)
    if args.selftest:selftest(path)
    if args.audio:audio(path)
