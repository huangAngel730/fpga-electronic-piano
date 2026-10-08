"""Capture bounded repository gate and seal versioned small raw evidence."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TEST = ROOT / "code/software/score_ble_test_candidate/target_adapter_repair_20261008"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_output(path):
    path = path.resolve()
    if not path.is_relative_to((ROOT / "code/output").resolve()) or not path.name.startswith("m3_t059_target_adapter_repair_"):
        raise ValueError("require target-adapter unique output")
    return path


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=30, check=True).stdout


def gate(path):
    out = safe_output(path)
    out.mkdir(exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "code/scripts/check_repo.ps1")]
    started = time.monotonic()
    timed = False
    tracked = git("ls-files", "-z").decode("utf-8").split("\0")
    identities = {name: sha((ROOT / name).read_bytes()) for name in tracked if name and (ROOT / name).is_file()}
    with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        try:
            process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            timed = True
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15, check=False)
            process.wait(timeout=15)
    same = all(sha((ROOT / name).read_bytes()) == expected for name, expected in identities.items())
    output = (out / "stdout.log").read_bytes()
    passed = process.returncode == 0 and not timed and same and output.count(b"[PASS]") == 9 and b"All repository checks passed." in output
    info = {"passed": passed, "command": command, "exit": process.returncode, "timed_out": timed,
            "seconds": round(time.monotonic() - started, 6), "tracked_inputs_unchanged": same,
            "tracked_input_count": len(identities), "stdout_sha256": sha(output),
            "stderr_sha256": sha((out / "stderr.log").read_bytes())}
    (out / "receipt.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (out / "input_sha256.json").write_text(json.dumps(identities, indent=2) + "\n", encoding="utf-8")
    print(output.decode("utf-8", errors="replace"), flush=True)
    print(json.dumps(info), flush=True)
    return 0 if passed else 1


def seal(run, gate_path, attempts):
    run, gate_path = safe_output(run), safe_output(gate_path)
    receipt = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
    gate_receipt = json.loads((gate_path / "receipt.json").read_text(encoding="utf-8"))
    if not receipt["passed"] or not gate_receipt["passed"]:
        raise ValueError("cannot seal passing delivery without regression and gate")
    evidence = HERE / "evidence"
    evidence.mkdir(exist_ok=False)
    manifest = {}
    selections = []
    for prefix, directory in [("run", run), ("gate", gate_path)] + [("attempt" + str(i + 1), safe_output(p)) for i, p in enumerate(attempts)]:
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix in (".log", ".json", ".c", ".kt", ".java"):
                # No executable/JVM class artifacts committed; their SHA remains in receipt.
                selections.append((prefix + "/" + path.relative_to(directory).as_posix(), path.read_bytes()))
    old_list = git("show", "5be92d9:code/docs/hardware/score_ble_v1/FILE_LIST.json")
    selections.append(("legacy/FILE_LIST.json", old_list))
    for name, data in selections:
        carrier = name.replace("/", "__") + ".gz.b64"
        encoded = base64.encodebytes(gzip.compress(data, mtime=0))
        (evidence / carrier).write_bytes(encoded)
        manifest[carrier] = {"original": name, "raw_sha256": sha(data), "raw_bytes": len(data), "carrier_sha256": sha(encoded)}
    (evidence / "raw_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    baseline = {"authorization": "D040; approved base 5be92d9; two file exception only",
                "adapter_versions": receipt["adapter_versions"], "eight_unchanged_sources": receipt["eight_unchanged_sources"],
                "regression_receipt_raw_sha256": sha((run / "receipt.json").read_bytes()),
                "old_10_source_list_preserved": True, "old_evidence_preserved": True,
                "actual_level": "C host compilation; source-derived JVM/mock logic, not target firmware/APK"}
    (HERE / "baseline.json").write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8", newline="\n")
    refresh_list()
    print("SEALED", len(manifest), "raw records; no binary payloads")


def refresh_list():
    path = HERE.parent / "FILE_LIST.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    additions = [p for folder in (HERE, TEST) for p in folder.rglob("*") if p.is_file()]
    additions += [ROOT / name for name in (
        "code/software/score_ble_bridge_candidate/main/main.c",
        "code/software/score_ble_android_candidate/app/src/main/java/org/m3/score/MainActivity.kt",
        "code/docs/hardware/score_ble_v1/DELIVERY.md", "code/docs/hardware/score_ble_v1/seal.py")]
    for p in additions:
        items[p.relative_to(ROOT).as_posix()] = {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
    path.write_text(json.dumps(dict(sorted(items.items())), indent=2) + "\n", encoding="utf-8", newline="\n")


def verify():
    manifest = json.loads((HERE / "evidence/raw_manifest.json").read_text(encoding="utf-8"))
    records = {}
    for name, item in manifest.items():
        data = (HERE / "evidence" / name).read_bytes()
        if sha(data) != item["carrier_sha256"]:
            raise ValueError("carrier SHA " + name)
        raw = gzip.decompress(base64.b64decode(data, validate=False))
        if sha(raw) != item["raw_sha256"] or len(raw) != item["raw_bytes"]:
            raise ValueError("raw SHA " + name)
        records[item["original"]] = raw
    baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    receipt = json.loads(records["run/receipt.json"])
    if not receipt["passed"] or sha(records["run/receipt.json"]) != baseline["regression_receipt_raw_sha256"]:
        raise ValueError("regression identity")
    for name, item in baseline["adapter_versions"].items():
        old = records["run/sources/old_" + Path(name).name]
        if sha(old) != item["old_sha256"] or sha((ROOT / name).read_bytes()) != item["new_sha256"]:
            raise ValueError("adapter version " + name)
    for name, expected in baseline["eight_unchanged_sources"].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError("immutable eight " + name)
    for name, expected in receipt["test_source_sha256"].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise ValueError("executed test source " + name)
    for label in ("run", "gate"):
        info = json.loads(records[label + "/receipt.json"])
        if label == "gate" and (not info["passed"] or info["exit"]):
            raise ValueError("gate identity")
        if label == "run":
            for step in info["steps"]:
                for stream in ("stdout", "stderr"):
                    if sha(records["run/" + step["label"] + "/" + stream + ".log"]) != step[stream + "_sha256"]:
                        raise ValueError("step log SHA")
    print("PASS", len(records), "raw evidence records; old/new adapters and eight unchanged")


def bundle(path, final_gate=None):
    out = safe_output(path)
    out.mkdir(exist_ok=False)
    archive = out / "M3_T059_D040三项定点返修_20261008.zip"
    members = [p for folder in (HERE, TEST) for p in folder.rglob("*") if p.is_file()]
    members += [ROOT / name for name in (
        "code/software/score_ble_bridge_candidate/main/main.c",
        "code/software/score_ble_bridge_candidate/core/bridge.c",
        "code/software/score_ble_bridge_candidate/core/bridge.h",
        "code/software/score_ble_android_candidate/app/src/main/java/org/m3/score/MainActivity.kt",
        "code/software/score_ble_android_candidate/app/src/main/java/org/m3/score/Protocol.java",
        "code/docs/hardware/score_ble_v1/DELIVERY.md",
        "code/docs/hardware/score_ble_v1/FILE_LIST.json",
        "code/docs/hardware/score_ble_v1/seal.py",
        "code/docs/M3_T059目标接入三问题_最小返修授权_2026-10-08.md")]
    inventory = {}
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(members):
            name = p.relative_to(ROOT).as_posix()
            data = p.read_bytes()
            z.writestr(name, data)
            inventory[name] = {"bytes": len(data), "sha256": sha(data)}
        if final_gate:
            for name in ("stdout.log", "stderr.log", "receipt.json", "input_sha256.json"):
                data=(safe_output(final_gate)/name).read_bytes()
                member="final_gate/"+name
                z.writestr(member,data)
                inventory[member]={"bytes":len(data),"sha256":sha(data)}
        state=json.dumps({"commit":git("rev-parse","HEAD").decode("ascii").strip(),
                          "working_tree_clean":not git("status","--porcelain").strip(),
                          "pushed_by_this_task":False,"m2_notice":"pending user forwarding"},indent=2).encode("utf-8")
        z.writestr("DELIVERY_STATE.json",state)
        inventory["DELIVERY_STATE.json"]={"bytes":len(state),"sha256":sha(state)}
        z.writestr("CONTENTS_SHA256.json", json.dumps(inventory, indent=2) + "\n")
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("bundle CRC")
        for name, item in inventory.items():
            if sha(z.read(name)) != item["sha256"]:
                raise ValueError("bundle SHA")
    print(str(archive)); print("bytes", archive.stat().st_size); print("SHA256", sha(archive.read_bytes()))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run-gate", type=Path)
    cli.add_argument("--seal", type=Path)
    cli.add_argument("--gate", type=Path)
    cli.add_argument("--attempt", type=Path, action="append", default=[])
    cli.add_argument("--refresh-list", action="store_true")
    cli.add_argument("--verify", action="store_true")
    cli.add_argument("--bundle", type=Path)
    args = cli.parse_args()
    if args.run_gate:
        return gate(args.run_gate)
    if args.seal:
        if not args.gate:
            cli.error("--gate required")
        seal(args.seal, args.gate, args.attempt)
    if args.refresh_list:
        refresh_list()
    if args.verify:
        verify()
    if args.bundle:
        bundle(args.bundle,args.gate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
