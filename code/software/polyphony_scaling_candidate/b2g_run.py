"""Same pinned real backend; legal full-velocity and FCW test substitutions."""
import hashlib
import json
import os
import sys

from b1_run import external
from inventory import FROZEN, ROOT, identity

TB_VELOCITY = "velocity[10*k+:10]= k%4==0 ? 255 : k%4==1 ? 256 : k%4==2 ? 512 : 1023;"


def substitute_once(data, old, new):
    if data.count(old) != 1:
        raise ValueError("PRECISE_SUBSTITUTION_COUNT")
    return data.replace(old, new)


def run_b2g(run, args):
    iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
    if not iv.is_file() or not vvp.is_file():
        raise ValueError("MISSING_EXISTING_ICARUS")
    suite = iv.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite)+os.sep}
    run.extra_path = [str(suite/"bin"), str(suite/"lib")]
    run.command("iverilog_version", [str(iv), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT/"code/software/polyphony_scaling_candidate"
    hdl = ROOT/"code/rtl/common/polyphony_scaling_candidate/b2_audio_backend.sv"
    original_tb = ROOT/"code/tb/common/polyphony_scaling_candidate/tb_b2_audio.sv"
    raw_tb = original_tb.read_bytes().replace(b"\r\n", b"\n")
    test_dir = run.output/"generated_test"
    test_dir.mkdir()
    tb = test_dir/"tb_b2_audio.sv"
    # No new wave ROM, forced DUT state or changed sample period. The original
    # fixture's reset, cancellation, snapshot perturbation and END stay intact.
    changed_tb = substitute_once(raw_tb, TB_VELOCITY.encode(),
                                 b"velocity[10*k+:10]=1023;")
    # Table0's positive peak is at index17: at the old440Hz input it arrives
    # too early in the attack to clip. 880Hz has another positive peak during
    # this existing96-frame short fixture. This is an INPUT, not expected PCM.
    changed_tb = substitute_once(changed_tb, b") : 32'd39370534;",
                                 b") : 32'd78741068;")
    tb.write_bytes(changed_tb)
    provenance = dict(source=identity(original_tb), generated=identity(tb),
                      source_lf_sha256=hashlib.sha256(raw_tb).hexdigest(),
                      substitutions=[dict(old=TB_VELOCITY,
                                          new="velocity[10*k+:10]=1023;", count=1),
                                     dict(old=") : 32'd39370534;", new=") : 32'd78741068;", count=1)])
    (test_dir/"provenance.json").write_text(json.dumps(provenance, indent=2)+"\n", encoding="utf-8")
    frozen = [FROZEN/"sources"/name for name in
              ("adsr_piano_envelope.sv", "pitch_mod_fcw_pipeline.sv",
               "piano_dds_oscillator.sv", "voice_gain_q15_candidate.sv")]
    base = [str(iv), "-g2012", "-s", "tb_b2_audio", "-DB2_N=32", "-DB2_LONG=0"]
    profiles, captures, mutants = [], {}, []
    for response in (1, 8):
        stem = f"B2G_N32_R{response}"
        image, report = run.output/(stem+".vvp"), run.output/(stem+".json")
        run.command(stem+"_compile", base+[f"-DB2_RESPONSE={response}", "-o", str(image),
                    str(hdl), str(tb)]+[str(p) for p in frozen])
        run.command(stem+"_simulate", [str(vvp), str(image)])
        captures[response] = ROOT/run.steps[-1]["stdout"]["path"]
        run.command(stem+"_replay", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2g_check.py"),
                                    "--input", str(captures[response]), "--output", str(report)])
        result = json.loads(report.read_text(encoding="utf-8"))
        if not result["sample_deadline_qualified"]:
            raise ValueError("SATURATION_PROFILE_DEADLINE")
        profiles.append(result)
    raw_hdl = hdl.read_bytes().replace(b"\r\n", b"\n")
    for name, old, new in (("POSITIVE_LIMIT_MINUS_ONE", b"saturated=24'h7fffff;", b"saturated=24'h7ffffe;"),
                           ("NEGATIVE_LIMIT_PLUS_ONE", b"saturated=24'h800000;", b"saturated=24'h800001;")):
        directory = run.output/("mutant_"+name)
        directory.mkdir()
        changed = directory/"b2_audio_backend.sv"
        changed.write_bytes(substitute_once(raw_hdl, old, new))
        image = directory/"mutant.vvp"
        run.command(name+"_compile", base+["-DB2_RESPONSE=1", "-o", str(image), str(changed), str(tb)]
                    +[str(p) for p in frozen])
        run.command(name+"_simulate", [str(vvp), str(image)])
        capture = ROOT/run.steps[-1]["stdout"]["path"]
        report = directory/"rejection.json"
        run.command(name+"_replay", [sys.executable, "-B", "-X", "utf8", str(candidate/"b2g_check.py"),
                    "--input", str(capture), "--output", str(report)], expected_exit=1)
        rejected = json.loads(report.read_text(encoding="utf-8"))
        if rejected != dict(status="REJECT", reason="MATH_STEREO_SATURATION"):
            raise ValueError("WRONG_SATURATION_MUTANT_REJECTION:"+name)
        mutants.append(dict(name=name, source=identity(changed), old=old.decode(), new=new.decode(),
                            substitutions=1, compile_exit=0, simulation_exit=0, replay_exit=1,
                            rejection=rejected, capture=identity(capture)))
    run.command("B2G_complete_counterexamples", [sys.executable, "-B", "-X", "utf8",
                str(candidate/"b2g_tests.py"), "--input", str(captures[1]),
                "--output", str(run.output/"checker_tests")])
    result = dict(status="B2G_N32_REAL_SATURATION_PASS_T061_PARTIAL", profiles=profiles,
                  tools=dict(iverilog=external(iv), vvp=external(vvp)),
                  generated_test_provenance=provenance, compiled_behavior_mutants=mutants,
                  new_functional_HDL=False, actual_RTL_capture_reuse=False,
                  original_source_revision="1c73e8d", old_checker_revision="b814096",
                  MIDI_B1_integration="NOT_RUN_IN_THIS_STAGE", N32_long_performance="NOT_RUN",
                  physical_STA="NOT_RUN", new_Gowin_allowance_used=False, task_complete=False)
    (run.output/"b2g_summary.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result
