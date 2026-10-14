"""Validate N32-C identities, reproducibility, and the blocked execution lock."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

from generate_plan import generate
from n32c_common import (
    ContractError,
    MUTATION_DIAGNOSTICS,
    exact_keys,
    file_sha256,
    is_reparse_point,
    read_jsonl,
    records_sha256,
    require,
    strict_json,
)


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")
SCENARIOS = [
    "C00_INITIAL_RESET", "C01_FILL32_STEAL33", "C02_RETRIGGER",
    "C03_IDENTITY_ISOLATION",
    "C04_CC64_MULTI_RECYCLE", "C05_CONTROL_SNAPSHOTS",
    "C06_READ_HOLD_RECOVERY", "C07_CANCEL_RESET", "C08_HIGH_DENSITY",
]
MUTATIONS = list(MUTATION_DIAGNOSTICS)
DEPENDENCY_ROLES = {
    "old_router_contract_reference_only", "sustain_contract_reference",
    "control_snapshot_reference", "b1_scheduler_reference",
    "b1_statebank_reference", "accurate_clipped_public_contract",
    "frozen_resource_input_receipt",
    "prior_independent_semantics_reference_only",
    "prior_transaction_fence_reference_only",
}


def repo_path(value, name, *, must_exist=True):
    require(type(value) is str and value, f"PATH_TYPE:{name}")
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts,
            f"PATH_SCOPE:{name}")
    root = Path(os.path.abspath(ROOT))
    resolved = Path(os.path.abspath(root / path))
    if must_exist:
        require(resolved.exists(), f"PATH_MISSING:{name}")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"PATH_ESCAPE:{name}") from exc
    cursor = resolved if resolved.exists() else resolved.parent
    while cursor != root:
        require(not is_reparse_point(cursor),
                f"PATH_REPARSE:{name}")
        cursor = cursor.parent
    return resolved


def sha_field(value, name):
    require(type(value) is str and HEX64.fullmatch(value) is not None,
            f"SHA:{name}")


def validate_dependencies():
    dependencies = strict_json(
        (HERE / "baseline_dependencies.json").read_text(encoding="utf-8"))
    exact_keys(dependencies, (
        "schema", "status", "original_prepared_path",
        "original_prepared_path_status", "explicit_same_bytes_alias",
        "readonly_dependencies", "required_b_binding",
    ), "dependencies")
    require(dependencies["schema"] == "t061-n32c-baseline-dependencies-v1"
            and dependencies["status"] == "STATIC_ONLY_WAIT_B"
            and dependencies["original_prepared_path_status"] == "MISSING",
            "DEPENDENCY_META")
    original = repo_path(dependencies["original_prepared_path"], "original",
                         must_exist=False)
    require(not original.exists(), "ORIGINAL_PATH_STATUS_CHANGED_REVIEW_REQUIRED")
    alias = dependencies["explicit_same_bytes_alias"]
    exact_keys(alias, ("path", "sha256"), "alias")
    sha_field(alias["sha256"], "alias")
    require(file_sha256(repo_path(alias["path"], "alias")) == alias["sha256"],
            "ALLOCATOR_ALIAS_SHA")
    rows = dependencies["readonly_dependencies"]
    require(type(rows) is list and len(rows) == len(DEPENDENCY_ROLES),
            "DEPENDENCY_COUNT")
    roles = set()
    for index, item in enumerate(rows):
        exact_keys(item, ("path", "role", "sha256"), f"dependency[{index}]")
        require(item["role"] not in roles, "DEPENDENCY_DUPLICATE_ROLE")
        roles.add(item["role"])
        sha_field(item["sha256"], f"dependency[{index}]")
        require(file_sha256(repo_path(item["path"], f"dependency[{index}]"))
                == item["sha256"], f"DEPENDENCY_SHA:{item['path']}")
    require(roles == DEPENDENCY_ROLES, "DEPENDENCY_ROLES")
    binding = dependencies["required_b_binding"]
    exact_keys(binding, (
        "status", "review_key", "fingerprint", "candidate_files",
        "compile_source_order", "pass_evidence",
    ), "b_binding")
    require(binding == {
        "status": "WAIT_B_EXACT_PASS", "review_key": None,
        "fingerprint": None, "candidate_files": [],
        "compile_source_order": [], "pass_evidence": [],
    }, "B_BINDING_NOT_LOCKED")
    return len(rows) + 1


def validate_vectors():
    generated_plan, generated_expected = generate()
    plan_path = HERE / "vectors" / "plan.jsonl"
    expected_path = HERE / "vectors" / "expected_skeleton.jsonl"
    receipt_path = HERE / "vectors" / "receipt.json"
    actual_plan = read_jsonl(plan_path)
    actual_expected = read_jsonl(expected_path)
    require(actual_plan == generated_plan, "PLAN_NOT_REPRODUCIBLE")
    require(actual_expected == generated_expected, "EXPECTED_NOT_REPRODUCIBLE")
    receipt = strict_json(receipt_path.read_text(encoding="utf-8"))
    exact_keys(receipt, (
        "status", "plan_records", "expected_records", "plan_sha256",
        "expected_sha256", "rtl_status", "gowin_status",
    ), "vector_receipt")
    require(receipt == {
        "status": "PASS_SOFTWARE_PLAN_ONLY",
        "plan_records": len(actual_plan),
        "expected_records": len(actual_expected),
        "plan_sha256": records_sha256(actual_plan),
        "expected_sha256": records_sha256(actual_expected),
        "rtl_status": "NOT_RUN_WAIT_B",
        "gowin_status": "NOT_RUN_PROHIBITED",
    }, "VECTOR_RECEIPT")
    return receipt


def validate_software_lock(manifest):
    lock_path = repo_path(manifest["identity"]["software_lock_path"],
                          "software_lock")
    require(file_sha256(lock_path)
            == manifest["identity"]["software_lock_sha256"],
            "SOFTWARE_LOCK_SHA")
    lock = strict_json(lock_path.read_text(encoding="utf-8"))
    exact_keys(lock, ("schema", "files"), "software_lock")
    require(lock["schema"] == "t061-n32c-software-lock-v2"
            and type(lock["files"]) is list and lock["files"],
            "SOFTWARE_LOCK_META")
    seen = set()
    for index, item in enumerate(lock["files"]):
        exact_keys(item, ("path", "sha256"), f"lock[{index}]")
        require(item["path"] not in seen, "SOFTWARE_LOCK_DUPLICATE")
        seen.add(item["path"])
        sha_field(item["sha256"], f"lock[{index}]")
        require(file_sha256(repo_path(item["path"], f"lock[{index}]"))
                == item["sha256"], f"SOFTWARE_LOCK_FILE:{item['path']}")
    required = {
        "code/software/t061_n32_stress_plan_candidate_20261013/n32c_common.py",
        "code/software/t061_n32_stress_plan_candidate_20261013/generate_plan.py",
        "code/software/t061_n32_stress_plan_candidate_20261013/check_capture.py",
        "code/software/t061_n32_stress_plan_candidate_20261013/selftest.py",
        "code/software/t061_n32_stress_plan_candidate_20261013/validate_static.py",
        "code/software/t061_n32_stress_plan_candidate_20261013/README.md",
        "code/software/t061_n32_stress_plan_candidate_20261013/baseline_dependencies.json",
        "code/software/t061_n32_stress_plan_candidate_20261013/vectors/plan.jsonl",
        "code/software/t061_n32_stress_plan_candidate_20261013/vectors/expected_skeleton.jsonl",
        "code/software/t061_n32_stress_plan_candidate_20261013/vectors/receipt.json",
        "code/tb/audio/t061_n32_allocator_candidate_20261013/C/CONTRACT.md",
    }
    require(seen == required, "SOFTWARE_LOCK_FILE_SET")


def validate_manifest(receipt):
    manifest = strict_json(
        (HERE / "rtl_execution_manifest.blocked.json").read_text(
            encoding="utf-8"))
    exact_keys(manifest, (
        "schema", "task", "stage", "status", "execution_authorized",
        "review_key", "approval_sha256", "identity", "plan", "expected",
        "machine", "tools", "sources", "math", "scenarios",
        "designated_mutations", "steps", "budget", "output",
        "failure_policy", "closure", "blocked_reasons",
    ), "blocked_manifest")
    require(manifest["schema"] == "t061-n32c-blocked-manifest-v2"
            and manifest["task"] == "T061" and manifest["stage"] == "N32-C"
            and manifest["status"] == "BLOCKED_WAIT_B_EXACT_PASS_AND_DUAL_REVIEW"
            and manifest["execution_authorized"] is False
            and manifest["review_key"] is None
            and manifest["approval_sha256"] is None, "MANIFEST_NOT_BLOCKED")
    exact_keys(manifest["identity"], (
        "base_git_sha", "software_lock_path", "software_lock_sha256",
        "workspace_state",
    ), "manifest.identity")
    require(type(manifest["identity"]["base_git_sha"]) is str
            and HEX40.fullmatch(manifest["identity"]["base_git_sha"]),
            "SHA:base_git_sha")
    sha_field(manifest["identity"]["software_lock_sha256"], "software_lock")
    require(manifest["identity"]["workspace_state"] == "UNSEALED_UNCOMMITTED",
            "WORKSPACE_STATE")
    for name in ("plan", "expected"):
        spec = manifest[name]
        exact_keys(spec, ("path", "records", "sha256"), f"manifest.{name}")
        sha_field(spec["sha256"], f"manifest.{name}")
        rows = read_jsonl(repo_path(spec["path"], f"manifest.{name}"))
        require(spec["records"] == len(rows)
                and spec["sha256"] == records_sha256(rows),
                f"MANIFEST_VECTOR:{name}")
    require(manifest["plan"]["sha256"] == receipt["plan_sha256"]
            and manifest["expected"]["sha256"] == receipt["expected_sha256"],
            "MANIFEST_RECEIPT_VECTOR")
    exact_keys(manifest["machine"], (
        "hostname", "os_arch", "repo_absolute_path", "cwd_absolute_path",
    ), "manifest.machine")
    require(all(value is None for value in manifest["machine"].values())
            and manifest["tools"] == {} and manifest["sources"] == {}
            and manifest["math"] is None and manifest["steps"] == [],
            "BLOCKED_MANIFEST_EXECUTABLE_FIELDS")
    require(manifest["scenarios"] == SCENARIOS
            and manifest["designated_mutations"] == MUTATIONS,
            "MANIFEST_COVERAGE_SET")
    require(manifest["budget"] == {
        "per_tool_seconds_max": 300, "runner_total_seconds_max": 900,
        "includes_prepare_postcheck_archive_receipt": True,
    }, "BUDGET")
    require(manifest["output"] == {
        "directory": None, "reject_overwrite": True,
        "exclusive_attempt_record_required": True,
        "private_process_tree_required": True,
        "stdout_stderr_timestamps_exit_timeout_required": True,
    }, "OUTPUT_LOCK")
    require(manifest["failure_policy"] == {
        "stop_on_first_failure": True, "fail_partial_required": True,
        "auto_retry": False, "tool_switch": False, "machine_switch": False,
        "timeout_increase": False,
    }, "FAILURE_POLICY")
    require(manifest["closure"] == {
        "source_tool_pre_post_sha_required": True,
        "artifact_log_sha_required": True,
        "not_run_unknown_partial_required": True,
        "sealed_small_archive_required": True,
    }, "CLOSURE")
    required_reasons = {
        "A exact functional PASS is not available",
        "B exact PASS Review-Key and Fingerprint are not available",
        "B module/parameter/port/source-order binding is not frozen",
        "independent frozen PCM/clipped ledger is not bound",
        "machine and exact tools are not bound",
        "immutable review archive has not been sent to both reviewers",
    }
    require(set(manifest["blocked_reasons"]) == required_reasons
            and len(manifest["blocked_reasons"]) == len(required_reasons),
            "BLOCKED_REASONS")
    validate_software_lock(manifest)


def main() -> int:
    checked = validate_dependencies()
    receipt = validate_vectors()
    validate_manifest(receipt)
    result = {
        "status": "PASS_STATIC_ONLY", "dependency_files_checked": checked,
        "plan_records": receipt["plan_records"],
        "expected_records": receipt["expected_records"],
        "mutations_locked": len(MUTATIONS),
        "original_prepared_path": "CONFIRMED_MISSING",
        "rtl_execution": "LOCKED_NOT_RUN_WAIT_B",
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
