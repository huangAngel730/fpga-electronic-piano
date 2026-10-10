"""Run exactly one bounded Gowin build for the v2 exact RAM fulltop."""
from __future__ import annotations

from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

import prepare_138k_score_bram_integration as prepared
import check_138k_score_bram_integration as gate

ROOT = Path(__file__).resolve().parents[2]
TOOL = Path("D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe")
RUNS = prepared.BUILD_ROOT / "runs"
ZONE = datetime.timezone(datetime.timedelta(hours=8))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")


def source_snapshot(receipts):
    snapshot = {}
    for receipt_path in receipts:
        record = json.loads(Path(receipt_path).read_bytes())
        if (record.get("passed") is not True or record.get("programmed") is not False
                or record.get("physical_STA_passed") is not False
                or not 0 < record.get("elapsed_seconds", 999999) <= 1800):
            raise ValueError("SIMULATION_NOT_QUALIFIED:" + str(receipt_path))
        for mapping_name in ("source_SHA256", "compiled_sources_SHA256"):
            if not record.get(mapping_name):
                raise ValueError("MISSING_SIMULATION_SOURCE_MANIFEST")
            for name, expected in record[mapping_name].items():
                if sha(name) != expected:
                    raise ValueError("SIMULATION_SOURCE_CHANGED:" + name)
                snapshot[name] = expected
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True,
                        help="v2 prepared project used only as the immutable input identity")
    parser.add_argument("--simulation-receipts", type=Path, nargs=4, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--preflight-only", action="store_true",
                        help="prepare and verify identities only; never start Gowin")
    args = parser.parse_args()
    source_project = args.project.resolve()
    run = args.output.resolve()
    run.relative_to(RUNS.resolve())
    if run == RUNS.resolve() or run.exists():
        parser.error("REFUSE_OVERWRITE_OR_NONUNIQUE_OUTPUT")
    if not 1 <= args.timeout_seconds <= 1800:
        parser.error("TIMEOUT_OUT_OF_RANGE")
    if not TOOL.is_file():
        parser.error("GOWIN_TOOL_MISSING")

    try:
        source_frozen = prepared.validate(source_project)
        simulation = {}
        names = set()
        for receipt_path in args.simulation_receipts:
            record = json.loads(receipt_path.read_bytes())
            if (record.get("frozen_receipt_SHA256") != sha(source_project / "frozen_receipt.json")
                    or record.get("prepare_script_SHA256") != source_frozen["prepare_script_sha256"]):
                parser.error("SIMULATED_PROJECT_IDENTITY_MISMATCH")
            name = record.get("negative") or "positive"
            if name in names:
                parser.error("DUPLICATE_SIMULATION_PROOF:" + name)
            names.add(name)
            simulation[name] = {"path": str(receipt_path.resolve()),
                                "sha256": sha(receipt_path),
                                "result": record.get("result"),
                                "specified_negative": record.get("specified_negative"),
                                "elapsed_seconds": record.get("elapsed_seconds")}
        if names != {"positive", "audio_isolation", "response_command", "video_isolation"}:
            parser.error("NEED_POSITIVE_AND_THREE_BEHAVIOR_NEGATIVES")
        positive = simulation["positive"]["result"]
        if (positive.get("passed") is not True or positive.get("cases") != 13
                or positive.get("responses") != 12 or positive.get("read_events") != 3):
            parser.error("EXACT_POSITIVE_SCOPE_MISSING")
        simulation_sources = source_snapshot(args.simulation_receipts)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.error(str(error))

    run.mkdir(parents=True, exist_ok=False)
    project = run / "project"
    prepared.prepare(project)
    # The preparation API already generates each absolute GPRJ/ROM path for
    # this unique output; no redirect or edit of the frozen Tcl is required.
    frozen_tcl = (project / "run.tcl").read_text(encoding="utf-8")
    run_project = project.resolve().as_posix()
    expected_open = "open_project {" + (project / prepared.PROJECT).as_posix() + "}"
    if (frozen_tcl.splitlines()[0] != expected_open or frozen_tcl.count(run_project) != 1):
        raise ValueError("RUN_TCL_UNIQUE_PROJECT_ANCHOR")
    invocation_tcl = run / "run_invocation.tcl"
    invocation_tcl.write_bytes((project / "run.tcl").read_bytes())
    if invocation_tcl.read_bytes() != (project / "run.tcl").read_bytes():
        raise ValueError("INVOCATION_TCL_NOT_EXACT")

    preflight = {"date": "2026-10-10", "version": prepared.VERSION,
                 "passed": True, "prepared_project_receipt_sha256": sha(project / "frozen_receipt.json"),
                 "source_project_receipt_sha256": sha(source_project / "frozen_receipt.json"),
                 "prepared_source_sha256": simulation_sources,
                 "tool_sha256": sha(TOOL), "build_runner_sha256": sha(Path(__file__)),
                 "gate_sha256": sha(Path(gate.__file__)), "programmed": False,
                 "physical_STA_passed": False, "new_Gowin_run_authorized_once": True}
    dump(run / "preflight_receipt.json", preflight)
    if args.preflight_only:
        preflight.update(new_Gowin_runs=0, scope="preflight only; not a physical build")
        dump(run / "preflight_receipt.json", preflight)
        print(json.dumps(preflight, ensure_ascii=False, indent=2), flush=True)
        return 0
    record = {"date": "2026-10-10", "version": prepared.VERSION, "attempt_count": 1,
              "state": "running", "programmed": False, "physical_STA_passed": False,
              "timeout_seconds": args.timeout_seconds, "timed_out": False,
              "started": datetime.datetime.now(ZONE).isoformat(),
              "simulation_proofs": simulation, "preflight_sha256": sha(run / "preflight_receipt.json"),
              "frozen_sha256_before": sha(project / "frozen_receipt.json"),
              "command": [str(TOOL), str(invocation_tcl)],
              "tools_and_sources_sha256": {str(TOOL): sha(TOOL), str(Path(__file__)): sha(Path(__file__)),
                                            str(Path(prepared.__file__)): sha(Path(prepared.__file__)),
                                            str(Path(gate.__file__)): sha(Path(gate.__file__)),
                                            str(prepared.SCOPE / "integration_manifest.json"):
                                                sha(prepared.SCOPE / "integration_manifest.json"),
                                            str(invocation_tcl): sha(invocation_tcl)}}
    dump(run / "build_receipt.json", record)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    environment["PATH"] = os.pathsep.join((str(Path(sys.executable).parent),
                                            "D:/Gowin/oss-cad-suite/bin",
                                            "D:/Gowin/oss-cad-suite/lib",
                                            environment.get("PATH", "")))
    start = time.monotonic()
    with (run / "build.log").open("xb") as log:
        process = subprocess.Popen(record["command"], cwd=project, env=environment,
                                   stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        record["pid"] = process.pid
        dump(run / "build_receipt.json", record)
        try:
            process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            record["timed_out"] = True
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=30)
            process.wait(timeout=30)
    record.update(exit_code=process.returncode,
                  state="finished" if process.returncode == 0 and not record["timed_out"] else "failed",
                  elapsed_seconds=round(time.monotonic() - start, 3),
                  finished=datetime.datetime.now(ZONE).isoformat(),
                  frozen_sha256_after=sha(project / "frozen_receipt.json"),
                  build_log_sha256=sha(run / "build.log"),
                  log_sha256=sha(run / "build.log"),
                  invocation_tcl_sha256=sha(invocation_tcl))
    dump(run / "build_receipt.json", record)
    if process.returncode != 0 or record["timed_out"]:
        print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
        return 1
    assessment = gate.review(run)
    dump(run / "assessment.json", assessment)
    record["assessment_passed"] = assessment.get("passed", False)
    dump(run / "build_receipt.json", record)
    print(json.dumps(assessment, ensure_ascii=False, indent=2), flush=True)
    return 0 if assessment.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
