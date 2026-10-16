"""One exclusive D increment batch, suspended children in a Windows Job."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
TOOLS = Path("E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy")
TB = ROOT / "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/tb_slider_audio_coexist.sv"
JOB = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
DECODER = ROOT / "code/software/m3_40mhz_pcm_i2s_latency_20261015/check_capture.py"
AUTH = ROOT / "code/docs/test/m3_r05_functional_integration_20261015/coordinator/night_20261016/RESUME_R01/AUTHORIZATION_AND_DISPATCH.md"
OLD_NORMAL = HERE.parent / "RUN_03/positive/capture.csv"
OLD_TB = TB.parent.parent / TB.name
OLD_CHECKER = HERE.parent / "check_coexist.py"
OLD_RUNNER = HERE.parent / "run_coexist.py"
EXPECTED = {1: "UNEXPECTED_UNDERFLOW", 2: "SERIAL_PCM_LSBJ_OR_STEREO",
            3: "SERIAL_PCM_LSBJ_OR_STEREO", 4: "SERIAL_PCM_LSBJ_OR_STEREO"}
ORIGINALS = [
    "code/rtl/common/audio_defs_pkg.sv", "code/rtl/common/reset_sync.sv",
    "code/rtl/common/visual_mailbox_cdc.sv", "code/rtl/common/visual_control_bridge.sv",
    "code/rtl/common/visual_event_bridge.sv", "code/rtl/input/visualizer/visual_live_state.sv",
    "code/rtl/input/visualizer/visual_score_tracker.sv", "code/rtl/input/visualizer/visual_scene_renderer.sv",
    "code/rtl/input/m3_dual_slider_138k_candidate_20261015/dual_slider_candidate.sv",
    "code/rtl/common/sample_tick_gen.sv", "code/rtl/audio_out/pcm_frame_buffer.sv",
    "code/rtl/audio_out/i2s_tx.sv",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(paths):
    return {str(p): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in paths}


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output).resolve()
    if out.parent != HERE or not out.name.startswith("RUN_"):
        parser.error("NEW_EXCLUSIVE_D_RUN_CHILD_REQUIRED")
    candidate = identities([TB, Path(__file__).resolve(), HERE / "check_coexist.py"])
    prior = [p for p in HERE.glob("RUN_*/CONSUMED.json")]
    if len(prior) >= 3 or any(json.loads(p.read_text())["candidate"] == candidate for p in prior):
        parser.error("BATCH_EXHAUSTED_OR_SAME_SOURCE_RETRY")
    spent = sum(json.loads(p.with_name("NIGHT_RUN_RECEIPT.json").read_text()).get("simulation_seconds", 900)
                if p.with_name("NIGHT_RUN_RECEIPT.json").exists() else 900 for p in prior)
    if spent >= 900:
        parser.error("SIMULATION_BUDGET_EXHAUSTED")
    out.mkdir(exist_ok=False)
    sources = [ROOT / p for p in ORIGINALS] + [TB]
    tool_files = sorted(p for p in TOOLS.rglob("*") if p.is_file())
    inputs = sources + [JOB, DECODER, AUTH, Path(__file__).resolve(), HERE / "check_coexist.py", Path(sys.executable), OLD_NORMAL, OLD_TB, OLD_CHECKER, OLD_RUNNER]
    before = {"inputs": identities(inputs), "tools": identities(tool_files)}
    write(out / "before.json", before)
    old_seal = json.loads((HERE.parent / "MANIFEST.json").read_text())['files']
    for path in (OLD_NORMAL, OLD_TB, OLD_CHECKER, OLD_RUNNER):
        entry = old_seal[path.relative_to(ROOT).as_posix()]
        if entry['sha256'] != sha(path):
            raise RuntimeError("OLD_SEALED_INPUT_DRIFT:" + str(path))
    if TB.read_bytes() != OLD_TB.read_bytes():
        raise RuntimeError("RESUME_TB_MUST_MATCH_PASSED_NORMAL_SOURCE")
    if (HERE / "check_coexist.py").read_text().replace("parents[6]", "parents[5]") != OLD_CHECKER.read_text():
        raise RuntimeError("CHECKER_LOGIC_DRIFT")
    # Relocated DLLs may be in bin instead of lib: compare bytes by historical
    # basename and SHA. Unused old tools absent from this minimal copy are not run.
    baseline = json.loads((HERE.parent.parent / "repair_run_02/before.json").read_text())
    historical = {(Path(x["path"]).name, x["sha256"]) for x in baseline["tools"]}
    for path in tool_files:
        if (path.name, sha(path)) not in historical:
            raise RuntimeError("FROZEN_TOOL_BYTE_DRIFT:" + str(path))
    old_inputs = {Path(x["path"]).name: x["sha256"] for x in baseline["inputs"]}
    for path in sources[:9] + [JOB, Path(sys.executable)]:
        if old_inputs.get(path.name) != sha(path):
            raise RuntimeError("FROZEN_D_DEPENDENCY_DRIFT:" + str(path))
    # Bind every tracked dependency to the published baseline, including C's decoder.
    for path in sources[:-1] + [DECODER, JOB]:
        original = subprocess.check_output(["git", "show", "c12636c:" + path.relative_to(ROOT).as_posix()], cwd=ROOT)
        if hashlib.sha256(original).hexdigest() != sha(path):
            raise RuntimeError("PUBLISHED_DEPENDENCY_DRIFT:" + str(path))
    stage = out / "stage"
    stage.mkdir()
    names = []
    for i, path in enumerate(sources):
        target = stage / f"s{i:02d}.sv"
        shutil.copyfile(path, target)
        if sha(target) != sha(path):
            raise RuntimeError("STAGING_SHA_MISMATCH")
        names.append(str(target))
    write(out / "staging.json", identities(sorted(stage.iterdir())))
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC", "OS", "USERPROFILE",
            "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "HOMEDRIVE", "HOMEPATH") if k in os.environ}
    env.update(PATH=os.pathsep.join([str(TOOLS / "bin"), str(TOOLS / "lib"), str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]]),
               IVERILOG_ROOT=str(TOOLS / "lib/ivl"), TEMP=str(out), TMP=str(out), PYTHONDONTWRITEBYTECODE="1")
    write(out / "environment.json", env)
    spec = importlib.util.spec_from_file_location("frozen_owned_job", JOB)
    job_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(job_module)
    calls = []
    simulation_seconds = 0.0
    start = time.monotonic()
    preflight = {"git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                 "candidate": candidate, "authorization": str(AUTH), "old_allowances_restored": False,
                 "new_batch_group": len(prior)+1, "per_tool_seconds": 300, "group_seconds": 300,
                 "batch_simulation_seconds": 900, "prior_simulation_seconds": spent,
                 "tools_byte_bound_to_old_repair": True, "board_release_allowed": False, "expected_rejections": EXPECTED, "positive_group_rerun": False, "new_authorization_batch": "RESUME_R01"}
    write(out / "PREFLIGHT.json", preflight)
    preserved = out / "execution_sources"
    preserved.mkdir()
    for path in (Path(__file__).resolve(), HERE / "check_coexist.py", JOB, DECODER, AUTH):
        shutil.copyfile(path, preserved / path.name)

    def run(label, argv, cwd, expected=0, simulation=False):
        nonlocal simulation_seconds
        budget = min(300, 300-(time.monotonic()-start), 900-spent-simulation_seconds)
        if budget <= 0:
            raise RuntimeError("OUTER_BUDGET")
        receipt = {"argv": list(map(str, argv)), "cwd": str(cwd), "timeout_seconds": budget,
                   "process_created": False, "exit_code": None, "timeout": False,
                   "start_utc": datetime.now(timezone.utc).isoformat()}
        write(out / (label + ".launch.json"), receipt)
        began = time.monotonic()
        job = job_module.WindowsJob()
        try:
            with (out / (label + ".stdout")).open("xb") as stdout, (out / (label + ".stderr")).open("xb") as stderr:
                if not (out / "CONSUMED.json").exists():
                    write(out / "CONSUMED.json", {"candidate": candidate, "reserved_before_create": True,
                                                  "old_allowance_restored": False})
                process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, creationflags=0x00000004)
                receipt.update(process_created=True, pid=process.pid)
                job.attach_and_resume(process)
                try:
                    receipt["exit_code"] = process.wait(timeout=budget)
                except subprocess.TimeoutExpired:
                    receipt["timeout"] = True
                    job.terminate()
                    receipt["exit_code"] = process.wait(timeout=5)
        finally:
            job.close()
            receipt["elapsed_seconds"] = time.monotonic()-began
            receipt["end_utc"] = datetime.now(timezone.utc).isoformat()
            if simulation:
                simulation_seconds += receipt["elapsed_seconds"]
            receipt["stdout_sha256"] = sha(out / (label + ".stdout"))
            receipt["stderr_sha256"] = sha(out / (label + ".stderr"))
            write(out / (label + ".receipt.json"), receipt)
            calls.append(receipt)
        if receipt["timeout"] or receipt["exit_code"] != expected:
            raise RuntimeError("CHILD_FAILED:" + label)
        return (out / (label + ".stdout")).read_text(encoding="utf-8", errors="strict")

    error = None
    results = []
    try:
        run("iverilog_version", [TOOLS / "bin/iverilog.exe", "-V"], stage)
        run("vvp_version", [TOOLS / "bin/vvp.exe", "-V"], stage)
        binary = stage / "coexist.vvp"
        run("compile", [TOOLS / "bin/iverilog.exe", "-g2012", "-Wall", "-s", "tb_slider_audio_coexist", "-o", binary] + names, stage)
        for mutation, expected_diagnostic in EXPECTED.items():
            label = "positive" if mutation == 0 else f"negative_{mutation}"
            work = out / label
            work.mkdir()
            text = run(label + "_simulate", [TOOLS / "bin/vvp.exe", binary, f"+mutation={mutation}"], work, simulation=True)
            if not re.search(r"^PASS D_AUDIO_VISUAL_COEXIST checks=58$", text, re.M) or re.search(r"FATAL|REJECT|ERROR", text):
                raise RuntimeError("TB_NOT_COMPLETE:" + label)
            run(label + "_check", [sys.executable, "-B", "-X", "utf8", HERE / "check_coexist.py", work / "capture.csv", work / "visual.csv", "--output", work / "CHECK.json"], work, expected=int(mutation != 0))
            result = json.loads((work / "CHECK.json").read_text())
            if expected_diagnostic and result.get("diagnostic") != expected_diagnostic:
                raise RuntimeError("WRONG_NEGATIVE_DIAGNOSTIC:" + label + ":" + str(result))
            results.append({"name": label, "accepted": mutation == 0,
                            "expected_diagnostic": expected_diagnostic, "check_sha256": sha(work / "CHECK.json")})
    except Exception as exc:
        error = repr(exc)
    after = {"inputs": identities(inputs), "tools": identities(tool_files)}
    write(out / "after.json", after)
    result = {"passed": error is None and before == after and len(results) == 4, "error": error,
              "identity_unchanged": before == after, "results": results, "calls": calls,
              "elapsed_seconds": time.monotonic()-start, "simulation_seconds": simulation_seconds,
              "level": "L2_FOUR_RTL_BEHAVIORAL_NEGATIVE_REJECTIONS" if error is None and before == after else "PARTIAL",
              "old_99_checks_4_negatives": "REUSED_NOT_RERUN", "old_failures_preserved": True,
              "board_release_allowed": False, "r05_algorithm": "NOT_RUN", "sta": "NOT_RUN",
              "hardware": "NOT_RUN", "hit_flash": "KNOWN_FAIL_DEFERRED_NOT_TESTED", **preflight}
    write(out / "NIGHT_RUN_RECEIPT.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "calls"}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
