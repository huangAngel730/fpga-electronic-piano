"""R05 preflight / one authorized ModelSim SE-64 2020.4 functional attempt.

No Gowin/device/Git operations. Version-only probes do not compile/elaborate
R05. A mismatch produces BLOCKED_TOOL and leaves the attempt unconsumed.
"""
from datetime import datetime, timezone
import hashlib
import argparse
import os
from pathlib import Path
import platform
import re
import sys
import time

from common import (
    HERE, ROOT, DOCS, R05, R05_SHA, AUTH, Refusal, identity, write_new,
    snapshot_sources, json_load,
)
from input_binding import inspect_archive, stage_exact
from receipt_check import check_step
from supervised_process import invoke
from tool_probe_policy import MODEL_2020, probe_arguments, probe_valid, pin_inventory
from watchdog_candidate import overlay, prerequisite, SECOND_MARKER


KNOWN = (
    Path("E:/FPGA/Bpan/modelsim/modelsim1/win64"),
    Path("D:/program/QUARTS/modelsim_ase/win32aloem"),
)


def tools_identity(directory):
    result = {}
    for name in ("vlib.exe", "vlog.exe", "vsim.exe"):
        result[name] = identity(directory / name)
    for path in sorted(directory.glob("*.dll")):
        result[path.name] = identity(path)
    for path in (
        directory.parent / ".version.txt", directory.parent / "modelsim.ini",
    ):
        if path.is_file():
            result[str(path.resolve())] = identity(path)
    return result


def runtime_configuration(directory):
    # Preserve no license secret/server text. Record presence and hashes only.
    result = {"dynamic_loaded_dependencies": "UNKNOWN_NOT_MEASURED", "license_env": {}, "libraries": {}}
    for key in ("MGLS_LICENSE_FILE", "LM_LICENSE_FILE", "MODELSIM"):
        value = os.environ.get(key)
        result["license_env"][key] = {
            "present": value is not None,
            "value_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None,
        }
    for name in ("std", "ieee", "verilog"):
        lib = directory.parent / name
        result["libraries"][name] = {
            "directory": str(lib), "exists": lib.is_dir(),
            "identity_files": [identity(p) for p in sorted(lib.glob("*")) if p.is_file()],
        }
    return result


def input_snapshot(stage, originals):
    return {
        name: identity(stage / name) for name in originals
    }


def run(output, *, execute=False, requested_bin=None, watchdog_candidate=False):
    output = output.resolve()
    if output.parent != DOCS.resolve() or output.name == "coordinator":
        raise Refusal("OUTPUT_SCOPE", "new direct child of owned documentation directory required")
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start + 900
    receipt = {
        "schema": "M3_R05_ISOLATED_RUN_V1", "status": "PREFLIGHT",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node(), "cwd": str(ROOT),
        "python": identity(sys.executable), "python_version": sys.version,
        "authorization_reference": identity(AUTH), "source_before": snapshot_sources(),
        "night_authorization_reference": identity(ROOT / "code/docs/M3_夜间M2候选权限预授权_2026-10-15.md"),
        "execution_identity": "M3_MODELSIM_SE64_2020_4_ONLY",
        "input_archive": identity(R05), "version_calls": [], "functional_calls": [],
        "functional_attempt_consumed": False, "functional_tool_count": 0,
        "board_release_allowed": False, "physical_signoff": False,
        "total_budget_s": 900, "tool_budget_s": 300,
        "per_request_deadline": "UNKNOWN_NO_PUBLIC_TRACE",
        "analog_latency": "UNKNOWN_NOT_MEASURED",
    }
    try:
        for relative, item in receipt["source_before"].items():
            target = output / "execution_sources" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(Path(item["path"]).read_bytes())
        data, bound = inspect_archive()
        write_new(output / "INPUT_BINDING.json", bound)
        if watchdog_candidate:
            receipt["prior_consumed_failure"] = prerequisite()
            data, receipt["candidate_overlay"] = overlay(data)
            write_new(output / "CANDIDATE_OVERLAY.json", receipt["candidate_overlay"])
        stage = output / "stage" / "inputs"
        staged = stage_exact(data, stage)
        receipt["stage_input_before"] = input_snapshot(stage, staged)
        receipt["stage"] = str(stage)
        selected = None
        for index, directory in enumerate((requested_bin,) if requested_bin else KNOWN[:1]):
            probe = output / f"tool_probe_{index:02d}"
            probe.mkdir()
            if not all((directory / name).is_file() for name in ("vlib.exe", "vlog.exe", "vsim.exe")):
                receipt["version_calls"].append({"directory": str(directory), "status": "MISSING_TOOL"})
                continue
            before = tools_identity(directory)
            pin_file = DOCS / "PREFLIGHT_2020_02/tool_probe_00/TOOL_IDENTITY.json"
            pinned = json_load(pin_file.read_bytes())["before"]
            binding = pin_inventory(before, pinned, (directory.parent / ".version.txt").read_bytes())
            receipt["original_tool_pin"] = identity(pin_file)
            child_environment = dict(os.environ)
            path_key = next((k for k in child_environment if k.upper() == "PATH"), "PATH")
            child_environment[path_key] = str(directory) + os.pathsep + child_environment.get(path_key, "")
            versions = []
            for name in ("vlib", "vlog", "vsim"):
                result = invoke(
                    [str(directory / f"{name}.exe"), *probe_arguments(name)],
                    stage, probe, name + "_version", deadline, step_budget=30,
                    environment=child_environment,
                )
                raw = (
                    Path(result["stdout"]["path"]).read_bytes()
                    + Path(result["stderr"]["path"]).read_bytes()
                )
                result["probe_contract_pass"] = probe_valid(name, result, raw)
                result["probe_kind"] = "HELP_NOT_VERSION" if name == "vlib" else "RUNTIME_VERSION"
                versions.append(result)
                if not result["probe_contract_pass"]:
                    break
            after = tools_identity(directory)
            probe_receipt = {
                "directory": str(directory), "before": before,
                "after": after, "unchanged": before == after,
                "calls": versions, "runtime_configuration": runtime_configuration(directory),
                "path_policy": "EXACT_BIN_PREFIX_CHILD_ONLY_NO_SYSTEM_CHANGE",
                "version_binding": binding,
            }
            write_new(probe / "TOOL_IDENTITY.json", probe_receipt)
            receipt["version_calls"].append(probe_receipt)
            if len(versions) == 3 and all(
                x["probe_contract_pass"] and not x["timeout"] and not x["error"]
                and x["exit_code"] == 0 for x in versions
            ) and before == after:
                selected = directory
                break
        if selected is None:
            receipt["status"] = "BLOCKED_TOOL"
            receipt["reason"] = "No verified ModelSim SE-64 2020.4 at the selected exact path; no compile/run"
            return_code = 2
        else:
            commands = [
                [str(selected / "vlib.exe"), "work"],
                [str(selected / "vlog.exe"), "-sv", "+incdir+include", "-f", "compile.f"],
                [str(selected / "vsim.exe"), "-c", "work.tb_m2_m1td_real_chain",
                 "-do", "run -all; quit -f"],
            ]
            tool_before = tools_identity(selected)
            receipt.update({"planned_argv": commands, "tool_before": tool_before})
            write_new(output / "PREFLIGHT.json", receipt)
            if not execute:
                receipt["status"] = "READY_NOT_EXECUTED"
                return_code = 3
            else:
                # Globally unique consumption across new output directories.
                # No fallback tool/version and no repeat after any failure.
                consume = SECOND_MARKER if watchdog_candidate else DOCS / "R05_FUNCTIONAL_ATTEMPT_CONSUMED.json"
                if consume.exists():
                    raise Refusal("ATTEMPT_ALREADY_CONSUMED", str(consume))
                reservation = output / "ATTEMPT_RESERVATION.json"
                write_new(reservation, {
                    "input_sha256": R05_SHA, "output": str(output),
                    "preflight": identity(output / "PREFLIGHT.json"),
                    "authorization_reference": identity(AUTH),
                    "machine": platform.node(), "commands": commands,
                    "candidate_overlay": receipt.get("candidate_overlay"),
                })
                receipt["reservation_marker"] = identity(reservation)
                logs = output / "functional_logs"
                logs.mkdir()
                def created(pid):
                    if not receipt["functional_attempt_consumed"]:
                        write_new(consume, {
                            "input_sha256": R05_SHA, "output": str(output), "pid": pid,
                            "preflight": identity(output / "PREFLIGHT.json"),
                            "authorization_reference": identity(AUTH),
                            "machine": platform.node(), "commands": commands,
                            "actual_functional_round": 2 if watchdog_candidate else 1,
                            "candidate_overlay": receipt.get("candidate_overlay"),
                            "prior_consumed_failure": receipt.get("prior_consumed_failure"),
                        })
                        receipt["functional_attempt_consumed"] = True
                        receipt["consumption_marker"] = identity(consume)
                for name, argv in zip(("vlib", "vlog", "vsim"), commands):
                    result = invoke(argv, stage, logs, name, deadline,
                                    environment=child_environment, on_created=created)
                    receipt["functional_calls"].append(result)
                    receipt["functional_tool_count"] += int(result["process_created"] is True)
                    if result["error"] or result["log_limit_exceeded"]:
                        raise Refusal("TOOL_SUPERVISION", name + ":" + str(result["error"]))
                    result["log_policy"] = check_step(
                        name, Path(result["stdout"]["path"]).read_bytes(),
                        Path(result["stderr"]["path"]).read_bytes(),
                        result["exit_code"], result["timeout"],
                    )
                receipt["tool_after"] = tools_identity(selected)
                if receipt["tool_after"] != tool_before:
                    raise Refusal("TOOL_CHANGED", "tool/dependency SHA changed")
                receipt["status"] = "CONSISTENT_PENDING_M2"
                return_code = 0
        receipt["stage_input_after"] = input_snapshot(stage, staged)
        if receipt["stage_input_before"] != receipt["stage_input_after"]:
            raise Refusal("INPUT_CHANGED", "stage originals changed")
        receipt["source_after"] = snapshot_sources()
        if receipt["source_before"] != receipt["source_after"]:
            raise Refusal("SOURCE_CHANGED", "runner/candidate changed")
        # Artifact collection and all final hashing are inside the budget.
        receipt["elapsed_s"] = time.monotonic() - start
        if receipt["elapsed_s"] >= 900:
            raise Refusal("TOTAL_TIMEOUT", "post-collection total limit")
        receipt["exit_code"] = return_code
        write_new(output / "RUN_RECEIPT.json", receipt)
        print(receipt["status"])
        return return_code
    except Exception as exc:
        if "stage" in locals() and "staged" in locals():
            receipt["stage_input_after"] = input_snapshot(stage, staged)
        receipt["source_after"] = snapshot_sources()
        if "selected" in locals() and selected is not None:
            receipt["tool_after"] = tools_identity(selected)
        receipt.update({
            "status": "FAILED_STOP_NO_RETRY", "error": repr(exc),
            "diagnostic": getattr(exc, "code", "RUNNER_FAILURE"),
            "elapsed_s": time.monotonic() - start, "exit_code": 1,
        })
        if not (output / "RUN_RECEIPT.json").exists():
            write_new(output / "RUN_RECEIPT.json", receipt)
        print(receipt["status"], receipt["error"])
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--modelsim-bin", type=Path)
    parser.add_argument("--watchdog-candidate", action="store_true")
    args = parser.parse_args()
    return run(args.output, execute=args.execute, requested_bin=args.modelsim_bin,
               watchdog_candidate=args.watchdog_candidate)


if __name__ == "__main__":
    sys.exit(main())
