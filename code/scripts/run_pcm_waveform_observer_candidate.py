"""M2 independent PCM observation/buffered-mailbox CDC acceptance; no hardware."""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
RTL = ROOT / "code/rtl/common/pcm_waveform_observer_candidate"
TB = ROOT / "code/tb/common/pcm_waveform_observer_candidate"
L = ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065"
CAP = ROOT / "code/tb/audio_out/m3_clock40_pcm_serial_acceptance/evidence"
CAD = Path("D:/Gowin/oss-cad-suite")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_checker():
    spec = importlib.util.spec_from_file_location("pcm_observer_checker", TB / "check_capture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", choices=["normal", "diagnostic", "stress", "isolation", "wrong_pcm", "wrong_sequence"])
    parser.add_argument("--check-capture", type=Path)
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--cad", type=Path, default=CAD)
    args = parser.parse_args()
    if args.check_capture:
        try:
            print("PASS", json.dumps(load_checker().check(args.check_capture, args.vectors), sort_keys=True))
            return 0
        except (OSError, ValueError, IndexError, KeyError, UnicodeError) as error:
            print("FAIL", error)
            return 1
    output = (args.output or ROOT / "code/output" / ("m2_pcm_observer_" + time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + 900
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(args.cad / "bin") + os.pathsep + str(args.cad / "lib") + os.pathsep + env.get("PATH", "")
    receipt = dict(passed=False, output=str(output), partial=bool(args.case),
                   scope="independent L2/limited L3; no production wiring/Gowin/physical CDC/STA/hardware",
                   steps={}, cases={}, source_manifest={}, raw_source_checks=[], corrupted_captures=[],
                   original_sources_modified=False, programmed=False)

    def run(name, command, cwd, limit=180):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("TOTAL_RUNNER_TIMEOUT")
        stdout = output / (name + ".stdout.bin")
        stderr = output / (name + ".stderr.bin")
        with stdout.open("wb") as so, stderr.open("wb") as se:
            creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen(list(map(str, command)), cwd=cwd, env=env,
                                       stdout=so, stderr=se, creationflags=creation)
            timeout = False
            try:
                code = process.wait(timeout=min(limit, remaining))
            except subprocess.TimeoutExpired:
                timeout = True
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
                else:
                    process.kill()
                process.wait(timeout=15)
                code = 124
        receipt["steps"][name] = dict(command=list(map(str, command)), cwd=str(cwd),
                                    exit_code=code, timeout=timeout,
                                    stdout_sha256=sha(stdout.read_bytes()), stderr_sha256=sha(stderr.read_bytes()))
        print(name, "exit", code, flush=True)
        return code

    exit_code = 0
    try:
        compiler = args.cad / "bin/iverilog.exe"
        simulator = args.cad / "bin/vvp.exe"
        if not compiler.is_file() or not simulator.is_file():
            raise ValueError("Icarus tools unavailable")
        if run("iverilog_version", [compiler, "-B", args.cad / "lib/ivl", "-V"], output) != 0:
            raise ValueError("version command")
        sealed = json.loads((L / "input_manifest.json").read_text(encoding="utf-8"))
        for item in sealed["inputs"]:
            raw = (L / item["path"]).read_bytes()
            restored = raw if sha(raw) == item["candidate_SHA256"] else raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            if sha(restored) != item["candidate_SHA256"]:
                raise ValueError("SEALED_L_SOURCE_CHANGED " + item["path"])
            receipt["raw_source_checks"].append(dict(path=item["path"],
                carrier_sha256=sha(raw), original_sha256=sha(restored), newline_only=restored != raw))
        source_files = [RTL / "pcm_frame_observer.sv", RTL / "pcm_waveform_observer_bridge.sv",
                        ROOT / "code/rtl/common/visual_mailbox_cdc.sv", ROOT / "code/rtl/common/reset_sync.sv",
                        L / "sources/pcm_frame_buffer.sv", L / "sources/i2s_tx.sv",
                        TB / "tb_pcm_observer_replay.sv", TB / "tb_pcm_observer_isolation.sv", TB / "check_capture.py", Path(__file__)]
        staged = output / "sources"
        staged.mkdir()
        for source in source_files:
            raw = source.read_bytes()
            receipt["source_manifest"][str(source.relative_to(ROOT)).replace("\\", "/")] = sha(raw)
            if source.suffix == ".sv":
                text = raw.decode("utf-8")
                # This Icarus build rejects unsigned integer parameter qualifiers. Only
                # integer parameter/localparam type syntax changes in staging;
                # no functions, arithmetic, widths, reset order or data changes.
                adapted = text.replace("int unsigned", "integer")
                dest = staged / source.name
                dest.write_text(adapted, encoding="utf-8", newline="\n")
                if adapted != text:
                    receipt.setdefault("simulation_adaptations", []).append(dict(
                        path=str(source.relative_to(ROOT)).replace("\\", "/"),
                        change="unsigned integer parameter qualifier only", staged_sha256=sha(dest.read_bytes())))
        vectors = {}
        raw_manifest = json.loads((CAP / "raw_manifest.json").read_text(encoding="utf-8"))
        for case, filename in [("normal", "normal_capture.b64"), ("diagnostic", "diagnostic_capture.b64")]:
            raw = base64.b64decode(b"".join((CAP / filename).read_bytes().split()), validate=True)
            item = raw_manifest[filename]
            if sha(raw) != item["raw_sha256"] or len(raw) != item["raw_bytes"]:
                raise ValueError("ORIGINAL_CAPTURE_SHA " + filename)
            adoption = [line.split() for line in raw.decode("ascii").splitlines() if line.startswith("A ")]
            rows = []
            for index, row in enumerate(adoption):
                if len(row) != 6 or int(row[2]) != index + 1:
                    raise ValueError("original A sequence")
                cycles = int(round((float(adoption[index + 1][1]) - float(row[1])) / 25)) if index + 1 < len(adoption) else 833
                rows.append((index, int(row[4]), int(row[5]), cycles))
            path = output / (case + ".vectors.txt")
            path.write_text("".join(" ".join(map(str, row)) + "\n" for row in rows), encoding="ascii")
            vectors[case] = (path, len(rows))
            receipt.setdefault("capture_inputs", {})[case] = dict(carrier=str((CAP / filename).relative_to(ROOT)).replace("\\", "/"),
                original_raw_sha256=sha(raw), rows=len(rows), vector_sha256=sha(path.read_bytes()))
        rng = random.Random(578025)
        rows = [(index, 0 if index < 8 else rng.randrange(-2**23, 2**23),
                 0 if index < 8 else rng.randrange(-2**23, 2**23), 1 if index % 9 < 5 else 12)
                for index in range(1400)]
        rows[8] = (8, 2**23 - 1, -2**23, 12)
        rows[9] = (9, -128, 127, 12)
        stress = output / "stress.vectors.txt"
        stress.write_text("".join(" ".join(map(str, row)) + "\n" for row in rows), encoding="ascii")
        vectors["stress"] = (stress, len(rows))
        receipt.setdefault("capture_inputs", {})["stress"] = dict(synthetic=True, seed=578025, rows=len(rows), vector_sha256=sha(stress.read_bytes()))
        for case in ([args.case] if args.case else ["normal", "diagnostic", "stress", "isolation", "wrong_pcm", "wrong_sequence"]):
            directory = output / case
            directory.mkdir()
            unit_dir = directory / "sources"
            unit_dir.mkdir()
            for source in staged.glob("*.sv"):
                text = source.read_text(encoding="utf-8")
                if case == "wrong_pcm" and source.name == "pcm_frame_observer.sv":
                    before = "observed_right <= play_right;"
                    if text.count(before) != 1:
                        raise ValueError("mutant patch identity")
                    text = text.replace(before, "observed_right <= play_left;", 1)
                if case == "wrong_sequence" and source.name == "pcm_waveform_observer_bridge.sv":
                    before = "{observed_seq, observed_left, observed_right}"
                    if text.count(before) != 1:
                        raise ValueError("mutant patch identity")
                    text = text.replace(before, "{(observed_seq + 32'd1), observed_left, observed_right}", 1)
                (unit_dir / source.name).write_text(text, encoding="utf-8", newline="\n")
            top = "tb_pcm_observer_isolation" if case == "isolation" else "tb_pcm_observer_replay"
            unit_names = ["reset_sync.sv", "visual_mailbox_cdc.sv", "pcm_frame_observer.sv", "pcm_waveform_observer_bridge.sv", top + ".sv"]
            if case == "isolation":
                unit_names += ["pcm_frame_buffer.sv", "i2s_tx.sv"]
            artifact = directory / "simulation.vvp"
            command = [compiler, "-B", args.cad / "lib/ivl", "-g2012", "-s", top, "-o", artifact]
            # Stress starts near rollover and uses a non-power-of-two queue.
            if case in ("stress", "wrong_sequence"):
                command += ["-P", top + ".FIRST_SEQ=4294967290", "-P", top + ".DEPTH=3"]
            command += [unit_dir / name for name in unit_names]
            compile_code = run(case + "_compile", command, directory, 45)
            if compile_code != 0 or not artifact.is_file():
                raise ValueError("compile failed " + case)
            capture = directory / "capture.txt"
            simulate = [simulator, artifact, "+CAPTURE=" + str(capture)]
            vector_case = "stress" if case == "wrong_sequence" else "diagnostic" if case == "wrong_pcm" else case
            if case != "isolation":
                vector_path, count = vectors[vector_case]
                simulate += ["+VECTORS=" + str(vector_path), "+COUNT=" + str(count)]
            simulation_code = run(case + "_simulate", simulate, directory, 240)
            stdout = (output / (case + "_simulate.stdout.bin")).read_bytes()
            if simulation_code != 0 or b"HARNESS COMPLETE" not in stdout:
                raise ValueError("simulation incomplete " + case)
            check_command = [sys.executable, "-B", "-X", "utf8", TB / "check_capture.py", capture]
            if case != "isolation":
                check_command += ["--vectors", vectors[vector_case][0]]
            check_code = run(case + "_check", check_command, directory, 30)
            negative = case.startswith("wrong_")
            text = (output / (case + "_check.stdout.bin")).read_text(encoding="utf-8")
            expected_reason = "OBSERVATION_PCM_OR_ORDINAL" if case == "wrong_pcm" else "DELIVERY_PCM_ORDER_OR_STALE"
            if check_code != (1 if negative else 0) or (negative and expected_reason not in text):
                raise ValueError("unexpected capture adjudication " + case + " " + text[:400])
            receipt["cases"][case] = dict(compile_exit=compile_code, simulation_exit=simulation_code,
                completed=True, check_exit=check_code, capture_sha256=sha(capture.read_bytes()),
                result=text.strip(), expected_behavior_rejection=negative)
            if negative:
                receipt["cases"][case]["mutant_sources"] = {path.name: sha(path.read_bytes()) for path in unit_dir.glob("*.sv")}
        if not args.case:
            capture = output / "normal/capture.txt"
            lines = capture.read_text(encoding="ascii").splitlines()
            d_index = next(i for i, line in enumerate(lines) if line.startswith("D "))
            changed = lines.copy()
            words = changed[d_index].split()
            words[-1] = str(int(words[-1]) ^ 1)
            changed[d_index] = " ".join(words)
            bad_epoch = lines.copy()
            words = bad_epoch[d_index].split()
            words[2] = str(int(words[2]) + 1)
            bad_epoch[d_index] = " ".join(words)
            variants = {"empty": [], "missing_META": lines[1:], "missing_END": lines[:-1],
                        "after_END": lines + ["R 0 0 0"], "unknown": lines[:-1] + ["BAD 1", lines[-1]],
                        "wrong_PCM": changed, "wrong_epoch": bad_epoch,
                        "duplicate_delivery": lines[:d_index] + [lines[d_index]] + lines[d_index:],
                        "wrong_END": lines[:-1] + ["END 0 0 0 0"]}
            corrupt_dir = output / "corruptions"
            corrupt_dir.mkdir()
            for name, rows in variants.items():
                path = corrupt_dir / (name + ".txt")
                path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="ascii")
                code = run("corrupt_" + name, [sys.executable, "-B", "-X", "utf8", TB / "check_capture.py", path, "--vectors", vectors["normal"][0]], output, 30)
                if code != 1:
                    raise ValueError("corrupted evidence accepted " + name)
                receipt["corrupted_captures"].append(dict(label=name, checker_exit=code, sha256=sha(path.read_bytes())))
        receipt["passed"] = True
    except (OSError, ValueError, subprocess.SubprocessError, UnicodeError, KeyError, IndexError) as error:
        receipt["error"] = str(error)
        print("FAIL", error, flush=True)
        exit_code = 1
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        for path, digest in receipt["source_manifest"].items():
            try:
                identity_matches = sha((ROOT / path).read_bytes()) == digest
            except OSError:
                identity_matches = False
            if not identity_matches:
                receipt["passed"] = False
                receipt["error"] = "source changed during run " + path
                exit_code = 1
        (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("receipt", output / "receipt.json", "passed", receipt["passed"], flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
