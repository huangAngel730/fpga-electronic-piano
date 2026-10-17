"""Bounded B2a real mathematical backend workflow. No synthesis/devices."""
import json
import os
import sys

from b1_run import external
from inventory import FROZEN, ROOT, identity


def run_b2(run, args):
    iverilog, vvp = args.iverilog.resolve(), args.vvp.resolve()
    if not iverilog.is_file() or not vvp.is_file():
        raise ValueError("MISSING_EXISTING_ICARUS")
    suite = iverilog.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite) + os.sep}
    run.extra_path = [str(suite / "bin"), str(suite / "lib")]
    run.command("iverilog_version", [str(iverilog), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT / "code/software/polyphony_scaling_candidate"
    sources = [ROOT / "code/rtl/common/polyphony_scaling_candidate/b2_audio_backend.sv",
               ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b2_audio.sv"]
    sources += [FROZEN / "sources" / name for name in
                ("adsr_piano_envelope.sv", "pitch_mod_fcw_pipeline.sv", "piano_dds_oscillator.sv",
                 "voice_gain_q15_candidate.sv")]
    reports = []
    captures = []
    # N4 must pass first, including the continuous ADSR decay/sustain/release
    # and all brightness windows, before higher-N DUT configurations run.
    for n, response, long_case in ((4, 1, 1), (4, 3, 0), (8, 1, 0),
                                    (16, 1, 0), (32, 1, 0), (32, 32, 0)):
        stem = f"B2_N{n}_R{response}_long{long_case}"
        image, report = run.output / (stem + ".vvp"), run.output / (stem + ".json")
        run.command(stem + "_compile", [str(iverilog), "-g2012", "-s", "tb_b2_audio", "-o", str(image),
                                       f"-DB2_N={n}", f"-DB2_RESPONSE={response}", f"-DB2_LONG={long_case}"] +
                    [str(path) for path in sources])
        run.command(stem + "_simulate", [str(vvp), str(image)])
        capture = ROOT / run.steps[-1]["stdout"]["path"]
        captures.append(capture)
        run.command(stem + "_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2_check.py"),
                                      "--input", str(capture), "--output", str(report)])
        reports.append(json.loads(report.read_text(encoding="utf-8")))
    mutants = []
    for name, diagnostic in (("GAIN_ZERO", "CHECK_GAIN_FROZEN"), ("SKIP_LAST", "CHECK_ALL_VOICES")):
        stem = "B2_mutant_" + name
        image = run.output / (stem + ".vvp")
        run.command(stem + "_compile", [str(iverilog), "-g2012", "-s", "tb_b2_audio", "-o", str(image),
                                       "-D", "B2_MUTANT_" + name] + [str(path) for path in sources])
        raw = run.command(stem + "_simulate", [str(vvp), str(image)], expected_exit=1)
        if diagnostic.encode("ascii") not in raw or b"TB_WATCHDOG" in raw:
            raise ValueError("WRONG_BEHAVIOR_MUTANT_REJECTION:" + name)
        mutants.append({"define": "B2_MUTANT_" + name, "diagnostic": diagnostic,
                        "compile_exit": 0, "simulation_exit": 1,
                        "capture": identity(ROOT / run.steps[-1]["stdout"]["path"])})
    run.command("B2_checker_counterexamples", [sys.executable, "-B", "-X", "utf8",
                str(candidate / "b2_negatives.py"), "--input", str(captures[1]),
                "--output", str(run.output / "B2_counterexamples")])
    run.command("B2_checker_unit", [sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover",
                                    "-s", str(candidate), "-p", "test_b2_checker.py", "-v"])
    result = {"status": "B2A_REAL_MATH_BACKEND_PASS_T061_PARTIAL", "profiles": reports,
              "tools": {"iverilog": external(iverilog), "vvp": external(vvp)},
              "compiled_behavior_mutants": mutants,
              "continuous_per_voice_frozen_algorithms": ["ADSR", "PitchMod"],
              "shared_backend": ["one piano wave ROM read port", "one signed gain multiplier", "one signed32 accumulator"],
              "not_a_fully_shared_context_engine": True,
              "MIDI_CC64_and_B1_integration": "NOT_IMPLEMENTED",
              "whole_frozen_L_event_to_PCM_equivalence": False,
              "new_Gowin_allowance_used": False, "physical_STA": "NOT_RUN", "task_complete": False}
    (run.output / "b2_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
