"""Verify, scan, or explicitly SRAM-program the checked T056 138K release."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys


sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import check_138k_l_sram_release as checker  # noqa: E402


DEFAULT_PROGRAMMER = Path("D:/Gowin/Programmer_V1.9.12.02/bin/programmer_cli.exe")


def run(command: list[object], timeout: int) -> tuple[int, bytes]:
    try:
        result = subprocess.run(
            list(map(str, command)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired as error:
        return 124, (error.stdout or b"") + b"\nPROGRAMMER_TIMEOUT\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--programmer", type=Path, default=DEFAULT_PROGRAMMER)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--program", action="store_true")
    parser.add_argument("--confirm-sram-only", action="store_true")
    parser.add_argument("--session-output", type=Path)
    args = parser.parse_args()
    release = args.release.resolve()
    try:
        verification = checker.check(release)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        verification = {
            "passed": False,
            "errors": ["missing or malformed release: " + str(error)],
            "programmed": False,
            "flash_modified": False,
        }
    if not verification["passed"]:
        print(json.dumps(verification, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(verification, ensure_ascii=False, indent=2))
    if not args.scan and not args.program:
        print("PASS release verification only; no cable access and no programming")
        return 0
    if args.program and not args.confirm_sram_only:
        print("FAIL --program requires --confirm-sram-only")
        return 2
    if not args.programmer.is_file():
        print("FAIL programmer_cli.exe not found", args.programmer)
        return 1
    session = args.session_output or (
        ROOT
        / "code/output"
        / ("138k_l6_session_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    )
    session = session.resolve()
    session.relative_to((ROOT / "code/output").resolve())
    if session.exists():
        print("FAIL REFUSE_OVERWRITE", session)
        return 1
    session.mkdir(parents=True)
    scan_code, scan_data = run([args.programmer, "--scan"], 30)
    (session / "scan.log").write_bytes(scan_data)
    text = scan_data.decode("utf-8", errors="replace")
    if scan_code != 0 or checker.EXPECTED_DEVICE not in text:
        print("FAIL JTAG scan did not identify", checker.EXPECTED_DEVICE)
        return 1
    if not args.program:
        print("PASS scan identified", checker.EXPECTED_DEVICE, "; no programming")
        return 0
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    bitstream = release / manifest["bitstream"]
    command = [
        args.programmer,
        "--device",
        checker.EXPECTED_DEVICE,
        "--operation_index",
        "2",
        "--fsFile",
        bitstream,
    ]
    code, data = run(command, 180)
    (session / "program.log").write_bytes(data)
    receipt = {
        "date": "2026-10-06",
        "device": checker.EXPECTED_DEVICE,
        "operation_index": 2,
        "bitstream_sha256": checker.EXPECTED_BITSTREAM_SHA256,
        "scan_exit_code": scan_code,
        "program_exit_code": code,
        "programmed": code == 0,
        "flash_modified": False,
    }
    (session / "session_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
