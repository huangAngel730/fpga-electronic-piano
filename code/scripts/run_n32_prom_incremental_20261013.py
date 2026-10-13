"""Bounded GW5A model ROM/component and N32 public interface equivalence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

import prepare_n32_prom_candidate_20261013 as candidate

ROOT = candidate.ROOT
SUITE = Path("D:/Gowin/oss-cad-suite")
TB = ROOT / "code/tb/audio_out/m2_polyphony_frame_candidate_20261012/tb_n32_prom_equivalence.sv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    out = args.output.resolve()
    if out.exists() or out == ROOT / "code/output" or not out.is_relative_to(ROOT / "code/output"):
        raise ValueError("REFUSE_OUTPUT_SCOPE_OR_EXISTS")
    out.mkdir(parents=True)
    start = time.monotonic()
    env = os.environ.copy()
    env["YOSYSHQ_ROOT"] = str(SUITE) + os.sep
    env["PATH"] = os.pathsep.join((str(SUITE / "bin"), str(SUITE / "lib"), env.get("PATH", "")))
    protected = sorted(p for root in (candidate.BASE, candidate.DEST) for p in root.rglob("*") if p.is_file())
    protected += [TB, candidate.VENDOR, Path(candidate.__file__), Path(__file__)]
    before = {str(p): sha(p) for p in protected}
    steps, error = [], None
    def run(label, cmd, expected=0, diagnostic=None):
        remaining = 300 - (time.monotonic() - start)
        if remaining <= 0:
            raise ValueError("TOTAL300_TIMEOUT")
        tick = time.monotonic()
        try:
            p = subprocess.run([str(x) for x in cmd], cwd=out, env=env, capture_output=True, timeout=min(90, remaining))
            stdout, stderr, code = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
        for name, raw in (("stdout", stdout), ("stderr", stderr)):
            (out / (label + "." + name + ".bin")).write_bytes(raw)
        steps.append(dict(label=label, command=list(map(str, cmd)), exit=code, expected=expected,
                          seconds=time.monotonic() - tick, stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest()))
        if code != expected or diagnostic and diagnostic.encode() not in stdout + stderr:
            raise ValueError("STEP_FAILED:" + label + ":" + str(code))
    try:
        expected_files, _ = candidate.expected()
        if {p.name: p.read_bytes() for p in candidate.DEST.iterdir() if p.is_file()} != expected_files:
            raise ValueError("EXACT_GENERATED_CANDIDATE")
        rom_dir = out / "rom"
        rom_dir.mkdir()
        for p in (candidate.BASE / "rom").iterdir():
            (rom_dir / p.name).write_bytes(p.read_bytes())
        # Verbatim targeted GW5A definitions extracted only to avoid unrelated
        # primitives being elaborated. Byte identity and full vendor SHA retained.
        library = candidate.VENDOR.read_text(encoding="utf-8")
        slices = []
        for module in ("GSR", "pROM"):
            m = re.search(r"^module " + module + r" \([^\n]*\);[\s\S]*?^endmodule[^\n]*", library, re.M)
            if not m:
                raise ValueError("VENDOR_MODULE_EXTRACTION:" + module)
            slices.append(m.group(0))
        vendor = out / "vendor_GW5A_GSR_pROM.v"
        vendor.write_text("`timescale 1ns/1ps\n" + "\n\n".join(slices) + "\n", encoding="utf-8", newline="\n")
        (out / "vendor_extract_identity.json").write_text(json.dumps(dict(original_sha256=sha(candidate.VENDOR), extracted_sha256=sha(vendor), modules=["GSR", "pROM"], source_verbatim=True), indent=2) + "\n", encoding="utf-8")
        wrappers = [candidate.DEST / ("m2_prom_" + n + ".sv") for n in ("gain", "oct", "sub", "lfo", "wave")]
        source = wrappers + [candidate.BASE / "sources/adsr_piano_envelope.sv", candidate.BASE / "sources/pitch_mod_fcw_pipeline.sv",
                             candidate.DEST / "m2_adsr_piano_prom.sv", candidate.DEST / "m2_pitch_mod_prom.sv", vendor, TB]
        iv = SUITE / "bin/iverilog.exe"
        vvp = SUITE / "bin/vvp.exe"
        for label, changed in (("normal_component", None), ("bad_gain_word", "gain"), ("bad_lfo_latency", "lfo")):
            sources = list(source)
            if changed:
                original = candidate.DEST / ("m2_prom_" + changed + ".sv")
                text = original.read_text()
                if changed == "gain":
                    m = re.search(r"(\.INIT_RAM_00\(256'h)([0-9a-f]{64})(\))", text)
                    modified = text[:m.start(2)] + format(int(m[2], 16) ^ 1, "064x") + text[m.end(2):]
                else:
                    modified = candidate.replace_once(text, ".READ_MODE(1'b0)", ".READ_MODE(1'b1)")
                altered = out / (label + ".sv")
                altered.write_text(modified, encoding="utf-8", newline="\n")
                sources[sources.index(original)] = altered
            image = out / (label + ".vvp")
            run(label + "_compile", [iv, "-g2012", "-s", "tb_n32_prom_equivalence", "-o", image, *sources])
            run(label + "_simulate", [vvp, image], int(changed is not None), "PROM_FULL_ADDRESS_OR_SINGLE_CYCLE_MISMATCH" if changed else "PASS PROM_VENDOR_ALL_ADDRESS_CE_AND_COMPONENT_EQUIVALENCE")
        # New full-N32 candidate versus frozen original, same short directed
        # metadata fixture. Only candidate implementation and GSR are changed.
        original_tb = ROOT / "code/tb/audio_out/m2_polyphony_frame_candidate_20261012/tb_n32_clipped_successor.sv"
        text = original_tb.read_text()
        text = candidate.replace_once(text, "b2d_event_audio_clipped #", "m2_b2d_event_audio_prom #")
        text = candidate.replace_once(text, "    import audio_defs_pkg::*;", "    import audio_defs_pkg::*;\n    GSR GSR(.GSRI(1'b1));")
        system_tb = out / "tb_n32_prom_public.sv"
        system_tb.write_text(text, encoding="utf-8", newline="\n")
        listing = ET.parse(candidate.BASE / "n32_r1_resource.gprj").getroot().find("FileList")
        old_hdl = [Path(f.attrib["path"]) for f in listing if f.attrib["path"].endswith(".sv") and not f.attrib["path"].endswith("b2l_resource_probe.sv")]
        new_hdl = sorted(candidate.DEST.glob("*.sv"))
        transport = [ROOT / p for p in ("code/rtl/audio_out/pcm_result_hold.sv", "code/rtl/audio_out/pcm_frame_buffer.sv", "code/rtl/common/pcm_clip_counter.sv", "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv")]
        protected += [original_tb, *transport]
        before.update({str(p): sha(p) for p in [original_tb, *transport]})
        run("N32_public_compile", [iv, "-g2012", "-I", candidate.BASE / "include", "-s", "tb_n32_clipped_successor", "-o", out / "N32.vvp", *old_hdl, *new_hdl, *transport, vendor, system_tb])
        run("N32_public_simulate", [vvp, out / "N32.vvp"], 0, "PASS N32_CLIPPED_METADATA")
        if time.monotonic() - start >= 300:
            raise ValueError("TOTAL300_POSTCHECK")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        error = str(exc)
    after = {str(p): sha(p) for p in protected if p.is_file()}
    if before != after:
        error = (error or "") + "; SOURCE_VENDOR_ROM_DRIFT"
    receipt = dict(status="PROM_INCREMENT_EQUIVALENCE_PASS" if error is None else "FAIL_PARTIAL", exit_code=int(error is not None), error=error,
                   seconds=time.monotonic() - start, total_limit=300, per_step=90, steps=steps,
                   sources_before=before, sources_after=after, new_EDA_calls=0, synthesized=False, physical_STA="NOT_RUN",
                   production_connected=False, old_specialties_replayed=False,
                   changed_implementation_new_equivalence_required=True,
                   vendor_startup_difference="pROM output initializes0; behavioral arrays may startX. Compare after first CE/valid only.")
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("status", "exit_code", "error", "seconds")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
