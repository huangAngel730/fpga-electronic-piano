#!/usr/bin/env python3
"""M2 pre-integration audio gate; intentionally separate from check_repo.ps1.

Checks standalone deliveries against their real dedicated regressions and
never treats the generic repository check as proof of T010 or T025 completion.
No source file is edited. Failed checks return nonzero and stay actionable.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "code/output/audio_delivery_gate"
CHECKS = (
    ("T004 DDS", "run_t004_dds_sim.ps1", r"T004 ALL PASS: 1000 model samples"),
    ("T009 ADSR", "run_t009_adsr_sim.ps1", r"T009 STAGE PASS: 73210 amplitude samples"),
    ("T010 voice", "run_t010_allocator_review.ps1", r"T010 review: 6/6 directed scenarios; oracle=PASS"),
    ("T023 mixer", "run_t023_mixer_sim.ps1", r"PASS mixer: 3008 stereo frames"),
    ("T025 clip", "run_t025_clip_counter_sim.ps1", r"PASS tb_pcm_clip_counter checks=57"),
    ("T025 PCM handoff", "run_t025_result_hold_sim.ps1", r"PASS tb_pcm_result_hold checks=35"),
)
SOURCE_PATHS = (
    "code/rtl/audio/dds_oscillator.sv",
    "code/rtl/audio/adsr_piano_envelope.sv",
    "code/rtl/audio/voice_allocator_4.sv",
    "code/rtl/mixer/pcm_mixer_4voice.sv",
    "code/rtl/common/pcm_clip_counter.sv",
    "code/rtl/audio_out/pcm_result_hold.sv",
)


def accept_result(returncode: int, output: str, required: str) -> bool:
    """Both a real zero exit and the test's asserted coverage are required."""
    return returncode == 0 and re.search(required, output) is not None


def main() -> int:
    shell = shutil.which("powershell.exe")
    if not shell:
        print("FAIL: powershell.exe unavailable", file=sys.stderr)
        return 2
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"purpose": "Standalone pre-integration only; not a full audio chain",
               "source_sha256": {}, "checks": []}
    for path in SOURCE_PATHS:
        source = ROOT / path
        if not source.is_file():
            print(f"FAIL missing source: {path}", file=sys.stderr)
            return 2
        summary["source_sha256"][path] = hashlib.sha256(source.read_bytes()).hexdigest()
    for label, name, marker in CHECKS:
        script = ROOT / "code/scripts" / name
        if not script.is_file():
            print(f"FAIL missing script: {name}", file=sys.stderr)
            return 2
        try:
            result = subprocess.run(
                [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                cwd=ROOT, capture_output=True, timeout=300, check=False)
            # The team scripts have ASCII PASS/FAIL markers even when a legacy
            # Windows PowerShell host renders Chinese stderr using ANSI/GBK.
            output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
            returncode = result.returncode
        except subprocess.TimeoutExpired as exc:
            output = f"Timed out after {exc.timeout}s"
            returncode = 124
        passed = accept_result(returncode, output, marker)
        log_name = name.removesuffix(".ps1") + ".log"
        (EVIDENCE_DIR / log_name).write_bytes(output.encode("utf-8"))
        lines = [line.strip() for line in output.splitlines()
                 if "PASS " in line or "FAIL " in line or "FATAL:" in line or "ERROR " in line]
        detail = lines[-5:]
        summary["checks"].append({"task": label, "script": name,
                                  "exit": returncode, "passed": passed,
                                  "required_marker": marker, "details": detail,
                                  "log": log_name})
        print(f"{'PASS' if passed else 'FAIL'} {label}: exit={returncode}, log={log_name}", flush=True)
        if not passed:
            for line in detail:
                print("  " + line, flush=True)
    unchanged = all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
                    for path, digest in summary["source_sha256"].items())
    summary["source_unchanged"] = unchanged
    summary["all_standalone_checks_passed"] = (
        unchanged and all(item["passed"] for item in summary["checks"]))
    (EVIDENCE_DIR / "summary.json").write_bytes(
        (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print("T010 and the D031 full-chain contract remain mandatory; "
          "a standalone PASS never asserts board readiness.")
    print(f"Source unchanged: {unchanged}. Summary: {EVIDENCE_DIR / 'summary.json'}")
    return 0 if summary["all_standalone_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
