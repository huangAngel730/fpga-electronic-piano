"""Reproduce frozen sample-model A/B, save WAV and independent per-band metrics.

These are static-lane FLOAT ADSR diagnostic WAVs, not board or full-top PCM24.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import wave
import numpy as np

from audio_metrics import compare, rms

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path, required=True)
    args = p.parse_args()
    snap = args.snapshot.resolve()
    if not snap.is_relative_to(ROOT / "build"):
        p.error("owned snapshot only")
    manifest = json.loads((snap / "frozen_input_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["staged_files"]:
        if hashlib.sha256((snap / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("staged input changed: " + item["path"])
    work = ROOT / "output/audio_audit_1"
    if work.exists():
        p.error("refuse to overwrite WAV results")
    work.mkdir(parents=True)
    sys.path.insert(0, str(snap / "source/model"))
    from v3_model import render
    from v3_parameters import FS
    cases = [(24,25),(36,37),(48,49),(60,61),(84,85),(36,38),(36,40),(36,37,40,43)]
    summary = {"scope":"frozen oscillator algorithms, same formal FLOAT ADSR, velocity900, 3s with NoteOff2.5s, mix /4 diagnostic PCM16 headroom",
               "not_board_or_exact_old_v2_fs":True,
               "v2":"old spectrum/lane signs/attack duration transplanted into current ADSR",
               "limits":"RMS matching is not perceptual loudness; eight Gaussian bands not ISO roughness; no listening acceptance",
               "cases":{}}
    for notes in cases:
        label = "_".join(map(str,notes))
        versions = {v:render(notes,v,velocity=900,duration=3.,release_at=2.5) for v in ("v1","v2","v3")}
        matched_rms = min(rms(x.astype(float)) for x in versions.values())
        paths = []
        def save(path, values):
            with wave.open(str(path),"wb") as writer:
                writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(FS)
                writer.writeframes(np.asarray(values,dtype="<i2").tobytes())
        for version, samples in versions.items():
            path = work / f"midi{label}_{version}_raw.wav"
            save(path, samples);paths.append(path)
            gain = matched_rms/rms(samples.astype(float))
            save(work / f"midi{label}_{version}_rmsmatched.wav",np.rint(samples.astype(float)*gain))
        report = compare(paths)
        for path in paths:
            report["records"][str(path)]["raw_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            # Diagnostic high-band ratio, not a standardized alias test: actual
            # low-note synthesis uses <=12 partials, lookup truncation remains.
            samples = versions[path.stem.split("_")[-2]].astype(float)[FS:2*FS]
            bins = np.fft.rfft(samples*np.hanning(FS))
            frequency = np.fft.rfftfreq(FS,1/FS)
            power = abs(bins)**2
            report["records"][str(path)]["held_1_to_2s_above_3khz_power_ratio"] = float(power[frequency>3000].sum()/max(power.sum(),1e-20))
        (work / f"midi{label}_metrics.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        summary["cases"][label] = {"metrics":str(work / f"midi{label}_metrics.json"),
            "v3_to_v1_raw_rms_db":float(20*np.log10(rms(versions["v3"])/rms(versions["v1"])))}
        print("PASS reproduced WAV/metrics",label,summary["cases"][label],flush=True)
    (work / "audio_audit.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    # Reproduce generated assets exclusively on a fresh owned build copy.
    repro = snap / "asset_reproduction"
    shutil.copytree(ROOT / "source", repro / "source")
    import subprocess
    result = subprocess.run([sys.executable,"-B",str(repro / "source/model/generate_v3_assets.py")],
                            capture_output=True,text=True,timeout=120)
    (repro / "actual_generator.log").write_text(result.stdout+result.stderr,encoding="utf-8")
    if result.returncode:
        raise RuntimeError("asset reproduction failed")
    hashes = {}
    for relative in ("rom/sine_v3_1024_32767.mem","rtl/v3_constants.svh"):
        original = ROOT / "source" / relative
        generated = repro / "source" / relative
        original_sha = hashlib.sha256(original.read_bytes()).hexdigest()
        generated_sha = hashlib.sha256(generated.read_bytes()).hexdigest()
        if original_sha != generated_sha:
            raise ValueError("asset SHA reproduction mismatch " + relative)
        hashes[relative] = original_sha
    (repro / "result.json").write_text(json.dumps({"status":"PASS","hashes":hashes},indent=2)+"\n",encoding="utf-8")
    print("PASS byte-identical V3 sine ROM/constants reproduction",flush=True)


if __name__ == "__main__":
    main()
