"""One full N32 long scenario, pinned RTL/TB and unchanged48k sample cadence."""
import json
import os
import sys

from b1_run import external
from b2d_run import sources
from inventory import FROZEN, ROOT


def run_b2h(run, args):
    iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
    if not iv.is_file() or not vvp.is_file():
        raise ValueError("MISSING_EXISTING_ICARUS")
    suite = iv.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite)+os.sep}
    run.extra_path = [str(suite/"bin"), str(suite/"lib")]
    run.command("iverilog_version", [str(iv), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT/"code/software/polyphony_scaling_candidate"
    base = [str(iv), "-g2012", "-I", str(FROZEN/"include"), "-s", "tb_b2d_event_audio", "-DB2C_N=32"]
    stem = "B2H_N32_R1_long1"
    image, report = run.output/(stem+".vvp"), run.output/(stem+".json")
    run.command(stem+"_compile", base+["-DB2C_RESPONSE=1", "-DB2C_LONG=1", "-o", str(image)]
                +[str(p) for p in sources()])
    if args.b2h_preflight_only:
        run.command("B2H_unit_preflight", [sys.executable, "-B", "-X", "utf8",
                    str(candidate/"b2h_tests.py"), "--unit-only"])
        return dict(status="B2H_PREFLIGHT_COMPILE_ONLY_NOT_LONG_PASS", compile_exit=0,
                    long_simulation="NOT_RUN", task_complete=False)
    run.command(stem+"_simulate", [str(vvp), str(image)])
    capture = ROOT/run.steps[-1]["stdout"]["path"]
    run.command(stem+"_replay", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2h_check.py"),
                                "--input", str(capture), "--output", str(report)])
    profile = json.loads(report.read_text(encoding="utf-8"))
    run.command("B2H_complete_counterexamples", [sys.executable, "-B", "-X", "utf8",
                str(candidate/"b2h_tests.py"), "--input", str(capture),
                "--output", str(run.output/"checker_tests")])
    mutants = []
    # These real compiled negatives are short: they fail on the first relevant
    # stale identity/gain, not after a gratuitous second long ADSR performance.
    for define, reason in (("B1_MUTANT_IGNORE_GENERATION", "B2B_STALE_GENERATION_ACCEPTED"),
                           ("B2_MUTANT_GAIN_ZERO", "MATH_GAIN_PCM")):
        image = run.output/(define+".vvp")
        run.command(define+"_compile", base+["-DB2C_RESPONSE=1", "-DB2C_LONG=0", "-D"+define,
                    "-o", str(image)]+[str(p) for p in sources()])
        raw = run.command(define+"_simulate", [str(vvp), str(image)],
                          expected_exit=1 if define.startswith("B1") else 0)
        if define.startswith("B1"):
            if reason.encode() not in raw or b"WATCHDOG" in raw:
                raise ValueError("WRONG_GENERATION_MUTANT_REJECTION")
        else:
            bad = ROOT/run.steps[-1]["stdout"]["path"]
            raw = run.command(define+"_replay", [sys.executable, "-B", "-X", "utf8",
                              str(candidate/"b2e_check.py"), "--input", str(bad)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_GAIN_MUTANT_REJECTION")
        mutants.append(dict(define=define, diagnostic=reason, compile_exit=0,
                            simulation_exit=1 if define.startswith("B1") else 0,
                            replay_exit=1 if define.startswith("B2") else None,
                            stimulus="N32 R1 original short fixture"))
    result = dict(status="B2H_N32_LONG_LIFECYCLE_PASS_T061_PARTIAL", profiles=[profile],
                  tools=dict(iverilog=external(iv), vvp=external(vvp)),
                  HDL_source_revision="0ca4515", new_HDL_sources=False,
                  actual_RTL_capture_reuse=False, compiled_behavior_mutants=mutants,
                  physical_STA="NOT_RUN", new_Gowin_allowance_used=False,
                  general_sustained_performance="NOT_VERIFIED", task_complete=False)
    (run.output/"b2h_summary.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result
