"""New Pro extension checks. Never programs devices or modifies baseline inputs."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project"
MODELSIM = Path("E:/FPGA/Bpan/modelsim/modelsim1/win64")
GOWIN = Path("D:/program/Gowin_work/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kind", choices=["audio", "physical", "build", "baseline", "static"])
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--full-playback", action="store_true",
                    help="physical simulation: real 2.016-second lead and complete six-event demo")
    args = ap.parse_args()
    out = args.output.resolve()
    allowed = (PROJECT / "extension_evidence" / "integration").resolve()
    if not out.is_relative_to(allowed):
        ap.error("output must be a new directory below project/extension_evidence/integration")
    out.mkdir(parents=True, exist_ok=False)
    receipt = {"kind": args.kind, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "status": "RUNNING", "steps": [], "device_operations": False,
               "physical_pll_simulated": args.kind in ("audio", "physical"),
               "dvi_serializer_simulation_boundary": args.kind == "physical",
               "hardware_pass": False, "c9_complete_claim": False}
    receipt["full_playback_requested"] = args.full_playback
    if args.kind == "audio":
        receipt["reference_scope"] = "preserved baseline core; both top instances use current FCW/delay leaves; original-leaf equivalence is separately evidenced by FCW_IDENTITY_R08_01 and DELAY_IDENTITY_R09_01 plus its corrected netlist review"
    if args.full_playback and args.kind != "physical":
        ap.error("--full-playback requires physical")
    source_paths = (PROJECT / "src").glob("*.sv") if args.kind == "audio" else (PROJECT / "src").rglob("*.sv")
    inputs = {p: sha(p) for p in source_paths}
    inputs.update({p: sha(p) for p in (PROJECT / "tb" / "extension_integration").glob("*.sv")})
    inputs.update({p: sha(p) for folder in (PROJECT / "include", PROJECT / "rom") for p in folder.rglob("*") if p.is_file()})
    # Actual GUI source closure includes vendor V/encrypted IP and constraints,
    # not only SystemVerilog. Preserve identities of included vendor headers.
    for entry in ET.parse(PROJECT / "pro_audio.gprj").findall("./FileList/File"):
        if entry.attrib.get("enable") == "1":
            p = Path(entry.attrib["path"]).resolve()
            inputs[p] = sha(p)
    for p in (PROJECT / "ip").rglob("*.v"):
        inputs[p] = sha(p)
    if args.kind == "physical":
        p = PROJECT / "tb/extension_visual/display/dvi_sim_boundary.sv"
        inputs[p] = sha(p)
    p = PROJECT / "impl/pro_audio_process_config.json"
    inputs[p] = sha(p)
    inputs.update({PROJECT / name: sha(PROJECT / name) for name in ("sine_wavetable.hex", "triangle_wavetable.hex")})
    for p in [Path(__file__), ROOT / "rebuild.tcl", ROOT / "options.tcl",
              PROJECT / "pro_audio.gprj", PROJECT / "pro_audio.cst", PROJECT / "pro_audio.sdc"]:
        inputs[p] = sha(p)
    receipt["source_sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"): h for p, h in inputs.items()}

    def save():
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def run(label, argv, cwd=out, env=None):
        command = [str(x) for x in argv]
        begin = time.monotonic()
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        with (out / (label + ".stdout.log")).open("wb") as stdout, (out / (label + ".stderr.log")).open("wb") as stderr:
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
            code = proc.wait()
        receipt["steps"].append({"label": label, "argv": command, "cwd": str(cwd),
                                 "started_utc": started, "exit_code": code,
                                 "elapsed_seconds": time.monotonic() - begin,
                                 "ended_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
        save()
        print(label, "exit", code, flush=True)
        if code:
            raise RuntimeError(f"{label}: exit {code}; preserve logs")
        return (out / (label + ".stdout.log")).read_text(encoding="utf-8", errors="replace")

    save()
    try:
        # Preserve exact executed source bytes, including failure versions.
        # Compilation still uses the real working copy; the final unchanged
        # check guards against a concurrent writer during execution.
        for p, expected in inputs.items():
            snapshot = out / "inputs" / p.relative_to(ROOT)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, snapshot)
            if sha(snapshot) != expected:
                raise RuntimeError("input changed before snapshot: " + str(p))
        if args.kind == "baseline":
            run("baseline_identity", [sys.executable, "-B", "-X", "utf8", ROOT / "verify_backup.py", "--baseline-only"])
        elif args.kind == "static":
            run("static_project", [sys.executable, "-B", "-X", "utf8", PROJECT / "extension_tools/check_project.py"])
        elif args.kind == "build":
            env = dict(os.environ)
            env["PRO_EXTENSION_BUILD_DIR"] = str(out / "gowin")
            env.pop("PRO_EXTENSION_SYNTHESIS_INPUT", None)
            receipt["tool_sha256"] = {str(GOWIN): sha(GOWIN)}
            run("gowin_all", [GOWIN, ROOT / "rebuild.tcl"], ROOT, env)
        else:
            receipt["tool_sha256"] = {str(MODELSIM / (x + ".exe")): sha(MODELSIM / (x + ".exe")) for x in ("vlib", "vlog", "vsim")}
            run("vlib", [MODELSIM / "vlib.exe", "work"])
            src = PROJECT / "src"
            sources = [src / "audio_defs_pkg.sv", src / "sustain_control_contract_pkg.sv"]
            sources += sorted(p for p in src.glob("*.sv") if p not in sources and p.name != "pro_audio_minimal_top.sv")
            fixture = PROJECT / "tb" / "extension_integration"
            sources.append(fixture / "clock_model.sv")
            sources.append(fixture / "gw5a_lut1_model.sv")
            if args.kind == "audio":
                original = ROOT / "baseline" / "A08" / "project" / "src" / "m3_pro_audio_core_r10.sv"
                receipt["baseline_reference_sha256"] = sha(original)
                old = original.read_text(encoding="utf-8")
                old = old.replace("M3_PRO_AUDIO_CORE_R10_SV", "M3_PRO_AUDIO_CORE_REFERENCE_SV")
                if old.count("module m3_pro_audio_core_r10 #(") != 1:
                    raise ValueError("baseline module identity")
                old = old.replace("module m3_pro_audio_core_r10 #(", "module m3_pro_audio_core_baseline #(")
                ref = out / "baseline_core_reference.sv"
                ref.write_text(old, encoding="utf-8", newline="\n")
                sources += [ref, fixture / "tb_audio_extension.sv"]
                top = "tb_audio_extension"
            else:
                demo = PROJECT / "extension_docs" / "demo_a4_c5.records.bin"
                raw_records = demo.read_bytes()
                if len(raw_records) != 48:
                    raise ValueError("demo importer output must have six complete records")
                (out / "demo_records.hex").write_text("".join(f"{b:02x}\n" for b in raw_records), encoding="ascii")
                receipt["demo_record_sha256"] = sha(demo)
                sources += sorted((src / "extension_transfer").rglob("*.sv"))
                sources += sorted((src / "extension_visual").rglob("*.sv"))
                # Vendor rgb2dvi is GOWIN-key encrypted. ModelSim checks the
                # real transport/audio/raster/scene up to this explicit PHY
                # boundary. Only the commercial synthesis uses the true IP.
                sources.append(PROJECT / "tb" / "extension_visual" / "display" / "dvi_sim_boundary.sv")
                sources += [src / "pro_audio_minimal_top.sv", fixture / "tb_pro_extension.sv"]
                top = "tb_pro_extension"
            run("vlog", [MODELSIM / "vlog.exe", "-sv", "-mfcu", "+incdir+" + str(PROJECT / "include"), *sources])
            # Keep the run's ROM inputs local; $readmemh paths are unchanged.
            shutil.copytree(PROJECT / "rom", out / "rom")
            for name in ("sine_wavetable.hex", "triangle_wavetable.hex"):
                shutil.copyfile(PROJECT / name, out / name)
            plusargs = ["+FULL_PLAYBACK"] if args.full_playback else []
            log = run("vsim", [MODELSIM / "vsim.exe", "-c", "-wlf", out / "simulation.wlf", "work." + top, *plusargs,
                               "-do", "onerror {quit -code 2}; onbreak {quit -code 3}; run -all; quit -code 0"])
            token = "INTEGRATION_AUDIO_TEST_COMPLETE" if args.kind == "audio" else "PRO_EXTENSION_TEST_COMPLETE"
            if token not in log:
                raise RuntimeError("simulation did not reach final completion marker")
        # EDA exit0 is not a timing sign-off. The coordinator must inspect
        # setup/hold/recovery/removal/pulse and exception coverage separately.
        receipt["status"] = "TOOL_COMPLETED_UNREVIEWED" if args.kind == "build" else "PASS"
        if args.kind == "build":
            receipt["timing_review"] = "NOT_REVIEWED"
            receipt["level"] = "EDA_TOOL_PROCESS_ONLY"
    except Exception as exc:
        receipt["status"] = "FAIL"
        receipt["error"] = str(exc)
        print(str(exc), file=sys.stderr)
    finally:
        # Other owners can legitimately add source files while this isolated
        # audio test runs. Require the exact executed inputs to remain stable.
        receipt["executed_inputs_unchanged"] = all(p.is_file() and sha(p) == h for p, h in inputs.items())
        if not receipt["executed_inputs_unchanged"]:
            receipt["status"] = "FAIL"
            receipt["error"] = "executed input changed during run"
        receipt["ended_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save()
    return int(receipt["status"] not in ("PASS", "TOOL_COMPLETED_UNREVIEWED"))


if __name__ == "__main__":
    raise SystemExit(main())
