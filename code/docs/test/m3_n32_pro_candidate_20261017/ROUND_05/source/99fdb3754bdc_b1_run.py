"""B1 isolated RTL workflow; called by the scoped runner, never by a device tool."""
import json
import os
from pathlib import Path
import sys

from inventory import ROOT, identity


def run_b1(run, args):
    iverilog, vvp = args.iverilog.resolve(), args.vvp.resolve()
    for tool in (iverilog, vvp):
        if not tool.is_file():
            raise RuntimeError("MISSING_RTL_TOOL:" + str(tool))
    suite = iverilog.parent.parent
    # Equivalent to the suite's runtime search path, without invoking its
    # unrelated gdk cache updater (which writes outside this task's scope).
    run.extra_env = {"YOSYSHQ_ROOT": str(suite) + os.sep}
    run.extra_path = [str(suite / "bin"), str(suite / "lib")]
    tools = {"iverilog": identity(iverilog) if iverilog.is_relative_to(ROOT) else external(iverilog),
             "vvp": external(vvp), "runtime_root": str(suite)}
    run.command("iverilog_version", [str(iverilog), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    rtl = ROOT / "code/rtl/common/polyphony_scaling_candidate"
    tb = ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b1.sv"
    sources = [rtl / name for name in ("b1_statebank.sv", "b1_scheduler.sv", "b1_tagged_rom.sv")] + [tb]
    checker = ROOT / "code/software/polyphony_scaling_candidate/b1_check.py"
    reports = []
    for n, latency, mode in [(n, latency, 0) for n in (4, 8, 16, 32) for latency in (1, 3)] + [(32, 3, 1)]:
        stem = f"N{n}_ROM{latency}_mode{mode}"
        image = run.output / (stem + ".vvp")
        compile_cmd = [str(iverilog), "-g2012", "-s", "tb_b1", "-o", str(image),
                       f"-DB1_N={n}", f"-DB1_LATENCY={latency}", f"-DB1_MODE={mode}"]
        run.command(stem + "_compile", compile_cmd + [str(path) for path in sources])
        run.command(stem + "_simulate", [str(vvp), str(image)])
        capture = ROOT / run.steps[-1]["stdout"]["path"]
        report = run.output / (stem + ".json")
        run.command(stem + "_replay", [sys.executable, "-B", "-X", "utf8", str(checker),
                                      "--input", str(capture), "--output", str(report)])
        reports.append(json.loads(report.read_text(encoding="utf-8")))
    mutants = []
    for name, diagnostic in [("IGNORE_GENERATION", "CHECK_TAG_GENERATION_OR_UNISSUED"),
                             ("SKIP_LAST", "CHECK_ALL_N_BEFORE_COMMIT")]:
        image = run.output / (name + ".vvp")
        run.command(name + "_compile", [str(iverilog), "-g2012", "-s", "tb_b1", "-o", str(image),
                                        "-D", "B1_MUTANT_" + name] + [str(path) for path in sources])
        raw = run.command(name + "_simulate", [str(vvp), str(image)], expected_exit=1)
        capture = ROOT / run.steps[-1]["stdout"]["path"]
        run.command(name + "_designated_reject", [sys.executable, "-B", "-X", "utf8", str(checker),
                                                  "--input", str(capture), "--expect-rtl-reject", diagnostic])
        mutants.append({"define": "B1_MUTANT_" + name, "compile_exit": 0, "simulation_exit": 1,
                        "diagnostic": diagnostic, "capture": identity(capture)})
    first_capture = ROOT / next(step["stdout"]["path"] for step in run.steps
                                if step["label"] == "N4_ROM1_mode0_simulate")
    run.command("checker_semantic_selftest", [sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover",
                                              "-s", str(checker.parent), "-p", "test_b1_checker.py", "-v"])
    run.command("checker_capture_counterexamples", [sys.executable, "-B", "-X", "utf8",
                                                      str(checker.parent / "b1_counterexamples.py"),
                                                      "--input", str(first_capture), "--output", str(run.output / "counterexamples")])
    summary = {"status": "B1_PROTOCOL_RTL_PASS_T061_PARTIAL", "tools": tools,
               "profiles": reports, "compiled_behavior_mutants": mutants,
               "logical_storage_major_arrays_not_tool_resources": [
                   {"N": n, "two_context_banks_bits": 2*n*635,
                    "identity_flags_configured_bits": n*(40+2+1),
                    "issued_tag_bank_and_masks_bits": n*(72+(n-1).bit_length()+2),
                    "control_values_valid_pedals_bits": 256*(29+1+1),
                    "fixture_ROM_bits": 256*16,
                    "FSM_pipeline_output_counters_and_decoders_included": False,
                    "frozen_sound_ROM_and_math_included": False,
                    "physical_FF_BSRAM_DSP": None}
                   for n in (4, 8, 16, 32)],
               "math": "Opaque XOR fixture only, not PCM or frozen L equivalence",
               "CC64": "256 isolated control/pedal snapshot storage; MIDI/Release scan and ACK service NOT implemented",
               "end_to_end_deadline": "UNKNOWN; observed durations include intentional TB stalls",
               "new_Gowin_allowance_used": False, "task_complete": False}
    (run.output / "b1_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def external(path):
    import hashlib
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
