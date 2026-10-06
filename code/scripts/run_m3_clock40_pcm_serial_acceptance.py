"""Sealed L PCM24 -> physical PT8211 serial acceptance; writes only new bench."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "code/tb/audio_out/m3_clock40_pcm_serial_acceptance"
TRIAL = ROOT / "code/rtl/138K_try/hold_trials_20261005"
ZIP_SHA = "c4eeefac8c28e3ebc01475177601a65abfc0da6f314b1c80f94b223ee9fa5b50"
DEFAULT_ZIP = TRIAL / "M3_138K_Hold修复证据_20261005.zip"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def io_path(path):
    """Extended Windows paths for deep, read-only snapshot identity checks."""
    value = str(path.absolute())
    return Path("\\\\?\\" + value) if os.name == "nt" and len(value) >= 248 else path


def checker():
    spec = importlib.util.spec_from_file_location("serial_scoreboard", BENCH / "scoreboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract(archive_path, out, candidate):
    if sha(archive_path.read_bytes()) != ZIP_SHA:
        raise ValueError("SEALED_ZIP_SHA")
    identities = {}
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("SEALED_ZIP_CRC")
        prefix = candidate + "/"
        for name in archive.namelist():
            relative = name.removeprefix(prefix)
            if not name.startswith(prefix) or not relative.startswith(("sources/", "include/", "rom/", "constraints/")):
                continue
            path = out / "sealed" / relative
            if ".." in Path(relative).parts or path.resolve().is_relative_to(out.resolve()) is False:
                raise ValueError("ZIP_PATH")
            data = archive.read(name)
            identities[relative] = sha(data)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        gprj = archive.read(prefix + "audio_visual_coexistence_top.gprj")
    if len(identities) != 56:
        raise ValueError("SEALED_INPUT_COUNT")
    # Source directory is immutable. Only a separately named simulation copy
    # receives necessary ROM/include path redirection, never logic changes.
    simulation = out / "sim_sources"
    simulation.mkdir()
    transformed = {}
    for relative, digest in identities.items():
        original = out / "sealed" / relative
        if sha(original.read_bytes()) != digest:
            raise ValueError("EXTRACTION_SHA")
        if relative.startswith("sources/"):
            data = original.read_bytes()
            text = data.decode("utf-8")
            old_root = (TRIAL / candidate).as_posix()
            redirected = text.replace(old_root, (out / "sealed").as_posix())
            # Existing headers use absolute frozen paths; root-only redirects
            # must be the only source change in the positive simulation copy.
            path = simulation / original.name
            path.write_text(redirected, encoding="utf-8", newline="")
            transformed[relative] = {"raw_sha256": digest, "simulation_sha256": sha(path.read_bytes()),
                                     "path_redirect_count": text.count(old_root)}
    ordered = []
    for entry in ET.fromstring(gprj).iter("File"):
        if entry.attrib.get("type") == "file.verilog":
            ordered.append(simulation / Path(entry.attrib["path"]).name)
    # We exercise the original complete AUDIO closure, not video/PLL recovery.
    # Uninstantiated visual top-levels/IP are not compiled or replaced by stubs.
    exclude = {"audio_visual_coexistence_top.sv", "TMDS_PLL_800_600_60.v", "DVI_TX_Top.v",
               "audio_visual_display_probe.sv", "m3_visualizer.sv", "visual_scene_renderer.sv",
               "visual_hit_flash.sv", "visual_live_state.sv", "visual_score_tracker.sv",
               "visual_event_bridge.sv", "video_scan_timing.sv", "visual_mailbox_cdc.sv", "visual_control_bridge.sv"}
    ordered = [p for p in ordered if p.name not in exclude]
    dump(out / "source_manifest.json", {"archive_sha256": ZIP_SHA, "candidate": candidate,
         "sealed_input_sha256": identities, "simulation_sources": transformed,
         "compiled_sources": [p.name for p in ordered], "gprj_sha256": sha(gprj)})
    return ordered


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, default=DEFAULT_ZIP)
    cli.add_argument("--candidate", choices=["L_locations_guard065", "I_hold_locations"], default="L_locations_guard065")
    cli.add_argument("--modelsim-bin", type=Path, default=Path("E:/FPGA/Bpan/modelsim/modelsim1/win64"))
    cli.add_argument("--check-capture", type=Path)
    cli.add_argument("--scenario", choices=["normal", "diagnostic"], default="normal")
    cli.add_argument("--repo-gate", action="store_true")
    args = cli.parse_args()
    oracle = checker()
    if args.check_capture:
        try:
            print(json.dumps(oracle.check_capture(args.check_capture, args.scenario), indent=2))
            return 0
        except (OSError, ValueError, IndexError, KeyError) as error:
            print("REJECT", error)
            return 1
    runtime = BENCH / "runtime"
    runtime.mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="run_", dir=runtime))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TEMP=str(out), TMP=str(out))
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    receipt = {"passed": False, "output": str(out), "runs": {}, "results": {},
               "scope": "L2/L3 audio subsystem only; no Gowin/PLL/electrical/screen/board claim"}
    tools = {n: args.modelsim_bin / (n + ".exe") for n in ["vlib", "vlog", "vsim"]}

    def run(label, command, cwd, timeout=900):
        try:
            result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                                    capture_output=True, timeout=timeout, check=False)
            data, code = result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            data = (error.stdout or b"") + (error.stderr or b"") + b"\nRUNNER_TIMEOUT\n"
            code = 124
        log = out / (label + ".log")
        log.write_bytes(data)
        receipt["runs"][label] = {"command": list(map(str, command)), "cwd": str(cwd),
                                  "exit_code": code, "log_sha256": sha(data)}
        print(label, "exit", code, flush=True)
        return code, data.decode("utf-8", errors="replace")

    try:
        sources = extract(args.archive.resolve(), out, args.candidate)
        receipt["test_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
                                  for p in [*BENCH.glob("*.sv"), *BENCH.glob("*.py"), Path(__file__)]}
        if not all(p.is_file() for p in tools.values()):
            raise FileNotFoundError("MODELSIM_TOOLS")
        if run("version", [tools["vsim"], "-version"], out, 30)[0]:
            raise ValueError("TOOL_VERSION")
        for label, scenario, mutation in [("normal", "normal", None), ("diagnostic", "diagnostic", None),
                                          ("wrong_bit", "diagnostic", "bit"), ("wrong_buffer", "diagnostic", "buffer")]:
            folder = out / label
            folder.mkdir()
            units = list(sources)
            if mutation:
                name = "i2s_tx.sv" if mutation == "bit" else "pcm_frame_buffer.sv"
                source = next(p for p in units if p.name == name)
                text = source.read_text(encoding="utf-8")
                if mutation == "bit":
                    anchor, replacement = "SLOT_CNT_BITS'(DAC_WIDTH);", "SLOT_CNT_BITS'(DAC_WIDTH-1);"
                else:
                    anchor = "assign play_left = pending_valid ? pending_left : held_left;"
                    replacement = "assign play_left = held_left; // MUTANT old frame"
                if text.count(anchor) != 1:
                    raise ValueError("MUTATION_ANCHOR")
                if mutation == "buffer":
                    right_anchor = "assign play_right = pending_valid ? pending_right : held_right;"
                    if text.count(right_anchor) != 1:
                        raise ValueError("RIGHT_MUTATION_ANCHOR")
                    text = text.replace(right_anchor, "assign play_right = held_right; // MUTANT old frame")
                mutant = folder / name
                mutant.write_text(text.replace(anchor, replacement), encoding="utf-8")
                units[units.index(source)] = mutant
                receipt.setdefault("mutations", {})[label] = {"original_sha256": sha(source.read_bytes()),
                     "mutant_sha256": sha(mutant.read_bytes()), "anchor": anchor, "replacement": replacement}
            if run(label+"_library", [tools["vlib"], "work"], folder, 30)[0]:
                raise ValueError("VLIB")
            units += [BENCH / "serial_capture.sv", BENCH / ("tb_"+scenario+".sv")]
            code, _ = run(label+"_compile", [tools["vlog"], "-sv", "+incdir+"+str(out/"sealed/include"), *units], folder)
            if code != 0:
                raise ValueError(label+"_COMPILE")
            do = "onerror {quit -code 2}; onbreak {quit -code 3}; run -all; quit -code 0"
            code, transcript = run(label+"_simulate", [tools["vsim"], "-c", "-wlf", "simulation.wlf", "work.tb_"+scenario, "-do", do], folder)
            if code != 0 or "SIM_DONE "+scenario not in transcript:
                raise ValueError(label+"_SIMULATION_OR_TIMEOUT")
            capture = folder / "capture.txt"
            receipt["runs"][label+"_simulate"]["capture_sha256"] = sha(capture.read_bytes())
            try:
                summary = oracle.check_capture(capture, scenario)
                if mutation:
                    raise RuntimeError("MUTANT_FALSE_PASS")
                receipt["results"][label] = summary
                print("PASS", json.dumps(summary), flush=True)
            except ValueError as error:
                receipt["results"][label] = {"rejected": True, "reason": str(error)}
                bit_failure = str(error).startswith(("SERIAL_SAMPLE", "LSBJ_PADDING_OR_TIMING"))
                if not mutation or (mutation == "bit" and not bit_failure) or (mutation == "buffer" and "BUFFER_ADOPTION" not in str(error)):
                    raise
                print("EXPECTED_REJECT", label, error, flush=True)
        spec = importlib.util.spec_from_file_location("serial_negative_checks", BENCH / "test_scoreboard.py")
        tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tests)
        receipt["checker_selftests"] = tests.run_checks(out, oracle)
        if args.repo_gate:
            # The unchanged legacy gate writes code/output. Its content-exact
            # snapshot stays inside the ONLY authorized new test directory.
            mirror = out / "repo_gate_snapshot"
            if run("gate_clone", ["git", "clone", "--shared", "--no-hardlinks", "-c", "core.longpaths=true",
                                   "--branch", "develop", ROOT, mirror], out)[0]:
                raise ValueError("GATE_SNAPSHOT_CLONE")
            names = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, env=env,
                                   capture_output=True, check=True).stdout.decode("utf-8").split("\0")
            snapshot_shas = {}
            checkout_newline_differences = []
            for relative in filter(None, names):
                live, copy = io_path(ROOT / relative), io_path(mirror / relative)
                task_owned = relative == "code/scripts/run_m3_clock40_pcm_serial_acceptance.py" or relative.startswith(
                    "code/tb/audio_out/m3_clock40_pcm_serial_acceptance/")
                if task_owned:
                    copy.parent.mkdir(parents=True, exist_ok=True)
                    copy.write_bytes(live.read_bytes())
                if not copy.is_file():
                    raise ValueError("GATE_SNAPSHOT_SOURCE_DIFFERENCE "+relative)
                live_data, copy_data = live.read_bytes(), copy.read_bytes()
                if live_data != copy_data:
                    if live_data.replace(b"\r\n", b"\n") != copy_data.replace(b"\r\n", b"\n"):
                        raise ValueError("GATE_SNAPSHOT_SOURCE_DIFFERENCE "+relative)
                    # Restore exact LIVE raw bytes only in the snapshot; do
                    # not normalize or touch the user's original checkout.
                    copy.write_bytes(live_data)
                    checkout_newline_differences.append(relative)
                snapshot_shas[relative] = sha(live_data)
            added = [Path(__file__), *(p for p in BENCH.iterdir() if p.is_file())]
            for live in added:
                copy = mirror / live.relative_to(ROOT)
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(live, copy)
                snapshot_shas[live.relative_to(ROOT).as_posix()] = sha(live.read_bytes())
            dump(out / "gate_snapshot_sha256.json", snapshot_shas)
            if run("gate_stage", ["git", "add", "--", "code/scripts/run_m3_clock40_pcm_serial_acceptance.py",
                                      "code/tb/audio_out/m3_clock40_pcm_serial_acceptance"], mirror, 30)[0]:
                raise ValueError("GATE_SNAPSHOT_INDEX")
            code, log = run("check_repo", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", mirror/"code/scripts/check_repo.ps1"], mirror)
            if code or "All repository checks passed." not in log:
                raise ValueError("REPOSITORY_GATE")
            for relative, digest in snapshot_shas.items():
                if sha(io_path(ROOT/relative).read_bytes()) != digest or sha(io_path(mirror/relative).read_bytes()) != digest:
                    raise ValueError("GATE_SNAPSHOT_CHANGED "+relative)
            receipt["repository_gate"] = {"passed": True, "mode": "content-exact isolated snapshot",
                 "files_sha_verified": len(snapshot_shas), "script_sha256": sha((ROOT/"code/scripts/check_repo.ps1").read_bytes()),
                 "clone_newlines_restored_to_live_raw_bytes": checkout_newline_differences,
                 "production_output_written": False}
        receipt["passed"] = True
    except (OSError, ValueError, RuntimeError, IndexError, KeyError) as error:
        receipt["error"] = str(error)
        print("FAIL", error, flush=True)
    finally:
        dump(out / "receipt.json", receipt)
        print("EVIDENCE", out, flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
