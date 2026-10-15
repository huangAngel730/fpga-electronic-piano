"""Independent fail-closed ROM gate. Production RTL and runners are read-only."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

SCHEMA = "rom-gate-config-v1"
EXPECTED_SCHEMA = "rom-gate-expected-v1"
PREFIX = "repo_gate_rom_audit_"
TOTAL_SECONDS = 300
JOB_REL = "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
JOB_SHA = "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"
TOPS = {
    "tb_electronic_piano_top": ">>> 顶层自检 PASS",
    "tb_key_to_tone": "PASS tb_key_to_tone checks=",
    "tb_midi_top_integration": "PASS tb_midi_top_integration checks=",
}
ROMS = (
    "code/model/generated/sine_wavetable.hex",
    "code/model/generated/triangle_wavetable.hex",
    "code/model/generated/wavetables/velocity_gain_rom.mem",
    "code/model/generated/wavetables/piano_band_4x256_8191.mem",
)
PROTECTED = (
    "code/build/electronic_piano.gprj", JOB_REL,
    "code/scripts/check_repo.ps1", "code/scripts/run_t007_sim.ps1",
    "code/scripts/run_t025_top_stat.py",
)
BAD_LOG = re.compile(
    r"\b(?:ERROR|FATAL)\b|\[FAIL\]|>>>[^\r\n]*FAIL|"
    r"(?:unable|cannot|could not|failed)\s+to\s+(?:open|read)|"
    r"(?:not enough|too many)\s+words|readmem[hb][^\r\n]*(?:warn|error)|"
    r"(?:segmentation fault|access violation|assertion[^\r\n]*failed)", re.I
)


class GateError(ValueError):
    """Specific rejection with no execution fallback."""


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise GateError("DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result
    result = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs)
    if not isinstance(result, dict):
        raise GateError("JSON_OBJECT_REQUIRED")
    return result


def write_json(path: Path, value: dict) -> None:
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or "\\" in relative:
        raise GateError("NON_CANONICAL_PATH:" + str(relative))
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts or ":" in relative:
        raise GateError("UNSAFE_PATH:" + relative)
    target = (root / item).resolve()
    if not target.is_relative_to(root.resolve()):
        raise GateError("OUTSIDE_ROOT:" + relative)
    return target


def identity(root: Path, table: dict) -> dict:
    if not isinstance(table, dict) or not table:
        raise GateError("EMPTY_IDENTITY_TABLE")
    actual = {}
    for relative, expected in sorted(table.items()):
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise GateError("INVALID_SHA:" + relative)
        target = inside(root, relative)
        if not target.is_file():
            raise GateError("MISSING_FILE:" + relative)
        actual[relative] = sha(target)
        if actual[relative] != expected:
            raise GateError("WRONG_SHA:" + relative)
    return actual


def required_files(repo: Path) -> tuple[list[str], list[Path]]:
    project = repo / PROTECTED[0]
    sources = []
    for element in ET.parse(project).findall(".//File"):
        if element.attrib.get("type") == "file.verilog" and element.attrib.get("enable", "1") == "1":
            path = (project.parent / element.attrib["path"]).resolve()
            if not path.is_relative_to(repo):
                raise GateError("PROJECT_SOURCE_OUTSIDE_REPO")
            sources.append(path)
    sources.sort(key=lambda path: {"audio_defs_pkg.sv": 0,
                                  "sustain_control_contract_pkg.sv": 1}.get(path.name, 2))
    required = set(PROTECTED) | set(ROMS)
    required.update(path.relative_to(repo).as_posix() for path in sources)
    required.update(path.relative_to(repo).as_posix() for path in (repo / "code/rtl").rglob("*.svh"))
    required.update("code/tb/board/" + top + ".sv" for top in TOPS)
    return sorted(required), sources


def required_tools(root: Path) -> set[str]:
    # Full native/DLL/ivl/plugin closure, not merely three executable hashes.
    required = {"environment.bat", "bin/yosys.exe", "bin/iverilog.exe", "bin/vvp.exe"}
    for folder in ("bin", "lib/ivl", "share/yosys"):
        directory = root / folder
        if not directory.is_dir():
            raise GateError("MISSING_TOOL_DIRECTORY:" + folder)
        for path in directory.rglob("*"):
            if path.is_file():
                required.add(path.relative_to(root).as_posix())
    required.update(path.relative_to(root).as_posix() for path in (root / "lib").iterdir() if path.is_file())
    required.update(path.relative_to(root).as_posix() for path in (root / "lib").rglob("*")
                    if path.is_file() and path.suffix.lower() in (".dll", ".vpi", ".ivl", ".so"))
    return required


def environment(tool_root: Path, output: Path) -> dict:
    system_root = Path(os.environ.get("SystemRoot", "C:/Windows")).resolve()
    env = {
        "SystemRoot": str(system_root), "WINDIR": str(system_root),
        "SystemDrive": system_root.drive,
        "COMSPEC": str(system_root / "System32/cmd.exe"),
        "PATH": os.pathsep.join(str(path) for path in (
            tool_root / "bin", tool_root / "lib", system_root / "System32", system_root)),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "TEMP": str(output / "temp"), "TMP": str(output / "temp"),
        "YOSYSHQ_ROOT": str(tool_root) + os.sep,
        "IVERILOG_ROOT": str(tool_root / "lib/ivl"),
        "PYTHON_EXECUTABLE": str(tool_root / "lib/python3.exe"),
        "QT_PLUGIN_PATH": str(tool_root / "lib/qt6/plugins"),
        "QT_LOGGING_RULES": "*=false",
        "SSL_CERT_FILE": str(tool_root / "etc/cacert.pem"),
    }
    return env


def commands(repo: Path, output: Path, tool_root: Path, top: str) -> list[dict]:
    if top not in TOPS:
        raise GateError("UNSUPPORTED_TOP:" + top)
    _, source_paths = required_files(repo)
    allocator = repo / "code/rtl/audio/voice_allocator_4.sv"
    sources = [output / "allocator.v" if path == allocator else path for path in source_paths]
    sources.append(repo / ("code/tb/board/" + top + ".sv"))
    return [
        {"name": "lower", "argv": [str(tool_root / "bin/yosys.exe"), "-Q", "-T", "-s", str(output / "lower.ys")], "limit": 90},
        {"name": "compile", "argv": [str(tool_root / "bin/iverilog.exe"), "-g2012", "-s", top,
          "-I", str(repo / "code/rtl/board"), "-I", str(repo / "code/rtl/common"),
          "-o", str(output / "tb.vvp")] + [str(path) for path in sources], "limit": 90},
        {"name": "simulate", "argv": [str(tool_root / "bin/vvp.exe"), str(output / "tb.vvp"),
          "+VELOCITY_ROM_PATH=" + str(output / ROMS[2][5:]),
          "+WAVETABLE_PATH=" + str(output / ROMS[3][5:])], "limit": 300},
    ]


def lower_text(repo: Path, output: Path) -> str:
    return ('read_slang --top voice_allocator_4 "' + (repo / "code/rtl/audio/voice_allocator_4.sv").as_posix()
            + '"\nproc\nopt\ntechmap\nopt\nwrite_verilog -noattr "'
            + (output / "allocator.v").as_posix() + '"\n')


def rom_contract(repo: Path, output: Path) -> dict:
    """Record declaration vs call-site propagation vs actual runtime resolution.

    This deliberately accepts the audited original expression set only. It is
    not a general Verilog elaborator and refuses new dynamic read expressions.
    """
    _, sources = required_files(repo)
    declarations, read_calls, propagation = [], [], []
    allowed = {"ROM_FILE", "wavetable_path", "rom_path", "SINE_ROM_FILE", "TRIANGLE_ROM_FILE",
               '"model/generated/wavetables/velocity_gain_rom.mem"'}
    for source in sources:
        text = source.read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
        relative = source.relative_to(repo).as_posix()
        for match in re.finditer(r'parameter\s+(\w*(?:ROM_FILE|ROM_PATH))\s*=\s*"([^"\n]+)"', text):
            declarations.append({"source": relative, "parameter": match[1], "declared_default": match[2]})
        for match in re.finditer(r"\$readmem[hb]\s*\(\s*([^,]+),", text):
            expression = match[1].strip()
            if expression not in allowed:
                raise GateError("UNSUPPORTED_READMEM_EXPRESSION:" + relative + ":" + expression)
            read_calls.append({"source": relative, "expression": expression})
        for match in re.finditer(r"\.((?:SINE_|TRIANGLE_|PIANO_)?ROM_FILE)\s*\(\s*(\w+)\s*\)", text):
            propagation.append({"source": relative, "callee_parameter": match[1], "caller_expression": match[2]})
    if len(read_calls) != 8:
        raise GateError("READMEM_CLOSURE_COUNT_CHANGED:" + str(len(read_calls)))
    words = {}
    for relative in ROMS:
        tokens = (repo / relative).read_text(encoding="ascii").split()
        if len(tokens) != 1024 or any(not re.fullmatch(r"[0-9A-Fa-f]{4}", token) for token in tokens):
            raise GateError("ROM_WORD_CONTRACT_REJECT:" + relative)
        words[relative] = {"words": 1024, "bits": 16}
    return {
        "source_declarations": declarations, "instance_parameter_propagation": propagation,
        "readmem_calls": read_calls, "rom_word_contract": words, "runtime_cwd": str(output),
        "actual_resolution": {
            "SINE_ROM_FILE": str(output / ROMS[0][5:]),
            "TRIANGLE_ROM_FILE": str(output / ROMS[1][5:]),
            "+VELOCITY_ROM_PATH": str(output / ROMS[2][5:]),
            "+WAVETABLE_PATH": str(output / ROMS[3][5:]),
        },
        "note": "timbre_oscillator standalone basename defaults are overridden by piano_triangle_voice; both initial ROM reads execute in simulation regardless of synthesis removal. DDS ROM_FILE defaults are overridden by bound +WAVETABLE_PATH.",
    }


def prepare(repo: Path, output: Path, expected: Path, tool_root: Path,
            top: str = "tb_electronic_piano_top") -> Path:
    repo, output, expected, tool_root = (Path(value).resolve() for value in (repo, output, expected, tool_root))
    if not output.is_relative_to(repo / "code/output") or not output.name.startswith(PREFIX):
        raise GateError("OUTPUT_SCOPE_REJECT")
    if output.exists():
        raise GateError("OUTPUT_ALREADY_EXISTS")
    frozen = read_json(expected)
    if frozen.get("schema") != EXPECTED_SCHEMA:
        raise GateError("EXPECTED_SCHEMA_REJECT")
    if Path(frozen["tool_root"]).resolve() != tool_root:
        raise GateError("TOOL_ROOT_REJECT")
    required, _ = required_files(repo)
    missing = set(required) - set(frozen.get("files", {}))
    if missing:
        raise GateError("MISSING_FROZEN_INPUT:" + ",".join(sorted(missing)))
    missing = required_tools(tool_root) - set(frozen.get("tools", {}))
    if missing:
        raise GateError("MISSING_TOOL_DEPENDENCY:" + ",".join(sorted(missing)))
    before_files = identity(repo, frozen["files"])
    before_tools = identity(tool_root, frozen["tools"])
    if before_files[JOB_REL] != JOB_SHA:
        raise GateError("OWNED_JOB_IDENTITY_REJECT")
    bound_commands = commands(repo, output, tool_root, top)
    closure = rom_contract(repo, output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "temp").mkdir()
    shutil.copyfile(expected, output / "expected.json")
    mapped = {}
    for relative in ROMS:
        target = output / relative[5:]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / relative, target)
        mapped[relative[5:]] = before_files[relative]
    (output / "lower.ys").write_text(lower_text(repo, output), encoding="utf-8", newline="\n")
    generated = {relative: sha(output / relative) for relative in mapped}
    generated["lower.ys"] = sha(output / "lower.ys")
    runner = Path(__file__).resolve()
    config = {
        "schema": SCHEMA, "repo": str(repo), "output": str(output),
        "tool_root": str(tool_root), "top": top, "pass_token": TOPS[top],
        "total_seconds": TOTAL_SECONDS, "commands": bound_commands,
        "environment": environment(tool_root, output),
        "expected_origin": str(expected), "expected_sha256": sha(expected),
        "inputs_before": before_files, "tools_before": before_tools,
        "mapped_roms": mapped, "generated": generated,
        "runner": str(runner), "runner_sha256": sha(runner),
        "scope": "ISOLATED_TOP_SIMULATION_NOT_HARDWARE",
        "rom_contract": closure,
    }
    config_path = output / "config.json"
    write_json(config_path, config)
    (output / "config.sha256").write_text(sha(config_path) + "\n", encoding="ascii")
    return config_path


def verify(config: Path) -> dict:
    config_path = Path(config).resolve()
    frozen_config = read_json(config_path)
    if frozen_config.get("schema") != SCHEMA:
        raise GateError("CONFIG_SCHEMA_REJECT")
    output = Path(frozen_config["output"]).resolve()
    if config_path != output / "config.json":
        raise GateError("CONFIG_LOCATION_REJECT")
    if sha(config_path) != (output / "config.sha256").read_text(encoding="ascii").strip():
        raise GateError("CONFIG_SHA_REJECT")
    repo, tool_root = Path(frozen_config["repo"]).resolve(), Path(frozen_config["tool_root"]).resolve()
    if not output.is_relative_to(repo / "code/output") or not output.name.startswith(PREFIX):
        raise GateError("OUTPUT_SCOPE_REJECT")
    expected = read_json(output / "expected.json")
    if sha(output / "expected.json") != frozen_config["expected_sha256"]:
        raise GateError("EXPECTED_SHA_REJECT")
    if sha(Path(frozen_config["expected_origin"])) != frozen_config["expected_sha256"]:
        raise GateError("EXPECTED_ORIGIN_CHANGED")
    required, _ = required_files(repo)
    if set(required) - set(expected["files"]) or required_tools(tool_root) - set(expected["tools"]):
        raise GateError("CLOSURE_CHANGED")
    if frozen_config["inputs_before"] != expected["files"] or frozen_config["tools_before"] != expected["tools"]:
        raise GateError("EXPECTED_BINDING_REJECT")
    if frozen_config["commands"] != commands(repo, output, tool_root, frozen_config["top"]):
        raise GateError("COMMAND_BINDING_REJECT")
    if frozen_config["rom_contract"] != rom_contract(repo, output):
        raise GateError("ROM_CONTRACT_BINDING_REJECT")
    if frozen_config["environment"] != environment(tool_root, output):
        raise GateError("ENVIRONMENT_DRIFT")
    if frozen_config["total_seconds"] != TOTAL_SECONDS or frozen_config["pass_token"] != TOPS[frozen_config["top"]]:
        raise GateError("CONTRACT_BINDING_REJECT")
    if sha(Path(frozen_config["runner"])) != frozen_config["runner_sha256"]:
        raise GateError("RUNNER_CHANGED")
    identity(repo, expected["files"])
    identity(tool_root, expected["tools"])
    identity(output, frozen_config["generated"])
    if (output / "lower.ys").read_text(encoding="utf-8") != lower_text(repo, output):
        raise GateError("LOWER_SCRIPT_CHANGED")
    return {"passed": True, "config_sha256": sha(config_path), "inputs": len(expected["files"]),
            "tools": len(expected["tools"]), "tool_calls": 0, "mapped_roms": frozen_config["mapped_roms"]}


def audit_logs(stdout: Path, stderr: Path, exit_code: int, pass_token: str,
               require_finish: bool = True) -> dict:
    raw_out, raw_err = Path(stdout).read_bytes(), Path(stderr).read_bytes()
    text = raw_out.decode("utf-8", errors="strict")
    errors = raw_err.decode("utf-8", errors="strict")
    reasons = []
    if type(exit_code) is not int or exit_code != 0:
        reasons.append("TOOL_NONZERO")
    if not raw_out or not raw_out.endswith(b"\n") or (raw_err and not raw_err.endswith(b"\n")):
        reasons.append("TRUNCATED_LOG")
    match = BAD_LOG.search(text + "\n" + errors)
    if match:
        reasons.append("LOG_ERROR:" + match.group(0))
    token = text.find(pass_token)
    if not pass_token or token < 0:
        reasons.append("MISSING_PASS")
    finish = re.search(r"\$finish called at[^\r\n]*", text)
    if require_finish and (not finish or finish.start() < token):
        reasons.append("MISSING_FINISH_AFTER_PASS")
    if require_finish and finish and text[finish.end():].strip():
        reasons.append("DATA_AFTER_FINISH")
    return {"passed": not reasons, "reasons": reasons, "exit_code": exit_code,
            "stdout_sha256": sha(Path(stdout)), "stderr_sha256": sha(Path(stderr)),
            "require_finish": require_finish,
            "scope": "COMPLETE_SIMULATION_LOG" if require_finish else "DIAGNOSTIC_ONLY"}


def _job_module(repo: Path):
    path = repo / JOB_REL
    if sha(path) != JOB_SHA:
        raise GateError("OWNED_JOB_IDENTITY_REJECT")
    spec = importlib.util.spec_from_file_location("rom_gate_owned_job", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _execute(command: list[str], cwd: Path, env: dict, seconds: float,
             stdout_path: Path, stderr_path: Path, job_module) -> dict:
    if seconds <= 0:
        raise GateError("BUDGET_EXHAUSTED_BEFORE_LAUNCH")
    job = job_module.WindowsJob()
    started = time.monotonic()
    result = {"argv": command, "cwd": str(cwd), "environment": env,
              "limit_seconds": seconds, "started": False, "timeout": False}
    try:
        with stdout_path.open("xb") as out, stderr_path.open("xb") as err:
            child = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                     creationflags=0x00000004)
            result["started"] = True
            job.attach_and_resume(child)
            try:
                child.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                result["timeout"] = True
                result["termination"] = job.terminate()
                child.wait(timeout=5)
            result["exit_code"] = child.returncode
    except Exception as error:
        result["error"] = type(error).__name__ + ":" + str(error)
        result.setdefault("exit_code", None)
    finally:
        job.close()
        result["elapsed_seconds"] = time.monotonic() - started
    return result


def run(config: Path) -> dict:
    started = time.monotonic()
    path = Path(config).resolve()
    frozen = read_json(path)
    output, repo = Path(frozen["output"]), Path(frozen["repo"])
    if not output.resolve().is_relative_to(repo.resolve() / "code/output") or not output.name.startswith(PREFIX):
        raise GateError("OUTPUT_SCOPE_REJECT")
    receipt = {"passed": False, "stages": [], "tool_calls": 0,
               "config_sha256": sha(path), "total_bound": TOTAL_SECONDS,
               "top": frozen["top"], "scope": frozen["scope"]}
    # Never reopen old logs/artifacts or overwrite a consumed attempt.
    if (output / "consumed.json").exists() or any((output / name).exists() for name in ("allocator.v", "tb.vvp", "receipt.json")):
        raise GateError("ATTEMPT_ALREADY_CONSUMED")
    try:
        receipt["preflight"] = verify(path)
        if os.name != "nt":
            raise GateError("WINDOWS_JOB_REQUIRED")
        job_module = _job_module(repo)
        write_json(output / "consumed.json", {"config_sha256": sha(path), "pid": os.getpid(), "consumed": True})
        for stage in frozen["commands"]:
            # Reserve time for both postflight identity checks and final receipt.
            remaining = TOTAL_SECONDS - (time.monotonic() - started) - 15
            limit = min(stage["limit"], remaining)
            if stage["name"] == "simulate":
                if not (output / "tb.vvp").is_file() or receipt["stages"][-1]["exit_code"] != 0:
                    raise GateError("FRESH_COMPILE_REQUIRED")
                receipt["vvp_before_run_sha256"] = sha(output / "tb.vvp")
            out, err = output / (stage["name"] + ".stdout.log"), output / (stage["name"] + ".stderr.log")
            result = _execute(stage["argv"], output, frozen["environment"], limit, out, err, job_module)
            result["name"] = stage["name"]
            result["stdout_sha256"], result["stderr_sha256"] = sha(out), sha(err)
            receipt["stages"].append(result)
            receipt["tool_calls"] += int(result["started"])
            if result["timeout"] or result["exit_code"] != 0:
                raise GateError("STAGE_FAILED:" + stage["name"])
            log_text = out.read_text(encoding="utf-8", errors="strict") + err.read_text(encoding="utf-8", errors="strict")
            if BAD_LOG.search(log_text):
                raise GateError("STAGE_LOG_ERROR:" + stage["name"])
            artifact = output / ("allocator.v" if stage["name"] == "lower" else "tb.vvp")
            if stage["name"] != "simulate" and (not artifact.is_file() or artifact.stat().st_size == 0):
                raise GateError("MISSING_FRESH_ARTIFACT:" + stage["name"])
        receipt["audit"] = audit_logs(output / "simulate.stdout.log", output / "simulate.stderr.log", 0, frozen["pass_token"])
        if not receipt["audit"]["passed"]:
            raise GateError("SIMULATION_LOG_REJECT")
        receipt["postflight"] = verify(path)
        receipt["passed"] = True
    except Exception as error:
        receipt["error"] = type(error).__name__ + ":" + str(error)
    finally:
        expected = read_json(output / "expected.json")
        receipt["inputs_before"], receipt["tools_before"] = frozen["inputs_before"], frozen["tools_before"]
        receipt["inputs_after"] = {name: sha(inside(repo, name)) if inside(repo, name).is_file() else None for name in expected["files"]}
        tool_root = Path(frozen["tool_root"])
        receipt["tools_after"] = {name: sha(inside(tool_root, name)) if inside(tool_root, name).is_file() else None for name in expected["tools"]}
        receipt["artifacts"] = {name: sha(output / name) for name in ("allocator.v", "tb.vvp") if (output / name).is_file()}
        receipt["elapsed_seconds"] = time.monotonic() - started
        if receipt["elapsed_seconds"] > TOTAL_SECONDS or receipt["inputs_before"] != receipt["inputs_after"] or receipt["tools_before"] != receipt["tools_after"]:
            receipt["passed"] = False
        receipt["runner_exit"] = 0 if receipt["passed"] else 1
        write_json(output / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    prep = sub.add_parser("prepare")
    for option in ("repo", "output", "expected", "tool-root"):
        prep.add_argument("--" + option, required=True, type=Path)
    prep.add_argument("--top", choices=TOPS, default="tb_electronic_piano_top")
    for operation in ("verify", "run"):
        sub.add_parser(operation).add_argument("--config", required=True, type=Path)
    audit = sub.add_parser("audit")
    audit.add_argument("--stdout", required=True, type=Path)
    audit.add_argument("--stderr", required=True, type=Path)
    audit.add_argument("--exit-code", required=True, type=int)
    audit.add_argument("--pass-token", required=True)
    audit.add_argument("--no-finish", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            path = prepare(args.repo, args.output, args.expected, args.tool_root, args.top)
            result = {"passed": True, "config": str(path), "config_sha256": sha(path), "tool_calls": 0}
        elif args.operation == "verify":
            result = verify(args.config)
        elif args.operation == "run":
            result = run(args.config)
        else:
            result = audit_logs(args.stdout, args.stderr, args.exit_code, args.pass_token, not args.no_finish)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["passed"] else 1
    except Exception as error:
        print(json.dumps({"passed": False, "error": type(error).__name__ + ":" + str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
