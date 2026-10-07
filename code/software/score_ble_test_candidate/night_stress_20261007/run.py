"""Bounded night T059 acceptance; no tool installation or device access."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

import stress

HERE = Path(__file__).resolve().parent
ROOT = stress.ROOT
spec = importlib.util.spec_from_file_location("night_wave_runner", ROOT / "code/tb/input/pcm_waveform_candidate/night_blackbox_20261007/run.py")
sys.path.insert(0, str(Path(spec.origin).parent))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def frozen():
    table = json.loads((ROOT / "code/docs/evidence/m3_night_tasks_baseline_20261007.json").read_text(encoding="utf-8"))
    for name, expected in table["frozen_candidate_sha256"].items():
        if common.digest(ROOT / name) != expected:
            raise ValueError("FROZEN_SOURCE_SHA " + name)
    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcc", default="D:/program/OSsystem/MinGW/bin/gcc.exe")
    parser.add_argument("--java-home", type=Path, default=Path("E:/FPGA/Bpan/Vivado/Vivado2020_2/2020.2/tps/win64/jre11.0.2"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (args.output or ROOT / "code/output" / ("m3_night_ble_" + time.strftime("%Y%m%d_%H%M%S"))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment["PATH"] = str(Path(args.gcc).parent) + os.pathsep + environment["PATH"]
    steps = []
    started = time.monotonic()
    deadline = started + 1800
    receipt = dict(task="T059 night frozen public API stress", steps=steps, passed=False, findings=[], output=str(output))

    def execute(command, name):
        return common.execute(command, name, output, environment, deadline, steps)

    try:
        receipt["baseline"] = frozen()
        java, javac = (args.java_home / "bin/java.exe"), (args.java_home / "bin/javac.exe")
        execute([args.gcc, "--version"], "tool_gcc")
        execute([str(javac), "-version"], "tool_javac")
        execute([str(java), "-version"], "tool_java")
        classes = output / "classes"
        classes.mkdir()
        protocol = ROOT / "code/software/score_ble_android_candidate/app/src/main/java/org/m3/score/Protocol.java"
        code = execute([str(javac), "--release", "8", "-Xlint:all", "-Werror", "-d", str(classes),
                        str(protocol), str(HERE / "NightClient.java")], "java_compile")
        if code:
            raise ValueError("JAVA_COMPILE_FAILED")
        for mutation in (0, 1, 2):
            name = "normal" if mutation == 0 else "mutant_" + str(mutation)
            folder = output / name
            folder.mkdir()
            executable = output / (name + ".exe")
            core = ROOT / "code/software/score_ble_bridge_candidate/core"
            code = execute([args.gcc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                            "-DMUTATION=" + str(mutation), "-I", str(core),
                            str(core / "bridge.c"), str(HERE / "host.c"), "-o", str(executable)], name + "_compile")
            if code:
                raise ValueError("C_COMPILE_FAILED " + name)
            code = execute([sys.executable, "-B", str(HERE / "stress.py"), "capture", "--exe", str(executable),
                            "--java", str(java), "--classes", str(classes), "--output", str(folder)], name + "_run")
            if code:
                receipt["findings"].append(name + " RUNTIME_FAILED")
                continue
            summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
            code = execute([sys.executable, "-B", str(HERE / "stress.py"), "check", "--capture", str(folder / "checks.jsonl.gz"),
                            "--reference-hash", summary["reference_plan_sha256"], "--minimum", "0" if mutation else "1000"], name + "_check")
            result = (output / (name + "_check.stdout.log")).read_text(encoding="utf-8")
            if mutation == 0:
                receipt["summary"] = summary
                if code:
                    receipt["findings"].append(result.strip())
            elif code != 1 or "SEMANTIC " not in result:
                receipt["findings"].append(name + " NOT_SEMANTIC_REJECTION " + result)
            else:
                receipt.setdefault("mutants_rejected", []).append(dict(name=name, reason=result.strip()))
        capture = output / "normal/checks.jsonl.gz"
        if capture.exists():
            lines = gzip.decompress(capture.read_bytes()).decode("utf-8").splitlines()
            reference_hash = receipt["summary"]["reference_plan_sha256"]
            versions = {"empty": [], "truncated": lines[:-1]}
            bad = lines.copy()
            end = json.loads(bad[-1])
            end["check_count"] += 1
            bad[-1] = stress.canonical(end)
            versions["count"] = bad
            bad = lines.copy()
            target = next(i for i, line in enumerate(bad) if json.loads(line).get("tag") == "ALL_256_PAYLOAD_BYTES")
            item = json.loads(bad[target])
            item["actual"] = ["UART 00"]
            bad[target] = stress.canonical(item)
            versions["bytes"] = bad
            for name, content in versions.items():
                path = output / ("corrupt_" + name + ".jsonl.gz")
                with gzip.open(path, "wt", encoding="utf-8", newline="\n") as handle:
                    handle.write("\n".join(content) + ("\n" if content else ""))
                code = execute([sys.executable, "-B", str(HERE / "stress.py"), "check", "--capture", str(path),
                                "--reference-hash", reference_hash], "corrupt_" + name + "_check")
                if code != 1:
                    receipt["findings"].append("CORRUPTION_NOT_REJECTED " + name)
        # Read-only availability probe: do not equate desktop tools with target SDKs.
        names = ("IDF_PATH", "IDF_TOOLS_PATH", "ANDROID_HOME", "ANDROID_SDK_ROOT", "JAVA_HOME", "GRADLE_HOME")
        receipt["target_environment"] = dict(environment={name: os.environ.get(name) for name in names},
                                             executable_paths={name: shutil.which(name) for name in ("idf.py", "riscv32-esp-elf-gcc", "gradle", "adb", "sdkmanager")},
                                             target_builds="NOT_EXECUTED: complete exact offline ESP-IDF5.4.2/RISC-V and Android35/Gradle8.9/JDK17 environments not found in configured PATH/environment",
                                             no_install=True, no_devices=True)
        frozen()
        receipt["sources_sha256"] = {str(p.relative_to(ROOT)): common.digest(p) for p in HERE.iterdir() if p.is_file()}
        receipt["class_sha256"] = {str(p.relative_to(classes)): common.digest(p) for p in classes.rglob("*.class")}
        receipt["passed"] = not receipt["findings"] and len(receipt.get("mutants_rejected", [])) == 2
    except (OSError, ValueError, RuntimeError) as error:
        receipt["findings"].append(str(error))
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        receipt["artifacts_sha256"] = {str(p.relative_to(output)): common.digest(p) for p in output.rglob("*") if p.is_file()}
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(("PASS" if receipt["passed"] else "FAIL") + " " + str(output), flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
