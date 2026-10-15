"""B round-one launcher: immutable reservation, private Job tree, <=1800s total."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"
STAGE = REPO / "code/output/m3_m2td_endpoint_probe_20261015_r01"
TOOL_ROOT = Path("E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03/IDE")
JOB = REPO / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
PREFLIGHT_SHA = "3a820e173373b82c375ede1ee57761dac63c61bea91e1018f131cfa33cf49d36"


def ident(path):
    b = path.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    start = time.monotonic()
    deadline = start + 1800
    preflight_path = STAGE / "PREFLIGHT.json"
    if ident(preflight_path)["sha256"] != PREFLIGHT_SHA:
        raise ValueError("PRECHECK_IDENTITY")
    pre = json.loads(preflight_path.read_bytes())
    if pre["status"] != "PREPARED_NOT_EXECUTED" or pre["round"] != 1 or pre["stage"] != str(STAGE):
        raise ValueError("PRECHECK_SCOPE")
    if list(DOC.glob("ROUND_*.consumed.json")) or (STAGE / "RUN_RECEIPT.json").exists() or (STAGE / "impl").exists():
        raise ValueError("NO_REUSE_OF_CONSUMED_OR_OLD_STAGE")
    expected = pre["inputs"]
    for name, value in expected.items():
        if ident(STAGE / name) != value:
            raise ValueError("STAGED_INPUT_DRIFT")
    if ident(STAGE / "m2_fourvoice_timbre_delay_board_top.gprj") != pre["project"] or ident(STAGE / "run.tcl") != pre["tcl"]:
        raise ValueError("PROJECT_TCL_DRIFT")
    if ident(STAGE / "TOOL_MANIFEST.json") != pre["tool_manifest"]:
        raise ValueError("TOOL_MANIFEST_DRIFT")
    tool_ids = json.loads((STAGE / "TOOL_MANIFEST.json").read_bytes())
    for name, value in tool_ids.items():
        if ident(TOOL_ROOT / name) != value:
            raise ValueError("TOOL_DEPENDENCY_DRIFT")
    migration = json.loads((STAGE / "PATH_MIGRATION.json").read_bytes())
    if migration["count"] != 40 or not migration["inverse_all_equal"]:
        raise ValueError("MIGRATION_NOT_VALID")
    for item in migration["files"]:
        raw = (STAGE / item["file"]).read_bytes()
        for old, new in {(c["old"], c["new"]) for c in item["changes"]}:
            raw = raw.replace(new.encode(), old.encode())
        if raw != (STAGE / "originals" / item["file"]).read_bytes():
            raise ValueError("MIGRATION_INVERSE_DRIFT")
        for c in item["changes"]:
            if ident(STAGE / c["dependency_relative"]) != c["dependency_original_identity"]:
                raise ValueError("MAPPED_DEPENDENCY_DRIFT")
    protected = [STAGE / name for name in expected] + [preflight_path, STAGE / "run.tcl", STAGE / "m2_fourvoice_timbre_delay_board_top.gprj",
                 STAGE / "TARGETS.json", STAGE / "ENVIRONMENT.json", STAGE / "PATH_MIGRATION.json", JOB, Path(__file__), Path(sys.executable)]
    before = {str(p): ident(p) for p in protected}
    module_spec = importlib.util.spec_from_file_location("b_owned_job", JOB)
    job_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(job_module)
    environment = json.loads((STAGE / "ENVIRONMENT.json").read_bytes())
    record = {"round": 1, "status": "RESERVED_NOT_STARTED", "argv": pre["argv"], "cwd": pre["cwd"],
              "start_utc": datetime.now(timezone.utc).isoformat(), "timeout_total_seconds": 1800,
              "tool_calls": 0, "process_created": False, "exit_code": None, "timed_out": False,
              "error": None, "input_before": before, "tool_manifest_before": pre["tool_manifest"],
              "board_release_allowed": False, "stage": str(STAGE)}
    write(DOC / "ROUND_1.consumed.json", {"classification": "IMMUTABLE_PRELAUNCH_RESERVATION",
          "stage": str(STAGE), "preflight_sha256": PREFLIGHT_SHA, "reserved_utc": record["start_utc"],
          "note": "Creation consumes the stage; actual tool-count consumption is in RUN_RECEIPT process_created."})
    write(STAGE / "LAUNCH.json", record)
    job = process = None
    try:
        budget = deadline - time.monotonic() - 30  # reserve post-hash/receipts/termination
        if budget <= 0:
            raise TimeoutError("NO_REMAINING_TOOL_BUDGET")
        record["tool_wait_budget_seconds"] = budget
        job = job_module.WindowsJob()
        with (STAGE / "stdout.log").open("xb") as out, (STAGE / "stderr.log").open("xb") as err:
            process = subprocess.Popen(pre["argv"], cwd=STAGE, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       creationflags=4)  # CREATE_SUSPENDED (not a subprocess constant)
            record.update(tool_calls=1, process_created=True, pid=process.pid)
            write(STAGE / "PROCESS_CREATED.json", {"pid": process.pid, "utc": datetime.now(timezone.utc).isoformat()})
            job.attach_and_resume(process)
            try:
                record["exit_code"] = process.wait(timeout=budget)
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                job.terminate()
                record["exit_code"] = process.wait(timeout=5)
    except Exception as error:
        record["error"] = type(error).__name__ + ": " + str(error)
        if process is not None and process.poll() is None:
            if job is not None:
                job.terminate()
            else:
                process.kill()
            record["exit_code"] = process.wait(timeout=5)
    finally:
        if job is not None:
            job.close()
        record["input_after"] = {str(p): ident(p) for p in protected}
        tool_after = {name: ident(TOOL_ROOT / name) for name in tool_ids}
        record["tool_identities_unchanged"] = tool_after == tool_ids
        record["input_unchanged"] = record["input_after"] == before
        record["logs"] = {name: ident(STAGE / name) for name in ("stdout.log", "stderr.log") if (STAGE / name).is_file()}
        report_dir = STAGE / "impl"
        record["reports"] = {p.relative_to(STAGE).as_posix(): ident(p) for p in report_dir.rglob("*")
                             if p.is_file() and p.suffix.lower() in (".html", ".txt", ".vg", ".fs", ".sdc", ".do", ".cfg")} if report_dir.exists() else {}
        record["seconds_total"] = time.monotonic() - start
        record["finish_utc"] = datetime.now(timezone.utc).isoformat()
        success = record["exit_code"] == 0 and record["error"] is None and not record["timed_out"] and record["input_unchanged"] and record["tool_identities_unchanged"] and record["seconds_total"] <= 1800
        record["status"] = "TOOL_EXIT0_AWAIT_INDEPENDENT_ENDPOINT_CHECK" if success else "FAIL_PARTIAL_STOP"
        write(STAGE / "RUN_RECEIPT.json", record)
        write(DOC / "NIGHT_B_ROUND_1.json", {"round": 1, "process_created": record["process_created"],
              "physical_tool_calls": record["tool_calls"], "seconds": record["seconds_total"], "status": record["status"],
              "run_receipt": str(STAGE / "RUN_RECEIPT.json"), "receipt_identity": ident(STAGE / "RUN_RECEIPT.json"),
              "board_release_allowed": False})
    print(json.dumps({k: record[k] for k in ("status", "exit_code", "timed_out", "error", "seconds_total", "tool_calls", "input_unchanged", "tool_identities_unchanged")}))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
