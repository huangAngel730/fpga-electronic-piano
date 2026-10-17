"""Six bounded E3 implementation rounds shared with any helper agents."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from common import DOCS, HERE, OLD_PY, ROOT, RTL, TB, TOOL, identity, save, sources


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--resume-checks-from", type=int)
    ap.add_argument("--reuse-inputs-from", type=int)
    args = ap.parse_args()
    assert 1 <= args.round <= 6
    assert not (args.resume_checks_from and args.reuse_inputs_from)
    out = DOCS / f"ROUND_{args.round:02}"
    out.mkdir(exist_ok=False)
    preflight = json.loads((DOCS / "PREFLIGHT/PREFLIGHT.json").read_text(encoding="utf-8"))
    assert all(identity(Path(i["path"])) == i for i in preflight["runtime"]), "RUNTIME_CHANGED_BEFORE_LAUNCH"
    before = [identity(p) for p in sources()]
    snapshot = out / "sources"
    snapshot.mkdir()
    for item in before:
        p = Path(item["path"])
        dest = snapshot / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
        assert identity(dest)["sha256"] == item["sha256"]
    launched = datetime.now(timezone.utc).isoformat()
    save(out / "LAUNCH.json", {"round": args.round, "source_before": before, "runtime": preflight["runtime"],
         "machine": platform.node(), "python": sys.version, "started_utc": launched,
         "module_group_limit_s": 600, "python_step_limit_s": 90,
         "resume_checks_from": args.resume_checks_from, "reuse_inputs_from": args.reuse_inputs_from,
         "max_rounds": 6, "shared_with_subagents": True})
    begun = time.monotonic()
    steps = []
    receipt = {"round": args.round, "status": "FAIL", "source_before": before, "steps": steps,
               "module_group_limit_s": 600, "python_step_limit_s": 90, "started_utc": launched,
               "EDA_calls": 0, "hardware_calls": 0, "Git_writes": 0, "board_release_allowed": False}
    # Match the repository's proven OSS runtime closure. Child ivl.exe lives
    # in lib/ivl, so a successful driver -V does not qualify inherited PATH DLLs.
    temp = out / "tmp"
    temp.mkdir()
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC", "OS", "PROCESSOR_ARCHITECTURE",
                                    "NUMBER_OF_PROCESSORS", "USERPROFILE", "HOMEDRIVE", "HOMEPATH") if k in os.environ}
    env.update(PATH=os.pathsep.join((str(TOOL / "bin"), str(TOOL / "lib"),
                                    str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"])),
               IVERILOG_ROOT=str(TOOL / "lib/ivl"), TEMP=str(temp), TMP=str(temp))
    save(out / "ENVIRONMENT.json", env)
    receipt["environment"] = identity(out / "ENVIRONMENT.json")

    def step(label, argv, expected=0, python=False, cwd=ROOT):
        deadline = datetime(2026, 10, 16, 21, 21, tzinfo=timezone.utc)
        remaining = min(600 - (time.monotonic() - begun), (deadline - datetime.now(timezone.utc)).total_seconds())
        assert remaining > 0, "GROUP_OR_NIGHT_DEADLINE"
        limit = min(90 if python else 600, remaining)
        record = {"label": label, "argv": argv, "cwd": str(cwd), "expected_exit": expected,
                  "limit_s": limit, "started_utc": datetime.now(timezone.utc).isoformat(), "timeout": False}
        start = time.monotonic()
        with (out / (label + ".stdout.bin")).open("xb") as stdout, (out / (label + ".stderr.bin")).open("xb") as stderr:
            child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
            if not (out / "CONSUMED.json").exists():
                save(out / "CONSUMED.json", {"round": args.round, "first_pid": child.pid,
                     "created_utc": datetime.now(timezone.utc).isoformat(), "launch": identity(out / "LAUNCH.json"),
                     "owner": "E3_SIX_ROUNDS_SHARED"})
            try:
                record["exit_code"] = child.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                record["timeout"] = True
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, check=False)
                child.wait(timeout=5)
                record["exit_code"] = 124
        record.update(seconds=time.monotonic() - start, ended_utc=datetime.now(timezone.utc).isoformat(),
                      stdout=identity(out / (label + ".stdout.bin")), stderr=identity(out / (label + ".stderr.bin")))
        steps.append(record)
        save(out / (label + ".RECEIPT.json"), record)
        assert not record["timeout"] and record["exit_code"] == expected, "UNEXPECTED_STEP_EXIT:" + label

    py = [sys.executable, "-B", "-X", "utf8"]
    inputs = out / "inputs"
    capture = out / "CAPTURE.txt"
    try:
        compact = out / "compile_sources"
        compact.mkdir()
        sv = []
        compile_map = []
        for n, p in enumerate([*RTL, TB]):
            short = compact / f"{n:02}_{p.name}"
            short.write_bytes((snapshot / p.relative_to(ROOT)).read_bytes())
            assert identity(short)["sha256"] == identity(p)["sha256"]
            sv.append(short.relative_to(out).as_posix())
            compile_map.append({"source": identity(p), "copy": identity(short),
                                "original_absolute_path_length": len(str(snapshot / p.relative_to(ROOT)))})
        save(out / "COMPILE_SOURCES.json", compile_map)
        if args.resume_checks_from:
            prior = DOCS / f"ROUND_{args.resume_checks_from:02}"
            old = json.loads((prior / "RUN_RECEIPT.json").read_text(encoding="utf-8"))
            old_source = {i["path"]: i for i in old["source_before"]}
            for item in before:
                # Checker/runner-only repair may reuse the exact old RTL capture.
                if Path(item["path"]).name not in {"check_e3.py", "run_round.py"}:
                    assert old_source[item["path"]] == item, "REUSE_SOURCE_CHANGED"
            assert old["source_before"] == old["source_after"]
            assert any(s["label"] == "03_simulate" and s["exit_code"] == 0 for s in old["steps"])
            inputs, capture = prior / "inputs", prior / "CAPTURE.txt"
            receipt["reused_capture"] = identity(capture)
            receipt["reused_input_files"] = [identity(p) for p in sorted(inputs.iterdir()) if p.is_file()]
        else:
            if args.reuse_inputs_from:
                prior = DOCS / f"ROUND_{args.reuse_inputs_from:02}"
                old = json.loads((prior / "RUN_RECEIPT.json").read_text(encoding="utf-8"))
                assert old["source_before"] == old["source_after"]
                assert any(s["label"] == "01_build_inputs" and s["exit_code"] == 0 for s in old["steps"])
                old_source = {i["path"]: i for i in old["source_before"]}
                for p in [*OLD_PY, HERE / "build_inputs.py", HERE / "common.py"]:
                    assert identity(p) == old_source[str(p)], "REUSED_INPUT_SOURCE_CHANGED"
                inputs = prior / "inputs"
                receipt["reused_input_files"] = [identity(p) for p in sorted(inputs.iterdir()) if p.is_file()]
            else:
                step("01_build_inputs", py + [str(HERE / "build_inputs.py"), "--output", str(inputs)], python=True)
            step("02_compile", [str(TOOL / "bin/iverilog.exe"), "-g2012", "-s", "tb_e3_file_uart",
                                "-o", "candidate.vvp", *sv], cwd=out)
            step("03_simulate", [str(TOOL / "bin/vvp.exe"), str(out / "candidate.vvp"),
                                 "+PLAN=" + str(inputs / "PLAN.txt"), "+CAPTURE=" + str(capture)])
        input_before = [identity(p) for p in sorted(inputs.iterdir()) if p.is_file()]
        capture_before = identity(capture)
        step("04_check", py + [str(HERE / "check_e3.py"), "--capture", str(capture),
                                "--inputs", str(inputs), "--output", str(out / "checked")], python=True)
        step("05_frozen_strict_trace", py + [str(OLD_PY[4]), "--trace", str(out / "checked/CLEAN_INTERLEAVED.jsonl"),
             "--expected-json", str(inputs / "score.json"), "--session", "1510", "--mode", "strict",
             "--output", str(out / "frozen_strict_trace")], python=True)
        # Real behavior fault: original signed mutant bypasses entire-score CRC.
        # Same real MIDI bytes and bad expected score CRC must now be rejected by checker.
        step("06_compile_crc_mutant", [str(TOOL / "bin/iverilog.exe"), "-g2012", "-DMUTANT_SKIP_SCORE_CRC",
             "-s", "tb_e3_file_uart", "-o", "crc_mutant.vvp", *sv], cwd=out)
        step("07_simulate_crc_mutant", [str(TOOL / "bin/vvp.exe"), str(out / "crc_mutant.vvp"),
             "+PLAN=" + str(inputs / "PLAN.txt"), "+CAPTURE=" + str(out / "MUTANT_CAPTURE.txt")])
        step("08_check_crc_mutant", py + [str(HERE / "check_e3.py"), "--capture", str(out / "MUTANT_CAPTURE.txt"),
             "--inputs", str(inputs), "--output", str(out / "mutant_checked")], expected=1, python=True)
        bad = json.loads((out / "mutant_checked/RESULT.json").read_text(encoding="utf-8"))
        assert bad["first_difference"]["code"] == "RESPONSE_ERROR", "MUTANT_WRONG_FIRST_DIFFERENCE"
        assert bad["first_difference"]["expected"] == [3, 9] and bad["first_difference"]["actual"] == [3, 0]
        assert input_before == [identity(p) for p in sorted(inputs.iterdir()) if p.is_file()], "INPUT_DRIFT"
        assert capture_before == identity(capture), "REUSED_CAPTURE_DRIFT"
        receipt["inputs"] = input_before
        receipt["positive_capture"] = capture_before
        receipt["mutant_capture"] = identity(out / "MUTANT_CAPTURE.txt")
        receipt["status"] = "PASS_ISOLATED_REAL_FILE_UART_RAM__HARDWARE_PENDING"
    except Exception as exc:
        receipt["failure"] = f"{type(exc).__name__}: {exc}"
    receipt["source_after"] = [identity(p) for p in sources()]
    receipt["runtime_after_same"] = all(identity(Path(i["path"])) == i for i in preflight["runtime"])
    if before != receipt["source_after"] or not receipt["runtime_after_same"]:
        receipt.update(status="FAIL", failure="SOURCE_OR_RUNTIME_DRIFT")
    receipt.update(seconds=time.monotonic() - begun, ended_utc=datetime.now(timezone.utc).isoformat(),
                   exit_code=0 if receipt["status"].startswith("PASS") else 1)
    save(out / "RUN_RECEIPT.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("round", "status", "exit_code", "seconds")}, ensure_ascii=True))
    if "failure" in receipt:
        print(receipt["failure"])
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
