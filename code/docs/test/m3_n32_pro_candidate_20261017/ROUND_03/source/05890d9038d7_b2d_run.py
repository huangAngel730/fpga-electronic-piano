"""N16 successor: identity-control repair, bounded RTL/replay, N8 retained."""
import base64
import hashlib
import io
import json
import os
import sys
import zipfile

from b1_run import external
from b2c_run import sources as n8_sources
from inventory import ROOT


def sources():
    replacements = {"b2c_event_audio.sv": "b2d_event_audio.sv",
                    "b2c_control_snapshot.sv": "b2d_control_snapshot.sv",
                    "tb_b2c_event_audio.sv": "tb_b2d_event_audio.sv"}
    return [p.with_name(replacements[p.name]) if p.name in replacements else p for p in n8_sources()]


def run_b2d(run, args):
    iv, vvp = args.iverilog.resolve(), args.vvp.resolve()
    suite = iv.parent.parent
    run.extra_env = {"YOSYSHQ_ROOT": str(suite) + os.sep}
    run.extra_path = [str(suite / "bin"), str(suite / "lib")]
    run.command("iverilog_version", [str(iv), "-V"])
    run.command("vvp_version", [str(vvp), "-V"])
    candidate = ROOT / "code/software/polyphony_scaling_candidate"
    # Replay one already sealed short N8 log without rerunning its RTL. The
    # new reference's optional N16 schema must not alter accepted N8 results.
    package = ROOT / "code/docs/hardware/polyphony_scaling_v1/B2C_20261010"
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    sealed = base64.b64decode((package / "evidence.zip.b64").read_bytes(), validate=True)
    if hashlib.sha256(sealed).hexdigest() != manifest["zip_sha256"]:
        raise ValueError("OLD_N8_SEAL_SHA")
    with zipfile.ZipFile(io.BytesIO(sealed)) as archive:
        receipt = json.loads(archive.read(manifest["qualified_receipt"]))
        step = next(s for s in receipt["steps"] if s["label"] == "B2C_N8_R3_long0_simulate")
        raw = archive.read(step["stdout"]["path"])
        prior_report = next(n for n in archive.namelist() if n.endswith("/B2C_N8_R3_long0.json"))
        expected = json.loads(archive.read(prior_report))
    if hashlib.sha256(raw).hexdigest() != step["stdout"]["sha256"]:
        raise ValueError("OLD_N8_CAPTURE_SHA")
    old_capture = run.output / "sealed_N8_R3.txt"
    old_capture.write_bytes(raw)
    old_report = run.output / "sealed_N8_R3_replay.json"
    run.command("N8_sealed_short_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2c_check.py"),
                "--input", str(old_capture), "--output", str(old_report)])
    observed = json.loads(old_report.read_text(encoding="utf-8"))
    if any(observed[key] != value for key, value in expected.items()):
        raise ValueError("N8_SEALED_REFERENCE_REGRESSION")
    from inventory import FROZEN
    base = [str(iv), "-g2012", "-I", str(FROZEN / "include"), "-s", "tb_b2d_event_audio"]
    alias_sources = [FROZEN / "sources/audio_defs_pkg.sv",
                     ROOT / "code/rtl/common/polyphony_scaling_candidate/b1_statebank.sv",
                     ROOT / "code/rtl/common/polyphony_scaling_candidate/b2d_control_snapshot.sv",
                     ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b2d_identity_alias.sv"]
    for mutant in (False, True):
        label = "identity_alias_mutant" if mutant else "identity_alias_normal"
        image = run.output / (label + ".vvp")
        command = [str(iv), "-g2012", "-I", str(FROZEN / "include"), "-s", "tb_b2d_identity_alias", "-o", str(image)]
        if mutant:
            command += ["-DB2D_MUTANT_MASK_IDLE_CONTROL"]
        run.command(label + "_compile", command + [str(p) for p in alias_sources])
        raw = run.command(label + "_simulate", [str(vvp), str(image)], expected_exit=1 if mutant else 0)
        expected = b"B2D_ACTIVE_IDENTITY_CONTROL_CLOBBER" if mutant else b"B2D_IDENTITY_ALIAS_PASS cases=3 active_reads=4"
        if expected not in raw or b"WATCHDOG" in raw:
            raise ValueError("WRONG_IDENTITY_ALIAS_RESULT")
    reports, captures = [], {}
    # Exercise short configurations before spending the long-run allowance.
    for response, long_case in ((3, 0), (32, 0), (64, 0), (1, 1)):
        stem = f"B2D_N16_R{response}_long{long_case}"
        image, report = run.output / (stem + ".vvp"), run.output / (stem + ".json")
        if args.reuse_b2d_run:
            run.command(stem + "_reuse_actual_RTL", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2d_reuse.py"),
                        "--receipt", str(args.reuse_b2d_run), "--response", str(response), "--long", str(long_case),
                        "--output", str(run.output / (stem + "_provenance"))])
        else:
            run.command(stem + "_compile", base + ["-o", str(image), "-DB2C_N=16",
                        f"-DB2C_RESPONSE={response}", f"-DB2C_LONG={long_case}"] + [str(p) for p in sources()])
            run.command(stem + "_simulate", [str(vvp), str(image)])
        capture = ROOT / run.steps[-1]["stdout"]["path"]
        captures[response] = capture
        run.command(stem + "_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2d_check.py"),
                                       "--input", str(capture), "--output", str(report)])
        result = json.loads(report.read_text(encoding="utf-8"))
        if result["sample_deadline_qualified"] != (response != 64):
            raise ValueError("UNEXPECTED_DEADLINE_CLASSIFICATION")
        reports.append(result)
    run.command("N16_complete_negatives", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2d_tests.py"),
                "--normal", str(captures[3]), "--slow", str(captures[64]),
                "--output", str(run.output / "checker_tests")])
    for define, reason in (("B1_MUTANT_IGNORE_GENERATION", "B2B_STALE_GENERATION_ACCEPTED"),
                           ("B2_MUTANT_GAIN_ZERO", "MATH_GAIN_PCM")):
        image = run.output / (define + ".vvp")
        run.command(define + "_compile", base + ["-o", str(image), "-DB2C_N=16", "-D" + define]
                    + [str(p) for p in sources()])
        raw = run.command(define + "_simulate", [str(vvp), str(image)], expected_exit=1 if define.startswith("B1") else 0)
        if define.startswith("B1"):
            if reason.encode() not in raw or b"WATCHDOG" in raw:
                raise ValueError("WRONG_GENERATION_MUTANT_REJECTION")
        else:
            capture = ROOT / run.steps[-1]["stdout"]["path"]
            raw = run.command(define + "_replay", [sys.executable, "-B", "-X", "utf8", str(candidate / "b2d_check.py"),
                                                  "--input", str(capture)], expected_exit=1)
            if reason.encode() not in raw:
                raise ValueError("WRONG_GAIN_MUTANT_REJECTION")
    result = dict(status="B2D_N16_EVENT_AUDIO_PASS_T061_PARTIAL", profiles=reports,
                  tools=dict(iverilog=external(iv), vvp=external(vvp)), task_complete=False,
                  N8_originals_unchanged=True, N16_identity_control_successor=True,
                  identity_alias_public_bank_cases=3, identity_alias_active_reads=4,
                  compiled_RTL_negatives=3, actual_RTL_capture_reuse=bool(args.reuse_b2d_run),
                  N32_event_router="NOT_VERIFIED", physical_STA="NOT_RUN",
                  sealed_N8_short_reference_unchanged=True,
                  new_Gowin_allowance_used=False, R64="EXPECTED_DEADLINE_MISS_NOT_QUALIFIED")
    (run.output / "b2d_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
