"""Bounded, public-interface-only joint acceptance of the frozen T058 pair."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import checker

HERE = Path(__file__).resolve().parent
ROOT = checker.ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, name, output, environment, deadline, steps):
    start = time.monotonic()
    limit = min(600, deadline - start)
    if limit <= 0:
        raise RuntimeError("TOTAL_DEADLINE")
    stdout = output / (name + ".stdout.log")
    stderr = output / (name + ".stderr.log")
    with stdout.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen(command, cwd=ROOT, env=environment,
                                   stdout=out, stderr=err)
        timed_out = False
        try:
            code = process.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=15, check=False)
            process.wait(timeout=15)
            code = 124
    record = dict(name=name, command=command, exit_code=code,
                  elapsed_seconds=round(time.monotonic() - start, 3),
                  timed_out=timed_out, stdout_sha256=digest(stdout),
                  stderr_sha256=digest(stderr))
    steps.append(record)
    print(json.dumps(record), flush=True)
    return code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iverilog", default="D:/Gowin/oss-cad-suite/bin/iverilog.exe")
    parser.add_argument("--vvp", default="D:/Gowin/oss-cad-suite/bin/vvp.exe")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "code/output" / (
        "m3_night_wave_" + time.strftime("%Y%m%d_%H%M%S"))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start + 1800
    environment = os.environ.copy()
    binary = Path(args.iverilog).parent
    environment["PATH"] = str(binary) + os.pathsep + str(binary.parent / "lib") + os.pathsep + environment["PATH"]
    steps = []
    receipt = dict(task="T058 night public joint blackbox", output=str(output),
                   steps=steps, passed=False, findings=[],
                   boundary="Digital simulation only; no physical CDC, HDMI, audio isolation, STA or PnR claim")
    try:
        receipt["baseline"] = checker.check_baseline()
        info = checker.prepare(output)
        receipt["stimulus"] = info
        sources = [
            ROOT / "code/rtl/common/reset_sync.sv",
            ROOT / "code/rtl/common/visual_mailbox_cdc.sv",
            ROOT / "code/rtl/common/pcm_waveform_observer_candidate/pcm_frame_observer.sv",
            ROOT / "code/rtl/common/pcm_waveform_observer_candidate/pcm_waveform_observer_bridge.sv",
            ROOT / "code/rtl/input/pcm_waveform_candidate/pcm_waveform_candidate.sv",
            HERE / "tb_joint.sv",
        ]
        execute([args.iverilog, "-V"], "tool_iverilog", output, environment, deadline, steps)
        receipt["sources_sha256"] = {str(p.relative_to(ROOT)): digest(p) for p in sources}
        for case, mutation in (("normal", 0), ("diagnostic", 0), ("stress", 0),
                               ("stress", 1), ("stress", 2)):
            name = case + "_m" + str(mutation)
            spec = info[case]
            executable = output / (name + ".vvp")
            capture = output / (name + ".capture")
            command = [args.iverilog, "-g2012", "-s", "tb_joint",
                       "-Ptb_joint.MUTATION=" + str(mutation),
                       "-Ptb_joint.FIRST_SEQ=" + str(spec.get("first_seq", 0)),
                       "-o", str(executable)] + [str(p) for p in sources]
            code = execute(command, name + "_compile", output, environment, deadline, steps)
            if code:
                raise RuntimeError(name + " COMPILE_FAILED")
            code = execute([args.vvp, str(executable), "+MODE=" + case,
                            "+CAPTURE=" + capture.as_posix(),
                            "+VECTORS=" + (output / (case + ".txt")).as_posix(),
                            "+COUNT=" + str(spec["count"]),
                            "+FRAMES=" + str(spec["frames"])],
                           name + "_run", output, environment, deadline, steps)
            if code:
                receipt["findings"].append(name + " SIMULATION_FAILED")
                continue
            code = execute([sys.executable, str(HERE / "checker.py"), str(capture),
                            "--vectors", str(output / (case + ".txt"))],
                           name + "_check", output, environment, deadline, steps)
            result = (output / (name + "_check.stdout.log")).read_text(encoding="utf-8").strip()
            if not mutation and code == 0:
                receipt.setdefault("positive_results", []).append(json.loads(result.split(" ", 1)[1]))
            elif mutation and code == 1 and any(word in result for word in ("PIXEL_REFERENCE", "STATE_REFERENCE")):
                receipt.setdefault("mutants_rejected", []).append(dict(name=name, reason=result))
            else:
                receipt["findings"].append(dict(case=name, checker_exit=code, result=result))
        normal = output / "normal_m0.capture"
        if normal.exists():
            lines = normal.read_text(encoding="ascii").splitlines()
            corruptions = {"empty": [], "truncated": lines[:-1]}
            bad = lines.copy()
            end = bad[-1].split()
            end[2] = str(int(end[2]) + 1)
            bad[-1] = " ".join(end)
            corruptions["wrong_count"] = bad
            bad = lines.copy()
            position = next(i for i, line in enumerate(bad) if line.startswith("L "))
            row = bad[position].split()
            row[-1] = str(int(row[-1]) ^ 1)
            bad[position] = " ".join(row)
            corruptions["wrong_pixel"] = bad
            for name, content in corruptions.items():
                capture = output / ("corrupt_" + name + ".capture")
                capture.write_text("\n".join(content) + ("\n" if content else ""), encoding="ascii")
                code = execute([sys.executable, str(HERE / "checker.py"), str(capture),
                                "--vectors", str(output / "normal.txt")],
                               "corrupt_" + name + "_check", output, environment, deadline, steps)
                if code != 1:
                    receipt["findings"].append("CORRUPTION_NOT_REJECTED " + name)
        checker.check_baseline()
        receipt["passed"] = not receipt["findings"] and len(receipt.get("positive_results", [])) == 3 and len(receipt.get("mutants_rejected", [])) == 2
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        receipt["findings"].append(str(exc))
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - start, 3)
        receipt["artifacts_sha256"] = {p.name: digest(p) for p in output.iterdir() if p.is_file()}
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(("PASS" if receipt["passed"] else "FAIL") + " " + str(output), flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
