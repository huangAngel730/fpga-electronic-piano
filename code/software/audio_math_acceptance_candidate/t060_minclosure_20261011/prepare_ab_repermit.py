"""Prepare a locked T060 A/B re-permit draft without invoking any tool.

This successor only reads the already-consumed A/B package and the later M2
compile-diagnostic preparation.  It hashes pinned inputs and tool files, then
writes static JSON evidence to a fresh directory.  It never executes Yosys,
Icarus, VVP, an HDL test, or an EDA program.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

OLD_PORTABLE_REL = Path(
    "code/output/m3_c_budget_tail_20261012_02/prepared/portable"
)
OLD_RUN_REL = Path("code/output/m3_t060_AB_authorized_20261012_01")
OLD_APPROVAL_REL = Path(
    "code/docs/hardware/audio_math_acceptance_v1/"
    "T060_MINCLOSURE_20261011/M2_AB_APPROVAL_20261012/approval.json"
)
M2_DIAGNOSTIC_MANIFEST_REL = Path(
    "code/docs/evidence/m2_t060_compile_prepare_20261013/MANIFEST.json"
)
M2_DIAGNOSTIC_GATE_REL = Path(
    "code/docs/evidence/m2_t060_compile_prepare_20261013/FINAL_GATE.json"
)
DURABLE_FAILURE_ROOT_REL = Path(
    "code/docs/evidence/m2_ab_failure_t052_static_review_20261013"
)

EXPECTED_FILES = {
    OLD_PORTABLE_REL / "CONTROLLED_CONFIG_NOT_AUTHORIZED.json": {
        "bytes": 143354,
        "sha256": "deef8bc73b6f8f2789149f3c1558bf05954919dbe05cda1d03dd2e97fefce637",
    },
    OLD_PORTABLE_REL / "future_commands_NOT_AUTHORIZED.json": {
        "bytes": 4911,
        "sha256": "31d53e71d64ba2376a267a312ff7ef994731cef4dd45dc479fd2ca50e5b1e434",
    },
    OLD_PORTABLE_REL / "ONE_SHOT_ATTEMPT.json": {
        "bytes": 1505,
        "sha256": "97f4ccd1bdeb3dcc5c26817d971fa86a2f7bc1e038ce0c3febead81b929d3538",
    },
    OLD_APPROVAL_REL: {
        "bytes": 1179,
        "sha256": "78c251492a8003db9a573ea3c0e4b6df0ce44bc59fa01444ba49426314627131",
    },
    OLD_RUN_REL / "receipt.json": {
        "bytes": 310162,
        "sha256": "c9cfb7ff1b1e8faaff62902201f17ac9fc23f5b5e0441a56d4589448f6bcd3fc",
    },
    OLD_RUN_REL / "A_compile.receipt.json": {
        "bytes": 1914,
        "sha256": "a38009c6146f8ecb2e6981d0dc95cc1e3ff4a37d72a4dc45953d947517ba0fca",
    },
    OLD_RUN_REL / "A_compile.stderr.txt": {
        "bytes": 3490,
        "sha256": "9f779e1341d8c62cd595d215ac84cb084a7ba958209e42a3dd9eff4eb2aed3c3",
    },
    OLD_RUN_REL / "snapshot/future_group_A/A.vvp": {
        "bytes": 681033,
        "sha256": "9fb6a6837817bf642e33913d4ea26dcbb309a8ad05e3f7e7b2b1740804a07c74",
    },
    M2_DIAGNOSTIC_MANIFEST_REL: {
        "bytes": 9428,
        "sha256": "61d4593ac977130a32875dd9271e3747394e5f82801bac8172e7d6edf9346f14",
    },
    M2_DIAGNOSTIC_GATE_REL: {
        "bytes": 327,
        "sha256": "50d8134fd29bfb71026fcbb135b2b00526dbf6130ecc505284136a3ff522c588",
    },
    DURABLE_FAILURE_ROOT_REL / "MANIFEST.json": {
        "bytes": 54082,
        "sha256": "ff37d7746f7a5c5f5aa78b5cc41dfd2d85bb3cb1c31ac91d4aa3d33f454115b4",
    },
    DURABLE_FAILURE_ROOT_REL / "RAW_EVIDENCE.zip": {
        "bytes": 828943,
        "sha256": "6a531fae9c846ad2098c26919cc063cac9df9e84f7ff89a18e4d4890c92ccf56",
    },
}

KEY_INPUTS = {
    "plan_A.json": "dc05bc68552b81e782db2ad0a7edf3c2e8f1278cb89728316dc7c4c3a63277e5",
    "plan_B.json": "288eff5d6d0249997adf7dd52a487d37b8d31f624695c332f77ba75bbe9ceee1",
    "source_calendar.json": "fae87f69f5ca21171635994dceb6cf42dc09e4b44e383580f9e13430f566b05a",
    "code/tb/board/m3_midi_pcm_acceptance/t060_minclosure_20261011/tb_minclosure.sv":
        "dc14db86e5423b74860611025389484b2dc0eca25af43af43b3d9207a83e50db",
    "code/tb/board/m3_midi_pcm_acceptance/t060_minclosure_20261011/observer.svh":
        "2065b3887db71e3df4ee8057179d72d91228d58b8db3024dfc9b79bb3c425226",
    "future_group_A/stimulus_A.txt":
        "c9e25af549b823894c5e519adc3820c6e6a5f091ccbdbfe663463bc42aede329",
    "future_group_B/stimulus_B.txt":
        "af9e7050ad26801a3834f1a624b6d7696e135477d1cfe4204acfac97e6e0cb6e",
}

KEY_TOOLS = {
    "D:/Gowin/oss-cad-suite/bin/iverilog.exe":
        "5c1f4e38c6dc0807aeab8814d63af97313bef5813e815e17021ae8e36e0a0bab",
    "D:/Gowin/oss-cad-suite/bin/vvp.exe":
        "d38cc76e6946136aaf46db8a3bf34bec2a54bad564dfe146686579ca2d39c9ed",
    "D:/Gowin/oss-cad-suite/bin/yosys.exe":
        "24cca7e387553b5981b831f7ad2df32cb28c05c6f73889e109c958278385c2b2",
    "D:/Gowin/oss-cad-suite/lib/ivl/ivl.exe":
        "ccbb3bbb3d3066aa49a550c5c93ffd1c10fa379cc248f4630e0c0b174a9fd861",
    "D:/Gowin/oss-cad-suite/share/yosys/plugins/slang.so":
        "7fd85a19a3cdf215c54cfaca88125cfef8de04e9a6a411be474c1f39be0e53f7",
    "E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe":
        "35b4bd456823c5ea3aba0856b95e113da92d5362a6fa7643f12aef9cc1a1875b",
}


def require(condition: bool, diagnostic: str) -> None:
    """Fail closed with a stable diagnostic."""
    if not condition:
        raise ValueError(diagnostic)


def unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys instead of silently accepting the last."""
    result: dict[str, Any] = {}
    for key, value in items:
        require(key not in result, "REPERMIT_DUPLICATE_KEY:" + key)
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ValueError("REPERMIT_NONFINITE:" + value)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_pairs,
        parse_constant=reject_constant,
    )
    require(isinstance(value, dict), "REPERMIT_JSON_NOT_OBJECT:" + str(path))
    return value


def identity(path: Path | str) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def dump_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def confined_member(root: Path, name: str) -> Path:
    relative = Path(name)
    require(not relative.is_absolute(), "REPERMIT_ABSOLUTE_INPUT:" + name)
    base = root.resolve()
    result = (base / relative).resolve()
    require(result != base and result.is_relative_to(base),
            "REPERMIT_INPUT_ESCAPE:" + name)
    return result


def pin_inventory(
    pins: dict[str, dict[str, Any]],
    base: Path | None,
) -> dict[str, Any]:
    """Hash pins without launching the pinned executables."""
    observed: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    changed: list[dict[str, Any]] = []
    for name in sorted(pins):
        expected = pins[name]
        require(
            set(expected) == {"bytes", "sha256"}
            and type(expected["bytes"]) is int
            and expected["bytes"] >= 0
            and isinstance(expected["sha256"], str)
            and len(expected["sha256"]) == 64,
            "REPERMIT_BAD_PIN:" + name,
        )
        path = Path(name) if base is None else confined_member(base, name)
        if not path.is_file():
            missing.append(name)
            continue
        actual = identity(path)
        observed[name] = actual
        if actual != expected:
            changed.append({"path": name, "expected": expected, "actual": actual})
    return {
        "expected_count": len(pins),
        "observed_count": len(observed),
        "expected_manifest_sha256": canonical_sha256(pins),
        "observed_manifest_sha256": canonical_sha256(observed),
        "all_match": not missing and not changed and len(observed) == len(pins),
        "missing": missing,
        "changed": changed,
    }


def current_machine() -> dict[str, Any]:
    executable = Path(sys.executable).resolve()
    return {
        "role": "M3_CURRENT_LOCAL_MACHINE",
        "computer_name": os.environ.get("COMPUTERNAME", "UNKNOWN"),
        "node": platform.node(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_runtime": {
            "path": executable.as_posix(),
            "identity": identity(executable),
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "identity_method": "OS/Python metadata plus file SHA only; no tool invoked",
    }


def verify_fixed_files(root: Path) -> dict[str, dict[str, Any]]:
    verified: dict[str, dict[str, Any]] = {}
    for relative, expected in EXPECTED_FILES.items():
        actual = identity(root / relative)
        require(actual == expected, "REPERMIT_FIXED_IDENTITY:" + relative.as_posix())
        verified[relative.as_posix()] = actual
    return verified


def verify_predecessor(root: Path) -> dict[str, Any]:
    """Validate the consumed attempt and the separate locked M2 diagnostic."""
    fixed = verify_fixed_files(root)
    portable = root / OLD_PORTABLE_REL
    run_root = root / OLD_RUN_REL
    config_path = portable / "CONTROLLED_CONFIG_NOT_AUTHORIZED.json"
    approval_path = root / OLD_APPROVAL_REL
    marker_path = portable / "ONE_SHOT_ATTEMPT.json"
    receipt_path = run_root / "receipt.json"
    compile_path = run_root / "A_compile.receipt.json"

    config = load_json(config_path)
    approval = load_json(approval_path)
    marker = load_json(marker_path)
    receipt = load_json(receipt_path)
    compile_receipt = load_json(compile_path)
    diagnostic = load_json(root / M2_DIAGNOSTIC_MANIFEST_REL)
    diagnostic_gate = load_json(root / M2_DIAGNOSTIC_GATE_REL)
    durable_failure = load_json(
        root / DURABLE_FAILURE_ROOT_REL / "MANIFEST.json"
    )

    require(config.get("schema") == 1, "REPERMIT_CONFIG_SCHEMA")
    require(config.get("execution_authorized") is False,
            "REPERMIT_CONFIG_NOT_LOCKED")
    require(config.get("groups") == ["A", "B"], "REPERMIT_CONFIG_GROUPS")
    require(config.get("total_seconds") == 900, "REPERMIT_CONFIG_BUDGET")
    require(len(config.get("inputs", {})) == 177, "REPERMIT_INPUT_COUNT")
    require(len(config.get("tool_files", {})) == 621, "REPERMIT_TOOL_COUNT")
    require(config.get("end_cycles") == {"A": 4095000, "B": 1600},
            "REPERMIT_END_CYCLES")
    for name, sha256 in KEY_INPUTS.items():
        require(config["inputs"].get(name, {}).get("sha256") == sha256,
                "REPERMIT_KEY_INPUT:" + name)
    for name, sha256 in KEY_TOOLS.items():
        require(config["tool_files"].get(name, {}).get("sha256") == sha256,
                "REPERMIT_KEY_TOOL:" + name)

    config_id = identity(config_path)
    require(approval.get("authority") == "M2"
            and approval.get("execution_authorized") is True
            and approval.get("config_sha256") == config_id["sha256"]
            and approval.get("groups") == ["A", "B"]
            and approval.get("attempt") == 1,
            "REPERMIT_OLD_APPROVAL_BINDING")
    require(marker.get("config") == config_id
            and marker.get("approval") == approval,
            "REPERMIT_OLD_MARKER_BINDING")
    require(Path(marker.get("output", "")).resolve() == run_root.resolve(),
            "REPERMIT_OLD_MARKER_OUTPUT")
    require(receipt.get("status") == "FAIL_PARTIAL"
            and receipt.get("exit_code") == 1
            and receipt.get("failure") == "RUNNER_STEP_FAILED:A_compile"
            and receipt.get("execution_authorized") is True
            and receipt.get("config") == config_id
            and receipt.get("total_limit_seconds") == 900,
            "REPERMIT_OLD_RUN_RESULT")
    require(compile_receipt.get("label") == "A_compile"
            and compile_receipt.get("exit_code") == 3221225477
            and compile_receipt.get("expected_exit") == 0
            and compile_receipt.get("timeout") is False
            and compile_receipt.get("stderr")
            == identity(run_root / "A_compile.stderr.txt"),
            "REPERMIT_OLD_COMPILE_RESULT")

    absent = [
        "A_capture.receipt.json",
        "B_lower.receipt.json",
        "B_compile.receipt.json",
        "B_capture.receipt.json",
    ]
    require(not any((run_root / name).exists() for name in absent),
            "REPERMIT_UNEXPECTED_LATER_STEP")
    require(diagnostic.get("status") == "PREPARED_NOT_EXECUTED"
            and diagnostic.get("actual_tool_calls") == 0
            and diagnostic.get("permission")
            == "new explicit once compile-only total90 required"
            and diagnostic_gate.get("actual_T060_compile") is False
            and diagnostic_gate.get("EDA") is False,
            "REPERMIT_DIAGNOSTIC_NOT_LOCKED")
    require(durable_failure.get("T060", {}).get("old_permission_consumed")
            is True
            and durable_failure.get("T060", {}).get("compile_exit")
            == 3221225477
            and durable_failure.get("T060", {}).get("B_started") is False
            and durable_failure.get("T060", {}).get("residual_A_vvp", {})
            .get("sha256")
            == "9fb6a6837817bf642e33913d4ea26dcbb309a8ad05e3f7e7b2b1740804a07c74",
            "REPERMIT_DURABLE_FAILURE_EVIDENCE")

    input_inventory = pin_inventory(config["inputs"], portable)
    tool_inventory = pin_inventory(config["tool_files"], None)
    require(input_inventory["all_match"], "REPERMIT_INPUT_DRIFT")
    require(tool_inventory["all_match"], "REPERMIT_TOOL_DRIFT")

    return {
        "config": config,
        "fixed_files": fixed,
        "input_inventory": input_inventory,
        "tool_inventory": tool_inventory,
        "old_attempt": {
            "permission_consumed": True,
            "marker": identity(marker_path),
            "approval": identity(approval_path),
            "run_receipt": identity(receipt_path),
            "status": "FAIL_PARTIAL",
            "failure": "RUNNER_STEP_FAILED:A_compile",
            "compile_exit_unsigned": 3221225477,
            "compile_exit_hex": "0xC0000005",
            "compile_timeout": False,
            "A_capture": "NOT_STARTED",
            "B": "NOT_STARTED",
            "automatic_retries": 0,
            "durable_archive": identity(
                root / DURABLE_FAILURE_ROOT_REL / "RAW_EVIDENCE.zip"
            ),
            "durable_manifest": identity(
                root / DURABLE_FAILURE_ROOT_REL / "MANIFEST.json"
            ),
        },
        "residual_A_vvp": {
            "identity": identity(run_root / "snapshot/future_group_A/A.vvp"),
            "integrity": "UNKNOWN",
            "executed_by_this_preparation": False,
            "future_execution_allowed": False,
        },
        "m2_compile_diagnostic": {
            "manifest": identity(root / M2_DIAGNOSTIC_MANIFEST_REL),
            "final_gate": identity(root / M2_DIAGNOSTIC_GATE_REL),
            "status": "PREPARED_NOT_EXECUTED",
            "actual_tool_calls": 0,
            "required_permission": "new explicit once compile-only total90",
            "blocks_AB_repermit_finalization": True,
        },
    }


def build_proposed_config(
    predecessor: dict[str, Any],
    machine: dict[str, Any],
) -> dict[str, Any]:
    old = predecessor["config"]
    return {
        "schema": "t060-ab-repermit-preparation-v1",
        "status": "PRE_DIAGNOSTIC_DRAFT_EXECUTION_LOCKED",
        "execution_authorized": False,
        "direct_runner_compatible": False,
        "groups": ["A", "B"],
        "proposed_execution_machine": machine,
        "predecessor": {
            "config": EXPECTED_FILES[
                OLD_PORTABLE_REL / "CONTROLLED_CONFIG_NOT_AUTHORIZED.json"
            ],
            "approval": predecessor["old_attempt"]["approval"],
            "attempt_marker": predecessor["old_attempt"]["marker"],
            "failed_run_receipt": predecessor["old_attempt"]["run_receipt"],
            "permission_consumed": True,
            "reuse_forbidden": True,
        },
        "frozen_workload": {
            "input_count": predecessor["input_inventory"]["expected_count"],
            "input_manifest_sha256": predecessor["input_inventory"]
            ["expected_manifest_sha256"],
            "plans": {
                name: old["inputs"][name]
                for name in ("plan_A.json", "plan_B.json", "source_calendar.json")
            },
            "tb": old["inputs"][
                "code/tb/board/m3_midi_pcm_acceptance/"
                "t060_minclosure_20261011/tb_minclosure.sv"
            ],
            "observer": old["inputs"][
                "code/tb/board/m3_midi_pcm_acceptance/"
                "t060_minclosure_20261011/observer.svh"
            ],
            "stimulus_A": old["inputs"]["future_group_A/stimulus_A.txt"],
            "stimulus_B": old["inputs"]["future_group_B/stimulus_B.txt"],
            "compile_sources": old["compile_sources"],
            "end_cycles": old["end_cycles"],
            "mutations": old["mutations"],
            "content_change_allowed": False,
        },
        "observed_tool_set": {
            "tool_count": predecessor["tool_inventory"]["expected_count"],
            "tool_manifest_sha256": predecessor["tool_inventory"]
            ["expected_manifest_sha256"],
            "tools": old["tools"],
            "key_file_identities": {
                name: old["tool_files"][name] for name in KEY_TOOLS
            },
            "identity_only": True,
            "tool_invocations": 0,
        },
        "proposed_limits_if_later_rebuilt_and_approved": {
            "combined_total_seconds": 900,
            "automatic_retries": 0,
            "groups": ["A", "B"],
            "end_cycles": old["end_cycles"],
            "frequency_or_seed_change": False,
        },
        "required_before_any_execution": [
            "M2 completes the separately authorized compile-only diagnosis",
            "M2 selects and records the final compiler/tool set",
            "A fresh portable root is built and rehashed; old marker is not moved or deleted",
            "A final runner-compatible config is generated and independently reviewed",
            "A new explicit one-shot approval binds that final config SHA256",
        ],
        "forbidden": [
            "reuse old approval",
            "reuse, move, delete, or reset old ONE_SHOT_ATTEMPT.json",
            "run residual A.vvp",
            "infer compiler root cause from constant-select warnings",
            "start A/B compile, VVP, RTL, EDA, Gowin, PnR, or hardware work",
        ],
        "diagnostic_state": predecessor["m2_compile_diagnostic"],
        "note": (
            "This is a static proposal descriptor, not the executable config and not "
            "an approval. M2 diagnostic outcome may require a new successor descriptor."
        ),
    }


def require_unredirected_root(lexical: Path, physical: Path) -> None:
    """Reject a trusted output root redirected by a symlink or junction."""
    same_path = os.path.normcase(os.path.normpath(str(lexical))) == os.path.normcase(
        os.path.normpath(str(physical))
    )
    attributes = getattr(os.lstat(lexical), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    require(same_path and not lexical.is_symlink()
            and not (reparse_flag and attributes & reparse_flag),
            "REPERMIT_CODE_OUTPUT_REDIRECTED")


def validate_output_path(output: Path, root: Path) -> tuple[Path, Path]:
    """Permit generated runtime evidence only below the real output tree."""
    root = root.resolve()
    lexical_output_root = Path(os.path.abspath(root / "code/output"))
    require(lexical_output_root.is_dir(), "REPERMIT_CODE_OUTPUT_MISSING")
    output_root = lexical_output_root.resolve()
    require_unredirected_root(lexical_output_root, output_root)
    lexical_output = output if output.is_absolute() else root / output
    output = lexical_output.resolve()
    require(output != output_root and output.is_relative_to(output_root),
            "REPERMIT_OUTPUT_OUTSIDE_CODE_OUTPUT")
    require(not output.exists(), "REPERMIT_OUTPUT_EXISTS")
    return root, output


def prepare(output: Path, root: Path = ROOT) -> dict[str, Any]:
    root, output = validate_output_path(output, root)

    predecessor = verify_predecessor(root)
    machine = current_machine()
    require(machine["computer_name"] == "LAPTOP-KSS1MRR7",
            "REPERMIT_UNEXPECTED_MACHINE")
    proposal = build_proposed_config(predecessor, machine)

    source_receipt = {
        "schema": "t060-ab-repermit-source-receipt-v1",
        "status": "PASS_STATIC_IDENTITY_ONLY",
        "source_script": identity(Path(__file__).resolve()),
        "machine": machine,
        "fixed_files": predecessor["fixed_files"],
        "input_inventory": predecessor["input_inventory"],
        "tool_inventory": predecessor["tool_inventory"],
        "old_attempt": predecessor["old_attempt"],
        "residual_A_vvp": predecessor["residual_A_vvp"],
        "m2_compile_diagnostic": predecessor["m2_compile_diagnostic"],
        "actions": {
            "json_files_read": True,
            "file_sha256_read": True,
            "preparation_python_process": True,
            "external_subprocesses_spawned_by_script": 0,
            "HDL_EDA_tool_invocations": 0,
            "compile_runs": 0,
            "RTL_runs": 0,
            "VVP_runs": 0,
            "EDA_runs": 0,
            "hardware_operations": 0,
        },
    }

    output.mkdir(parents=True)
    proposal_path = output / "PROPOSED_CONFIG_NOT_AUTHORIZED.json"
    source_path = output / "STATIC_SOURCE_RECEIPT.json"
    dump_new(proposal_path, proposal)
    dump_new(source_path, source_receipt)
    receipt = {
        "schema": "t060-ab-repermit-preparation-receipt-v1",
        "status": "PASS_PREPARATION_ONLY_EXECUTION_LOCKED",
        "execution_authorized": False,
        "output": output.relative_to(root).as_posix(),
        "artifacts": {
            proposal_path.name: identity(proposal_path),
            source_path.name: identity(source_path),
        },
        "input_count": predecessor["input_inventory"]["expected_count"],
        "tool_file_count": predecessor["tool_inventory"]["expected_count"],
        "old_permission_consumed": True,
        "compile_diagnostic_completed": False,
        "new_AB_approval_present": False,
        "preparation_python_process": True,
        "actual_HDL_EDA_tool_calls": 0,
        "actual_compile_runs": 0,
        "actual_RTL_runs": 0,
        "actual_EDA_runs": 0,
    }
    receipt_path = output / "PREPARATION_RECEIPT.json"
    dump_new(receipt_path, receipt)
    return {
        "output": output.as_posix(),
        "proposal": identity(proposal_path),
        "source_receipt": identity(source_path),
        "preparation_receipt": identity(receipt_path),
        "status": receipt["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
