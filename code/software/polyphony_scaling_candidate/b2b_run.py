"""Bounded N4 event/router/B1/real math integration. No device/synthesis."""
import json
import os
import re
import sys

from b1_run import external
from inventory import FROZEN, ROOT


def sources():
    return [FROZEN / "sources" / name for name in (
        "audio_defs_pkg.sv", "sustain_control_contract_pkg.sv", "note_pitch.sv",
        "voice_allocator_4.sv", "sustain_controller.sv", "polyphonic_event_router.sv",
        "performance_control_snapshot.sv", "adsr_piano_envelope.sv",
        "pitch_mod_fcw_pipeline.sv")] + [
        ROOT / "code/rtl/common/polyphony_scaling_candidate" / name for name in (
            "b1_statebank.sv", "b1_scheduler.sv", "b2_audio_backend.sv", "b2b_event_audio.sv")] + [
        ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b2b_event_audio.sv"]


def compile_sources(output):
    # Icarus' MSYS preprocessor cannot open the Windows drive-letter absolute
    # include embedded in frozen L. Relocate ONLY that literal in a fresh build
    # carrier; prove reversing the substitution gives the exact frozen bytes.
    original = FROZEN / "sources/sustain_controller.sv"
    raw = original.read_bytes()
    old = ('"' + FROZEN.as_posix() + '/include/sustain_controller_ports.svh"').encode()
    new = b'"sustain_controller_ports.svh"'
    if raw.count(old) != 1:
        raise ValueError("FROZEN_INCLUDE_RELOCATION_COUNT")
    relocated = raw.replace(old, new)
    if relocated.replace(new, old) != raw:
        raise ValueError("FROZEN_INCLUDE_RELOCATION_REVERSE")
    carrier = output / "sustain_controller_include_carrier.sv"
    carrier.write_bytes(relocated)
    allocator = FROZEN / "sources/voice_allocator_4.sv"
    raw_alloc = allocator.read_bytes()
    text = raw_alloc.decode("utf-8")
    declaration = "voice_slot_t slots [0:3];"
    if text.count(declaration) != 1:
        raise ValueError("ALLOCATOR_DECLARATION")
    text = text.replace(declaration, "logic [19:0] slots [0:3];")
    fields = {"note_active": "19", "in_release": "18", "source": "17:14",
              "channel": "13:10", "note": "9:2", "age": "1:0"}
    substitutions = []
    pattern = r"slots\[(i|target_slot)\]\.([a-z_]+)"
    def expand(match):
        old = match.group(0)
        new = f"slots[{match[1]}][{fields[match[2]]}]"
        substitutions.append((old, new))
        return new
    text = re.sub(pattern, expand, text)
    reverse = text
    for old_ref, new_ref in reversed(substitutions):
        reverse = reverse.replace(new_ref, old_ref)
    reverse = reverse.replace("logic [19:0] slots [0:3];", declaration)
    if reverse.encode("utf-8") != raw_alloc:
        raise ValueError("ALLOCATOR_SYNTAX_EXPANSION_NOT_REVERSIBLE")
    alloc_carrier = output / "voice_allocator_packed_carrier.sv"
    alloc_carrier.write_bytes(text.encode("utf-8"))
    from inventory import identity
    (output / "compile_carriers.json").write_text(json.dumps({
        "scope": "literal include relocation and packed struct field syntax expansion ONLY",
        "struct_width": 20, "field_bits": fields, "substitutions": substitutions,
        "frozen": [identity(p) for p in (original, allocator)],
        "compiled": [identity(p) for p in (carrier, alloc_carrier)],
        "exact_reverse_byte_identity": True}, indent=2) + "\n", encoding="utf-8")
    return [carrier if p == original else alloc_carrier if p == allocator else p for p in sources()]


def run_b2b(run, args):
    iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
    suite = iv.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite) + os.sep}
    run.extra_path = [str(suite / "bin"), str(suite / "lib")]
    run.command("iverilog_version", [str(iv), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT / "code/software/polyphony_scaling_candidate"
    compiled = compile_sources(run.output)
    base = [str(iv), "-g2012", "-I", str(FROZEN / "include"), "-s", "tb_b2b_event_audio"]
    reports = []
    captures = []
    for response, long_case in ((1, 1), (3, 0)):
        stem = f"B2B_N4_R{response}_long{long_case}"
        image, report = run.output / (stem + ".vvp"), run.output / (stem + ".json")
        run.command(stem + "_compile", base + ["-o", str(image), f"-DB2B_RESPONSE={response}",
                    f"-DB2B_LONG={long_case}"] + [str(p) for p in compiled])
        run.command(stem + "_simulate", [str(vvp), str(image)])
        capture = ROOT / run.steps[-1]["stdout"]["path"]
        captures.append(capture)
        run.command(stem + "_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2b_check.py"),
                                       "--input", str(capture), "--output", str(report)])
        reports.append(json.loads(report.read_text(encoding="utf-8")))
    for define, reason in (("B1_MUTANT_IGNORE_GENERATION", "B2B_STALE_GENERATION_ACCEPTED"),
                           ("B2_MUTANT_GAIN_ZERO", "MATH_GAIN_PCM")):
        image = run.output / (define + ".vvp")
        run.command(define + "_compile", base + ["-o", str(image), "-D" + define] + [str(p) for p in compiled])
        raw = run.command(define + "_simulate", [str(vvp), str(image)], expected_exit=1 if define.startswith("B1") else 0)
        if define.startswith("B1"):
            if reason.encode() not in raw or b"WATCHDOG" in raw:
                raise ValueError("WRONG_GENERATION_MUTANT_REJECTION")
        else:
            capture = ROOT / run.steps[-1]["stdout"]["path"]
            raw = run.command(define + "_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2b_check.py"),
                                                  "--input", str(capture)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_GAIN_MUTANT_REJECTION")
    run.command("B2B_checker_negative_unit", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2b_negatives.py"),
                                             "--input", str(captures[1]), "--output", str(run.output / "negatives")])
    result = {"status": "B2B_N4_EVENT_AUDIO_PASS_T061_PARTIAL", "profiles": reports,
              "tools": {"iverilog": external(iv), "vvp": external(vvp)},
              "task_complete": False, "N8_N16_N32_event_router": "NOT_IMPLEMENTED",
              "frozen_L_whole_clock_path_equivalence": False, "physical_STA": "NOT_RUN",
              "new_Gowin_allowance_used": False}
    (run.output / "b2b_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
