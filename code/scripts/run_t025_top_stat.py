"""Run the official top source list; keep fresh logs even on a timeout."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
TOTAL_SECONDS = 300
JOB_PATH = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
JOB_SHA = "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_stage(top):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", top):
        raise ValueError("Invalid top name")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    stage = ROOT / "code/output" / (top + "_" + stamp + "_" + uuid.uuid4().hex[:8])
    stage.mkdir(parents=True, exist_ok=False)
    return stage


def run_bounded(command, stage, seconds):
    """No PIPEs: preserve partial output and terminate only this owned tree."""
    if seconds <= 0:
        raise TimeoutError("Budget exhausted before process launch")
    if sha(JOB_PATH) != JOB_SHA:
        raise ValueError("Owned process helper identity changed")
    spec = importlib.util.spec_from_file_location("t025_owned_job", JOB_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    job = module.WindowsJob()
    timed_out = False
    try:
        with (stage / "stdout.log").open("wb") as stdout, (stage / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(command, cwd=stage, stdout=stdout, stderr=stderr,
                                       creationflags=0x00000004)  # CREATE_SUSPENDED
            job.attach_and_resume(process)
            try:
                process.wait(timeout=max(0.001, seconds))
            except subprocess.TimeoutExpired:
                timed_out = True
                job.terminate()
                process.wait(timeout=5)
        return process.returncode, timed_out
    finally:
        # Kill-on-close covers descendants left behind by a failed parent.
        job.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", default="tb_t025_top_stat")
    parser.add_argument("--tb", default="code/tb/board/tb_t025_top_stat.sv")
    args = parser.parse_args()
    started = time.monotonic()
    stage = new_stage(args.top)
    cad = Path("D:/Gowin/oss-cad-suite")
    quote = lambda path: '"' + str(path) + '"'
    receipt = {"top": args.top, "tb": args.tb, "total_bound": TOTAL_SECONDS,
               "stage": str(stage), "passed": False, "timeout": False, "exit": None}
    result = 1
    try:
        allocator = ROOT / "code/rtl/audio/voice_allocator_4.sv"
        project = ROOT / "code/build/electronic_piano.gprj"
        sources = []
        originals = [project, allocator, ROOT / args.tb, JOB_PATH, Path(__file__)]
        for element in ET.parse(project).findall(".//File"):
            if element.attrib["type"] == "file.verilog":
                path = (project.parent / element.attrib["path"]).resolve()
                originals.append(path)
                sources.append(stage / "allocator.v" if path.name == allocator.name else path)
        sources.sort(key=lambda path: {"audio_defs_pkg.sv": 0,
                                      "sustain_control_contract_pkg.sv": 1}.get(path.name, 2))
        sources.append(ROOT / args.tb)
        originals.extend((ROOT / "code/rtl").rglob("*.svh"))
        roms = [ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem",
                ROOT / "code/model/generated/wavetables/piano_band_4x256_8191.mem"]
        originals.extend(roms)
        tools = [cad / ("bin/" + name + ".exe") for name in ("yosys", "iverilog", "vvp")]
        originals.extend(tools + [cad / "environment.bat"])
        before = {str(path): sha(path) for path in sorted(set(originals))}
        receipt["inputs_before"] = before
        ys = stage / "lower.ys"
        ys.write_text("read_slang --top voice_allocator_4 " + allocator.as_posix()
                      + "\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr "
                      + (stage / "allocator.v").as_posix() + "\n", encoding="ascii")
        commands = [quote(tools[0]) + " -Q -T -s " + quote(ys),
                    quote(tools[1]) + " -g2012 -s " + args.top
                    + " -I " + quote(ROOT / "code/rtl/board")
                    + " -I " + quote(ROOT / "code/rtl/common")
                    + " -o " + quote(stage / "tb.vvp") + " " + " ".join(map(quote, sources)),
                    quote(tools[2]) + " " + quote(stage / "tb.vvp") + " "
                    + quote("+VELOCITY_ROM_PATH=" + str(roms[0])) + " "
                    + quote("+WAVETABLE_PATH=" + str(roms[1]))]
        receipt["commands"] = commands
        batch = "@echo off\r\ncall " + quote(cad / "environment.bat") + " >nul\r\nif errorlevel 1 exit /b 1\r\n"
        for name, command in zip(("lower", "compile", "simulate"), commands):
            batch += "echo STAGE " + name + "\r\n" + command + "\r\nif errorlevel 1 exit /b 1\r\n"
        bat = stage / "run.bat"
        bat.write_bytes((batch + "exit /b 0\r\n").encode("ascii"))
        receipt["exit"], receipt["timeout"] = run_bounded(
            ["cmd.exe", "/c", str(bat)], stage,
            TOTAL_SECONDS - (time.monotonic() - started))
        stdout = (stage / "stdout.log").read_text(encoding="utf-8", errors="replace")
        stderr = (stage / "stderr.log").read_text(encoding="utf-8", errors="replace")
        (stage / "run.log").write_text(stdout + stderr, encoding="utf-8")
        after = {path: sha(Path(path)) for path in before}
        receipt["inputs_after"] = after
        passed = bool(("PASS " + args.top) in stdout or re.search(r">>>.*PASS", stdout))
        failed = bool(re.search(r"FATAL|\[FAIL\]|>>>.*FAIL", stdout + stderr))
        receipt["passed"] = (receipt["exit"] == 0 and not receipt["timeout"]
                             and passed and not failed and before == after
                             and time.monotonic() - started <= TOTAL_SECONDS)
        for line in stdout.splitlines():
            if any(word in line for word in ("STAGE ", "PASS", "FATAL", "[FAIL]", "DEBUG")):
                print(line)
        if not receipt["passed"]:
            print((stdout + stderr)[-2000:])
        result = 0 if receipt["passed"] else 1
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print("[FAIL] " + receipt["error"])
    finally:
        receipt["seconds"] = time.monotonic() - started
        if receipt["seconds"] > TOTAL_SECONDS:
            receipt["passed"] = False
            result = 1
        receipt["runner_exit"] = result
        (stage / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print("Receipt:", stage / "receipt.json")
        print("Log:", stage / "run.log")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
