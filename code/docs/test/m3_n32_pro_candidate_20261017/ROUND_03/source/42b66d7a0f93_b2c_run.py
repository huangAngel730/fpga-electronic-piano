"""Same hybrid chain expanded to N8; bounded RTL and independent replay only."""
import json
import os
import sys

from b1_run import external
from inventory import FROZEN, ROOT


def sources():
    return [FROZEN / "sources" / name for name in (
        "audio_defs_pkg.sv", "sustain_control_contract_pkg.sv", "note_pitch.sv",
        "adsr_piano_envelope.sv", "pitch_mod_fcw_pipeline.sv")] + [
        ROOT / "code/rtl/common/polyphony_scaling_candidate" / name for name in (
            "b1_statebank.sv", "b1_scheduler.sv", "b2_audio_backend.sv",
            "b2c_voice_allocator.sv", "b2c_sustain_controller.sv",
            "b2c_event_router.sv", "b2c_control_snapshot.sv", "b2c_event_audio.sv")] + [
        ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b2c_event_audio.sv"]


def run_b2c(run, args):
    iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
    suite = iv.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite) + os.sep}
    run.extra_path = [str(suite / "bin"), str(suite / "lib")]
    run.command("iverilog_version", [str(iv), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT / "code/software/polyphony_scaling_candidate"
    base = [str(iv), "-g2012", "-I", str(FROZEN / "include"), "-s", "tb_b2c_event_audio"]
    reports, captures = [], []
    for n, response, long_case in ((4, 1, 0), (8, 1, 1), (8, 3, 0), (8, 64, 0)):
        stem = f"B2C_N{n}_R{response}_long{long_case}"
        image, report = run.output / (stem + ".vvp"), run.output / (stem + ".json")
        run.command(stem + "_compile", base + ["-o", str(image), f"-DB2C_N={n}",
                    f"-DB2C_RESPONSE={response}", f"-DB2C_LONG={long_case}"] + [str(p) for p in sources()])
        run.command(stem + "_simulate", [str(vvp), str(image)])
        capture = ROOT / run.steps[-1]["stdout"]["path"]
        captures.append(capture)
        run.command(stem + "_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2c_check.py"),
                                       "--input", str(capture), "--output", str(report)])
        reports.append(json.loads(report.read_text(encoding="utf-8")))
    # Fresh short N4 reference run is necessary because the front end changed.
    from b2b_run import compile_sources
    prior_sources = compile_sources(run.output)
    prior_image = run.output / "prior_n4.vvp"
    run.command("prior_N4_compile", [str(iv), "-g2012", "-I", str(FROZEN / "include"),
                "-s", "tb_b2b_event_audio", "-o", str(prior_image)] + [str(p) for p in prior_sources])
    run.command("prior_N4_simulate", [str(vvp), str(prior_image)])
    prior = ROOT / run.steps[-1]["stdout"]["path"]
    # This is exact N4 trace equivalence, not a whole frozen-top claim.
    run.command("N4_prior_compare", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2c_tests.py"),
                                    "--n4", str(captures[0]), "--n8", str(captures[2]), "--prior", str(prior),
                                    "--output", str(run.output / "checker_tests")])
    for define, reason in (("B1_MUTANT_IGNORE_GENERATION", "B2B_STALE_GENERATION_ACCEPTED"),
                           ("B2_MUTANT_GAIN_ZERO", "MATH_GAIN_PCM")):
        image = run.output / (define + ".vvp")
        run.command(define + "_compile", base + ["-o", str(image), "-D" + define] + [str(p) for p in sources()])
        raw = run.command(define + "_simulate", [str(vvp), str(image)], expected_exit=1 if define.startswith("B1") else 0)
        if define.startswith("B1"):
            if reason.encode() not in raw or b"WATCHDOG" in raw:
                raise ValueError("WRONG_GENERATION_MUTANT_REJECTION")
        else:
            capture = ROOT / run.steps[-1]["stdout"]["path"]
            raw = run.command(define + "_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2c_check.py"),
                                                  "--input", str(capture)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_GAIN_MUTANT_REJECTION")
    result = {"status": "B2C_N8_EVENT_AUDIO_PASS_T061_PARTIAL", "profiles": reports,
              "tools": {"iverilog": external(iv), "vvp": external(vvp)},
              "task_complete": False, "N16_N32_event_router": "NOT_VERIFIED",
              "physical_STA": "NOT_RUN", "new_Gowin_allowance_used": False}
    (run.output / "b2c_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
