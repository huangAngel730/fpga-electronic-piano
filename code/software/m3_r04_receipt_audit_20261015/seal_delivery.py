"""Seal this task only; optional mandatory repository gate, no R04 execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[2]
DOCS = REPO / "code/docs/test/m3_r04_receipt_audit_20261015"


def identity(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository-gate", action="store_true")
    args = parser.parse_args()
    run = args.run.resolve()
    output = args.output.resolve()
    if not run.is_relative_to(DOCS.resolve()) or not output.is_relative_to(DOCS.resolve()):
        raise ValueError("run and output must stay in the authorized new evidence directory")
    output.mkdir(parents=True, exist_ok=False)
    selftest = json.loads((run / "SOFTWARE_SELFTEST_RECEIPT.json").read_text(encoding="utf-8"))
    if selftest["status"] != "PASS":
        raise ValueError("cannot publish failed software selftest as a completed task")
    for name, recorded in selftest["source_before"].items():
        if identity((SOURCE / name).read_bytes()) != recorded:
            raise ValueError(f"tested source changed: {name}")
    if args.repository_gate:
        env = dict(os.environ)
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-File", str(REPO / "code/scripts/check_repo.ps1")]
        started = time.monotonic()
        timeout = False
        try:
            proc = subprocess.run(command, cwd=REPO, env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=900, check=False)
            code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            timeout, code = True, 124
            stdout, stderr = exc.stdout or b"", exc.stderr or b""
        (output / "repository_gate.stdout.txt").write_bytes(stdout)
        (output / "repository_gate.stderr.txt").write_bytes(stderr)
        gate = {"command": command, "cwd": str(REPO), "exit_code": code,
                "elapsed_seconds": time.monotonic() - started, "timed_out": timeout,
                "budget_seconds": 900,
                "passed": code == 0 and not timeout and b"All repository checks passed." in stdout}
        (output / "REPOSITORY_GATE.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
        if not gate["passed"]:
            print("FAIL REPOSITORY_GATE; original streams preserved", file=sys.stderr)
            return 1
    members = {}
    paths = list(SOURCE.glob("*.py")) + list(SOURCE.glob("*.md"))
    paths += list(DOCS.glob("*.md"))
    paths += [p for p in run.iterdir() if p.is_file()]
    paths += [p for p in output.iterdir() if p.is_file()]
    for path in sorted(paths):
        members[path.relative_to(REPO).as_posix()] = identity(path.read_bytes())
    manifest = {"scope": "M3_R04_RECEIPT_SOFTWARE_SUCCESSOR_ONLY", "members": members,
                "real_r04_status": "PENDING", "t052_old_4207": "UNKNOWN"}
    raw_manifest = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    (output / "MANIFEST.json").write_bytes(raw_manifest)
    target = output / "M3_R04_RECEIPT_REPAIR_DELIVERY.zip"
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("MANIFEST.json", raw_manifest)
        for name, recorded in members.items():
            data = (REPO / name).read_bytes()
            if identity(data) != recorded:
                raise ValueError(f"source changed during seal: {name}")
            archive.writestr(name, data)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for name, recorded in members.items():
            if identity(archive.read(name)) != recorded:
                raise ValueError(f"ZIP member SHA mismatch: {name}")
    receipt = {"package": str(target), **identity(target.read_bytes()),
               "manifest": identity(raw_manifest), "payload_members": len(members),
               "software_scope_only": True, "real_r04_status": "PENDING"}
    (output / "SEAL_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
