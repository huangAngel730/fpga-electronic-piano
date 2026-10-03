"""F real UART -> public FIFO -> actual four-voice candidate -> PCM acceptance.

Read-only production dependencies. Only reviewed ADSR and three behavioral
mutants are generated under ignored output. ModelSim compiles the real allocator
directly: no hand-written identity generator or modified bank used as oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "code/tb/board/m3_midi_pcm_acceptance"
BANK = ROOT / "code/tb/board/pitch_mod_bank_integration_candidate"
CONTRACT = ROOT / "code/docs/evidence/M3_E_F_mainline_contract_20261003.json"
PARSER_SHA = "834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_sources():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    identities = {}
    for relative, expected in contract["source_sha256"].items():
        path = ROOT / relative
        actual = sha(path)
        basis = "contract exact raw SHA"
        if relative == "code/rtl/input/midi_input/midi_event_parser.sv":
            if actual != PARSER_SHA:
                raise ValueError("E parser identity changed: " + relative)
            basis = "de68038 optimized parser (intentional E replacement)"
        elif actual != expected:
            data = path.read_bytes()
            lf = data.replace(b"\r\n", b"\n")
            variants = {hashlib.sha256(lf).hexdigest(),
                        hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest()}
            if path.suffix != ".mem" or expected not in variants:
                raise ValueError("frozen dependency changed: " + relative)
            basis = "ROM newline-only difference; raw SHAs remain distinct"
        identities[relative] = {"contract_sha256": expected, "actual_raw_sha256": actual, "basis": basis}
    # Dependencies outside the explicit contract list are frozen by the same
    # Git base. No silent substitution of live audio/transport modules.
    extras = ["code/rtl/audio/dds_oscillator.sv", "code/rtl/common/note_pitch.sv",
              "code/rtl/audio/adsr_piano_envelope.sv", "code/rtl/mixer/pcm_mixer_4voice.sv",
              "code/rtl/audio_out/pcm_result_hold.sv", "code/rtl/audio_out/pcm_frame_buffer.sv",
              "code/rtl/common/pcm_clip_counter.sv", "code/rtl/common/system_status_counters.sv",
              "code/rtl/board/voice_gain_q15_candidate.sv"]
    for relative in extras:
        frozen = subprocess.run(["git", "show", f"{contract['baseline_commit']}:{relative}"],
                                cwd=ROOT, capture_output=True, check=True).stdout
        actual = sha(ROOT / relative)
        frozen_sha = hashlib.sha256(frozen).hexdigest()
        if actual != frozen_sha:
            raise ValueError("additional frozen dependency changed: " + relative)
        identities[relative] = {"contract_sha256": frozen_sha, "actual_raw_sha256": actual,
                                "basis": "contract Git baseline exact raw SHA"}
    return identities


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path)
    cli.add_argument("--modelsim-bin", type=Path, default=Path(os.environ.get(
        "MODELSIM_BIN", "E:/FPGA/Bpan/modelsim/modelsim1/win64")))
    cli.add_argument("--positive-only", action="store_true", help="development only; not full acceptance")
    cli.add_argument("--check-capture", type=Path, help="strict offline recheck; does not claim new RTL run")
    args = cli.parse_args()
    checker = load_module("m3_pcm_checker", BENCH / "scoreboard.py")
    if args.check_capture:
        try:
            print(json.dumps(checker.check_capture(args.check_capture, ROOT), indent=2))
            return 0
        except (OSError, AssertionError, ValueError) as error:
            print("FAIL capture: " + str(error))
            return 1
    output_root = ROOT / "code/output"
    output_root.mkdir(exist_ok=True)
    if args.output:
        out = args.output.resolve()
        if output_root.resolve() not in out.parents:
            cli.error("output must be a new child of code/output")
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix="m3_midi_pcm_", dir=output_root))
    evidence = {"scope": "F candidate L2/L3 only; no STA or board claim", "passed": False,
                "full_acceptance": not args.positive_only, "runs": {}, "results": []}
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(label, command, cwd, timeout=300):
        log = out / (label + ".log")
        try:
            result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                                    capture_output=True, timeout=timeout, check=False)
            data, code = result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            data = (error.stdout or b"") + (error.stderr or b"") + b"\nRUNNER_TIMEOUT\n"
            code = 124
        log.write_bytes(data)
        evidence["runs"][label] = {"command": list(map(str, command)), "cwd": str(cwd),
                                   "exit_code": code, "log_sha256": sha(log)}
        print(label, "exit", code, flush=True)
        return code, data.decode("utf-8", errors="replace")

    try:
        evidence["source_identity"] = validate_sources()
        evidence["test_sources"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in
                                    [BENCH / "tb_midi_pcm.sv", BENCH / "scoreboard.py", BENCH / "test_capture.py", Path(__file__)]}
        tools = {name: args.modelsim_bin / (name + ".exe") for name in ("vlib", "vlog", "vsim")}
        if not all(tool.is_file() for tool in tools.values()):
            raise FileNotFoundError("ModelSim vlib/vlog/vsim missing")
        code, _ = run("tool_version", [tools["vsim"], "-version"], out, 30)
        if code:
            raise RuntimeError("tool version failed")
        adsr_folder = out / "adsr_generated"
        adsr_folder.mkdir()
        patcher = load_module("m2_adsr_patch", ROOT / "code/scripts/run_adsr_pipeline_isolated.py")
        metadata, _ = patcher.patch_copies(adsr_folder)
        evidence["generated_sources"] = metadata
        reference = out / "bank_reference.sv"
        reference_text = (adsr_folder / "polyphonic_envelope_bank.sv").read_text(encoding="utf-8")
        anchor = "module polyphonic_envelope_bank"
        if reference_text.count(anchor) != 1:
            raise ValueError("reference bank module rename anchor")
        reference.write_text(reference_text.replace(anchor, "module bank_reference", 1), encoding="utf-8", newline="\n")
        evidence["generated_reference_sha256"] = sha(reference)
        sources = [
            ROOT / "code/rtl/common/audio_defs_pkg.sv",
            ROOT / "code/rtl/common/uart_rx.sv", ROOT / "code/rtl/common/performance_event_fifo.sv",
            ROOT / "code/rtl/input/midi_input/midi_event_parser.sv", ROOT / "code/rtl/input/midi_input/midi_input.sv",
            ROOT / "code/rtl/audio/voice_allocator_4.sv", ROOT / "code/rtl/common/note_pitch.sv",
            ROOT / "code/rtl/board/sustain_control_contract_pkg.sv",
            ROOT / "code/rtl/input/sustain_control/sustain_controller.sv",
            BANK / "polyphonic_event_router.sv", BANK / "polyphonic_envelope_bank.sv", reference,
            ROOT / "code/rtl/board/performance_control_snapshot.sv",
            ROOT / "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_fcw_pipeline.sv",
            ROOT / "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_snapshot_pipeline.sv",
            ROOT / "code/rtl/audio/dds_oscillator.sv", ROOT / "code/rtl/audio/piano_dds_oscillator.sv",
            adsr_folder / "adsr_piano_envelope.sv", ROOT / "code/rtl/board/polyphonic_pcm_commit.sv",
            ROOT / "code/rtl/mixer/pcm_mixer_4voice.sv", ROOT / "code/rtl/audio_out/pcm_result_hold.sv",
            ROOT / "code/rtl/audio_out/pcm_frame_buffer.sv", ROOT / "code/rtl/common/pcm_clip_counter.sv",
            ROOT / "code/rtl/common/system_status_counters.sv", ROOT / "code/rtl/board/voice_gain_q15_candidate.sv",
            ROOT / "code/rtl/board/polyphonic_audio_core.sv", BENCH / "tb_midi_pcm.sv",
        ]
        evidence["compiled_sources"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
        cases = [("positive", None, None, None, None)]
        if not args.positive_only:
            cases.extend([
                ("dds_base_bypass", BANK / "polyphonic_envelope_bank.sv",
                 "computed_fcw[32*k+:32]<=frozen_occupied[k] ? fcw_values[32*k+:32] : frozen_base[32*k+:32];",
                 "computed_fcw[32*k+:32]<=frozen_base[32*k+:32];", "DDS adjusted FCW bypass"),
                ("wrong_pcm_frame", ROOT / "code/rtl/audio_out/pcm_result_hold.sv",
                 "pcm_req_id <= result_req_id;", "pcm_req_id <= result_req_id ^ 32'd1;", "PCM frame tag mismatch"),
                ("early_control", BANK / "polyphonic_envelope_bank.sv",
                 ".event_valid(event_valid && router_ready)", ".event_valid(event_valid)",
                 "control updated before public FIFO acceptance"),
            ])
        roms = {"wave.mem": "code/model/generated/wavetables/piano_band_4x256_8191.mem",
                "velocity.mem": "code/model/generated/wavetables/velocity_gain_rom.mem",
                "oct_ratio_q16.mem": "code/model/generated/pitch_mod/oct_ratio_q16.mem",
                "sub_ratio_q16.mem": "code/model/generated/pitch_mod/sub_ratio_q16.mem",
                "lfo_sine_q15.mem": "code/model/generated/pitch_mod/lfo_sine_q15.mem"}
        for name, target, before, after, reason in cases:
            folder = out / name
            folder.mkdir()
            for rom_name, relative in roms.items():
                destination = folder / rom_name if rom_name in ("wave.mem", "velocity.mem") else folder / "model/generated/pitch_mod" / rom_name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            selected = sources.copy()
            mutant_sha = None
            if target:
                text = target.read_text(encoding="utf-8")
                if text.count(before) != 1:
                    raise ValueError("unique behavioral mutation anchor missing: " + name)
                mutant = folder / target.name
                mutant.write_text(text.replace(before, after, 1), encoding="utf-8", newline="\n")
                selected[selected.index(target)] = mutant
                mutant_sha = sha(mutant)
            commands = [[tools["vlib"], "work"],
                        [tools["vlog"], "-sv", "+incdir+" + str(ROOT / "code/rtl/board"), *selected],
                        [tools["vsim"], "-c", "-onfinish", "stop", "-voptargs=+acc", "tb_midi_pcm",
                         "+VELOCITY_ROM_PATH=" + str(folder / "velocity.mem"), "-do",
                         "onbreak {quit -code 1}; onerror {quit -code 1}; run -all; "
                         "if {[examine -radix unsigned /tb_midi_pcm/test_passed] != 1} "
                         "{quit -code 1}; quit -code 0"]]
            statuses = []
            transcript = ""
            for phase, command in zip(("library", "compile", "run"), commands):
                code, transcript = run(name + "_" + phase, command, folder)
                statuses.append(code)
                if code:
                    break
            compiled = len(statuses) >= 2 and statuses[:2] == [0, 0]
            capture_path = folder / "midi_pcm.capture"
            verdict = {"name": name, "exit_codes": statuses, "compiled": compiled,
                       "mutant_sha256": mutant_sha, "passed": False}
            if capture_path.is_file():
                verdict["capture_sha256"] = sha(capture_path)
            if name == "positive":
                if not compiled or statuses != [0, 0, 0] or "PASS F real UART" not in transcript or re.search(r"Fatal:|\*\* Error|RUNNER_TIMEOUT", transcript):
                    raise RuntimeError("positive RTL failed: " + transcript[-2000:])
                verdict["independent_reference"] = checker.check_capture(capture_path, ROOT)
                evidence_checks = load_module("f_evidence_checks", BENCH / "test_capture.py")
                evidence["capture_preflight_negatives"] = evidence_checks.run_checks(
                    capture_path, ROOT, out / "capture_preflight_negatives")
                verdict["passed"] = True
            elif reason == "DDS adjusted FCW bypass" and compiled and statuses == [0, 0, 0]:
                try:
                    checker.check_capture(capture_path, ROOT)
                except AssertionError as error:
                    verdict["rejection"] = str(error)
                    verdict["passed"] = reason in str(error)
            else:
                verdict["rejection"] = reason
                verdict["passed"] = compiled and len(statuses) == 3 and statuses[2] not in (0, 124) and reason in transcript and "RUNNER_TIMEOUT" not in transcript
            evidence["results"].append(verdict)
            if not verdict["passed"]:
                raise RuntimeError("case not behaviorally accepted/rejected: " + name + "\n" + transcript[-2000:])
            print("PASS " + name, flush=True)
        evidence["passed"] = True
        evidence["source_identity_after"] = validate_sources()
        if evidence["source_identity_after"] != evidence["source_identity"]:
            raise ValueError("input identity changed during acceptance")
        if {p.relative_to(ROOT).as_posix(): sha(p) for p in sources} != evidence["compiled_sources"]:
            raise ValueError("compiled source changed during acceptance")
        if any(sha(ROOT / relative) != digest for relative, digest in evidence["test_sources"].items()):
            raise ValueError("test or runner changed during acceptance")
    except (OSError, ValueError, RuntimeError, AssertionError, subprocess.SubprocessError) as error:
        evidence["passed"] = False
        evidence["error"] = str(error)
        print("FAIL " + str(error), flush=True)
    evidence["log_sha256"] = {path.name: sha(path) for path in out.glob("*.log")}
    write_json(out / "evidence.json", evidence)
    print("Evidence: " + str(out / "evidence.json"), flush=True)
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
