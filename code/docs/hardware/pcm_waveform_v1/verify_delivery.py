"""Read-only source/evidence verification; optional bounded repository gate."""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--gate-output", type=Path)
    cli.add_argument("--archive-gate", type=Path)
    cli.add_argument("--file-list", action="store_true")
    args = cli.parse_args()
    raw_manifest = json.loads((HERE / "evidence/raw_manifest.json").read_text(encoding="utf-8"))
    raw = {}
    for relative, item in raw_manifest.items():
        data = base64.b64decode((HERE / "evidence" / relative).read_bytes())
        if sha(data) != item["raw_sha256"] or len(data) != item["raw_bytes"]:
            raise ValueError("EVIDENCE_IDENTITY " + relative)
        raw[relative.removesuffix(".b64")] = data
    receipt = json.loads(raw["acceptance/receipt.json"])
    if not receipt["passed"] or not json.loads(raw["synthesis/receipt.json"])["passed"]:
        raise ValueError("RECEIPT_FAIL")
    for relative, expected in receipt["source_sha256"].items():
        if sha((ROOT / relative).read_bytes()) != expected:
            raise ValueError("EXECUTED_SOURCE_CHANGED " + relative)
    paths = [ROOT / "code/rtl/input/pcm_waveform_candidate", ROOT / "code/tb/input/pcm_waveform_candidate", HERE]
    for folder in paths:
        for file in folder.rglob("*.py"):
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    print("PASS", len(raw_manifest), "sealed raw identities and executed source SHA", flush=True)
    if args.archive_gate:
        gate_dir = args.archive_gate
        gate = json.loads((gate_dir / "receipt.json").read_text(encoding="utf-8"))
        if not gate["passed"] or gate["exit"] != 0:
            raise ValueError("GATE_NOT_PASS")
        for name in ("stdout", "stderr"):
            if sha((gate_dir / (name + ".log")).read_bytes()) != gate[name + "_sha256"]:
                raise ValueError("GATE_LOG_IDENTITY")
        for name in ("stdout.log", "stderr.log", "receipt.json"):
            data = (gate_dir / name).read_bytes()
            relative = "gate/" + name + ".b64"
            dest = HERE / "evidence" / relative
            if dest.exists():
                raise ValueError("REFUSE_GATE_OVERWRITE")
            dest.parent.mkdir(exist_ok=True)
            dest.write_bytes(base64.encodebytes(data))
            raw_manifest[relative] = {"raw_bytes": len(data), "raw_sha256": sha(data)}
        (HERE / "evidence/raw_manifest.json").write_text(json.dumps(raw_manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.file_list:
        listing = HERE / "FILE_LIST.json"
        if listing.exists():
            raise ValueError("REFUSE_FILE_LIST_OVERWRITE")
        files = [p for folder in paths for p in folder.rglob("*") if p.is_file()]
        files.append(ROOT / "code/scripts/run_m3_pcm_waveform_acceptance.py")
        listing.write_text(json.dumps({p.relative_to(ROOT).as_posix(): {"bytes": p.stat().st_size,
            "sha256": sha(p.read_bytes())} for p in sorted(files)}, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.gate_output:
        out = args.gate_output.resolve()
        if out.exists() or not out.is_relative_to((ROOT / "code/output").resolve()) or not out.name.startswith("m3_pcm_waveform_"):
            cli.error("require new code/output/m3_pcm_waveform_* directory")
        out.mkdir(parents=True)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + "D:/Gowin/oss-cad-suite/bin;D:/Gowin/oss-cad-suite/lib;" + env.get("PATH", "")
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "code/scripts/check_repo.ps1")]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=600, check=False)
        for name, data in [("stdout", result.stdout), ("stderr", result.stderr)]:
            (out / (name + ".log")).write_bytes(data)
        ok = result.returncode == 0 and b"All repository checks passed." in result.stdout
        gate = {"passed": ok, "exit": result.returncode, "command": command,
                "gate_script_sha256": sha((ROOT / "code/scripts/check_repo.ps1").read_bytes()),
                "stdout_sha256": sha(result.stdout), "stderr_sha256": sha(result.stderr)}
        (out / "receipt.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
        print(result.stdout.decode("utf-8", errors="replace"), flush=True)
        if not ok:
            print(result.stderr.decode("utf-8", errors="replace"), flush=True)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
