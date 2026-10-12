"""One short frozen N32/public-frame interface test; no EDA or old math replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

import prepare_138k_polyphony_selectorless_20261012 as successor

ROOT = Path(__file__).resolve().parents[2]
SUITE = Path("D:/Gowin/oss-cad-suite")
NEW_SOURCES = [ROOT / p for p in (
    "code/rtl/audio_out/pcm_result_hold.sv",
    "code/rtl/audio_out/pcm_frame_buffer.sv",
    "code/rtl/common/pcm_clip_counter.sv",
    "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv",
    "code/tb/audio_out/m2_polyphony_frame_candidate_20261012/tb_n32_frame_interface.sv")]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    out = args.output.resolve()
    output_root = (ROOT / "code/output").resolve()
    if out == output_root or not out.is_relative_to(output_root) or out.exists():
        raise ValueError("REFUSE_OUTPUT_SCOPE_OR_EXISTS")
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    steps, error, before, after = [], None, {}, {}
    env = os.environ.copy()
    env["YOSYSHQ_ROOT"] = str(SUITE) + os.sep
    env["PATH"] = os.pathsep.join((str(SUITE / "bin"), str(SUITE / "lib"), env.get("PATH", "")))
    protected = []
    try:
        static = successor.verify()
        (out / "selectorless_static.json").write_text(
            json.dumps(static, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        project = successor.SOURCE / successor.original.PROJECT
        prepared = [Path(f.attrib["path"]) for f in ET.parse(project).getroot().find("FileList")
                    if Path(f.attrib["path"]).suffix == ".sv"]
        prepared = [p for p in prepared if p.name != "b2l_resource_probe.sv"]
        protected = sorted(p for p in successor.SOURCE.rglob("*") if p.is_file()) + NEW_SOURCES + [Path(__file__)]
        before = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
        sources = prepared + NEW_SOURCES
        for label, macro, expected, target in (
                ("real_interface", None, 0, "PASS N32_PUBLIC_FRAME_INTERFACE"),
                ("bad_pcm_connection", "M2_N32_MUTANT_ZERO_PCM", 1, "N32_PUBLIC_PCM_TRANSPORT_MISMATCH")):
            image = out / (label + ".vvp")
            command = [str(SUITE / "bin/iverilog.exe"), "-g2012", "-I", str(successor.SOURCE / "includes"),
                       "-s", "tb_n32_frame_interface", "-o", str(image)]
            if macro:
                command.append("-D" + macro)
            command += [str(p) for p in sources]
            for step, cmd, wanted, diagnostic in (
                    (label + "_compile", command, 0, None),
                    (label + "_simulate", [str(SUITE / "bin/vvp.exe"), str(image)], expected, target)):
                remaining = 180 - (time.monotonic() - start)
                if remaining <= 0:
                    raise ValueError("TOTAL180_TIMEOUT")
                tick = time.monotonic()
                try:
                    result = subprocess.run(cmd, cwd=out, env=env, capture_output=True,
                                            timeout=min(30, remaining))
                    stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
                except subprocess.TimeoutExpired as exc:
                    stdout, stderr, exit_code = exc.stdout or b"", exc.stderr or b"", None
                for stream, raw in (("stdout", stdout), ("stderr", stderr)):
                    (out / (step + "." + stream + ".bin")).write_bytes(raw)
                steps.append(dict(label=step, command=cmd, exit=exit_code, expected=wanted,
                                  seconds=time.monotonic() - tick, timeout=exit_code is None,
                                  stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                                  stderr_sha256=hashlib.sha256(stderr).hexdigest()))
                if exit_code != wanted:
                    raise ValueError("UNEXPECTED_EXIT:" + step + ":" + str(exit_code))
                if diagnostic and diagnostic.encode() not in stdout + stderr:
                    raise ValueError("TARGET_DIAGNOSTIC_MISSING:" + step)
        after = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected}
        if before != after:
            raise ValueError("SOURCE_DRIFT")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        error = str(exc)
        if protected:
            after = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected if p.is_file()}
    receipt = dict(status="PUBLIC_INTERFACE_PASS_CLIP_UNVERIFIED" if error is None else "FAIL",
                   exit_code=0 if error is None else 1, error=error, steps=steps,
                   source_before=before, source_after=after, total_bound=180, step_bound=30,
                   seconds=time.monotonic() - start,
                   tool_identity={n: digest(SUITE / "bin" / n) for n in ("iverilog.exe", "vvp.exe")},
                   N=32, response=1, original_frozen_sha256=successor.FROZEN_SHA,
                   real_public_ports=True, clip_metadata_public=False, clip_input_in_test=0,
                   math_recomputed=False, old_specialties_replayed=False, EDA_runs=0,
                   resources="UNKNOWN", physical_STA="NOT_RUN", production_connected=False,
                   automatic_retry=False)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("status", "exit_code", "error", "seconds")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
