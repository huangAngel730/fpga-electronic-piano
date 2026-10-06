"""Sealed L 40/25MHz UART/audio/scan/publish/render acceptance, no hardware."""
from __future__ import annotations

import argparse
import base64
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
BENCH = ROOT / "code/tb/board/m3_clock40_audio_visual_acceptance"
OLD_RUNNER = ROOT / "code/scripts/run_m3_clock40_pcm_serial_acceptance.py"
OLD_SHA = "755ee24965d35835536dc6698a16c72e4b93cfd8cae8fd5f3dc009e025181c9c"
CANDIDATE = "L_locations_guard065"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8", newline="\n")


def prepare(helper, archive, out):
    # Reuse the already-reviewed CRC/SHA-locked extractor, not its serial test.
    helper.extract(archive, out, CANDIDATE)
    manifest_path = out / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with zipfile.ZipFile(archive) as source:
        project = ET.fromstring(source.read(CANDIDATE+"/audio_visual_coexistence_top.gprj"))
    exclude = {"TMDS_PLL_800_600_60.v", "DVI_TX_Top.v", "audio_visual_coexistence_top.sv", "audio_visual_display_probe.sv"}
    units = [out/"sim_sources"/Path(entry.attrib["path"]).name for entry in project.iter("File")
             if entry.attrib.get("type") == "file.verilog" and Path(entry.attrib["path"]).name not in exclude]
    reused = {
        "extractor": OLD_RUNNER,
        "midi": ROOT/"code/tb/audio_out/m3_clock40_pcm_serial_acceptance/tb_normal.sv",
        "renderer": ROOT/"code/tb/input/visualizer/tb_renderer_geometry_equiv.sv",
        "coexistence_method": ROOT/"code/tb/board/tb_audio_visual_coexistence.sv",
        "bar_contract": ROOT/"code/tb/input/visualizer/held_bar_semantics_20261002.md",
    }
    midi = reused["midi"].read_text(encoding="utf-8")
    start = midi.index("    task automatic byte_midi(")
    finish = midi.index("    endtask", start)+len("    endtask")
    midi = midi[start:finish].replace("monitor.fd", "fd")
    golden = reused["renderer"].read_text(encoding="utf-8")
    start = golden.index("    function automatic [23:0] golden;")
    finish = golden.index("    endfunction", start)+len("    endfunction")
    golden = golden[start:finish]
    includes = out/"test_include"
    includes.mkdir()
    (includes/"midi_tasks.svh").write_text(midi+"\n", encoding="utf-8", newline="\n")
    (includes/"renderer_golden.svh").write_text(golden+"\n", encoding="utf-8", newline="\n")
    manifest.update(compiled_sources=[unit.name for unit in units],
                    test_scope="audio/video subsystem, original raster; no PLL or TMDS model",
                    excluded_uninstantiated_board_modules=sorted(exclude),
                    reused_sha256={str(path.relative_to(ROOT).as_posix()): sha(path.read_bytes()) for path in reused.values()},
                    generated_include_sha256={p.name: sha(p.read_bytes()) for p in includes.iterdir()})
    dump(manifest_path, manifest)
    return units, includes


def repository_gate(out, run, helper):
    mirror = out/"repo_gate_snapshot"
    if run("gate_clone", ["git", "clone", "--shared", "--no-hardlinks", "-c", "core.longpaths=true",
                          "--branch", "develop", ROOT, mirror], out)[0]:
        raise ValueError("GATE_CLONE")
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    digests, restored = {}, []
    for name in filter(None, names):
        live, copy = helper.io_path(ROOT/name), helper.io_path(mirror/name)
        owned = name == Path(__file__).relative_to(ROOT).as_posix() or name.startswith(BENCH.relative_to(ROOT).as_posix()+"/")
        if owned:
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(live.read_bytes())
        if not copy.is_file():
            raise ValueError("GATE_MISSING "+name)
        a, b = live.read_bytes(), copy.read_bytes()
        if a != b:
            if a.replace(b"\r\n", b"\n") != b.replace(b"\r\n", b"\n"):
                raise ValueError("GATE_CONTENT "+name)
            copy.write_bytes(a)
            restored.append(name)
        digests[name] = sha(a)
    for live in [Path(__file__), *(p for p in BENCH.rglob("*") if p.is_file() and "runtime" not in p.relative_to(BENCH).parts)]:
        relative = live.relative_to(ROOT)
        copy = helper.io_path(mirror/relative)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(live, copy)
        digests[relative.as_posix()] = sha(live.read_bytes())
    dump(out/"gate_snapshot_sha256.json", digests)
    if run("gate_stage", ["git", "add", "--", Path(__file__).relative_to(ROOT), BENCH.relative_to(ROOT)], mirror)[0]:
        raise ValueError("GATE_STAGE")
    code, log = run("check_repo", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", mirror/"code/scripts/check_repo.ps1"], mirror)
    if code or "All repository checks passed." not in log or log.count("[PASS]") != 9:
        raise ValueError("REPOSITORY_GATE")
    for name, digest in digests.items():
        if sha(helper.io_path(ROOT/name).read_bytes()) != digest or sha(helper.io_path(mirror/name).read_bytes()) != digest:
            raise ValueError("GATE_CHANGED "+name)
    return {"passed": True, "mode": "content-exact isolated snapshot", "files_sha_verified": len(digests),
            "script_sha256": sha((ROOT/"code/scripts/check_repo.ps1").read_bytes()),
            "newline_restored": restored, "production_output_written": False}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path)
    cli.add_argument("--modelsim-bin", type=Path, default=Path("E:/FPGA/Bpan/modelsim/modelsim1/win64"))
    cli.add_argument("--repo-gate", action="store_true")
    cli.add_argument("--case", choices=["normal", "overflow", "wrong_note", "wrong_audio"])
    cli.add_argument("--check-capture", type=Path)
    cli.add_argument("--scenario", choices=["normal", "overflow"], default="normal")
    args = cli.parse_args()
    oracle = load(BENCH/"scoreboard.py", "joint_scoreboard")
    if args.check_capture:
        try:
            print(json.dumps(oracle.check_capture(args.check_capture, args.scenario), indent=2))
            return 0
        except (OSError, ValueError, IndexError, KeyError) as error:
            print("REJECT", error)
            return 1
    if sha(OLD_RUNNER.read_bytes()) != OLD_SHA:
        raise ValueError("REUSED_EXTRACTOR_SHA")
    helper = load(OLD_RUNNER, "sealed_pcm_helpers")
    archive = (args.archive or helper.DEFAULT_ZIP).resolve()
    runtime = BENCH/"runtime"
    runtime.mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="run_", dir=runtime))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TEMP=str(out), TMP=str(out))
    env["PATH"] = str(Path(sys.executable).parent)+os.pathsep+env.get("PATH", "")
    receipt = {"passed": False, "partial": bool(args.case), "runs": {}, "results": {}, "output": str(out),
               "scope": "L2/limited L3 scan/publish/render/audio coexistence; no PLL/TMDS/hardware/STA/serial acceptance"}

    def run(label, command, cwd, timeout=900):
        command = list(map(str, command))
        try:
            result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False)
            data, code = result.stdout+result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            data = (error.stdout or b"")+(error.stderr or b"")+b"\nRUNNER_TIMEOUT\n"
            code = 124
        (out/(label+".log")).write_bytes(data)
        receipt["runs"][label] = {"command": command, "cwd": str(cwd), "exit_code": code, "log_sha256": sha(data)}
        print(label, "exit", code, flush=True)
        return code, data.decode("utf-8", errors="replace")

    selected_ok = False
    try:
        units, includes = prepare(helper, archive, out)
        receipt["archive_sha256"] = helper.ZIP_SHA
        receipt["source_manifest_sha256"] = sha((out/"source_manifest.json").read_bytes())
        receipt["test_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in [Path(__file__), *BENCH.glob("*.py"), *BENCH.glob("*.sv")]}
        tools = {name: args.modelsim_bin/(name+".exe") for name in ["vlib", "vlog", "vsim"]}
        if run("version", [tools["vsim"], "-version"], out, 30)[0]:
            raise ValueError("TOOL_VERSION")
        for label in ["normal", "overflow", "wrong_note", "wrong_audio"]:
            if args.case and args.case != label:
                continue
            folder = out/label
            folder.mkdir()
            tb = (BENCH/"tb_joint.sv").read_text(encoding="utf-8")
            if label == "wrong_note":
                anchor = "assign scene_data=video_data;"
                replacement = "always_comb begin scene_data=video_data; if(video_data.note_number==60) scene_data.note_number=61; end"
                if tb.count(anchor) != 1:
                    raise ValueError("NOTE_MUTATION_ANCHOR")
                tb = tb.replace(anchor, replacement)
            elif label == "wrong_audio":
                anchor, replacement = "wire audio_gate=1'b1;", "wire audio_gate=!video_block;"
                if tb.count(anchor) != 1:
                    raise ValueError("AUDIO_MUTATION_ANCHOR")
                tb = tb.replace(anchor, replacement)
            source = folder/"tb_joint.sv"
            source.write_text(tb, encoding="utf-8", newline="\n")
            if label.startswith("wrong"):
                receipt.setdefault("mutations", {})[label] = {"anchor": anchor, "replacement": replacement, "source_sha256": sha(source.read_bytes())}
            if run(label+"_library", [tools["vlib"], "work"], folder)[0]:
                raise ValueError("VLIB")
            code, log = run(label+"_compile", [tools["vlog"], "-sv", "+incdir+"+str(out/"sealed/include"), "+incdir+"+str(includes), *units, source], folder)
            if code:
                print(log[-5000:], flush=True)
                raise ValueError(label+"_COMPILE")
            do = "onerror {quit -code 2}; onbreak {quit -code 3}; run -all; quit -code 0"
            cmd = [tools["vsim"], "-c", "-wlf", "simulation.wlf", "work.tb_joint"]
            if label == "overflow":
                cmd.append("-gOVERFLOW=1")
            code, log = run(label+"_simulate", [*cmd, "-do", do], folder)
            if code or "SIM_DONE joint" not in log:
                print(log[-5000:], flush=True)
                raise ValueError(label+"_SIMULATION_OR_TIMEOUT")
            capture = folder/"capture.txt"
            receipt["runs"][label+"_simulate"]["capture_sha256"] = sha(capture.read_bytes())
            try:
                result = oracle.check_capture(capture, "overflow" if label == "overflow" else "normal")
                if label.startswith("wrong"):
                    raise RuntimeError("MUTANT_FALSE_PASS")
                receipt["results"][label] = result
                print("PASS", json.dumps(result), flush=True)
            except ValueError as error:
                expected = "VIDEO_EVENT_MAPPING_OR_DUPLICATE" if label == "wrong_note" else "AUDIO_ACCEPT_BACKPRESSURE"
                if not label.startswith("wrong") or str(error) != expected:
                    raise
                receipt["results"][label] = {"rejected": True, "reason": str(error)}
                print("EXPECTED_REJECT", label, error, flush=True)
        if not args.case:
            tests = load(BENCH/"test_scoreboard.py", "joint_checker_tests")
            receipt["checker_selftests"] = tests.run_checks(out, oracle)
            if args.repo_gate:
                receipt["repository_gate"] = repository_gate(out, run, helper)
            receipt["passed"] = True
        selected_ok = True
    except (OSError, ValueError, RuntimeError, IndexError, KeyError) as error:
        receipt["error"] = str(error)
        print("FAIL", error, flush=True)
    finally:
        dump(out/"receipt.json", receipt)
        print("EVIDENCE", out, flush=True)
    return 0 if selected_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
