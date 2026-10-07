"""New-artifact serialization: raw carriers plus LF views, matching .gitattributes."""
from __future__ import annotations

import ast
import base64
import gzip
import json
from pathlib import Path

import checker

ROOT = checker.ROOT


def main():
    for task, source in (("pcm_waveform_v1", ROOT / "code/tb/input/pcm_waveform_candidate/night_blackbox_20261007"),
                         ("score_ble_v1", ROOT / "code/software/score_ble_test_candidate/night_stress_20261007")):
        destination = ROOT / "code/docs/hardware" / task / "night_20261007"
        evidence = destination / "evidence"
        table = {}
        for path in evidence.iterdir():
            if path.suffix != ".log" and path.name not in ("original_receipt.json", "gate_receipt.json", "final_checks.json"):
                continue
            raw = path.read_bytes()
            carrier = path.with_name(path.name + ".gz.b64")
            if carrier.exists():
                raise ValueError("REFUSE_REENCODE_EXISTING_RAW " + carrier.name)
            carrier.write_bytes(base64.b64encode(gzip.compress(raw, mtime=0)) + b"\n")
            if gzip.decompress(base64.b64decode(carrier.read_bytes())) != raw:
                raise ValueError("RAW_CARRIER_VERIFY")
            table[carrier.name] = dict(raw_bytes=len(raw), raw_sha256=checker.sha(raw), carrier_sha256=checker.sha(carrier.read_bytes()))
        (evidence / "raw_log_manifest.json").write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8", newline="\n")
        # Only NEW generated readable JSON views are canonicalized. Original
        # output/receipt/log bytes remain immutable and in the raw carriers.
        for path in destination.rglob("*.json"):
            if path.name != "delivery_manifest.json":
                value = json.loads(path.read_text(encoding="utf-8"))
                path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        files = [p for folder in (source, destination) for p in folder.rglob("*") if p.is_file()
                 and "__pycache__" not in p.parts and p.name != "delivery_manifest.json" and p.suffix != ".log"]
        manifest = {p.relative_to(ROOT).as_posix(): checker.sha(p.read_bytes()) for p in files}
        (destination / "delivery_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        for path in source.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"))
    checker.check_baseline()
    print("PASS raw bytes preserved, LF-readable views, tracked-file manifests, seven new Python ASTs")


if __name__ == "__main__":
    main()
