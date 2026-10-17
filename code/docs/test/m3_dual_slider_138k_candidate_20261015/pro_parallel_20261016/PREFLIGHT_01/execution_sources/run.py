"""New 10/17 package: preflight then <=6 bounded candidate iterations."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TOOLS = Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy")
JOB = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
RTL = ROOT / "code/rtl/input/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/dual_slider_pro_parallel.sv"
TB = ROOT / "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/tb_pro_parallel.sv"
PACKAGE = Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/M1_M2_M3_Pro夜间任务与并行窗口_20261016")
AUTH = PACKAGE / "M3_并行拓展双滑块窗口_2026-10-16.md"
ORIGINALS = ["code/rtl/common/audio_defs_pkg.sv", "code/rtl/common/reset_sync.sv",
    "code/rtl/common/visual_mailbox_cdc.sv", "code/rtl/common/visual_control_bridge.sv",
    "code/rtl/common/visual_event_bridge.sv", "code/rtl/input/visualizer/visual_live_state.sv",
    "code/rtl/input/visualizer/visual_score_tracker.sv", "code/rtl/input/visualizer/visual_scene_renderer.sv",
    "code/rtl/common/sample_tick_gen.sv", "code/rtl/audio_out/pcm_frame_buffer.sv", "code/rtl/audio_out/i2s_tx.sv"]
EXPECTED = {1: "MODE_CDC_DELIVERY", 2: "EVENT_LOSS", 3: "MODE_SWITCH_STALL", 4: "AUDIO_DISPLAY_BACKPRESSURE"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(paths):
    return {str(p): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(set(paths))}


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    out = args.output.resolve()
    if out.parent != HERE or not out.name.startswith("PREFLIGHT_" if args.preflight else "ROUND_"):
        ap.error("EXCLUSIVE_NEW_OUTPUT_REQUIRED")
    previous = list(HERE.glob("ROUND_*/CONSUMED.json"))
    candidate = identities([RTL, TB, Path(__file__).resolve()])
    if not args.preflight:
        if len(previous) >= 6 or any(json.loads(p.read_text(encoding="utf-8"))["candidate"] == candidate for p in previous):
            ap.error("SIX_ROUND_LIMIT_OR_SAME_SOURCE_RETRY")
        if any(json.loads(p.read_text(encoding="utf-8")).get("passed") for p in HERE.glob("ROUND_*/NIGHT_RUN_RECEIPT.json")):
            ap.error("SUCCESS_ALREADY_REACHED_STOP")
    out.mkdir(exist_ok=False)
    sources = [ROOT / p for p in ORIGINALS] + [RTL, TB]
    python_root = Path(sys.executable).parent
    python_dependencies = list(python_root.glob("python*.dll")) + list(python_root.glob("vcruntime*.dll"))
    python_dependencies += list((python_root / "Lib/ctypes").glob("*.py"))
    python_dependencies += [python_root / "DLLs/_ctypes.pyd", python_root / "Lib/subprocess.py"]
    tool_files = [p for p in TOOLS.rglob("*") if p.is_file()] + [Path(sys.executable)] + python_dependencies
    inputs = sources + [JOB, AUTH, PACKAGE / "M3_夜间五小时_Pro四声基础_2026-10-16.md",
        PACKAGE / "夜间任务通用执行规范.md", Path(__file__).resolve(), HERE / "START.md"]
    before = {"inputs": identities(inputs), "tools": identities(tool_files)}
    write(out / "before.json", before)
    if not args.preflight:
        preflight = json.loads((HERE / "PREFLIGHT_01/NIGHT_RUN_RECEIPT.json").read_text(encoding="utf-8"))
        if not preflight["passed"] or preflight["before"]["tools"] != before["tools"]:
            raise RuntimeError("PREFLIGHT_TOOL_IDENTITY_DRIFT")
    work = out / "stage"
    work.mkdir()
    staged = []
    for i, p in enumerate(sources):
        target = work / f"s{i:02d}.sv"
        shutil.copyfile(p, target)
        if sha(p) != sha(target):
            raise RuntimeError("STAGED_INPUT_DRIFT")
        staged.append(target)
    frozen = out / "execution_sources"
    frozen.mkdir()
    for p in (Path(__file__).resolve(), JOB, AUTH, HERE / "START.md"):
        shutil.copyfile(p, frozen / p.name)
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC", "OS", "PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS", "USERPROFILE", "HOMEDRIVE", "HOMEPATH") if k in os.environ}
    env.update(PATH=os.pathsep.join([str(TOOLS / "bin"), str(TOOLS / "lib"), str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]]),
        IVERILOG_ROOT=str(TOOLS / "lib/ivl"), TEMP=str(out), TMP=str(out), PYTHONDONTWRITEBYTECODE="1")
    write(out / "environment.json", env)
    spec = importlib.util.spec_from_file_location("frozen_windows_job", JOB)
    job_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(job_module)
    started = time.monotonic()
    calls = []
    results = []
    error = None
    metadata = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "origin_develop_visible": subprocess.check_output(["git", "rev-parse", "origin/develop"], cwd=ROOT, text=True).strip(),
        "machine": platform.node(), "platform": platform.platform(), "python_version": sys.version,
        "python_executable": sys.executable, "authorization": str(AUTH),
        "expected_negative_diagnostics": EXPECTED, "round_number": 0 if args.preflight else len(previous)+1,
        "prior_rounds_consumed": len(previous), "round_limit": 6,
        "total_icarus_seconds_limit": 240, "python_step_limit": 90, "old_allowances_restored": False,
        "global_deadline_utc": "2026-10-16T21:21:00+00:00", "board_release_allowed": False}
    write(out / "PREFLIGHT.json", metadata)

    def run(label, argv, cwd, expected=0):
        budget = min(90 if args.preflight else 240, 240-(time.monotonic()-started))
        if datetime.now(timezone.utc) >= datetime.fromisoformat(metadata["global_deadline_utc"]) or budget <= 0:
            raise RuntimeError("NIGHT_OR_ROUND_DEADLINE")
        call = {"label": label, "argv": list(map(str, argv)), "cwd": str(cwd), "timeout_seconds": budget,
                "expected_exit": expected, "exit_code": None, "process_created": False,
                "start_utc": datetime.now(timezone.utc).isoformat(), "timeout": False}
        write(out / (label + ".launch.json"), call)
        began = time.monotonic()
        job = job_module.WindowsJob()
        try:
            with (out / (label + ".stdout")).open("xb") as stdout, (out / (label + ".stderr")).open("xb") as stderr:
                if not args.preflight and not (out / "CONSUMED.json").exists():
                    write(out / "CONSUMED.json", {"candidate": candidate, "round_number": len(previous)+1,
                        "reserved_before_process_create": True, "old_allowances_restored": False})
                process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, creationflags=0x00000004)
                call.update(process_created=True, pid=process.pid)
                job.attach_and_resume(process)
                try:
                    call["exit_code"] = process.wait(timeout=budget)
                except subprocess.TimeoutExpired:
                    call["timeout"] = True;job.terminate();call["exit_code"] = process.wait(timeout=5)
        finally:
            job.close()
            call["elapsed_seconds"] = time.monotonic()-began
            call["end_utc"] = datetime.now(timezone.utc).isoformat()
            call["stdout_sha256"] = sha(out / (label + ".stdout"))
            call["stderr_sha256"] = sha(out / (label + ".stderr"))
            write(out / (label + ".receipt.json"), call);calls.append(call)
        if call["timeout"] or call["exit_code"] != expected:
            raise RuntimeError("CALL_FAILED:" + label)
        return (out / (label + ".stdout")).read_text(encoding="utf-8", errors="strict")

    try:
        if args.preflight:
            run("python_version", [sys.executable, "--version"], work)
            run("iverilog_version", [TOOLS / "bin/iverilog.exe", "-V"], work)
            run("vvp_version", [TOOLS / "bin/vvp.exe", "-V"], work)
        else:
            binary = work / "parallel.vvp"
            run("compile", [TOOLS / "bin/iverilog.exe", "-g2012", "-Wall", "-s", "tb_pro_parallel", "-o", binary] + staged, work)
            text = run("positive", [TOOLS / "bin/vvp.exe", binary], work)
            if len(re.findall(r"^PASS PRO_PARALLEL_FIXTURE .+$", text, re.M)) != 1 or "REJECT" in text or "FATAL" in text:
                raise RuntimeError("POSITIVE_NOT_COMPLETE")
            results.append({"name": "positive", "accepted": True, "summary": text.split("PASS PRO_PARALLEL_FIXTURE ")[1].splitlines()[0]})
            for mutation, target in EXPECTED.items():
                text = run(f"negative_{mutation}", [TOOLS / "bin/vvp.exe", binary, f"+mutation={mutation}"], work, 1)
                rejects = re.findall(r"REJECT ([A-Z0-9_]+)", text)
                if rejects != [target] or "PASS PRO_PARALLEL_FIXTURE" in text:
                    raise RuntimeError(f"NEGATIVE_FIRST_DIFFERENCE:{mutation}:{rejects}")
                results.append({"name": f"negative_{mutation}", "accepted": False, "actual_first_difference": target})
    except Exception as exc:
        error = repr(exc)
    after = {"inputs": identities(inputs), "tools": identities(tool_files)}
    write(out / "after.json", after)
    passed = error is None and before == after
    receipt = {**metadata, "passed": passed, "error": error, "before": before, "after": after,
        "identity_stable": before == after, "calls": calls, "results": results,
        "elapsed_seconds": time.monotonic()-started, "preflight_only": args.preflight,
        "level": "L0_TOOL_PREFLIGHT" if args.preflight else "L2_ISOLATED_DEFAULT_GEOMETRY_FIFO32_FIXTURE" if passed else "PARTIAL",
        "pro_dut": "NOT_TESTED", "formal_geometry_source": "MISSING", "hit_flash": "KNOWN_FAIL_DEFERRED_NOT_TESTED",
        "modelsim_gowin_hardware_invocations": 0, "git_writes": 0}
    write(out / "NIGHT_RUN_RECEIPT.json", receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("before", "after", "calls")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
