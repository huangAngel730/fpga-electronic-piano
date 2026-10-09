"""Capture isolated profile checks, gate, or the single approved C3 build."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parents[6]
RUNNER = ROOT / "code/software/score_ble_test_candidate/target_build_20261008/run.py"
SPEC = importlib.util.spec_from_file_location("target_runner", RUNNER)
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("selftest", "gate", "c3"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT / "code/output") or not out.name.startswith("m3_t059_target_"):
        parser.error("require new approved output")
    out.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1")
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    commands = RUN.Commands(out, env, 1860 if args.stage == "c3" else 600)
    before = {path: RUN.digest(ROOT / path) for path in (
        RUNNER.relative_to(ROOT).as_posix(),
        "code/software/score_ble_test_candidate/target_build_20261008/test_run.py",
        RUN.HEADER_PROFILE.relative_to(ROOT).as_posix(), RUN.BASELINE.relative_to(ROOT).as_posix(),
        RUN.HEADER_APPROVAL.relative_to(ROOT).as_posix())}
    identity, errors = RUN.frozen_sources("c3_header_fix_20261009")
    record = {"stage": args.stage, "source_profile": RUN.source_profile("c3_header_fix_20261009")[1],
              "ten_source_identity": identity, "identity_errors": errors,
              "source_config_before_sha256": before, "invocation": sys.argv,
              "orchestrator_sha256": RUN.digest(Path(__file__)),
              "steps": commands.steps, "status": "FAIL", "exit_code": 1}
    code = 1
    try:
        if errors:
            raise ValueError("; ".join(errors))
        if args.stage == "selftest":
            commands.run("profile_selftest", [sys.executable, "-B", "-X", "utf8", RUNNER.with_name("test_run.py")], limit=120)
        elif args.stage == "gate":
            paths = [Path("D:/Gowin/oss-cad-suite/bin"), Path("D:/Gowin/oss-cad-suite/lib")]
            env["PATH"] = os.pathsep.join([str(p) for p in paths if p.is_dir()] + [env["PATH"]])
            names = subprocess_names()
            tracked_before = {name: RUN.digest(ROOT / name) for name in names if (ROOT / name).is_file()}
            RUN.dump(out / "tracked_inputs_before.json", tracked_before)
            text = commands.run("repository_gate", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                 "-File", ROOT / "code/scripts/check_repo.ps1"], limit=600)
            tracked_after = {name: RUN.digest(ROOT / name) for name in names if (ROOT / name).is_file()}
            RUN.dump(out / "tracked_inputs_after.json", tracked_after)
            record["tracked_inputs_unchanged"] = tracked_before == tracked_after
            record["pass_lines"] = [line for line in text.splitlines() if "[PASS]" in line]
            if len(record["pass_lines"]) != 9 or tracked_before != tracked_after:
                raise ValueError("Repository gate not 9 PASS with stable inputs")
        else:
            # Reuse exact installed paths from the original failed execution, not newer tools.
            prior = json.loads((ROOT / "code/output/m3_t059_target_20261009_c3_01/receipt.json").read_text(encoding="utf-8"))
            idf = Path(prior["explicit_paths"]["idf_root"])
            tools = Path(prior["explicit_paths"]["idf_tools"])
            python = Path(prior["explicit_paths"]["idf_python"])
            prefixes = [python.parent] + [Path(prior["path_tools"][name]).parent
                        for name in ("riscv32-esp-elf-gcc", "cmake", "ninja")]
            env.update(IDF_PATH=str(idf), IDF_TOOLS_PATH=str(tools),
                       IDF_PYTHON_ENV_PATH=str(python.parent.parent))
            env["PATH"] = os.pathsep.join([str(p) for p in prefixes] + [env["PATH"]])
            # Ignore Windows ZIP executable-mode differences, never content differences.
            count = int(env.get("GIT_CONFIG_COUNT", "0"))
            env[f"GIT_CONFIG_KEY_{count}"] = "core.fileMode"
            env[f"GIT_CONFIG_VALUE_{count}"] = "false"
            env["GIT_CONFIG_COUNT"] = str(count + 1)
            record["child_environment"] = {"IDF_PATH": str(idf), "IDF_TOOLS_PATH": str(tools),
                                           "IDF_PYTHON_ENV_PATH": str(python.parent.parent),
                                           "path_prefix": [str(p) for p in prefixes],
                                           "git_file_mode_override": "current child only"}
            target_out = out / "m3_t059_target_20261009_c3_header_build_01"
            record["target_output"] = str(target_out)
            commands.run("target_runner", [sys.executable, "-B", "-X", "utf8", RUNNER, "c3",
                         "--source-profile", "c3_header_fix_20261009", "--output", target_out,
                         "--idf-root", idf, "--idf-tools", tools, "--idf-python", python,
                         "--timeout", "1800"], limit=1860)
            result = json.loads((target_out / "receipt.json").read_text(encoding="utf-8"))
            if not result["target_build_passed"] or result["exit_code"] != 0:
                raise ValueError("C3 target receipt not successful")
            record["target_build_passed"] = True
        record["status"] = "PASS"
        code = 0
    except Exception as error:
        record["error"] = type(error).__name__ + ": " + str(error)
    finally:
        record["source_config_after_sha256"] = {name: RUN.digest(ROOT / name) for name in before}
        record["source_config_unchanged"] = before == record["source_config_after_sha256"]
        record["complete_t059_passed"] = False
        record["device_operations"] = False
        if not record["source_config_unchanged"]:
            record.update(status="FAIL", error="SOURCE_MUTATION")
            code = 1
        record["exit_code"] = code
        RUN.dump(out / "invocation_receipt.json", record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return code


def subprocess_names():
    import subprocess
    return subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")[:-1]


if __name__ == "__main__":
    raise SystemExit(main())
