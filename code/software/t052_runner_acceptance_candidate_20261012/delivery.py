"""Qualify and seal the T052 runner software successor."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOC = ROOT / "code/docs/test/t052_runner_acceptance_20261012"


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sources():
    return {path.name: identity(path) for path in HERE.glob("*.py")}


def fresh_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT / "code/output") or path.exists():
        raise ValueError("OUTPUT_SCOPE_OR_EXISTS")
    path.mkdir(parents=True)
    return path


def qualify(output):
    output = fresh_output(output)
    before = sources()
    started = time.monotonic()
    command = [sys.executable, "-I", "-S", "-B", "-X", "utf8",
               str(HERE / "test_runner.py"), "--evidence-dir", str(output / "cases"), "-v"]
    result = subprocess.run(command, cwd=output, capture_output=True, timeout=300)
    (output / "tests.stdout.bin").write_bytes(result.stdout)
    (output / "tests.stderr.bin").write_bytes(result.stderr)
    after = sources()
    elapsed = time.monotonic() - started
    passed = result.returncode == 0 and before == after and elapsed < 300
    receipt = {
        "status": "SOFTWARE_FAKE_TOOLS_ONLY_PASS" if passed else "FAIL_PARTIAL",
        "exit_code": 0 if passed else 1,
        "test_exit_code": result.returncode,
        "command": command,
        "elapsed_seconds": elapsed,
        "total_limit_seconds": 300,
        "per_step_limit_seconds": 90,
        "sources_before": before,
        "sources_after": after,
        "stdout": identity(output / "tests.stdout.bin"),
        "stderr": identity(output / "tests.stderr.bin"),
        "qualification_tools": ["PYTHON_FAKE_TOOL_ONLY"],
        "ModelSim_runs": 0,
        "Icarus_runs": 0,
        "Gowin_runs": 0,
        "T052_complete": False,
        "notice": "待用户转发，尚未送达",
    }
    write_json(output / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "exit_code": receipt["exit_code"]}))
    return receipt["exit_code"]


def make_zip(payload):
    members = {
        name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        for name, raw in payload.items()
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(name, raw)
        archive.writestr("MEMBERS.json", json.dumps(members, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP_CRC")
        for name, expected in members.items():
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
                raise ValueError("ZIP_MEMBER_SHA:" + name)
    return buffer.getvalue(), members


def seal(evidence, target):
    evidence = Path(evidence).resolve()
    target = Path(target).resolve()
    if target.parent != DOC or target.exists():
        raise ValueError("SEAL_SCOPE_OR_EXISTS")
    receipt = json.loads((evidence / "receipt.json").read_text(encoding="utf-8"))
    if receipt["status"] != "SOFTWARE_FAKE_TOOLS_ONLY_PASS":
        raise ValueError("QUALIFICATION_NOT_PASS")
    if receipt["sources_before"] != receipt["sources_after"] or sources() != receipt["sources_before"]:
        raise ValueError("SOURCE_DRIFT")
    payload = {
        "evidence/" + path.relative_to(evidence).as_posix(): path.read_bytes()
        for path in evidence.rglob("*") if path.is_file()
    }
    for path in HERE.glob("*.py"):
        payload["source/" + path.name] = path.read_bytes()
    for path in DOC.glob("*.md"):
        payload["docs/" + path.name] = path.read_bytes()
    raw, members = make_zip(payload)
    target.mkdir()
    (target / "evidence.zip.b64").write_bytes(base64.b64encode(raw) + b"\n")
    write_json(target / "seal.json", {
        "status": "SEALED_SOFTWARE_FAKE_TOOLS_ONLY",
        "zip_bytes": len(raw),
        "zip_sha256": hashlib.sha256(raw).hexdigest(),
        "members": len(members) + 1,
        "sources": sources(),
        "qualification_receipt": receipt,
        "notice": "待用户转发，尚未送达",
    })
    print(json.dumps({"status": "SEALED_SOFTWARE_FAKE_TOOLS_ONLY",
                      "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["qualify", "seal"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    if args.mode == "qualify":
        raise SystemExit(qualify(args.output))
    seal(args.evidence, args.target)
