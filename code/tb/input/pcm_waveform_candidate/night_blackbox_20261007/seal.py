"""Seal NEW night receipts and package raw evidence without touching old runs."""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import time
import zipfile

import checker
import run

ROOT = checker.ROOT
HERE = Path(__file__).resolve().parent


def probe_gate(output):
    environment = os.environ.copy()
    runtime = Path(sys.executable).parent
    environment["PATH"] = str(runtime) + ";D:/Gowin/oss-cad-suite/bin;D:/Gowin/oss-cad-suite/lib;" + environment["PATH"]
    steps = []
    code = run.execute(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "code/scripts/check_repo.ps1")],
                       "repository_gate", output, environment, time.monotonic() + 620, steps)
    report = dict(exit_code=code, steps=steps,
                  syntax_checked_new_files=[], frozen_sha_verified=checker.check_baseline())
    for folder in (HERE, ROOT / "code/software/score_ble_test_candidate/night_stress_20261007"):
        for path in folder.glob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"))
            report["syntax_checked_new_files"].append(str(path.relative_to(ROOT)))
    text = (output / "repository_gate.stdout.log").read_text(encoding="utf-8", errors="replace")
    report["nine_gate_pass"] = code == 0 and text.count("[PASS]") == 9 and "All repository checks passed." in text
    report["historical_rom_messages"] = [line for line in text.splitlines() if "readmemh" in line and "ERROR" in line]
    (output / "gate_receipt.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def seal(raw, task):
    receipt = json.loads((raw / "receipt.json").read_text(encoding="utf-8"))
    if not receipt["passed"]:
        raise ValueError("SPECIALTY_NOT_PASS " + task)
    destination = ROOT / ("code/docs/hardware/pcm_waveform_v1/night_20261007" if task == "wave" else
                          "code/docs/hardware/score_ble_v1/night_20261007")
    destination.mkdir(parents=True, exist_ok=False)
    evidence = destination / "evidence"
    evidence.mkdir()
    source_folder = HERE if task == "wave" else ROOT / "code/software/score_ble_test_candidate/night_stress_20261007"
    sources = {str(path.relative_to(ROOT)): run.digest(path) for path in source_folder.iterdir() if path.is_file()}
    shutil.copyfile(raw / "receipt.json", evidence / "original_receipt.json")
    if task == "wave":
        results, steps = [], []
        for mode, mutation in (("normal", 0), ("diagnostic", 0), ("stress", 0), ("stress", 1), ("stress", 2)):
            name = mode + "_m" + str(mutation)
            command = [sys.executable, "-B", str(HERE / "checker.py"), str(raw / (name + ".capture")),
                       "--vectors", str(raw / (mode + ".txt"))]
            code = run.execute(command, name + "_final_check", evidence, os.environ.copy(), time.monotonic() + 60, steps)
            if code != (1 if mutation else 0):
                raise ValueError("FINAL_CHECK_FAILED " + name)
            if not mutation:
                results.append(checker.check(raw / (name + ".capture"), raw / (mode + ".txt")))
        # Raw capture compressed, not substituted with EXPECTED dumps.
        for path in raw.glob("*.capture"):
            if path.name.startswith("corrupt_"):
                continue
            (evidence / (path.name + ".gz.b64")).write_bytes(base64.b64encode(gzip.compress(path.read_bytes(), mtime=0)) + b"\n")
        (evidence / "final_checks.json").write_text(json.dumps(dict(steps=steps, results=results, checker_sha256=run.digest(HERE / "checker.py")), indent=2) + "\n", encoding="utf-8")
    else:
        shutil.copyfile(raw / "normal/summary.json", evidence / "summary.json")
        # Full 9MB compressed host/check transcripts remain in the transfer ZIP;
        # do not turn temporary stress output into a large tracked artifact.
    for path in raw.glob("*.log"):
        shutil.copyfile(path, evidence / path.name)
    manifest = dict(task=task, baseline=checker.check_baseline(), new_sources_sha256=sources,
                    raw_output=str(raw), raw_artifacts_sha256=receipt["artifacts_sha256"],
                    full_evidence_transfer="Full raw host/check transcripts supplied separately in SHA-verified ZIP; old evidence unchanged")
    (evidence / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("SEALED", destination, flush=True)


def bundle(wave, ble, output):
    filename = output / "M3_T058_T059_night_acceptance_20261008.zip"
    table = {}
    entries = {}
    for task, folder in (("wave", wave), ("ble", ble)):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix not in (".vvp", ".exe", ".class") and "corrupt_" not in path.name:
                entries["raw/" + task + "/" + path.relative_to(folder).as_posix()] = path
    for folder in (HERE, ROOT / "code/software/score_ble_test_candidate/night_stress_20261007",
                   ROOT / "code/docs/hardware/pcm_waveform_v1/night_20261007",
                   ROOT / "code/docs/hardware/score_ble_v1/night_20261007"):
        for path in folder.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                entries[path.relative_to(ROOT).as_posix()] = path
    for path in output.glob("*.json"):
        entries[path.name] = path
    for path in output.glob("*.log"):
        entries[path.name] = path
    with zipfile.ZipFile(filename, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in entries.items():
            archive.write(path, name)
            table[name] = run.digest(path)
        archive.writestr("PAYLOAD_SHA256.json", json.dumps(table, indent=2) + "\n")
    with zipfile.ZipFile(filename) as archive:
        for name, digest in table.items():
            if checker.sha(archive.read(name)) != digest:
                raise ValueError("ZIP_VERIFY " + name)
    (output / "bundle_receipt.json").write_text(json.dumps(dict(file=str(filename), size=filename.stat().st_size,
                                                               sha256=run.digest(filename), verified_payload_files=len(table)), indent=2) + "\n", encoding="utf-8")
    print("BUNDLE", filename, run.digest(filename), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("gate", "seal-wave", "seal-ble", "bundle"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wave", type=Path)
    parser.add_argument("--ble", type=Path)
    args = parser.parse_args()
    if args.mode == "gate":
        args.output.mkdir(parents=True, exist_ok=False)
        return 0 if probe_gate(args.output)["nine_gate_pass"] else 1
    if args.mode.startswith("seal-"):
        seal(args.wave if args.mode == "seal-wave" else args.ble, args.mode[5:])
    else:
        bundle(args.wave, args.ble, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
