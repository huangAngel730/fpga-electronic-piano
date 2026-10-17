"""One hybrid N32 checkpoint: pinned N16 RTL, four bounded short profiles."""
import json
import os
import sys

from b1_run import external
from b2d_run import sources
from inventory import FROZEN, ROOT


def run_b2e(run, args):
    iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
    suite = iv.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite)+os.sep}
    run.extra_path = [str(suite/"bin"), str(suite/"lib")]
    run.command("iverilog_version", [str(iv), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT/"code/software/polyphony_scaling_candidate"
    base = [str(iv), "-g2012", "-I", str(FROZEN/"include"), "-s", "tb_b2d_event_audio"]
    reports, captures = [], {}
    for response in (1, 8, 16, 32):
        stem = f"B2E_N32_R{response}_long0"
        image, report = run.output/(stem+".vvp"), run.output/(stem+".json")
        run.command(stem+"_compile", base+["-o", str(image), "-DB2C_N=32",
                    f"-DB2C_RESPONSE={response}", "-DB2C_LONG=0"]+[str(p) for p in sources()])
        run.command(stem+"_simulate", [str(vvp), str(image)])
        capture = ROOT/run.steps[-1]["stdout"]["path"]
        captures[response] = capture
        run.command(stem+"_replay", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2e_check.py"),
                                    "--input", str(capture), "--output", str(report)])
        result = json.loads(report.read_text(encoding="utf-8"))
        # These expectations come from the unchanged source calendar, not a
        # permissive observed range. R16 is near the limit and dispatch can
        # exceed it; R32 is deliberately slow. Neither is an admitted profile.
        if result["sample_deadline_qualified"] != (response in (1, 8)):
            raise ValueError("UNEXPECTED_N32_DEADLINE_CLASSIFICATION")
        reports.append(result)
    run.command("N32_complete_negatives", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2e_tests.py"),
                "--normal", str(captures[8]), "--slow", str(captures[32]),
                "--output", str(run.output/"checker_tests")])
    for define, reason in (("B1_MUTANT_IGNORE_GENERATION", "B2B_STALE_GENERATION_ACCEPTED"),
                           ("B2_MUTANT_GAIN_ZERO", "MATH_GAIN_PCM")):
        image = run.output/(define+".vvp")
        run.command(define+"_compile", base+["-o", str(image), "-DB2C_N=32", "-DB2C_LONG=0", "-D"+define]
                    +[str(p) for p in sources()])
        raw = run.command(define+"_simulate", [str(vvp), str(image)],
                          expected_exit=1 if define.startswith("B1") else 0)
        if define.startswith("B1"):
            if reason.encode() not in raw or b"WATCHDOG" in raw:
                raise ValueError("WRONG_GENERATION_MUTANT_REJECTION")
        else:
            capture = ROOT/run.steps[-1]["stdout"]["path"]
            raw = run.command(define+"_replay", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2e_check.py"),
                                               "--input", str(capture)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_GAIN_MUTANT_REJECTION")
    result = dict(status="B2E_N32_SHORT_EVENT_AUDIO_PASS_T061_PARTIAL", profiles=reports,
                  tools=dict(iverilog=external(iv), vvp=external(vvp)), task_complete=False,
                  HDL_source_revision="0ca4515", new_HDL_sources=False,
                  actual_RTL_capture_reuse=False, compiled_RTL_negatives=2,
                  N32_long_ADSR_retirement="NOT_RUN", N32_sustained_performance="NOT_VERIFIED",
                  physical_STA="NOT_RUN", new_Gowin_allowance_used=False,
                  R16_R32="DEADLINE_MISS_NOT_QUALIFIED")
    (run.output/"b2e_summary.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result
