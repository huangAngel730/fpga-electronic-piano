"""N8 repaired identity controls: pinned N16 RTL, original N8 stimulus, new evidence."""
import json
import os
import sys

from b1_run import external
from b2d_run import sources as n16_sources
from inventory import FROZEN, ROOT


def sources():
    return [p.with_name("tb_b2f_event_audio.sv") if p.name == "tb_b2d_event_audio.sv" else p
            for p in n16_sources()]


def run_b2f(run, args):
    iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
    suite = iv.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite)+os.sep}
    run.extra_path = [str(suite/"bin"), str(suite/"lib")]
    run.command("iverilog_version", [str(iv), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT/"code/software/polyphony_scaling_candidate"
    old = run.command("original_N8_fixture", ["git", "show",
                      "33c8b70:code/tb/common/polyphony_scaling_candidate/tb_b2c_event_audio.sv"])
    renamed = old.replace(b"\r\n", b"\n").replace(b"module tb_b2c_event_audio;", b"module tb_b2f_event_audio;")
    renamed = renamed.replace(b"b2c_event_audio #", b"b2d_event_audio #")
    if renamed != sources()[-1].read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError("ORIGINAL_N8_STIMULUS_CHANGED")
    alias_sources = [FROZEN/"sources/audio_defs_pkg.sv",
                     ROOT/"code/rtl/common/polyphony_scaling_candidate/b1_statebank.sv",
                     ROOT/"code/rtl/common/polyphony_scaling_candidate/b2d_control_snapshot.sv",
                     ROOT/"code/tb/common/polyphony_scaling_candidate/tb_b2f_identity_control.sv"]
    for mutant in (False, True):
        label = "identity_control_old_mask" if mutant else "identity_control_normal"
        image = run.output/(label+".vvp")
        command = [str(iv), "-g2012", "-I", str(FROZEN/"include"), "-s",
                   "tb_b2f_identity_control", "-o", str(image)]
        if mutant:
            command += ["-DB2D_MUTANT_MASK_IDLE_CONTROL"]
        run.command(label+"_compile", command+[str(p) for p in alias_sources])
        raw = run.command(label+"_simulate", [str(vvp), str(image)], expected_exit=int(mutant))
        expected = b"B2F_BANK_CONTROL_CLOBBER" if mutant else b"B2F_IDENTITY_CONTROL_PASS cases=13 bank_reads=104"
        if expected not in raw or b"WATCHDOG" in raw:
            raise ValueError("WRONG_IDENTITY_CONTROL_RESULT")
    base = [str(iv), "-g2012", "-I", str(FROZEN/"include"), "-s", "tb_b2f_event_audio"]
    reports, captures = [], {}
    for response, long_case in ((3, 0), (64, 0), (1, 1)):
        stem = f"B2F_N8_R{response}_long{long_case}"
        image, report = run.output/(stem+".vvp"), run.output/(stem+".json")
        run.command(stem+"_compile", base+["-o", str(image), "-DB2C_N=8",
                    f"-DB2C_RESPONSE={response}", f"-DB2C_LONG={long_case}"]+[str(p) for p in sources()])
        run.command(stem+"_simulate", [str(vvp), str(image)])
        capture = ROOT/run.steps[-1]["stdout"]["path"]
        captures[response] = capture
        run.command(stem+"_replay", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2f_check.py"),
                                    "--input", str(capture), "--output", str(report)])
        result = json.loads(report.read_text(encoding="utf-8"))
        if not result["sample_deadline_qualified"]:
            raise ValueError("N8_UNEXPECTED_DEADLINE_MISS")
        reports.append(result)
    run.command("N8_complete_negatives", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2f_tests.py"),
                "--normal", str(captures[3]), "--slow", str(captures[64]),
                "--output", str(run.output/"checker_tests")])
    for define, reason in (("B1_MUTANT_IGNORE_GENERATION", "B2B_STALE_GENERATION_ACCEPTED"),
                           ("B2_MUTANT_GAIN_ZERO", "MATH_GAIN_PCM")):
        image = run.output/(define+".vvp")
        run.command(define+"_compile", base+["-o", str(image), "-DB2C_N=8", "-DB2C_LONG=0", "-D"+define]
                    +[str(p) for p in sources()])
        raw = run.command(define+"_simulate", [str(vvp), str(image)],
                          expected_exit=1 if define.startswith("B1") else 0)
        if define.startswith("B1"):
            if reason.encode() not in raw or b"WATCHDOG" in raw:
                raise ValueError("WRONG_GENERATION_MUTANT_REJECTION")
        else:
            capture = ROOT/run.steps[-1]["stdout"]["path"]
            raw = run.command(define+"_replay", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2f_check.py"),
                                               "--input", str(capture)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_GAIN_MUTANT_REJECTION")
    result = dict(status="B2F_N8_IDENTITY_SUCCESSOR_PASS_T061_PARTIAL", profiles=reports,
                  tools=dict(iverilog=external(iv), vvp=external(vvp)), task_complete=False,
                  HDL_source_revision="0ca4515", new_functional_HDL_sources=False,
                  original_N8_stimulus_unchanged=True, actual_RTL_capture_reuse=False,
                  directed_cases=13, directed_public_bank_reads=104, compiled_RTL_negatives=3,
                  physical_STA="NOT_RUN", new_Gowin_allowance_used=False)
    (run.output/"b2f_summary.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result
