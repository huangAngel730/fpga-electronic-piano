"""Capture raw child gate logs and narrow SDK availability, read-only sources."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

import checker

ROOT = checker.ROOT


def main():
    gate = ROOT / "code/output/m3_night_gate_20261008"
    manifest_only = sys.argv[1:] == ["--manifest-only"]
    sources = [ROOT / "code/output" / top / "run.log" for top in
               ("tb_electronic_piano_top", "tb_key_to_tone", "tb_midi_top_integration")]
    detail = dict(logs={}, historical_rom_messages=[], boundary="Official nine-gate summary PASS does not assert all old timbre ROM reads succeeded")
    for path in ([] if manifest_only else sources):
        raw = path.read_bytes()
        target = gate / (path.parent.name + "_gate_child.log")
        if target.exists():
            raise ValueError("DO_NOT_OVERWRITE_GATE_CAPTURE")
        target.write_bytes(raw)
        detail["logs"][path.parent.name] = dict(source=str(path), sha256=checker.sha(raw),
                                              modified_ns=path.stat().st_mtime_ns)
        detail["historical_rom_messages"].extend(line for line in raw.decode("utf-8", errors="replace").splitlines()
                                                 if "ERROR:" in line and "$readmemh" in line)
    for task, source in (("wave", ROOT / "code/tb/input/pcm_waveform_candidate/night_blackbox_20261007"),
                         ("ble", ROOT / "code/software/score_ble_test_candidate/night_stress_20261007")):
        destination = ROOT / ("code/docs/hardware/pcm_waveform_v1/night_20261007" if task == "wave" else
                              "code/docs/hardware/score_ble_v1/night_20261007")
        if not manifest_only:
            for path in gate.glob("*.log"):
                shutil.copyfile(path, destination / "evidence" / path.name)
            shutil.copyfile(gate / "gate_receipt.json", destination / "evidence/gate_receipt.json")
            (destination / "evidence/gate_child_context.json").write_text(json.dumps(detail, indent=2) + "\n", encoding="utf-8")
        table = {str(path.relative_to(ROOT)): checker.sha(path.read_bytes()) for folder in (source, destination)
                 for path in folder.rglob("*") if path.is_file() and "__pycache__" not in path.parts
                 and path.name != "delivery_manifest.json"}
        (destination / "delivery_manifest.json").write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    if manifest_only:
        print("PASS refreshed NEW manifests only; raw receipts/logs unchanged")
        return
    known = [Path("C:/Users/songdongkuan/.espressif"), Path("C:/Users/songdongkuan/.gradle"),
             Path("C:/Users/songdongkuan/AppData/Local/Android/Sdk")]
    probe = dict(configured={name: os.environ.get(name) for name in ("IDF_PATH", "ANDROID_HOME", "ANDROID_SDK_ROOT", "GRADLE_HOME", "JAVA_HOME")},
                 known_roots={str(path): path.exists() for path in known},
                 boundary="Narrow installed/configured environment check, not exhaustive disk search; no download or install")
    (gate / "target_sdk_probe.json").write_text(json.dumps(probe, indent=2) + "\n", encoding="utf-8")
    print("PASS new delivery manifests, raw gate child logs, SDK availability captured")


if __name__ == "__main__":
    main()
