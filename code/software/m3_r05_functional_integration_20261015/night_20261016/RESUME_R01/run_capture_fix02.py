"""One new bounded observation candidate, using the unchanged Job supervisor."""
import argparse
import hashlib
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from common import ROOT, DOCS, TB_DIR, identity, write_new, json_load
from input_binding import inspect_archive, stage_exact
from runner import tools_identity, runtime_configuration
from tool_probe_policy import pin_inventory, probe_arguments, probe_valid
from receipt_check import check_step
from supervised_process import invoke

BASE = DOCS / "night_20261016/RESUME_R01"
BOARD = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016/RESUME_R01/FIX_02/m2_fourvoice_timbre_delay_board_observed.sv"
TOOL = Path("E:/FPGA/Bpan/modelsim/modelsim1/win64")


def source_snapshot():
    paths = list(HERE.glob("*.py")) + list((TB_DIR / "night_20261016/RESUME_R01").glob("*.sv")) + [BOARD, TB_DIR / "night_20261016/RESUME_R01/FIX_02/m3_r05_public_observer.sv"]
    paths += list(HERE.parent.parent.glob("*.py"))
    return {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}


def run(name):
    if not name.startswith("RUN_") or not name[4:].isdigit():
        raise ValueError("explicit numbered run required")
    index = int(name[4:])
    if not 1 <= index <= 9:
        raise ValueError("numbered output range exceeded")
    if (BASE / (name + "_CONSUMED.json")).exists():
        raise ValueError("RESUME_FUNCTIONAL_GROUP_ALREADY_CONSUMED")
    if len(list(BASE.glob("RUN_*_CONSUMED.json"))) >= 3:
        raise ValueError("RESUME_THREE_GROUP_BUDGET_EXHAUSTED")
    out = BASE / name
    out.mkdir(exist_ok=False)
    started = time.monotonic()
    deadline = started + 900
    receipt = {"schema": "M3_R05_NIGHT_OBSERVATION_RUN_V1", "head": "c12636c034be62e10c564217298564422a533b9c",
        "started_utc": datetime.now(timezone.utc).isoformat(), "source_before": source_snapshot(),
        "python": identity(sys.executable), "authorization": identity(DOCS / "coordinator/night_20261016/RESUME_R01/AUTHORIZATION_AND_DISPATCH.md"),
        "prior_success_receipt": identity(DOCS / "REWORK_WATCHDOG_RUN_02/RUN_RECEIPT.json"),
        "prior_failure_receipt": identity(DOCS / "REWORK_AUTHORIZED_RUN_01/RUN_RECEIPT.json"),
        "new_batch_candidate": index, "functional_attempt_consumed": False,
        "version_calls": [], "functional_calls": [], "tool_budget_s": 300, "round_budget_s": 900,
        "capture_origin": "REAL_MODELSIM_R05_UART_MIDI_BOARD_PUBLIC_PORTS",
        "analog_latency": "UNKNOWN_NOT_MEASURED", "first_valid": "UNKNOWN_NOT_EXPORTED", "board_release_allowed": False}
    code = 1
    try:
        receipt["source_snapshot_layout"] = "FLAT_RELATIVE_SHA_MAP_V1"
        receipt["source_snapshot_files"] = {}
        for relative, item in receipt["source_before"].items():
            tag = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
            target = out / "source" / (tag + "_" + Path(relative).name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item["path"], target)
            receipt["source_snapshot_files"][relative] = identity(target)
            if receipt["source_snapshot_files"][relative]["sha256"] != item["sha256"]:
                raise ValueError("EXECUTED_SOURCE_SNAPSHOT_BYTES_CHANGED")
        data, binding = inspect_archive()
        stage = out / "stage/inputs"
        data["inputs/sources/m2_fourvoice_timbre_delay_board_top.sv"] = BOARD.read_bytes()
        data["inputs/tb_m2_m1td_real_chain.sv"] = (TB_DIR / "night_20261016/RESUME_R01/tb_r05_observed_7ms.sv").read_bytes()
        data["inputs/sources/m3_r05_public_observer.sv"] = (TB_DIR / "night_20261016/RESUME_R01/FIX_02/m3_r05_public_observer.sv").read_bytes()
        compile_file = data["inputs/compile.f"]
        data["inputs/compile.f"] = compile_file + b"sources/m3_r05_public_observer.sv\n"
        receipt["stage_before"] = stage_exact(data, stage)
        receipt["stage"] = str(stage.resolve())
        receipt["frozen_input_binding"] = identity(BASE / "INPUT_BINDING.json")
        receipt["candidate_changes"] = identity(BASE / "CANDIDATE_CHANGES_FIX02.json")
        before = tools_identity(TOOL)
        prior = json_load((DOCS / "REWORK_WATCHDOG_RUN_02/tool_probe_00/TOOL_IDENTITY.json").read_bytes())
        receipt["tool_pin"] = pin_inventory(before, prior["before"], (TOOL.parent / ".version.txt").read_bytes())
        receipt["tool_before"] = before
        receipt["runtime"] = runtime_configuration(TOOL)
        env = dict(os.environ)
        pathkey = next((k for k in env if k.upper() == "PATH"), "PATH")
        env[pathkey] = str(TOOL) + os.pathsep + env.get(pathkey, "")
        logs = out / "logs"
        logs.mkdir()
        for tool in ("vlib", "vlog", "vsim"):
            call = invoke([str(TOOL / (tool + ".exe")), *probe_arguments(tool)], stage,
                logs, tool + "_probe", deadline, step_budget=30, environment=env)
            receipt["version_calls"].append(call)
            raw = Path(call["stdout"]["path"]).read_bytes() + Path(call["stderr"]["path"]).read_bytes()
            if not probe_valid(tool, call, raw):
                raise ValueError("BLOCKED_TOOL_PROBE:" + tool)
        commands = [[str(TOOL / "vlib.exe"), "work"],
            [str(TOOL / "vlog.exe"), "-sv", "+incdir+include", "-f", "compile.f"],
            [str(TOOL / "vsim.exe"), "-c", "work.tb_m2_m1td_real_chain", "-do", "run -all; quit -f"]]
        receipt["argv"] = commands
        write_new(out / "PREFLIGHT.json", receipt)
        def created(pid):
            if not receipt["functional_attempt_consumed"]:
                write_new(BASE / (name + "_CONSUMED.json"), {"pid": pid, "output": str(out.resolve()),
                    "preflight": identity(out / "PREFLIGHT.json"), "round": index,
                    "authorization": receipt["authorization"], "new_batch_only": True})
                receipt["functional_attempt_consumed"] = True
        for tool, argv in zip(("vlib", "vlog", "vsim"), commands):
            call = invoke(argv, stage, logs, tool, deadline, environment=env, on_created=created)
            receipt["functional_calls"].append(call)
            if call["error"] or call["log_limit_exceeded"]:
                raise ValueError("SUPERVISION:" + str(call["error"]))
            call["policy"] = check_step(tool, Path(call["stdout"]["path"]).read_bytes(),
                Path(call["stderr"]["path"]).read_bytes(), call["exit_code"], call["timeout"])
        receipt["stage_after"] = {n: {"bytes": (stage/n).stat().st_size,
            "sha256": identity(stage/n)["sha256"]} for n in receipt["stage_before"]}
        if receipt["stage_after"] != receipt["stage_before"]:
            raise ValueError("STAGE_SOURCE_CHANGED")
        receipt["status"] = "REAL_CAPTURE_TOOL_PASS_PENDING_INDEPENDENT_VALIDATION"
        for name in ("REAL_CAPTURE.jsonl", "REAL_INPUTS.jsonl", "STARTUP_CAPTURE.jsonl", "STARTUP_INPUTS.jsonl", "STARTUP_BOUNDARY_RAW.json"):
            receipt[name] = identity(stage / name)
        code = 0
    except Exception as exc:
        receipt.update(status="FAILED_STOP", error=repr(exc), original_exception=repr(exc))
    receipt["source_after"] = source_snapshot()
    receipt["tool_after"] = tools_identity(TOOL)
    if receipt["source_before"] != receipt["source_after"] or ("tool_before" in receipt and receipt["tool_before"] != receipt["tool_after"]):
        receipt.update(status="IDENTITY_CHANGED", error="source or tool changed", preceding_error=receipt.get("error"))
        code = 1
    receipt["elapsed_s"] = time.monotonic() - started
    receipt["exit_code"] = code
    write_new(out / "RUN_RECEIPT.json", receipt)
    print(receipt["status"], receipt.get("error", ""))
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    sys.exit(run(parser.parse_args().run))
