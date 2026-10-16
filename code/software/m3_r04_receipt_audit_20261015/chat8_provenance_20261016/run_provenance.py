"""Run the focused tests and one real read-only provenance audit with receipts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def run(command: list[str], root: Path, prefix: Path) -> dict[str, object]:
    stdout_path = prefix.with_suffix(".stdout.txt")
    stderr_path = prefix.with_suffix(".stderr.txt")
    started = time.monotonic()
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        completed = subprocess.run(
            command,
            cwd=root,
            stdout=stdout,
            stderr=stderr,
            timeout=60,
            check=False,
        )
    return {
        "argv": command,
        "cwd": str(root),
        "exit_code": completed.returncode,
        "elapsed_s": time.monotonic() - started,
        "stdout": identity(stdout_path),
        "stderr": identity(stderr_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    a_root = root / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02"
    c_root = root / "code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02"
    protected = [
        a_root / "RUN_01/RUN_RECEIPT.json",
        a_root / "RUN_01_CONSUMED.json",
        a_root / "RUN_01/stage/inputs/REAL_CAPTURE.jsonl",
        a_root / "RUN_01/stage/inputs/REAL_INPUTS.jsonl",
        a_root / "SEAL_SUCCESS/M3_NIGHT_A_RESUME_R02_REAL_CAPTURE.zip",
        c_root / "CONSUME_R01/RUN_RECEIPT.json",
        c_root / "CONSUME_R01/REAL_RESULT.json",
        c_root / "NIGHT_RUN_RECEIPT.json",
        c_root / "SEAL_R01/C_R02_REAL_R05_DIGITAL_EVIDENCE.zip",
    ]
    sources = sorted(here.glob("*.py"))
    before = {str(path.relative_to(root)): identity(path) for path in protected}
    source_before = {str(path.relative_to(root)): identity(path) for path in sources}
    receipt: dict[str, object] = {
        "schema": "M3_CHAT8_PROVENANCE_RUN_V1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "python": identity(Path(sys.executable)),
        "protected_before": before,
        "source_before": source_before,
        "steps": [],
        "new_rtl_or_eda_invocations": 0,
    }
    code = 1
    try:
        tests = run(
            [sys.executable, "-B", "-X", "utf8", str(here / "test_provenance.py")],
            root,
            output / "tests",
        )
        receipt["steps"].append(tests)
        if tests["exit_code"] != 0:
            raise RuntimeError("TESTS_FAILED")
        audit_command = [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(here / "provenance_audit.py"),
            "--a-root",
            str(a_root),
            "--c-root",
            str(c_root),
            "--output",
            str(output / "PROVENANCE_RESULT.json"),
        ]
        actual = run(audit_command, root, output / "audit")
        receipt["steps"].append(actual)
        if actual["exit_code"] != 0:
            raise RuntimeError("AUDIT_FAILED")
        receipt["result"] = identity(output / "PROVENANCE_RESULT.json")
        receipt["status"] = "PASS"
        code = 0
    except Exception as error:
        receipt["status"] = "FAIL"
        receipt["error"] = repr(error)
    receipt["source_after"] = {
        str(path.relative_to(root)): identity(path) for path in sources
    }
    receipt["protected_after"] = {
        str(path.relative_to(root)): identity(path) for path in protected
    }
    receipt["source_unchanged"] = receipt["source_before"] == receipt["source_after"]
    receipt["protected_unchanged"] = receipt["protected_before"] == receipt["protected_after"]
    if not receipt["source_unchanged"] or not receipt["protected_unchanged"]:
        receipt["status"] = "FAIL_IDENTITY_CHANGED"
        code = 1
    receipt["ended_utc"] = datetime.now(timezone.utc).isoformat()
    with (output / "RUN_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "output": str(output)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
