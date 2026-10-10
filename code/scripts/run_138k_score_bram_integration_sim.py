"""Bounded exact RAM fulltop simulation; never Gowin, PnR or programming."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/scripts"))
import prepare_138k_score_bram_integration as prepare

OLD_TB = ROOT / "code/tb/board/score_receive_integration_20261009"
TB = ROOT / "code/tb/board/score_bram_integration_20261010"
SPEC = importlib.util.spec_from_file_location("frozen_score_vectors", OLD_TB / "vectors.py")
vectors = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vectors)
CAD = Path("D:/Gowin/oss-cad-suite")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def syntax_copy(name, raw):
    text = raw.decode("utf-8")
    text = re.sub(r"\bint unsigned\b", "integer", text)
    text = re.sub(r'`include "[^"]*/(sine_table\.svh|sustain_controller_ports\.svh)"',
                  r'`include "\1"', text)
    if name == "voice_allocator_4.sv":
        fields = {"note_active": 1, "in_release": 1, "source": 4,
                  "channel": 4, "note": 8, "age": 2}
        anchor = "    voice_slot_t slots [0:3];"
        if text.count(anchor) != 1:
            raise ValueError("ALLOCATOR_SYNTAX_ANCHOR")
        declarations = "\n".join("    logic " + (f"[{width-1}:0] " if width > 1 else "")
                                  + "sim_slot_" + field + " [0:3];"
                                  for field, width in fields.items())
        text = text.replace(anchor, declarations).replace("                slots[i] <= '0;",
            "\n".join("                sim_slot_" + field + "[i] <= '0;" for field in fields), 1)
        for field in fields:
            text = re.sub(r"slots\[([^\]]+)\]\." + field + r"\b",
                          r"sim_slot_" + field + r"[\1]", text)
    return text.encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--negative", choices=("audio_isolation", "video_isolation", "response_command"))
    args = parser.parse_args()
    project = args.project.resolve()
    frozen = prepare.validate(project)
    output = args.output.resolve()
    output.relative_to((ROOT / "code/output").resolve())
    if output == (ROOT / "code/output").resolve() or not str(output).isascii():
        raise ValueError("ASCII_UNIQUE_OUTPUT_REQUIRED")
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    env["PATH"] = os.pathsep.join((str(CAD / "bin"), str(CAD / "lib"), env.get("PATH", "")))
    record = {"passed": False, "date": "2026-10-10", "steps": {}, "negative": args.negative,
              "scope": "exact RAM62/53 fulltop short13case logical equivalence; nominal PLL/DVI stub",
              "physical_STA_passed": False, "programmed": False, "source_SHA256": {},
              "adaptations": {}, "mutation": None, "global_limit_seconds": 1800,
              "frozen_receipt_SHA256": sha(project / "frozen_receipt.json"),
              "prepare_script_SHA256": frozen["prepare_script_sha256"]}

    def run(label, command, limit):
        remaining = 1800 - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("GLOBAL_TIMEOUT")
        command = list(map(str, command))
        start = time.monotonic()
        with (output / (label + ".stdout.log")).open("xb") as stdout, \
                (output / (label + ".stderr.log")).open("xb") as stderr:
            process = subprocess.Popen(command, cwd=output, env=env, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            timed_out = False
            try:
                code = process.wait(timeout=min(limit, remaining))
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=30)
                else:
                    process.kill()
                process.wait(timeout=30)
                code = process.returncode
        info = {"command": command, "exit_code": code, "timed_out": timed_out,
                "limit": min(limit, remaining), "seconds": round(time.monotonic() - start, 3),
                "stdout_SHA256": sha(output / (label + ".stdout.log")),
                "stderr_SHA256": sha(output / (label + ".stderr.log"))}
        record["steps"][label] = info
        print(label, code, info["seconds"], flush=True)
        if timed_out:
            raise ValueError(label + "_TIMEOUT")
        return code, (output / (label + ".stdout.log")).read_bytes() + \
            (output / (label + ".stderr.log")).read_bytes()

    def copy_source(name, raw):
        adapted = syntax_copy(name, raw)
        path = sources / name
        path.write_bytes(adapted)
        record["adaptations"][name] = {"original_SHA256": hashlib.sha256(raw).hexdigest(),
                                      "adapted_SHA256": sha(path),
                                      "scope": "Icarus int qualifier/struct fields/include syntax only"}
        return path

    def mutate(name, old, new):
        path = sources / name
        raw = path.read_bytes()
        if raw.count(old) != 1:
            raise ValueError("MUTATION_ANCHOR_NOT_UNIQUE")
        path.write_bytes(raw.replace(old, new, 1))
        record["mutation"] = {"file": name, "before_SHA256": hashlib.sha256(raw).hexdigest(),
                              "after_SHA256": sha(path), "only_simulation_copy": True}

    code = 1
    try:
        oracle = vectors.build(output / "vectors")
        record["oracle_SHA256"] = sha(output / "vectors/oracle.json")
        for folder in (project / "inputs/sources", project / "inputs/include"):
            for path in folder.iterdir():
                if path.is_file():
                    record["source_SHA256"][str(path)] = sha(path)
                    if path.name not in ("DVI_TX_Top.v", "TMDS_PLL_800_600_60.v"):
                        copy_source(path.name, path.read_bytes())
        parent_data = prepare.base.parent.inputs(project)[0]
        original = parent_data["sources/audio_visual_coexistence_top.sv"]
        reference = original.replace(b"module audio_visual_coexistence_top", b"module reference_audio_visual_top")
        reference = reference.replace(b"AUDIO_VISUAL_COEXISTENCE_TOP_SV", b"REFERENCE_AUDIO_VISUAL_TOP_SV")
        copy_source("reference_audio_visual_top.sv", reference)
        record["reference_frozen_v3_top_SHA256"] = hashlib.sha256(original).hexdigest()
        tree = ET.parse(project / prepare.PROJECT).getroot()
        if len(tree.find("FileList")) != 53:
            raise ValueError("EXACT53_PROJECT_FILES")
        names = [Path(node.attrib["path"]).name for node in tree.find("FileList")
                 if node.attrib["type"] == "file.verilog"
                 and Path(node.attrib["path"]).name not in ("DVI_TX_Top.v", "TMDS_PLL_800_600_60.v")]
        units = [sources / name for name in names] + [sources / "reference_audio_visual_top.sv"]
        if args.negative == "audio_isolation":
            mutate("audio_visual_coexistence_top.sv", b".pcm_left  (buffered_left)",
                   b".pcm_left  (buffered_left ^ 24'sh000100)")
        elif args.negative == "video_isolation":
            mutate("audio_visual_display_probe.sv", b"dvi_hs<=hs_d2;", b"dvi_hs<=hs_d1;")
        elif args.negative == "response_command":
            mutate("score_transfer_bram_candidate.sv", b"buffer[12]=command;",
                   b"buffer[12]=command ^ 8'h01;")
        bench = TB / "tb_score_bram_integration.sv"
        clock = ROOT / "code/tb/board/t058_waveform_integration_20261008/clock_plan_sim.v"
        stub = ROOT / "code/rtl/138K_try/clock_trials_20261005/dvi_sim_stub.v"
        checker = TB / "check_capture.py"
        tools = (CAD / "bin/iverilog.exe", CAD / "bin/vvp.exe")
        inputs = (bench, clock, stub, checker, OLD_TB / "vectors.py", OLD_TB / "check_capture.py",
                  Path(__file__), Path(prepare.__file__), *tools)
        record["source_SHA256"].update({str(path.resolve()): sha(path) for path in inputs})
        if run("tool_version", [tools[0], "-B", CAD / "lib/ivl", "-V"], 30)[0]:
            raise ValueError("TOOL_VERSION_FAILED")
        command = [tools[0], "-B", CAD / "lib/ivl", "-g2012", "-I", sources,
                   "-s", "tb_score_bram_integration", "-o", output / "sim.vvp"]
        if args.negative == "response_command":
            command += ["-Ptb_score_bram_integration.NEGATIVE_STOP=1"]
        command += units + [clock, stub, bench]
        if run("compile", command, 90)[0]:
            raise ValueError("COMPILE_FAILED")
        compiled = {str(path.resolve()): sha(path) for path in (*units, clock, stub, bench)}
        record["compiled_sources_SHA256"] = compiled
        sim_exit, sim_log = run("simulate", [tools[1], output / "sim.vvp",
            "+PLAN=" + str(output / "vectors/plan.txt"), "+CAPTURE=" + str(output / "capture.txt")], 1200)
        if args.negative in ("audio_isolation", "video_isolation"):
            reason = ("UPLOAD_AUDIO_OR_STAT_CHANGED" if args.negative == "audio_isolation"
                      else "UPLOAD_WAVE_OR_VIDEO_CHANGED")
            if sim_exit != 1 or reason.encode("ascii") not in sim_log:
                raise ValueError("SPECIFIED_BEHAVIOR_REJECTION_MISSING")
            record["specified_negative"] = {"compile_exit": 0, "actual_sim_exit": sim_exit, "reason": reason}
        else:
            if sim_exit:
                raise ValueError("SIMULATE_FAILED")
            marker = (b"NEGATIVE_FIRST_REPLY_CAPTURED" if args.negative else b"HARNESS_COMPLETE_SCORE_AUDIO_EQ")
            if marker not in sim_log:
                raise ValueError("EXACT_COMPLETION_MARKER_MISSING")
            check_command = [sys.executable, "-B", "-X", "utf8", checker,
                             "--capture", output / "capture.txt", "--oracle", output / "vectors/oracle.json"]
            if args.negative:
                check_command += ["--negative"]
            check_exit, check_log = run("check_capture", check_command, 30)
            if args.negative:
                reason = "RESPONSE_BYTES_COMMAND_METADATA_OR_EVENT"
                if check_exit != 1 or reason.encode("ascii") not in check_log:
                    raise ValueError("SPECIFIED_WIRE_REJECTION_MISSING")
                record["specified_negative"] = {"compile_exit": 0, "actual_sim_exit": 0,
                                                "actual_checker_exit": check_exit, "reason": reason}
            else:
                if check_exit or not check_log.startswith(b"PASS "):
                    raise ValueError("PUBLIC_WIRE_CHECK_FAILED")
                record["result"] = json.loads(check_log[len(b"PASS "):].decode("utf-8"))
        if any(sha(path) != value for path, value in record["source_SHA256"].items()):
            raise ValueError("SOURCE_CHANGED_DURING_RUN")
        if any(sha(path) != value for path, value in compiled.items()):
            raise ValueError("COMPILED_SOURCE_CHANGED_DURING_RUN")
        prepare.validate(project)
        record["passed"] = True
        code = 0
    except Exception as error:
        record["error"] = type(error).__name__ + ": " + str(error)
        print(record["error"], flush=True)
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    capture = output / "capture.txt"
    record["capture_SHA256"] = sha(capture) if capture.exists() else None
    record["output_SHA256"] = {str(path.relative_to(output)): sha(path)
                               for path in output.rglob("*") if path.is_file()}
    if record["elapsed_seconds"] > 1800:
        record.update(passed=False, error="GLOBAL_TIME_LIMIT_EXCEEDED")
        code = 1
    (output / "receipt.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    print("RAM_FULLTOP", record["passed"], record["elapsed_seconds"], flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
