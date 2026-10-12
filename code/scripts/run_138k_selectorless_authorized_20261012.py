"""Exact newly authorized selectorless N32/R1 attempt, at most once/900s.

Old frozen project, false receipt and failed attempt remain readonly.
No PnR, STA, bitstream, automatic retry, new feature or device operation.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import inspect_polyphony_synthesis_report as reports
import prepare_138k_polyphony_selectorless_20261012 as prepared

ROOT = prepared.original.ROOT
PROJECT = prepared.DEST
OUTPUT = ROOT / "code/output/M2_N32R1_selectorless_authorized_20261012_01"
AUTH = ROOT / "code/build/138k_polyphony_resource/selectorless_authorization_20261012"
TCL_SHA = "c1747c36bf4cc16f35e578e8fb6b8712a4507313d017d825465c932d0e724f2b"
REPAIR_SHA = "90f41bba512a3b7b4e4033e37bdce20e53b0347acf188d76c4286574cad8f576"
SHELL_SHA = "4c172d4c0d2a4c7ef5c764d091a315cbcde2127573554bfd7d09ac6f2e5ea535"
HELPER = ROOT / "code/software/audio_math_acceptance_candidate/t060_minclosure_20261011"
HELPER_SHA = "7284f721fa5c9ba1e8e03be31df6b6a1e4b87b5234cb21130c33c07d07bb831f"
JOB_SHA = "6783aa1e1901118cbab2adac295659d3dbdd426ef281a53a84cf1a6e8b984f30"
HUMAN_APPROVAL = "批准M2完成selectorless后继的精确身份绑定和执行门禁，并执行一次仅综合，总上限900秒，使用全新输出目录，失败不重试、不提高超时；不执行PnR、STA或设备操作。"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def helper():
    if digest(HELPER / "controlled_runner.py") != HELPER_SHA or digest(HELPER / "windows_job.py") != JOB_SHA:
        raise ValueError("EXACT_BUDGET_AND_OWNED_JOB_HELPER_REQUIRED")
    sys.path.insert(0, str(HELPER))
    spec = importlib.util.spec_from_file_location("m2_exact_selectorless_budget", HELPER / "controlled_runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_tcl(text):
    commands = [line.strip() for line in text.splitlines() if line.strip()]
    prefixes = ("cd {", "open_project {", "set_option -top_module b2l_resource_probe",
                "set_option -verilog_std sysv2017", "set_option -include_path {", "run syn")
    if len(commands) != 6 or any(not value.startswith(prefix) for value, prefix in zip(commands, prefixes)):
        raise ValueError("EXACT_SIX_SYNTHESIS_ONLY_COMMANDS")
    if commands[2] != prefixes[2] or commands[3] != prefixes[3] or commands[5] != "run syn":
        raise ValueError("SYNTHESIS_SCOPE_OR_TOP_CHANGED")


def preflight(budget):
    budget.limit(90)
    record = prepared.verify()
    if digest(PROJECT / "repair_receipt.json") != REPAIR_SHA:
        raise ValueError("EXACT_PREPARED_REPAIR_RECEIPT")
    if digest(PROJECT / "run_synthesis_only.tcl") != TCL_SHA:
        raise ValueError("EXACT_SELECTORLESS_TCL")
    if record["configuration"] != dict(N=32, response=1, profile="audio_and_public_read_no_injection"):
        raise ValueError("EXACT_N32_R1_CONFIGURATION")
    if record["synthesis_authorized"] is not False:
        raise ValueError("OLD_FALSE_RECEIPT_MODIFIED")
    tool = Path(record["tool"]["identities"]["shell"]["path"])
    if digest(tool) != SHELL_SHA:
        raise ValueError("EXACT_GW_SH_IDENTITY")
    if OUTPUT.exists() or (AUTH / "consumed.json").exists():
        raise ValueError("ONE_ATTEMPT_OUTPUT_OR_AUTH_ALREADY_EXISTS_NO_RETRY")
    validate_tcl((PROJECT / "run_synthesis_only.tcl").read_text("ascii"))
    budget.limit(90)
    return record, tool


def execute():
    started = time.monotonic()
    lib = helper()
    budget = lib.Budget(900)
    budget.started = started
    record, tool = preflight(budget)
    protected = sorted(p for root in (prepared.SOURCE, PROJECT) for p in root.rglob("*") if p.is_file())
    before = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
    budget.limit(90)
    AUTH.mkdir(parents=True, exist_ok=True)
    approval = dict(schema=1, human_instruction=HUMAN_APPROVAL,
                    human_source="Direct user instruction in this chat 2026-10-12",
                    project=str(PROJECT), output=str(OUTPUT), total_seconds=900,
                    configuration=record["configuration"], Tcl_sha256=TCL_SHA,
                    repair_receipt_sha256=REPAIR_SHA, shell_sha256=SHELL_SHA,
                    entry_sha256=digest(Path(__file__)), budget_helper_sha256=HELPER_SHA,
                    job_helper_sha256=JOB_SHA, one_attempt=True, automatic_retry=False,
                    original_receipts_modified=False, PnR=False, STA=False, device=False,
                    clipped_successor_in_this_synthesis=False)
    # Atomic reservation is persistent, even launch/configuration failure uses it.
    lib.dump(AUTH / "consumed.json", dict(approval=approval,
             consumed_UTC=datetime.now(timezone.utc).isoformat(), state="RESERVED_NO_RETRY"))
    OUTPUT.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="FAIL_PARTIAL", exit_code=1, failure=None, approval=approval,
                   tool_runs=0, timed_out=False, PnR=False, STA=False,
                   resources="UNKNOWN", resource_admission=False, device=False,
                   source_before=before, physical_STA="NOT_RUN", total_limit_seconds=900,
                   tool_before=record["tool"]["identities"],
                   automatic_retries=0, steps=[])
    process, job = None, None
    try:
        work = OUTPUT / "project"
        work.mkdir()
        gprj = (PROJECT / prepared.original.PROJECT).read_bytes()
        (work / prepared.original.PROJECT).write_bytes(gprj)
        old = (PROJECT / "run_synthesis_only.tcl").read_text("ascii")
        old_cd = "cd {" + PROJECT.as_posix() + "}"
        old_open = "open_project {" + (PROJECT / prepared.original.PROJECT).as_posix() + "}"
        new_cd = "cd {" + work.as_posix() + "}"
        new_open = "open_project {" + (work / prepared.original.PROJECT).as_posix() + "}"
        if old.count(old_cd) != 1 or old.count(old_open) != 1:
            raise ValueError("RUNTIME_PATH_ANCHORS")
        runtime = old.replace(old_cd, new_cd).replace(old_open, new_open)
        if runtime.replace(new_cd, old_cd).replace(new_open, old_open) != old:
            raise ValueError("NONREVERSIBLE_RUNTIME_RELOCATION")
        validate_tcl(runtime)
        (work / "run_synthesis_only.tcl").write_bytes(runtime.encode("ascii"))
        command = [str(tool), "run_synthesis_only.tcl"]
        receipt.update(command=command, cwd=str(work), runtime_gprj_sha256=digest(work / prepared.original.PROJECT),
                       runtime_tcl_sha256=digest(work / "run_synthesis_only.tcl"),
                       relocation_changes=["cd", "open copied GPRJ"], source_paths_readonly=True)
        remaining = 900 - budget.elapsed()
        if remaining <= 0:
            raise ValueError("PREFLIGHT_TOTAL_TIMEOUT_NO_RETRY")
        with (OUTPUT / "stdout.bin").open("xb") as stdout, (OUTPUT / "stderr.bin").open("xb") as stderr:
            job = lib.WindowsJob() if os.name == "nt" else None
            flags = dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x4) if job else dict(start_new_session=True)
            process = subprocess.Popen(command, cwd=work, stdout=stdout, stderr=stderr, **flags)
            receipt.update(tool_runs=1, tool_pid=process.pid, effective_tool_timeout=remaining)
            if job:
                job.attach_and_resume(process)
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                receipt["timed_out"] = True
                receipt["owned_cleanup"] = lib.kill_owned_tree(process, job)
                process.wait(timeout=5)
                raise ValueError("SYNTHESIS_TOTAL_TIMEOUT_NO_RETRY")
        receipt["tool_exit"] = process.returncode
        if process.returncode != 0:
            raise ValueError("TOOL_NONZERO_NO_RETRY")
        budget.limit(90)
        if any(p.suffix.lower() in (".fs", ".bit") for p in work.rglob("*")):
            raise ValueError("FORBIDDEN_PNR_OR_BITSTREAM_PRODUCT")
        names = ("b2l_resource_probe", Path(prepared.original.PROJECT).stem)
        found = [work / "impl/gwsynthesis" / (n + "_syn_rsc.xml") for n in names
                 if (work / "impl/gwsynthesis" / (n + "_syn_rsc.xml")).is_file()]
        if len(found) != 1:
            raise ValueError("ONE_FRESH_SYNTHESIS_RESOURCE_XML_REQUIRED")
        netlists = sorted(work.rglob("*.vg"))
        if not netlists:
            raise ValueError("FRESH_SYNTHESIS_NETLIST_REQUIRED")
        receipt.update(resource_report=reports.inspect(found[0]),
                       netlists=[dict(path=str(p), sha256=digest(p)) for p in netlists],
                       status="SYNTHESIS_COMPLETE_RESOURCE_REVIEW_REQUIRED", exit_code=0,
                       resources="SEE_REAL_REPORT_NOT_YET_ADMITTED")
        budget.limit(90)
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as exc:
        receipt.update(status="FAIL_PARTIAL", exit_code=1, failure=str(exc))
    finally:
        if process is not None and process.poll() is None:
            receipt["exception_cleanup"] = lib.kill_owned_tree(process, job)
            process.wait(timeout=5)
        if job:
            job.close()
        try:
            after = {}
            for path in protected:
                budget.limit(90)
                after[path.relative_to(ROOT).as_posix()] = digest(path)
            receipt["source_after"] = after
            if before != after:
                raise ValueError("FROZEN_OR_PREPARED_SOURCE_DRIFT")
            budget.limit(90)
            tool_after = {}
            for name, pinned in record["tool"]["identities"].items():
                budget.limit(90)
                tool_after[name] = digest(Path(pinned["path"]))
                if tool_after[name] != pinned["sha256"]:
                    raise ValueError("EXACT_TOOL_IDENTITY_CHANGED:" + name)
            receipt["tool_after_SHA256"] = tool_after
            budget.limit(90)
        except (OSError, ValueError) as exc:
            receipt.update(status="FAIL_PARTIAL", exit_code=1,
                           failure=(receipt["failure"] or "") + "; POSTCHECK:" + str(exc))
        lib.finish(OUTPUT, budget, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        if args.execute:
            result = execute()
            print(json.dumps({k: result.get(k) for k in ("status", "exit_code", "failure", "tool_runs", "tool_exit", "elapsed_seconds")}))
            return result["exit_code"]
        lib = helper()
        record, _ = preflight(lib.Budget(900))
        print(json.dumps(dict(status="EXACT_SELECTORLESS_PREFLIGHT_PASS", Tcl_sha256=TCL_SHA,
                             original_frozen_sha256=record["original_frozen_sha256"],
                             tool_runs=0, new_user_authorization=True, attempt_consumed=False)))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps(dict(status="REJECT_NOT_RETRIED", diagnostic=str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
