"""Validate one T056 138K L build without changing it or authorizing a board."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import check_platform_timing  # noqa: E402
import prepare_138k_l_project as adapter  # noqa: E402


STEM = "audio_visual_coexistence_top"
PROFILE = "138k_c40_hold065"
REQUIRED_MARKERS = (
    "GowinSynthesis finish",
    "Placement and routing completed",
    "Timing analysis completed",
    "Bitstream generation completed",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def require_run(path: Path) -> Path:
    resolved = path.resolve()
    runs = (ROOT / "code/build/138k_l/runs").resolve()
    resolved.relative_to(runs)
    if resolved == runs:
        raise ValueError("RUN_MUST_BE_CHILD_OF_RUNS")
    return resolved


def validate(run: Path) -> dict[str, object]:
    run = require_run(run)
    project = run / "project"
    frozen = adapter.check(project)
    frozen_path = project / "receipt.json"
    build_path = run / "build_receipt.json"
    log_path = run / "build.log"
    build = json.loads(build_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if build.get("attempt_count") != 1:
        errors.append("build was not exactly one attempt")
    if build.get("state") != "finished" or build.get("exit_code") != 0:
        errors.append("build did not finish successfully")
    if build.get("timed_out") is not False:
        errors.append("build timed out")
    if build.get("programmed") is not False:
        errors.append("programming flag must remain false")
    if not 1 <= int(build.get("timeout_seconds", 0)) <= 1800:
        errors.append("invalid build timeout contract")
    if build.get("frozen_receipt_sha256_before") != sha256(frozen_path):
        errors.append("frozen receipt SHA differs from pre-build record")
    if build.get("frozen_receipt_sha256_after") != sha256(frozen_path):
        errors.append("frozen receipt changed during build")
    if build.get("project_sha256_before") != sha256(project / adapter.SOURCE_PROJECT):
        errors.append("adapted GPRJ changed during build")
    if build.get("project_sha256_after") != sha256(project / adapter.SOURCE_PROJECT):
        errors.append("adapted GPRJ post-build SHA mismatch")
    if build.get("build_log_sha256") != sha256(log_path):
        errors.append("build log SHA mismatch")
    if build.get("runner_sha256") != sha256(SCRIPT_DIR / "run_138k_l_build_once.py"):
        errors.append("runner SHA mismatch")
    if build.get("acceptance_sha256") != sha256(Path(__file__)):
        errors.append("acceptance SHA mismatch")
    command = build.get("command")
    if (
        not isinstance(command, list)
        or len(command) != 2
        or Path(command[0]).name.lower() != "gw_sh.exe"
        or command[1] != "run.tcl"
    ):
        errors.append("unexpected build command")
    log = read(log_path)
    for marker in REQUIRED_MARKERS:
        if marker not in log:
            errors.append("missing build completion marker: " + marker)

    pnr = project / "impl/pnr"
    report_paths = {
        "timing": pnr / f"{STEM}_tr_content.html",
        "usage": pnr / f"{STEM}.rpt.txt",
        "pins": pnr / f"{STEM}.pin.html",
        "command": pnr / "cmd.do",
        "config": pnr / "device.cfg",
        "bitstream": pnr / f"{STEM}.fs",
    }
    missing = [name for name, path in report_paths.items() if not path.is_file()]
    if missing:
        errors.append("missing build artifacts: " + ",".join(missing))
        timing_result = {
            "profile": PROFILE,
            "errors": ["reports unavailable"],
            "offline_timing_gate_pass": False,
            "board_release_allowed": False,
        }
    else:
        timing_result = check_platform_timing.review(
            PROFILE,
            read(report_paths["timing"]),
            read(report_paths["usage"]),
            read(report_paths["pins"]),
            read(project / "inputs/constraints/audio_visual_hold055.sdc"),
            read(report_paths["command"]),
            read(report_paths["config"]),
        )
        errors.extend(timing_result["errors"])

    setup = timing_result.get("slacks", {}).get("Setup")
    setup_floor = (
        isinstance(setup, (int, float)) and math.isfinite(setup) and setup >= 0.5
    )
    if not setup_floor:
        errors.append("Setup engineering floor 0.5ns not met")
    report_sha = {
        name: sha256(path) for name, path in report_paths.items() if path.is_file()
    }
    result = {
        "date": "2026-10-06",
        "run_directory": str(run),
        "profile": PROFILE,
        "source_commit": frozen["source_commit"],
        "source_archive_sha256": frozen["source_archive_sha256"],
        "frozen_receipt_sha256": sha256(frozen_path),
        "build_receipt_sha256": sha256(build_path),
        "build_log_sha256": sha256(log_path),
        "build_exit_code": build.get("exit_code"),
        "timed_out": build.get("timed_out"),
        "attempt_count": build.get("attempt_count"),
        "programmed": False,
        "setup_floor_0p5_passed": setup_floor,
        "report_gate": timing_result,
        "artifact_sha256": report_sha,
        "errors": errors,
        "passed": not errors,
        "board_release_allowed": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.run)
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        result = {
            "date": "2026-10-06",
            "passed": False,
            "errors": ["missing or malformed T056 build: " + str(error)],
            "programmed": False,
            "board_release_allowed": False,
        }
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        destination = args.json.resolve()
        destination.relative_to(require_run(args.run))
        destination.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
