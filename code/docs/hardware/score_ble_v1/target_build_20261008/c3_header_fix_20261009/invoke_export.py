"""Bounded C3 retry with official IDF export and non-nested fresh output."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
RUNNER = ROOT / "code/software/score_ble_test_candidate/target_build_20261008/run.py"
SPEC = importlib.util.spec_from_file_location("target_runner", RUNNER)
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exported", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-output", type=Path, required=True)
    args = parser.parse_args()
    out, target = args.output.resolve(), args.target_output.resolve()
    allowed = ROOT / "code/output"
    if any(p.parent != allowed or not p.name.startswith("m3_t059_target_")
           for p in (out, target)) or out == target or target.exists():
        parser.error("require distinct fresh direct code/output/m3_t059_target_* paths")
    if not args.exported:
        if out.exists():
            parser.error("outer output already exists")
        out.mkdir()
    elif not out.is_dir():
        parser.error("missing outer output")
    prior = json.loads((allowed / "m3_t059_target_20261009_c3_01/receipt.json").read_text(encoding="utf-8"))
    idf = Path(prior["explicit_paths"]["idf_root"])
    tools = Path(prior["explicit_paths"]["idf_tools"])
    python = Path(prior["explicit_paths"]["idf_python"])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1")
    commands = RUN.Commands(out, env, 1860)
    before = {str(p.relative_to(ROOT)): RUN.digest(p) for p in (
        RUNNER, RUN.HEADER_PROFILE, RUN.BASELINE, RUN.HEADER_APPROVAL,
        Path(__file__), HERE / "export_build.cmd")}
    record = {"stage": "exported_build" if args.exported else "official_export_and_build",
              "invocation": sys.argv, "target_output": str(target), "steps": commands.steps,
              "inputs_before_sha256": before, "exit_code": 1,
              "complete_t059_passed": False, "device_operations": False}
    code = 1
    try:
        _, errors = RUN.frozen_sources("c3_header_fix_20261009")
        if errors:
            raise ValueError(str(errors))
        if args.exported:
            names = ("IDF_PATH", "IDF_TOOLS_PATH", "IDF_PYTHON_ENV_PATH",
                     "ESP_IDF_VERSION", "ESP_ROM_ELF_DIR", "OPENOCD_SCRIPTS")
            record["exported_environment"] = {name: os.environ.get(name) for name in names}
            if Path(os.environ.get("IDF_PATH", "")).resolve() != idf.resolve():
                raise ValueError("EXPORTED_IDF_PATH_MISMATCH")
            rom = Path(os.environ.get("ESP_ROM_ELF_DIR", ""))
            if not os.environ.get("ESP_ROM_ELF_DIR") or not (rom / "esp32c3_rev0_rom.elf").is_file():
                raise ValueError("ROM_ELF_EXPORT_MISSING")
            record["rom_elf_sha256"] = {p.name: RUN.digest(p) for p in sorted(rom.glob("esp32c3*.elf"))}
            record["tool_paths"] = {name: shutil.which(name) for name in (
                "python", "git", "riscv32-esp-elf-gcc", "cmake", "ninja")}
            record["tool_sha256"] = {name: RUN.digest(p) for name, p in record["tool_paths"].items() if p}
            dep = target / "build/esp-idf/esp_driver_usb_serial_jtag/CMakeFiles/__idf_esp_driver_usb_serial_jtag.dir/src/usb_serial_jtag_connection_monitor.c.obj.d"
            record["previous_failing_dependency_path_characters"] = len(str(dep))
            RUN.dump(out / "exported_environment.json", record)
            commands.run("target_runner", [python, "-B", "-X", "utf8", RUNNER, "c3",
                         "--source-profile", "c3_header_fix_20261009", "--output", target,
                         "--idf-root", idf, "--idf-tools", tools, "--idf-python", python,
                         "--timeout", "1800"], limit=1830)
            result = json.loads((target / "receipt.json").read_text(encoding="utf-8"))
            if result["exit_code"] or not result["target_build_passed"]:
                raise ValueError("TARGET_RECEIPT_NOT_PASS")
            record["target_build_passed"] = True
        else:
            env["IDF_TOOLS_PATH"] = str(tools)
            git = tools / "tools/idf-git/2.44.0/cmd/git.exe"
            env["PATH"] = os.pathsep.join((str(python.parent), str(git.parent), env.get("PATH", "")))
            count = int(env.get("GIT_CONFIG_COUNT", "0"))
            env[f"GIT_CONFIG_KEY_{count}"] = "core.fileMode"
            env[f"GIT_CONFIG_VALUE_{count}"] = "false"
            env["GIT_CONFIG_COUNT"] = str(count + 1)
            record["git_mode_override"] = "child environment only; SDK content checks retained"
            record["export_script_sha256"] = RUN.digest(idf / "export.bat")
            commands.run("official_export", [HERE / "export_build.cmd", idf, python,
                         Path(__file__), out, target], limit=1860)
            exported = json.loads((out / "exported_build_receipt.json").read_text(encoding="utf-8"))
            if exported["exit_code"]:
                raise ValueError("EXPORTED_BUILD_NOT_PASS")
            record["target_build_passed"] = True
        code = 0
    except Exception as error:
        record["error"] = type(error).__name__ + ": " + str(error)
    finally:
        record["inputs_after_sha256"] = {name: RUN.digest(ROOT / name) for name in before}
        record["inputs_unchanged"] = before == record["inputs_after_sha256"]
        if not record["inputs_unchanged"]:
            record["error"] = "INPUT_MUTATION"
            code = 1
        record["exit_code"] = code
        record["status"] = "PASS_TARGET_COMPILED_ONLY" if code == 0 else "FAIL"
        RUN.dump(out / ("exported_build_receipt.json" if args.exported else "invocation_receipt.json"), record)
    print(json.dumps({key: record.get(key) for key in (
        "status", "exit_code", "error", "target_output", "target_build_passed")}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
