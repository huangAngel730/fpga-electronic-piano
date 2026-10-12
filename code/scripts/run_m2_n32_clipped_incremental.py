"""Bounded new metadata verification, no old specialty replay/EDA/production."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

import prepare_138k_polyphony_resource as original

ROOT = original.ROOT
PREPARED = ROOT / "code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01"
CANDIDATE = ROOT / "code/rtl/common/m2_n32_clipped_candidate_20261012/b2d_event_audio_clipped.sv"
TB = ROOT / "code/tb/audio_out/m2_polyphony_frame_candidate_20261012/tb_n32_clipped_successor.sv"
SUITE = Path("D:/Gowin/oss-cad-suite")
SOURCE_PIN = "5f1a0d2e89fcb6f2d6ff97964e96953c2e9247e828536b521a43327d80c0a0ce"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_successor():
    frozen = ROOT / "code/rtl/common/polyphony_scaling_candidate/b2d_event_audio.sv"
    if digest(frozen) != SOURCE_PIN:
        raise ValueError("EXACT_ORIGINAL_B2D_SHA")
    text = CANDIDATE.read_text("utf-8")
    banner = "// M2 isolated metadata successor; original b2d, backend math and ROM readonly.\n// clipped is qualified by result_valid and retained with ID/stereo under HOLD.\n"
    substitutions = (
        (banner, ""),
        ("module b2d_event_audio_clipped #", "module b2d_event_audio #"),
        ("output logic late, clipped,", "output logic late,"),
        ("left<=0;right<=0;late<=0;clipped<=0;", "left<=0;right<=0;late<=0;"),
        ("if(stop) begin state<=DRAIN;result_valid<=0;\n`ifndef M2_CLIP_MUTANT_NO_CANCEL_CLEAR\n                clipped<=0;\n`endif\n            end", "if(stop) begin state<=DRAIN;result_valid<=0;end"),
        ("`ifdef M2_CLIP_MUTANT_ZERO\n                        clipped<=0;\n`else\n                        clipped<=be_clipped;\n`endif\n", ""))
    for new, old in substitutions:
        if text.count(new) != 1:
            raise ValueError("EXACT_METADATA_DIFF_COUNT:" + new[:30])
        text = text.replace(new, old)
    if text.encode("utf-8") != frozen.read_bytes():
        raise ValueError("SUCCESSOR_CHANGED_OTHER_LOGIC_OR_ALGORITHM")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    out = args.output.resolve()
    root = (ROOT / "code/output").resolve()
    if out == root or not out.is_relative_to(root) or out.exists():
        raise ValueError("REFUSE_OUTPUT_SCOPE_OR_EXISTS")
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    steps, error = [], None
    protected, before, after = [], {}, {}
    env = os.environ.copy()
    env["YOSYSHQ_ROOT"] = str(SUITE) + os.sep
    env["PATH"] = os.pathsep.join((str(SUITE / "bin"), str(SUITE / "lib"), env.get("PATH", "")))
    try:
        original.verify(PREPARED)
        verify_successor()
        prepared_hdl = [Path(n.attrib["path"]) for n in ET.parse(PREPARED / original.PROJECT).getroot().find("FileList")
                        if Path(n.attrib["path"]).suffix == ".sv" and Path(n.attrib["path"]).name != "b2l_resource_probe.sv"]
        extra = [ROOT / p for p in ("code/rtl/audio_out/pcm_result_hold.sv",
                 "code/rtl/audio_out/pcm_frame_buffer.sv", "code/rtl/common/pcm_clip_counter.sv",
                 "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv")]
        sources = prepared_hdl + extra + [CANDIDATE, TB]
        protected = sorted(p for p in PREPARED.rglob("*") if p.is_file()) + extra + [CANDIDATE, TB, Path(__file__), ROOT / "code/rtl/common/polyphony_scaling_candidate/b2d_event_audio.sv"]
        before = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
        for label, macro, expected, target in (
                ("normal", None, 0, "PASS N32_CLIPPED_METADATA"),
                ("bad_zero", "M2_CLIP_MUTANT_ZERO", 1, "PUBLIC_CLIPPED_NOT_EXACT_WIDE_SUM"),
                ("bad_cancel", "M2_CLIP_MUTANT_NO_CANCEL_CLEAR", 1, "CLIPPED_NOT_CLEARED_ON_CANCEL")):
            image = out / (label + ".vvp")
            command = [str(SUITE / "bin/iverilog.exe"), "-g2012", "-I", str(PREPARED / "include"),
                       "-s", "tb_n32_clipped_successor", "-o", str(image)]
            if macro:
                command += ["-D" + macro]
            command += [str(p) for p in sources]
            for step, cmd, wanted, diagnostic in (
                    (label + "_compile", command, 0, None),
                    (label + "_simulate", [str(SUITE / "bin/vvp.exe"), str(image)], expected, target)):
                remaining = 300 - (time.monotonic() - start)
                if remaining <= 0:
                    raise ValueError("TOTAL300_TIMEOUT")
                tick = time.monotonic()
                try:
                    process = subprocess.run(cmd, cwd=out, env=env, capture_output=True,
                                             timeout=min(90, remaining))
                    stdout, stderr, code = process.stdout, process.stderr, process.returncode
                except subprocess.TimeoutExpired as exc:
                    stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
                for stream, raw in (("stdout", stdout), ("stderr", stderr)):
                    (out / (step + "." + stream + ".bin")).write_bytes(raw)
                steps.append(dict(label=step, command=cmd, exit=code, expected=wanted,
                                  seconds=time.monotonic() - tick, timeout=code is None,
                                  stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                                  stderr_sha256=hashlib.sha256(stderr).hexdigest()))
                if code != wanted:
                    raise ValueError("UNEXPECTED_EXIT:" + step + ":" + str(code))
                if diagnostic and diagnostic.encode() not in stdout + stderr:
                    raise ValueError("TARGET_DIAGNOSTIC_MISSING:" + step)
        after = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
        verify_successor()
        if before != after:
            raise ValueError("SOURCE_ROM_ORIGINAL_CHANGED")
        if time.monotonic() - start >= 300:
            raise ValueError("TOTAL300_POSTCHECK_TIMEOUT")
    except (ValueError, OSError, ET.ParseError, subprocess.SubprocessError) as exc:
        error = str(exc)
        after = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected if p.is_file()}
    result = dict(status="N32_CLIPPED_INCREMENT_PASS" if error is None else "FAIL_PARTIAL",
                  exit_code=int(error is not None), error=error, steps=steps,
                  source_before=before, source_after=after, seconds=time.monotonic() - start,
                  original_source_sha256=SOURCE_PIN, exactly_reversible_metadata_diff=True,
                  tool_identity={name: digest(SUITE / "bin" / name) for name in ("iverilog.exe", "vvp.exe")},
                  total_bound=300, step_bound=90, automatic_retry=False,
                  old_specialties_replayed=False, audio_algorithm_or_ROM_changed=False,
                  mathematical_audio_reference_replayed=False, production_connected=False,
                  synthesized_candidate=False, physical_STA=False, device=False)
    (out / "receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "exit_code", "error", "seconds")}))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
