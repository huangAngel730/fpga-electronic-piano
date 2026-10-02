"""Reproduce the M2 isolated ADSR pipeline candidate, never edit formal RTL.

A frozen baseline hash + reviewed unified patch produce output-only modules.
Default runs original ADSR gates, model traces, all-velocity contract and negatives.
--subsystems also runs original bank/V1/CC64/capability suites with only two source
replacements in their isolated copies. This is not deployment or board acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")
PATCH = ROOT / "code/tb/audio/adsr_pipeline_isolated_candidate.patch"
BASELINE = ROOT / "code/tb/audio/adsr_pipeline_candidate_baseline.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_copies(folder):
    metadata = json.loads(BASELINE.read_text(encoding="utf-8"))
    lines = PATCH.read_text(encoding="utf-8").splitlines(keepends=True)
    index = 0
    produced = {}
    while index < len(lines):
        if not lines[index].startswith("--- a/"):
            raise ValueError("unexpected patch header")
        path = lines[index][6:].strip()
        if path not in metadata["files"]:
            raise ValueError("patch outside reviewed scope")
        original = ROOT / path
        if digest(original) != metadata["files"][path]:
            raise ValueError("formal source changed; review new baseline: " + path)
        if lines[index + 1].strip() != "+++ b/" + path:
            raise ValueError("mismatching patch target")
        index += 2
        before = original.read_text(encoding="utf-8").splitlines(keepends=True)
        output, cursor = [], 0
        while index < len(lines) and lines[index].startswith("@@ "):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[index])
            if not match:
                raise ValueError("bad hunk")
            start = int(match.group(1)) - 1
            if start < cursor:
                raise ValueError("overlapping hunks")
            output.extend(before[cursor:start]); cursor = start; index += 1
            while index < len(lines) and not lines[index].startswith(("@@ ", "--- a/")):
                line = lines[index]
                if line[:1] in (" ", "-"):
                    if cursor >= len(before) or before[cursor] != line[1:]:
                        raise ValueError("patch does not exactly match " + path)
                    cursor += 1
                if line[:1] in (" ", "+"):
                    output.append(line[1:])
                if line[:1] not in (" ", "+", "-"):
                    raise ValueError("unknown patch line")
                index += 1
        output.extend(before[cursor:])
        dest = folder / original.name
        dest.write_text("".join(output), encoding="utf-8", newline="\n")
        produced[path] = {"output": str(dest), "sha256": digest(dest)}
    reference = folder / "adsr_reference.sv"
    reference.write_text((ROOT / "code/rtl/audio/adsr_piano_envelope.sv").read_text(encoding="utf-8").replace(
        "module adsr_piano_envelope", "module adsr_reference", 1), encoding="utf-8", newline="\n")
    return produced, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--subsystems", action="store_true")
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.relative_to(ROOT / "code/output")
    if folder.exists():
        parser.error("output already exists; preserve old evidence")
    folder.mkdir(parents=True)
    sources, reference = patch_copies(folder)
    candidate = folder / "adsr_piano_envelope.sv"
    bank = folder / "polyphonic_envelope_bank.sv"
    facts = {"formal_modified": False, "formal_accepted": False,
             "sources": sources, "runs": {}, "physical_STA_done_by_this_entry": False}
    env = dict(os.environ)
    env["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + env["PATH"]
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(name, command, expected_success=True, timeout=180):
        log = folder / (name + ".log")
        with log.open("w", encoding="utf-8", newline="\n") as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout, check=False)
        text = log.read_text(encoding="utf-8", errors="replace")
        facts["runs"][name] = {"command": list(map(str, command)), "exit": result.returncode,
                                "expected_success": expected_success, "log_sha256": digest(log)}
        if (result.returncode == 0) != expected_success:
            print(text[-4000:])
            raise RuntimeError("unexpected verdict: " + name)
        print(name, "exit", result.returncode)
        return text

    if not args.generate_only:
        rom = ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem"
        for top, bench in (("tb_adsr_piano", ROOT / "code/tb/audio/tb_adsr_piano.sv"),
                           ("tb_adsr_model_trace", ROOT / "code/tb/audio/tb_adsr_piano.sv"),
                           ("tb_adsr_zero_slope", ROOT / "code/tb/audio/tb_adsr_zero_slope.sv"),
                           ("tb_adsr_pipeline_contract", ROOT / "code/tb/audio/tb_adsr_pipeline_contract.sv")):
            binary = folder / (top + ".vvp")
            extras = [reference] if top == "tb_adsr_pipeline_contract" else []
            run(top + "_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", top,
                                   "-o", str(binary), str(candidate), *map(str, extras), str(bench)])
            trace = folder / (top + ".trace")
            log = run(top, [str(CAD / "bin/vvp.exe"), str(binary), "+VELOCITY_ROM_PATH=" + str(rom),
                            "+TRACE=" + str(trace)])
            if "PASS" not in log or "FATAL" in log:
                raise RuntimeError("missing self-check PASS: " + top)
            if top in ("tb_adsr_model_trace", "tb_adsr_zero_slope"):
                run(top + "_model", [sys.executable, "-X", "utf8", str(ROOT / "code/tb/audio/check_adsr_model_trace.py"),
                                      str(trace), "--min-samples", "2800" if top.endswith("zero_slope") else "26000"])
        for label in ("missing", "short"):
            rom_path = folder / (label + ".mem")
            if label == "short": rom_path.write_text("0000\n", encoding="ascii")
            run(label + "_ROM", [str(CAD / "bin/vvp.exe"), str(folder / "tb_adsr_piano.vvp"),
                                  "+VELOCITY_ROM_PATH=" + str(rom_path)], False, 10)
        trace = folder / "tb_adsr_model_trace.trace"
        lines = trace.read_text(encoding="utf-8").splitlines()
        target = next(i for i, line in enumerate(lines) if line.startswith("S "))
        fields = lines[target].split(); fields[1] = str(int(fields[1]) + 10)
        lines[target] = " ".join(fields)
        bad = folder / "bad_model.trace"; bad.write_text("\n".join(lines) + "\n", encoding="utf-8")
        run("bad_model", [sys.executable, "-X", "utf8", str(ROOT / "code/tb/audio/check_adsr_model_trace.py"), str(bad)], False)
        if args.subsystems:
            for name in ("run_t024_envelope_bank.py", "run_piano_v1_audio_core.py",
                         "run_sustain_audio_integration.py", "run_piano_v1_audio_capabilities.py"):
                text = (ROOT / "code/scripts" / name).read_text(encoding="utf-8")
                text = text.replace("root=Path(__file__).resolve().parents[2];stage=root/",
                                    f"root=Path({ROOT.as_posix()!r});stage=root/")
                stage = (folder / (Path(name).stem + "_run")).as_posix()
                text = re.sub(r"stage=root/'code/output/[^']+'", lambda match: f"stage=Path({stage!r})", text, count=1)
                text = text.replace("root/'code/rtl/audio/adsr_piano_envelope.sv'", f"Path({candidate.as_posix()!r})")
                text = text.replace("root/'code/rtl/board/polyphonic_envelope_bank.sv'", f"Path({bank.as_posix()!r})")
                if name == "run_t024_envelope_bank.py":
                    text = text.replace("-s tb_polyphonic_envelope_bank -o",
                                        "-s tb_polyphonic_envelope_bank -s tb_bank_pipeline_event_monitor -o")
                    bench = "root/'code/tb/board/tb_polyphonic_envelope_bank.sv'"
                    if bench not in text:
                        raise RuntimeError("bank bench compile source changed")
                    monitor = ROOT / "code/tb/audio/tb_bank_adsr_pipeline_monitor.sv"
                    text = text.replace(bench, bench + f",Path({monitor.as_posix()!r})")
                script = folder / name; script.write_text(text, encoding="utf-8", newline="\n")
                run(name, [sys.executable, "-X", "utf8", str(script)], timeout=300)
        facts["module_experiment_pass"] = True
    (folder / "experiment.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    print("Output-only candidate; no formal HDL, clock, constraint or board mutation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
