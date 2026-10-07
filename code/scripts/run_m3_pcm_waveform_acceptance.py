"""T058 isolated RTL runner. No CDC, audio integration, PnR or programming."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "code/tb/input/pcm_waveform_candidate"
RTL = ROOT / "code/rtl/input/pcm_waveform_candidate/pcm_waveform_candidate.sv"
sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_reference():
    spec = importlib.util.spec_from_file_location("waveform_reference", BENCH / "reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-capture", type=Path)
    parser.add_argument("--iverilog-bin", type=Path, default=Path("D:/Gowin/oss-cad-suite/bin"))
    args = parser.parse_args()
    oracle = load_reference()
    if args.check_capture:
        try:
            print(json.dumps(oracle.check_capture(args.check_capture), indent=2))
            return 0
        except (OSError, ValueError, IndexError, KeyError) as error:
            print("REJECT", error)
            return 1
    if args.output is None:
        parser.error("--output is required")
    out = args.output.resolve()
    if not out.is_relative_to((ROOT / "code/output").resolve()) or not out.name.startswith("m3_pcm_waveform_"):
        parser.error("output must be a new code/output/m3_pcm_waveform_* directory")
    if out.exists():
        parser.error("refusing to overwrite existing output")
    out.mkdir(parents=True)
    start = time.monotonic()
    receipt = {"passed": False, "runs": {}, "results": {},
               "scope": "pixel-domain L2/limited L3 only; no CDC/audio/STA/HDMI/device claim"}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    # Existing portable Icarus DLLs live in its sibling lib directory.
    env["PATH"] = str(args.iverilog_bin) + os.pathsep + str(args.iverilog_bin.parent / "lib") + os.pathsep + env.get("PATH", "")

    def run(label, command):
        remaining = min(600, 1800 - (time.monotonic() - start))
        if remaining <= 0:
            raise ValueError("TOTAL_TIMEOUT")
        try:
            process = subprocess.Popen(list(map(str, command)), cwd=out, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=remaining)
            code = process.returncode
        except subprocess.TimeoutExpired as error:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=30, check=False)
            if process.poll() is None:
                process.kill()
            stdout, stderr = process.communicate(timeout=30)
            code = 124
        for stream, data in (("stdout", stdout), ("stderr", stderr)):
            (out / (label + "." + stream + ".log")).write_bytes(data)
        receipt["runs"][label] = {"command": list(map(str, command)), "exit": code,
                                  "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                                  "stderr_sha256": hashlib.sha256(stderr).hexdigest()}
        print(label, "exit", code, flush=True)
        return code, stdout.decode("utf-8", errors="replace")

    try:
        receipt["baseline"] = oracle.baseline_identity()
        receipt["inputs"] = oracle.prepare(out)
        originals = [RTL, BENCH / "tb_waveform.sv", BENCH / "reference.py", Path(__file__)]
        receipt["source_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in originals}
        (out / "source_manifest.json").write_text(json.dumps(receipt["source_sha256"], indent=2), encoding="utf-8")
        compiler, simulator = args.iverilog_bin / "iverilog.exe", args.iverilog_bin / "vvp.exe"
        if not compiler.is_file() or not simulator.is_file():
            raise FileNotFoundError("ICARUS_TOOLS")
        if run("version", [compiler, "-V"])[0]:
            raise ValueError("TOOL_VERSION")
        for label, mutation in [("positive", None), ("signed_wrong", "signed"), ("torn_front", "torn")]:
            folder = out / label
            folder.mkdir()
            source = RTL
            if mutation:
                text = RTL.read_text(encoding="utf-8")
                anchor = "17'sd191 - $signed" if mutation == "signed" else "frame_start && pending_valid && !stream_restart"
                replacement = "17'sd191 + $signed" if mutation == "signed" else "pending_valid && !stream_restart"
                if text.count(anchor) != (2 if mutation == "signed" else 1):
                    raise ValueError("MUTATION_ANCHOR")
                source = folder / "mutant.sv"
                source.write_text(text.replace(anchor, replacement), encoding="utf-8", newline="\n")
            binary, capture = folder / "simulation.vvp", folder / "capture.txt"
            if run(label + "_compile", [compiler, "-g2012", "-s", "tb_waveform", "-o", binary,
                                        source, BENCH / "tb_waveform.sv"])[0]:
                raise ValueError("COMPILE " + label)
            code, transcript = run(label + "_simulate", [simulator, binary,
                "+vectors=" + str(out / "vectors.txt"), "+normal=" + str(out / "normal.txt"),
                "+capture=" + str(capture)])
            if code or "SIM_DONE T058" not in transcript:
                raise ValueError("SIMULATION " + label)
            code, transcript = run(label + "_check", [sys.executable, "-B", "-X", "utf8", Path(__file__),
                                                     "--check-capture", capture])
            receipt["results"][label] = {"capture_sha256": sha(capture), "checker_exit": code,
                                          "mutant_sha256": sha(source) if mutation else None}
            if mutation:
                reason = "PIXEL_REFERENCE" if mutation == "signed" else "STATE_REFERENCE"
                if code != 1 or reason not in transcript:
                    raise ValueError("MUTANT_NOT_SPECIFICALLY_REJECTED " + label + " " + transcript)
            elif code:
                raise ValueError("POSITIVE_CHECK " + transcript)
            else:
                receipt["results"][label]["summary"] = json.loads(transcript)
        positive = (out / "positive/capture.txt").read_text(encoding="ascii")
        damages = {"empty": "", "truncated": positive.rsplit("END ", 1)[0],
                   "end_count": positive.replace(" 5849 8 ", " 5848 8 "),
                   "bad_seq": positive.replace("I ", "I x", 1),
                   "garbage": positive.replace("HEADER T058 1", "HEADER T058 1\nGARBAGE")}
        receipt["damaged_captures"] = {}
        for label, content in damages.items():
            if content == positive:
                raise ValueError("DAMAGE_ANCHOR")
            path = out / (label + ".txt")
            path.write_text(content, encoding="ascii")
            code, _ = run("damage_" + label, [sys.executable, "-B", "-X", "utf8", Path(__file__), "--check-capture", path])
            if code != 1:
                raise ValueError("DAMAGED_CAPTURE_FALSE_PASS " + label)
            receipt["damaged_captures"][label] = {"exit": code, "sha256": sha(path)}
        if oracle.baseline_identity() != receipt["baseline"] or any(sha(p) != receipt["source_sha256"][p.relative_to(ROOT).as_posix()] for p in originals):
            raise ValueError("SOURCE_CHANGED_DURING_RUN")
        receipt["passed"] = True
    except (OSError, ValueError, RuntimeError, IndexError, KeyError) as error:
        receipt["error"] = str(error)
        print("FAIL", error, flush=True)
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - start
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print("EVIDENCE", out, flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
