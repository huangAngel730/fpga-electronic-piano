"""Prepare, verify, and execute the reviewed N32/R1 B qualification.

Preparation is fail-closed on a successful N32-A receipt and copies every HDL,
checker, model, ROM, include, and vendor simulation input into one immutable-by-
identity snapshot.  Execution additionally requires the exact reviewed plan SHA
and repeats the A receipt/allocator binding before starting any child process.

This harness has no lowering or EDA step.  It runs exactly four cases: one long
normal case and three short output-only behavioral mutants.  Each case receives
one compile, one simulation, and one independent checker invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import time
import zipfile


HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parents[4]


def _bootstrap_repo_root() -> Path:
    """Read the reviewed repository root before argparse initializes."""
    if "--repo-root" not in sys.argv:
        return SOURCE_ROOT
    index = sys.argv.index("--repo-root")
    require_value = index + 1 < len(sys.argv)
    if not require_value:
        raise ValueError("REPO_ROOT_ARGUMENT_MISSING")
    return Path(sys.argv[index + 1]).resolve()


ROOT = _bootstrap_repo_root()
SNAPSHOT_MODE = SOURCE_ROOT.resolve() != ROOT.resolve()
HELPERS = SOURCE_ROOT / "code/software/t052_runner_acceptance_candidate_20261012"
sys.path.insert(0, str(HELPERS))

from runner import identity, load_json, require, safe_member, write_json  # noqa: E402
from runner_tail_20261013 import _run_process, finalize_receipt  # noqa: E402
sys.path.insert(0, str(HERE))
from b_progress import run_simulation  # noqa: E402


class Budget:
    """B-only extended wall budget authorized by the user on 2026-10-14."""

    def __init__(self, seconds, clock=time.monotonic):
        require(type(seconds) in (int, float) and 0 < seconds <= 345600,
                "B_EXTENDED_TOTAL_BUDGET_LIMIT")
        self.seconds = float(seconds)
        self.clock = clock
        self.started = clock()

    def elapsed(self):
        return self.clock() - self.started

    def remaining(self, cap):
        left = self.seconds - self.elapsed()
        require(left > 0, "TOTAL_BUDGET_EXHAUSTED")
        require(type(cap) in (int, float) and cap > 0, "STEP_BUDGET_INVALID")
        return min(float(cap), left)


SCHEMA = "T061_N32_B_REVIEWED_PLAN_V2"
A_PASS_STATUS = "ALLOCATOR_COMPARISON_AND_MUTATIONS_PASS"
COMPILER_RUNTIME_DLLS = (
    "libgcc_s_seh-1.dll",
    "libstdc++-6.dll",
    "libwinpthread-1.dll",
)
TOOL_ENVIRONMENT_KEYS = {"PATH", "YOSYSHQ_ROOT"}
A_ALLOCATOR = (
    SOURCE_ROOT
    / "code/rtl/common/m3_n32_allocator_candidate_20261013"
    / "m3_balanced_voice_allocator.sv"
)
FROZEN = SOURCE_ROOT / "code/rtl/138K_try/hold_trials_20261005/L_locations_guard065"
POLY = SOURCE_ROOT / "code/rtl/common/polyphony_scaling_candidate"
PROM = SOURCE_ROOT / "code/rtl/common/m2_n32_prom_candidate_20261013"
B_RTL = SOURCE_ROOT / "code/rtl/common/m3_n32_allocator_candidate_20261013/B"
PY_MODEL = SOURCE_ROOT / "code/software/polyphony_scaling_candidate"
MATH_MODEL = SOURCE_ROOT / "code/software/audio_math_acceptance_candidate"
VENDOR_MODEL = Path(
    "E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03/"
    "IDE/simlib/gw5a/prim_sim.v"
)
VENDOR_MODEL_SHA = "202f65ccf77126d04e47db36c95e237e48522f3a105a3e64d9fcbf4e3b782f27"


# These identities are already frozen by the B2L and pROM preparation receipts.
# B-specific files and the A allocator are intentionally bound at prepare time.
AUTHORITY_SHA = {
    FROZEN / "sources/audio_defs_pkg.sv":
        "833076283882bae79af3f54c40e6cd6ae4a9ff5638a90e4f0afc3e2b3861d064",
    FROZEN / "sources/sustain_control_contract_pkg.sv":
        "329d855dea5885cbcd97e5c8ab75c5283bbb15db33cab3460bde637be7b207a2",
    FROZEN / "sources/note_pitch.sv":
        "9a86ebea3041f73d8624c0dc9a32844ef13c448b46d911d39f94ebb39ee88e69",
    POLY / "b1_statebank.sv":
        "9ab598affbd317dedb5bdd7e099335ad1f60e3c84ed115f6669d52b3966521ed",
    POLY / "b1_scheduler.sv":
        "e11c2fb7e4c80160d42b44948003863892435050e27e47afc6e61ad6d5b78c9d",
    POLY / "b2c_sustain_controller.sv":
        "ebb942402e190c136a6ff0d2fd751cabdbf34a83be75bf7953360f0d8534a2d5",
    POLY / "b2d_control_snapshot.sv":
        "9cb23b971d243e1dcf43d2acf0445239f1f26b2f0edc51476ce6a0d5c5d450fd",
    PROM / "m2_prom_gain.sv":
        "5321b6e854ad5be02f78f7e82c8ba311ddce72c28ce7ca72323a9ef84adc17b0",
    PROM / "m2_prom_oct.sv":
        "2f5d8e901eba60634ae2daa40d29e0c074520e2f7fb5111f00882f5c30874b5b",
    PROM / "m2_prom_sub.sv":
        "b683d5d49834632e3413a3038ea5b8f5c79c7c783a7cfe47e8c8f8cb124d9c23",
    PROM / "m2_prom_lfo.sv":
        "f5684f760ed41a7ac86284e36ade73bbaa36e0b48dde2c765203843c29283fee",
    PROM / "m2_prom_wave.sv":
        "fa606e6e05ed36ad9b880f19684a0b7859262e56c9a104df30bef59d8b04f909",
    PROM / "m2_adsr_piano_prom.sv":
        "d8918defedb1d9bd14a21903d5bc955a815f5064860ed948fa1f38e585e06087",
    PROM / "m2_pitch_mod_prom.sv":
        "190cf8a854563ab64cdd1afe16da40a8f061613636b6f3183c28eb8272c33b50",
    PROM / "m2_b2_backend_prom.sv":
        "6727971f60c5aadab9985641035ec5ff8ad284f1e06adcfd9e58f78cf74d6953",
    VENDOR_MODEL: VENDOR_MODEL_SHA,
}


HDL_SOURCES = [
    FROZEN / "sources/audio_defs_pkg.sv",
    FROZEN / "sources/sustain_control_contract_pkg.sv",
    FROZEN / "sources/note_pitch.sv",
    POLY / "b1_statebank.sv",
    POLY / "b1_scheduler.sv",
    A_ALLOCATOR,
    POLY / "b2c_sustain_controller.sv",
    B_RTL / "b_n32_event_router.sv",
    POLY / "b2d_control_snapshot.sv",
    PROM / "m2_prom_gain.sv",
    PROM / "m2_prom_oct.sv",
    PROM / "m2_prom_sub.sv",
    PROM / "m2_prom_lfo.sv",
    PROM / "m2_prom_wave.sv",
    PROM / "m2_adsr_piano_prom.sv",
    PROM / "m2_pitch_mod_prom.sv",
    PROM / "m2_b2_backend_prom.sv",
    B_RTL / "b_n32_event_audio_prom.sv",
    B_RTL / "b_n32_r1_wrapper.sv",
    VENDOR_MODEL,
    SOURCE_ROOT / "code/tb/common/polyphony_scaling_candidate/tb_b2d_event_audio.sv",
    HERE / "b_n32_observer.sv",
    HERE / "tb_b_n32_r1.sv",
]

SUPPORT_INPUTS = [
    HERE / "b_harness.py",
    HERE / "b_launch.py",
    HERE / "b_progress.py",
    HERE / "b_delivery.py",
    HERE / "b_n32_check.py",
    B_RTL / "b_n32_c_interface.json",
    PY_MODEL / "b2c_check.py",
    PY_MODEL / "inventory.py",
    PY_MODEL / "b2_clock.py",
    PY_MODEL / "b2c_router_model.py",
    MATH_MODEL / "strict_capture.py",
    MATH_MODEL / "dds_model.py",
    MATH_MODEL / "envelope_model.py",
    HELPERS / "runner.py",
    HELPERS / "runner_tail_20261013.py",
    HELPERS / "windows_job.py",
    HELPERS / "supervisor_20261013.py",
    FROZEN / "include/sine_table.svh",
    FROZEN / "include/sustain_controller_ports.svh",
    FROZEN / "rom/velocity_gain_rom.mem",
    FROZEN / "rom/piano_band_4x256_8191.mem",
    FROZEN / "rom/oct_ratio_q16.mem",
    FROZEN / "rom/sub_ratio_q16.mem",
    FROZEN / "rom/lfo_sine_q15.mem",
]

CASES = (
    ("normal_long", None, 1, 0, "N32_B_R1_EVENT_AUDIO_PASS_T061_PARTIAL"),
    ("wrong_id", "B_N32_MUTANT_RESULT_ID", 0, 1, "RESULT_ID_LEDGER"),
    ("wrong_pcm", "B_N32_MUTANT_PCM", 0, 1, "RESULT_PCM_LEDGER"),
    ("wrong_clipped", "B_N32_MUTANT_CLIPPED", 0, 1, "RESULT_CLIPPED_LEDGER"),
)


def under_output(path: Path) -> Path:
    path = Path(path).resolve()
    lexical_root = (ROOT / "code/output").absolute()
    require(lexical_root.is_dir() and not lexical_root.is_symlink(),
            "OUTPUT_ROOT_MISSING_OR_SYMLINK")
    if os.name == "nt":
        attributes = lexical_root.stat().st_file_attributes
        require(not attributes & 0x400, "OUTPUT_ROOT_REPARSE_POINT")
    output_root = lexical_root.resolve()
    require(output_root == lexical_root, "OUTPUT_ROOT_REDIRECTED")
    require(path != output_root and path.is_relative_to(output_root),
            "OUTPUT_OUTSIDE_CODE_OUTPUT")
    return path


def snapshot_name(path: Path) -> str:
    """Return a collision-free, portable path below the prepared snapshot."""
    path = path.resolve()
    root = SOURCE_ROOT.resolve()
    if path.is_relative_to(root):
        return path.relative_to(root).as_posix()
    require(path == VENDOR_MODEL.resolve(), "EXTERNAL_INPUT_NOT_VENDOR_MODEL")
    return "vendor/gw5a/prim_sim.v"


def tool_inventory(suite: Path) -> tuple[dict, dict]:
    suite = Path(suite).resolve()
    tools = {
        "python": Path(sys.executable).resolve(),
        "compile": suite / "bin/iverilog.exe",
        "simulate": suite / "bin/vvp.exe",
    }
    files = set(tools.values())
    files.update((suite / "bin").glob("*.dll"))
    files.update((suite / "lib").glob("*.dll"))
    files.update(path for path in (suite / "lib/ivl").rglob("*") if path.is_file())
    python_root = tools["python"].parent
    files.update(python_root.glob("*.dll"))
    for folder in (python_root / "Lib", python_root / "DLLs"):
        files.update(path for path in folder.rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts
                     and path.suffix.lower() != ".pyc")
    require(all(path.is_file() for path in tools.values()), "TOOL_MISSING")
    require(all((suite / "lib" / name).is_file()
                for name in COMPILER_RUNTIME_DLLS),
            "COMPILER_RUNTIME_DLL_MISSING")
    return ({name: str(path) for name, path in tools.items()},
            {str(path): identity(path) for path in sorted(files)})


def copy_compiler_capsule(prepared: Path, suite: Path,
                          origin_tools: dict, origin_files: dict) -> tuple[dict, dict, Path]:
    """Copy the exact Icarus executable/plugin closure into the reviewed tree."""
    suite = Path(suite).resolve()
    capsule_root = prepared / "tools/iverilog"
    capsule_files = {}
    for name, expected in origin_files.items():
        source = Path(name).resolve()
        if not source.is_relative_to(suite):
            continue
        relative = source.relative_to(suite)
        target = safe_member(capsule_root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        require(identity(target) == expected,
                "COMPILER_CAPSULE_COPY_DRIFT:" + relative.as_posix())
        capsule_files[str(target)] = expected

    compile_tool = safe_member(
        capsule_root, Path(origin_tools["compile"]).resolve().relative_to(suite)
    )
    simulate_tool = safe_member(
        capsule_root, Path(origin_tools["simulate"]).resolve().relative_to(suite)
    )
    compiler_lib = safe_member(capsule_root, Path("lib/ivl/.capsule_anchor")).parent
    require(compile_tool.is_file() and simulate_tool.is_file()
            and compiler_lib.is_dir(), "COMPILER_CAPSULE_INCOMPLETE")
    tools = {
        "python": origin_tools["python"],
        "compile": str(compile_tool),
        "simulate": str(simulate_tool),
    }
    python_files = {
        name: expected for name, expected in origin_files.items()
        if not Path(name).resolve().is_relative_to(suite)
    }
    bound_files = {**python_files, **capsule_files}
    validate_compiler_dll_closure(capsule_root, bound_files)
    return tools, bound_files, compiler_lib


def validate_compiler_dll_closure(capsule_root: Path,
                                  tool_files: dict) -> str:
    """Require the load-visible bin/lib DLL set to equal the frozen manifest."""
    capsule_root = Path(capsule_root).resolve()
    visible_dirs = (
        safe_member(capsule_root, "bin"),
        safe_member(capsule_root, "lib"),
    )
    expected = {}
    for name, file_identity in tool_files.items():
        path = Path(name).resolve()
        if path.suffix.lower() == ".dll" and path.parent in visible_dirs:
            expected[path.relative_to(capsule_root).as_posix()] = file_identity
    actual_paths = {
        path.resolve()
        for folder in visible_dirs
        for path in folder.glob("*.dll")
        if path.is_file()
    }
    actual = {
        path.relative_to(capsule_root).as_posix(): identity(path)
        for path in actual_paths
    }
    require(set(actual) == set(expected), "COMPILER_DLL_CLOSURE_DRIFT")
    require(actual == expected, "COMPILER_DLL_IDENTITY_DRIFT")
    return hashlib.sha256(
        json.dumps(actual, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def compiler_environment(capsule_root: Path) -> dict[str, str]:
    """Return the exact loader overrides without invoking environment.bat."""
    capsule_root = Path(capsule_root).resolve()
    compiler_bin = safe_member(capsule_root, "bin")
    runtime_lib = safe_member(capsule_root, "lib")
    require(compiler_bin.is_dir() and runtime_lib.is_dir(),
            "COMPILER_ENVIRONMENT_DIRECTORY_MISSING")
    require(all(safe_member(runtime_lib, name).is_file()
                for name in COMPILER_RUNTIME_DLLS),
            "COMPILER_ENVIRONMENT_DLL_MISSING")
    return {
        "PATH": os.pathsep.join((str(compiler_bin), str(runtime_lib))),
        "YOSYSHQ_ROOT": str(capsule_root),
    }


def _run_process_with_environment(output: Path, label: str, argv: list[str],
                                  cwd: Path, cap: int, budget: Budget,
                                  environment: dict[str, str]) -> dict:
    """Run one child with reviewed loader overrides and restore the parent."""
    require(set(environment) == TOOL_ENVIRONMENT_KEYS,
            "TOOL_ENVIRONMENT_KEYS")
    require(all(isinstance(value, str) and value for value in environment.values()),
            "TOOL_ENVIRONMENT_VALUE")
    previous = {key: os.environ.get(key) for key in TOOL_ENVIRONMENT_KEYS}
    try:
        os.environ.update(environment)
        if label.endswith('_simulate'):
            return run_simulation(output, label, argv, cwd, cap, budget)
        return _run_process(output, label, argv, cwd, cap, budget)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def validate_a_gate(receipt_path: Path, receipt_sha: str,
                    allocator_sha: str, review_key: str) -> dict:
    receipt_path = Path(receipt_path).resolve()
    require(len(receipt_sha) == 64 and len(allocator_sha) == 64, "A_SHA_SCHEMA")
    require(review_key.startswith("T061-N32-A-RESULT-") or
            review_key == "N32-A-FUNCTION-RECOVERY-20261014-R01",
            "A_REVIEW_KEY_SCHEMA")
    require(identity(receipt_path)["sha256"] == receipt_sha, "A_RECEIPT_SHA")
    require(identity(A_ALLOCATOR)["sha256"] == allocator_sha, "A_ALLOCATOR_SHA")
    receipt = load_json(receipt_path)
    require(receipt.get("status") == A_PASS_STATUS and receipt.get("exit_code") == 0,
            "A_RECEIPT_NOT_PASS")
    require(receipt.get("automatic_retries") == 0, "A_RECEIPT_RETRY")
    after = receipt.get("identities_after", {})
    allocator_origin = (
        ROOT
        / "code/rtl/common/m3_n32_allocator_candidate_20261013"
        / "m3_balanced_voice_allocator.sv"
    )
    relative = allocator_origin.relative_to(ROOT).as_posix()
    bindings = [after[key] for key in (str(allocator_origin), relative)
                if key in after]
    require(bool(bindings) and all(value == identity(A_ALLOCATOR)
                                  for value in bindings),
            "A_RECEIPT_ALLOCATOR_BINDING")
    require(receipt.get("EDA_calls") == 0, "A_RECEIPT_EDA_SCOPE")
    return receipt


def _copy_snapshot(prepared: Path, paths: list[Path]) -> list[dict]:
    snapshot = prepared / "snapshot"
    records = []
    names = set()
    for source in paths:
        source = Path(source).resolve()
        require(source.is_file(), "INPUT_MISSING:" + str(source))
        relative = snapshot_name(source)
        require(relative not in names, "SNAPSHOT_NAME_COLLISION:" + relative)
        names.add(relative)
        target = safe_member(snapshot, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        source_id = identity(source)
        require(identity(target) == source_id, "SNAPSHOT_COPY_DRIFT:" + relative)
        records.append({
            "role": "HDL" if source in HDL_SOURCES else "SUPPORT",
            "origin": str(source),
            "snapshot": relative,
            **source_id,
        })
    return records


def _snapshot_path(plan: dict, relative: str) -> Path:
    return safe_member(Path(plan["prepared"]) / "snapshot", relative)


def _source_snapshot(records: list[dict], origin: Path) -> str:
    matches = [row["snapshot"] for row in records
               if Path(row["origin"]).resolve() == Path(origin).resolve()]
    require(len(matches) == 1, "SOURCE_MANIFEST_LOOKUP:" + str(origin))
    return matches[0]


def _validate_step_snapshot_binding(plan: dict) -> None:
    """Prove every executable step consumes sealed inputs, never live sources."""
    active_origins = {str(Path(row["origin"]).resolve()) for row in plan["inputs"]}
    hdl_snapshots = [str(_snapshot_path(plan, snapshot_name(path)))
                     for path in HDL_SOURCES]
    checker_snapshot = str(_snapshot_path(plan, snapshot_name(HERE / "b_n32_check.py")))
    include_snapshot = str(_snapshot_path(
        plan, snapshot_name(FROZEN / "include/sine_table.svh")
    ))
    include_dir = str(Path(include_snapshot).parent)

    for step in plan["steps"]:
        argv = [str(item) for item in step["argv"]]
        require(active_origins.isdisjoint(argv),
                "ACTIVE_REPOSITORY_INPUT:" + step["label"])
        if step["kind"] == "compile":
            require(all(argv.count(path) == 1 for path in hdl_snapshots),
                    "COMPILE_NOT_SNAPSHOT_BOUND:" + step["label"])
            require("-B" in argv
                    and argv[argv.index("-B") + 1] == plan["compiler_lib"],
                    "COMPILER_LIB_NOT_CAPSULE_BOUND:" + step["label"])
            require("-I" in argv and argv[argv.index("-I") + 1] == include_dir,
                    "INCLUDE_NOT_SNAPSHOT_BOUND:" + step["label"])
        elif step["kind"] == "check":
            require(argv.count(checker_snapshot) == 1,
                    "CHECKER_NOT_SNAPSHOT_BOUND:" + step["label"])


def prepare(prepared: Path, execution_output: Path, suite: Path,
            a_receipt: Path, a_receipt_sha: str, a_allocator_sha: str,
            a_review_key: str) -> dict:
    require(not SNAPSHOT_MODE, "PREPARE_REQUIRES_ACTIVE_SOURCE_TREE")
    prepared = under_output(prepared)
    execution_output = under_output(execution_output)
    require(not prepared.exists() and not execution_output.exists(), "OUTPUT_EXISTS")
    validate_a_gate(a_receipt, a_receipt_sha, a_allocator_sha, a_review_key)
    for path, expected in AUTHORITY_SHA.items():
        require(identity(path)["sha256"] == expected,
                "FROZEN_AUTHORITY_DRIFT:" + str(path))

    prepared.mkdir(parents=True)
    inputs = _copy_snapshot(prepared, list(dict.fromkeys(HDL_SOURCES + SUPPORT_INPUTS)))
    # The A receipt is an external prerequisite, not a compile/check input.  It
    # is copied separately so the reviewed package carries the exact evidence.
    dependency_copy = prepared / "dependency/a_receipt.json"
    dependency_copy.parent.mkdir()
    dependency_copy.write_bytes(Path(a_receipt).read_bytes())
    require(identity(dependency_copy)["sha256"] == a_receipt_sha,
            "A_RECEIPT_SNAPSHOT_DRIFT")

    origin_tools, origin_tool_files = tool_inventory(suite)
    tools, tool_files, compiler_lib = copy_compiler_capsule(
        prepared, suite, origin_tools, origin_tool_files
    )
    compiler_root = Path(tools["compile"]).resolve().parent.parent
    environment = compiler_environment(compiler_root)
    compiler_dll_closure_sha256 = validate_compiler_dll_closure(
        compiler_root, tool_files
    )
    snapshot_root = prepared / "snapshot"
    compile_sources = [str(_snapshot_path({"prepared": str(prepared)},
                                           _source_snapshot(inputs, path)))
                       for path in HDL_SOURCES]
    include_dir = snapshot_root / snapshot_name(FROZEN / "include/sine_table.svh")
    include_dir = include_dir.parent
    checker = _snapshot_path({"prepared": str(prepared)},
                             _source_snapshot(inputs, HERE / "b_n32_check.py"))
    capsule_runner = _snapshot_path(
        {"prepared": str(prepared)},
        _source_snapshot(inputs, HERE / "b_harness.py"),
    )

    steps = []
    cases = []
    for name, mutation, long_case, check_exit, diagnostic in CASES:
        work = execution_output / "work" / name
        image = work / "sim.vvp"
        report = work / "report.json"
        compile_argv = [
            tools["compile"], "-B", str(compiler_lib),
            "-g2012", "-I", str(include_dir), "-s", "tb_b_n32_r1",
            "-DB2C_N=32", "-DB2C_RESPONSE=1", f"-DB2C_LONG={long_case}",
        ]
        if mutation:
            compile_argv.append("-D" + mutation)
        compile_argv.extend(["-o", str(image), *compile_sources])
        simulate_label = name + "_simulate"
        capture = execution_output / (simulate_label + ".stdout.bin")
        check_argv = [
            tools["python"], "-I", "-S", "-B", "-X", "utf8",
            str(checker), "--input", str(capture), "--output", str(report),
        ]
        cases.append({
            "name": name, "mutation_define": mutation, "long": long_case,
            "work": str(work), "expected_checker_exit": check_exit,
            "required_diagnostic": diagnostic,
        })
        steps.extend([
            {"label": name + "_compile", "kind": "compile",
             "argv": compile_argv, "cwd": str(work), "timeout_seconds": 300,
             "calls": 1, "expected_exit": 0, "marker": None},
            {"label": simulate_label, "kind": "simulate",
             "argv": [tools["simulate"], str(image)], "cwd": str(work),
             "timeout_seconds": 86400, "calls": 1, "expected_exit": 0,
             "marker": "END "},
            {"label": name + "_check", "kind": "check",
             "argv": check_argv, "cwd": str(work), "timeout_seconds": 300,
             "calls": 1, "expected_exit": check_exit, "marker": diagnostic},
        ])

    plan = {
        "schema": SCHEMA,
        "hostname": socket.gethostname(),
        "repo": str(ROOT),
        "execution_entrypoint": str(capsule_runner),
        "execution_argv_prefix": [
            tools["python"], "-I", "-S", "-B", "-X", "utf8",
            str(capsule_runner), "--repo-root", str(ROOT), "execute",
        ],
        "prepared": str(prepared),
        "execution_output": str(execution_output),
        "configuration": {"N": 32, "ROM_RESPONSE_CYCLES": 1},
        "total_seconds": 345600,
        "tool_step_max_seconds": 86400,
        "time_extension_authority": "USER_20261014_EXTEND_WHILE_PROGRESSING",
        "tools": tools,
        "tool_files": tool_files,
        "tool_origins": origin_tools,
        "tool_origin_files": origin_tool_files,
        "compiler_lib": str(compiler_lib),
        "compiler_dll_closure_sha256": compiler_dll_closure_sha256,
        "environment": environment,
        "environment_policy": "INHERIT_HOST_WITH_EXACT_LOADER_OVERRIDES",
        "environment_bat_invoked": False,
        "inputs": inputs,
        "snapshot_manifest_sha256": hashlib.sha256(
            json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "dependency_gate": {
            "status": "A_PASS_BOUND",
            "a_receipt_origin": str(Path(a_receipt).resolve()),
            "a_receipt_snapshot": "dependency/a_receipt.json",
            "a_receipt_sha256": a_receipt_sha,
            "a_allocator_path": str(A_ALLOCATOR),
            "a_allocator_sha256": a_allocator_sha,
            "a_result_review_key": a_review_key,
        },
        "cases": cases,
        "steps": steps,
        "status": "PREPARED_NOT_EXECUTED_REVIEW_REQUIRED",
        "review_required": True,
        "lower_calls": 0,
        "tool_version_calls": 0,
        "EDA_calls": 0,
        "automatic_retries": 0,
        "normal_fixture": "B2C_LONG=1",
        "mutant_fixture": "B2C_LONG=0",
        "risk": (
            "User authorized extended simulation on 2026-10-14. Each simulation "
            "has a 24-hour emergency cap and stops after 300 seconds without "
            "stdout growth. No automatic retry; original failed evidence retained."
        ),
        "T061_complete": False,
    }
    write_json(prepared / "plan.json", plan)
    return plan


def verify(plan_path: Path, *, verify_origins: bool = True) -> dict:
    plan_path = Path(plan_path).resolve()
    plan = load_json(plan_path)
    require(plan.get("schema") == SCHEMA, "PLAN_SCHEMA")
    require(plan.get("hostname") == socket.gethostname(), "MACHINE_IDENTITY")
    require(plan.get("repo") == str(ROOT), "REPO_IDENTITY")
    require(Path(plan["prepared"]).resolve() == plan_path.parent, "PREPARED_PATH")
    expected_entrypoint = str(_snapshot_path(
        plan, snapshot_name(HERE / "b_harness.py")
    ))
    require(plan.get("execution_entrypoint") == expected_entrypoint,
            "EXECUTION_ENTRYPOINT")
    require(plan.get("execution_argv_prefix") == [
        plan["tools"]["python"], "-I", "-S", "-B", "-X", "utf8",
        expected_entrypoint, "--repo-root", str(ROOT), "execute",
    ], "EXECUTION_ARGV_PREFIX")
    compiler_root = safe_member(Path(plan["prepared"]), "tools/iverilog")
    require(Path(plan["tools"]["compile"]).resolve().is_relative_to(compiler_root)
            and Path(plan["tools"]["simulate"]).resolve().is_relative_to(compiler_root)
            and Path(plan["compiler_lib"]).resolve().is_relative_to(compiler_root),
            "COMPILER_NOT_CAPSULE_BOUND")
    require(plan.get("environment") == compiler_environment(compiler_root),
            "COMPILER_ENVIRONMENT")
    require(plan.get("environment_policy")
            == "INHERIT_HOST_WITH_EXACT_LOADER_OVERRIDES",
            "COMPILER_ENVIRONMENT_POLICY")
    require(plan.get("environment_bat_invoked") is False,
            "ENVIRONMENT_BAT_FORBIDDEN")
    require(all(str(safe_member(compiler_root, Path("lib") / name))
                in plan["tool_files"] for name in COMPILER_RUNTIME_DLLS),
            "COMPILER_RUNTIME_DLL_NOT_BOUND")
    require(all(Path(path).name.lower() != "environment.bat"
                for path in plan["tool_files"]),
            "ENVIRONMENT_BAT_IN_TOOL_CLOSURE")
    require(validate_compiler_dll_closure(compiler_root, plan["tool_files"])
            == plan.get("compiler_dll_closure_sha256"),
            "COMPILER_DLL_CLOSURE_SHA")
    under_output(plan["execution_output"])
    require(plan.get("configuration") == {"N": 32, "ROM_RESPONSE_CYCLES": 1},
            "CONFIGURATION_SCOPE")
    require(plan.get("total_seconds") == 345600
            and plan.get("tool_step_max_seconds") == 86400, "BUDGET_CONTRACT")
    require(plan.get("lower_calls") == 0 and plan.get("tool_version_calls") == 0
            and plan.get("EDA_calls") == 0, "FORBIDDEN_CALLS")
    require(plan.get("automatic_retries") == 0, "RETRY_CONTRACT")
    require(len(plan.get("cases", [])) == 4 and len(plan.get("steps", [])) == 12,
            "CASE_OR_STEP_COUNT")
    require([(row["name"], row["long"], row["expected_checker_exit"])
             for row in plan["cases"]] == [
                 ("normal_long", 1, 0), ("wrong_id", 0, 1),
                 ("wrong_pcm", 0, 1), ("wrong_clipped", 0, 1)],
            "CASE_MATRIX")
    require([row["kind"] for row in plan["steps"]]
            == [kind for _ in CASES for kind in ("compile", "simulate", "check")],
            "STEP_ORDER")
    require(all(row.get("calls") == 1 and row.get("timeout_seconds") ==
                (86400 if row['kind'] == 'simulate' else 300)
                for row in plan["steps"]), "STEP_BOUND")
    require(all(row["argv"][0] in plan["tools"].values()
                for row in plan["steps"]), "STEP_TOOL")
    execution_root = Path(plan["execution_output"]).resolve()
    expected_cwds = {
        case["name"]: Path(case["work"]).resolve() for case in plan["cases"]
    }
    for step in plan["steps"]:
        case_name = step["label"].rsplit("_", 1)[0]
        cwd = Path(step["cwd"]).resolve()
        require(case_name in expected_cwds and cwd == expected_cwds[case_name],
                "STEP_CWD_CASE_DRIFT:" + step["label"])
        require(cwd != execution_root and cwd.is_relative_to(execution_root),
                "STEP_CWD_OUTSIDE_EXECUTION:" + step["label"])
    _validate_step_snapshot_binding(plan)

    manifest_hash = hashlib.sha256(
        json.dumps(plan["inputs"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    require(manifest_hash == plan["snapshot_manifest_sha256"], "MANIFEST_SHA")
    for row in plan["inputs"]:
        expected = {key: row[key] for key in ("bytes", "sha256")}
        require(identity(_snapshot_path(plan, row["snapshot"])) == expected,
                "SNAPSHOT_DRIFT:" + row["snapshot"])
        if verify_origins:
            require(identity(row["origin"]) == expected,
                    "ORIGIN_DRIFT:" + row["origin"])
    for path, expected in plan["tool_files"].items():
        require(identity(path) == expected, "TOOL_DRIFT:" + path)

    gate = plan["dependency_gate"]
    receipt_copy = safe_member(Path(plan["prepared"]), gate["a_receipt_snapshot"])
    require(identity(receipt_copy)["sha256"] == gate["a_receipt_sha256"],
            "A_RECEIPT_SNAPSHOT_DRIFT")
    validate_a_gate(receipt_copy, gate["a_receipt_sha256"],
                    gate["a_allocator_sha256"], gate["a_result_review_key"])
    return plan


def _collect_artifacts(output: Path, budget: Budget) -> dict:
    result = {}
    for path in sorted(output.rglob("*")):
        budget.remaining(300)
        if path.is_file() and path.name not in {"receipt.json", "evidence.zip"}:
            result[path.relative_to(output).as_posix()] = identity(path)
    return result


def execute(plan_path: Path, reviewed_plan_sha: str, a_receipt_sha: str,
            a_allocator_sha: str, a_review_key: str) -> dict:
    require(SNAPSHOT_MODE, "EXECUTE_REQUIRES_SNAPSHOT_CAPSULE")
    budget = Budget(345600)
    plan_path = Path(plan_path).resolve()
    require(identity(plan_path)["sha256"] == reviewed_plan_sha, "REVIEWED_PLAN_SHA")
    plan = verify(plan_path)
    gate = plan["dependency_gate"]
    require(a_receipt_sha == gate["a_receipt_sha256"], "EXEC_A_RECEIPT_SHA")
    require(a_allocator_sha == gate["a_allocator_sha256"], "EXEC_A_ALLOCATOR_SHA")
    require(a_review_key == gate["a_result_review_key"], "EXEC_A_REVIEW_KEY")
    require(Path(plan["execution_entrypoint"]).resolve() == Path(__file__).resolve(),
            "EXECUTION_NOT_FROM_REVIEWED_CAPSULE")
    receipt_copy = safe_member(Path(plan["prepared"]), gate["a_receipt_snapshot"])
    validate_a_gate(receipt_copy, a_receipt_sha,
                    a_allocator_sha, a_review_key)

    output = under_output(plan["execution_output"])
    require(not output.exists(), "ATTEMPT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    write_json(output / "attempt.json", {
        "plan": identity(plan_path),
        "a_receipt_sha256": a_receipt_sha,
        "a_allocator_sha256": a_allocator_sha,
        "a_result_review_key": a_review_key,
        "hostname": socket.gethostname(),
        "environment": plan["environment"],
        "environment_policy": plan["environment_policy"],
        "environment_bat_invoked": False,
        "compiler_dll_closure_sha256": plan["compiler_dll_closure_sha256"],
        "automatic_retries": 0,
    })
    receipt = {
        "schema": "T061_N32_B_EXECUTION_RECEIPT_V2",
        "status": "FAIL_PARTIAL",
        "exit_code": 1,
        "failure": None,
        "plan": identity(plan_path),
        "dependency_gate": gate,
        "environment": plan["environment"],
        "environment_policy": plan["environment_policy"],
        "environment_bat_invoked": False,
        "compiler_dll_closure_sha256": plan["compiler_dll_closure_sha256"],
        "steps": [],
        "automatic_retries": 0,
        "lower_calls": 0,
        "EDA_calls": 0,
        "T061_complete": False,
    }
    try:
        for case in plan["cases"]:
            Path(case["work"]).mkdir(parents=True)
        for step in plan["steps"]:
            require(budget.remaining(300) > 0, "TOTAL_BUDGET_EXHAUSTED")
            result = _run_process_with_environment(
                output, step["label"], step["argv"], Path(step["cwd"]),
                step['timeout_seconds'], budget, plan["environment"]
            )
            receipt["steps"].append(result)
            require(not result["timed_out"] and result["launch_error"] is None,
                    "STEP_TIMEOUT_OR_LAUNCH:" + step["label"])
            require(result["exit_code"] == step["expected_exit"],
                    "STEP_EXIT:" + step["label"])
            raw = ((output / (step["label"] + ".stdout.bin")).read_bytes()
                   + (output / (step["label"] + ".stderr.bin")).read_bytes())
            require(step["marker"] is None or step["marker"].encode("ascii") in raw,
                    "STEP_DIAGNOSTIC:" + step["label"])

        # Verify source, dependency, plan, and tool identities after all work.
        verify(plan_path)
        receipt["inputs_after"] = {
            row["origin"]: identity(row["origin"]) for row in plan["inputs"]
        }
        receipt["snapshot_after"] = {
            row["snapshot"]: identity(_snapshot_path(plan, row["snapshot"]))
            for row in plan["inputs"]
        }
        receipt["tools_after"] = {
            path: identity(path) for path in plan["tool_files"]
        }
        receipt["artifacts"] = _collect_artifacts(output, budget)
        bundle_path = output / "evidence.zip"
        with zipfile.ZipFile(bundle_path, "x", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(output.rglob("*")):
                budget.remaining(300)
                if path.is_file() and path != bundle_path:
                    bundle.write(path, "execution/" + path.relative_to(output).as_posix())
            for path in sorted(Path(plan["prepared"]).rglob("*")):
                budget.remaining(300)
                if path.is_file():
                    bundle.write(path, "prepared/" + path.relative_to(plan["prepared"]).as_posix())
        receipt["bundle"] = identity(bundle_path)
        receipt.update(status="N32_B_R1_EVENT_AUDIO_AND_MUTANTS_PASS_T061_PARTIAL",
                       exit_code=0)
    except Exception as error:
        receipt["failure"] = type(error).__name__ + ":" + str(error)
    return finalize_receipt(output / "receipt.json", receipt, budget)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path,
                        help="reviewed active repository root for capsule execution")
    commands = parser.add_subparsers(dest="command", required=True)
    item = commands.add_parser("prepare")
    item.add_argument("--prepared", required=True, type=Path)
    item.add_argument("--execution-output", required=True, type=Path)
    item.add_argument("--suite", required=True, type=Path)
    item.add_argument("--a-receipt", required=True, type=Path)
    item.add_argument("--a-receipt-sha", required=True)
    item.add_argument("--a-allocator-sha", required=True)
    item.add_argument("--a-review-key", required=True)
    item = commands.add_parser("verify")
    item.add_argument("--plan", required=True, type=Path)
    item = commands.add_parser("execute")
    item.add_argument("--plan", required=True, type=Path)
    item.add_argument("--reviewed-plan-sha", required=True)
    item.add_argument("--a-receipt-sha", required=True)
    item.add_argument("--a-allocator-sha", required=True)
    item.add_argument("--a-review-key", required=True)
    args = parser.parse_args()
    try:
        require(not SNAPSHOT_MODE or args.repo_root is not None,
                "SNAPSHOT_CAPSULE_REQUIRES_REPO_ROOT")
        require(args.repo_root is None or args.repo_root.resolve() == ROOT,
                "REPO_ROOT_ARGUMENT_DRIFT")
        if args.command == "prepare":
            prepare(args.prepared, args.execution_output, args.suite,
                    args.a_receipt, args.a_receipt_sha,
                    args.a_allocator_sha, args.a_review_key)
            result = {"status": "PREPARED_NOT_EXECUTED_REVIEW_REQUIRED"}
        elif args.command == "verify":
            verify(args.plan)
            result = {"status": "STATIC_VERIFY_PASS"}
        else:
            result = execute(args.plan, args.reviewed_plan_sha,
                             args.a_receipt_sha, args.a_allocator_sha,
                             args.a_review_key)
        print(json.dumps(result, sort_keys=True))
        return result.get("exit_code", 0)
    except Exception as error:
        print(json.dumps({"status": "FAIL",
                          "diagnostic": type(error).__name__ + ":" + str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
