"""Create an immutable, zero-HDL-tool review package for the T052 observer fix."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[3]
BASE = "33490aad60a0bc5fa7f723508d1050c796c6d2e2"
REVIEW_KEY = "T052-M3-20261014-OBSERVER-REPAIR-PRELAUNCH-R08"
STATE = "SEALED-UNCOMMITTED_NOT_EXECUTED"
OUT = ROOT / "code/output/m3_t052_observer_repair_prelaunch_seal_20261014_r08"
ZIP_PATH = OUT / "T052_OBSERVER_REPAIR_PRELAUNCH_R08.zip"
PYTHON = Path(
    "C:/Users/songdongkuan/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/python.exe"
)
RUNNER_DIR = ROOT / "code/software/t052_runner_acceptance_candidate_20261012"
CONTROLLER = RUNNER_DIR / "t052_observer_repair_successor_20261014.py"
ENVELOPE_TEST = RUNNER_DIR / "test_t052_observer_repair_successor_20261014.py"
SEALER = Path(__file__).resolve()
SUCCESSOR = ROOT / (
    "code/tb/audio/t052_publication_acceptance_candidate_20261012/"
    "successor_20261013"
)
OBSERVER = SUCCESSOR / "t052_public_observer_v2.sv"
SCHEDULE_CHECK = SUCCESSOR / "schedule_check.py"
TEST_SCHEDULE = SUCCESSOR / "test_schedule.py"
ATTEMPT = ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_10"
PREVIOUS_PREPARES = [
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_01",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_02",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_03",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_04",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_05",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_06",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_07",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_08",
    ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_09",
]
PARENT = ROOT / "code/output/m3_t052_observer_repair_parent_20261014_10"
CONFIG = ATTEMPT / "prepared/config.json"
MANIFEST = ATTEMPT / "prepared/manifest.json"
APPROVAL = ATTEMPT / "approval.json"
BINDING = ATTEMPT / "observer_repair_binding.json"
LAUNCH_COMMAND = ATTEMPT / "launch_command.json"
OUTPUT = ATTEMPT / "prepared/actual_once"
CHILD = ATTEMPT / "prepared/consumed.json"
OUTER = ATTEMPT / "outer_consumed.json"
WORKER = ATTEMPT / "worker_entry_consumed.json"
OLD_SEAL = ROOT / "code/output/m3_t052_review_seal_20261014_r03"
OLD_PRELAUNCH_SEAL = ROOT / (
    "code/output/m3_t052_observer_repair_prelaunch_seal_20261014_r07"
)
ATTEMPT09_FAILURE_SEAL = ROOT / (
    "code/output/m3_t052_observer_repair_attempt09_failure_seal_20261014"
)
CONFIG_SHA = "86fd779a7f6134c4d9e9f35a95e94ee5bd048b31eed3211160c66b89967672a2"
MANIFEST_SHA = "15fc387996e069d363c82129882fcdb11cdd4dda078d54cd00e7047f32c0fc74"
APPROVAL_SHA = "d05a7b7a4376fb7aafd21ccef402e49c7a644a04a58c58c12713b0b057fcf6e3"
BINDING_SHA = "f7c58ba5e4f267bf476813d1f4dfc1ca1681417f16ba5d7d2b28795315ef4c10"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def ident(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def need(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ValueError(diagnostic)


def add_file(payload: dict[str, bytes], name: str, path: Path) -> None:
    need(name not in payload, "DUPLICATE_MEMBER:" + name)
    payload[name] = path.read_bytes()


def add_tree(payload: dict[str, bytes], prefix: str, root: Path) -> None:
    need(root.is_dir(), "MISSING_TREE:" + str(root))
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        add_file(payload, prefix + "/" + path.relative_to(root).as_posix(), path)


def run(argv: list[str], cwd: Path = ROOT) -> dict[str, object]:
    result = subprocess.run(
        argv, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=60,
        check=False,
    )
    return {
        "argv": argv,
        "cwd": str(cwd.resolve()),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def spec_bytes(spec: dict) -> bytes:
    path = Path(spec["path"])
    if not path.is_absolute():
        path = ROOT / path
    if "member" not in spec:
        raw = path.read_bytes()
    else:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read(spec["member"])
    need({"bytes": len(raw), "sha256": sha(raw)}
         == {"bytes": spec["bytes"], "sha256": spec["sha256"]},
         "SPEC_IDENTITY:" + str(path))
    return raw


def freshness() -> dict[str, object]:
    paths = {"output": OUTPUT, "child_marker": CHILD,
             "outer_marker": OUTER, "worker_marker": WORKER,
             "parent": PARENT}
    return {
        "schema": "T052_PRELAUNCH_FRESHNESS_V1",
        "review_key": REVIEW_KEY,
        "paths": {name: {"path": str(path.resolve()), "exists": path.exists()}
                  for name, path in paths.items()},
        "all_absent": all(not path.exists() for path in paths.values()),
        "tool_calls": {"compile": 0, "run": 0, "check": 0, "gowin": 0},
    }


def main() -> None:
    need(not OUT.exists(), "SEAL_OUTPUT_EXISTS")
    need(ident(CONFIG)["sha256"] == CONFIG_SHA, "CONFIG_SHA")
    need(ident(MANIFEST)["sha256"] == MANIFEST_SHA, "MANIFEST_SHA")
    need(ident(APPROVAL)["sha256"] == APPROVAL_SHA, "APPROVAL_SHA")
    need(ident(BINDING)["sha256"] == BINDING_SHA, "BINDING_SHA")
    before = freshness()
    need(before["all_absent"] is True, "ATTEMPT_ALREADY_USED")

    test = run([str(PYTHON), "-B", str(TEST_SCHEDULE)], SUCCESSOR)
    envelope_test = run([str(PYTHON), "-B", str(ENVELOPE_TEST)], RUNNER_DIR)
    diff_check = run([
        "git", "diff", "--check", "--", rel(OBSERVER),
        rel(SCHEDULE_CHECK), rel(TEST_SCHEDULE), rel(CONTROLLER),
    ])
    launch_command = load(LAUNCH_COMMAND)
    verify_argv = list(launch_command["argv"])
    verify_argv[verify_argv.index("launch")] = "verify"
    verify = run(verify_argv)
    need(test["exit_code"] == 0 and "Ran 9 tests" in test["stderr"],
         "ISOLATED_TEST_FAILURE")
    need(envelope_test["exit_code"] == 0
         and "Ran 5 tests" in envelope_test["stderr"],
         "ENVELOPE_TEST_FAILURE")
    need(diff_check["exit_code"] == 0, "DIFF_CHECK_FAILURE")
    need(verify["exit_code"] == 0 and "VERIFIED_LOCKED" in verify["stdout"],
         "VERIFY_FAILURE")
    after = freshness()
    need(after["all_absent"] is True, "SELF_REVIEW_CONSUMED_ATTEMPT")

    manifest = load(MANIFEST)
    payload: dict[str, bytes] = {}
    add_tree(payload, "attempt10_prelaunch", ATTEMPT)
    for index, path in enumerate(PREVIOUS_PREPARES, start=1):
        add_tree(payload, f"preserved_prepare_{index:02d}", path)
    add_file(payload, "implementation/controller.py", CONTROLLER)
    add_file(payload, "implementation/envelope_test.py", ENVELOPE_TEST)
    add_file(payload, "implementation/observer.sv", OBSERVER)
    add_file(payload, "implementation/schedule_check.py", SCHEDULE_CHECK)
    add_file(payload, "implementation/test_schedule.py", TEST_SCHEDULE)
    add_file(payload, "implementation/prelaunch_sealer.py", SEALER)
    add_tree(payload, "preserved_q0019_seal", OLD_SEAL)
    add_tree(payload, "preserved_q0025_r07_seal", OLD_PRELAUNCH_SEAL)
    add_tree(payload, "preserved_attempt09_failure", ATTEMPT09_FAILURE_SEAL)

    for role, spec in sorted(manifest["sources"].items()):
        payload[f"frozen_inputs/sources/{role}/{Path(spec['path']).name}"] = spec_bytes(spec)
    payload["frozen_inputs/plan/controls_proposed.jsonl"] = spec_bytes(manifest["plan"])
    payload["frozen_inputs/calendar/publication.py"] = spec_bytes(manifest["calendar"])

    tracked = [OBSERVER, SCHEDULE_CHECK, TEST_SCHEDULE]
    for path in tracked:
        baseline = run(["git", "show", f"{BASE}:{rel(path)}"])
        need(baseline["exit_code"] == 0, "BASELINE_READ:" + rel(path))
        payload["baseline/" + rel(path)] = baseline["stdout"].encode("utf-8")
    diff = run(["git", "diff", "--binary", "--", *[rel(path) for path in tracked]])
    need(diff["exit_code"] == 0, "DIFF_CAPTURE")
    payload["review/IMPLEMENTATION.diff"] = diff["stdout"].encode("utf-8")

    self_review = {
        "schema": "T052_OBSERVER_REPAIR_SELF_REVIEW_V1",
        "review_key": REVIEW_KEY,
        "isolated_tests": test,
        "envelope_tests": envelope_test,
        "git_diff_check": diff_check,
        "verify_locked": verify,
        "freshness_before": before,
        "freshness_after": after,
        "actual_tool_calls": {"compile": 0, "run": 0, "check": 0, "gowin": 0},
        "miniconda_preparation_rejection": {
            "diagnostic": "TOOL_INVENTORY_DRIFT",
            "effect": "rejected before ATTEMPT_ROOT creation",
            "attempt_03_involvement": False,
        },
    }
    payload["review/SELF_REVIEW_RECEIPT.json"] = canonical(self_review)
    payload["review/FRESHNESS.json"] = canonical(after)

    tools = manifest["tools"]
    current_tool_mismatches = []
    for name, spec in tools.items():
        if ident(Path(spec["path"])) != {
                "bytes": spec["bytes"], "sha256": spec["sha256"]}:
            current_tool_mismatches.append(name)
    identity_audit = {
        "schema": "T052_OBSERVER_REPAIR_IDENTITY_AUDIT_V1",
        "review_key": REVIEW_KEY,
        "config": {"path": rel(CONFIG), **ident(CONFIG)},
        "manifest": {"path": rel(MANIFEST), **ident(MANIFEST)},
        "approval": {"path": rel(APPROVAL), **ident(APPROVAL)},
        "binding": {"path": rel(BINDING), **ident(BINDING)},
        "controller": {"path": rel(CONTROLLER), **ident(CONTROLLER)},
        "observer": {"path": rel(OBSERVER), **ident(OBSERVER)},
        "source_roles": len(manifest["sources"]),
        "tool_files": len(tools),
        "tool_mismatches": current_tool_mismatches,
        "compile_argv": manifest["compile_argv"],
        "run_argv": manifest["run_argv"],
        "calls": load(CONFIG)["calls"],
        "budgets_seconds": load(CONFIG)["budgets_seconds"],
    }
    need(not current_tool_mismatches, "TOOL_IDENTITY_DRIFT")
    payload["review/IDENTITY_AUDIT.json"] = canonical(identity_audit)

    scope = {
        "schema": "T052_OBSERVER_REPAIR_PRELAUNCH_SCOPE_V1",
        "review_key": REVIEW_KEY,
        "repo": ROOT.as_posix(),
        "base_git_sha": BASE,
        "state": STATE,
        "task": "observer reason exact-format repair and fresh prelaunch binding",
        "authorized_changes": [rel(OBSERVER), rel(SCHEDULE_CHECK),
                               rel(TEST_SCHEDULE), rel(CONTROLLER),
                               rel(ENVELOPE_TEST), rel(SEALER)],
        "execution_status": "NOT_EXECUTED",
        "T052_complete": False,
        "prohibited_changes": [
            "frozen DUT/ROM/128-line plan/calendar/math",
            "checker acceptance relaxation", "tool replacement", "timeout increase",
        ],
    }
    payload["review/SCOPE.json"] = canonical(scope)
    evidence = {
        "schema": "T052_OBSERVER_REPAIR_PRELAUNCH_EVIDENCE_V1",
        "review_key": REVIEW_KEY,
        "members": {name: {"bytes": len(raw), "sha256": sha(raw)}
                    for name, raw in sorted(payload.items())},
    }
    payload["review/EVIDENCE.json"] = canonical(evidence)
    package_manifest = {
        "schema": "T052_IMMUTABLE_REVIEW_PACKAGE_V1",
        "review_key": REVIEW_KEY,
        "repo": ROOT.as_posix(),
        "base_git_sha": BASE,
        "state": STATE,
        "scope_sha256": sha(payload["review/SCOPE.json"]),
        "evidence_sha256": sha(payload["review/EVIDENCE.json"]),
        "member_count_excluding_manifest": len(payload),
        "members_excluding_manifest": {
            name: {"bytes": len(raw), "sha256": sha(raw)}
            for name, raw in sorted(payload.items())
        },
    }
    payload["MANIFEST.json"] = canonical(package_manifest)

    OUT.mkdir(parents=True)
    with zipfile.ZipFile(ZIP_PATH, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100444 << 16
            archive.writestr(info, raw)
    with zipfile.ZipFile(ZIP_PATH) as archive:
        need(archive.namelist() == sorted(payload), "ARCHIVE_ORDER")
        for name, raw in payload.items():
            need(archive.read(name) == raw, "ARCHIVE_MEMBER:" + name)

    target = ident(ZIP_PATH)
    fingerprint = {
        "schema": "REVIEW_FINGERPRINT_V1",
        "review_key": REVIEW_KEY,
        "repo": ROOT.as_posix(), "base": BASE,
        "target": target["sha256"], "target_bytes": target["bytes"],
        "scope": package_manifest["scope_sha256"],
        "evidence": package_manifest["evidence_sha256"], "state": STATE,
    }
    (OUT / "FINGERPRINT.json").write_bytes(canonical(fingerprint))
    receipt = {
        "schema": "T052_OBSERVER_REPAIR_PRELAUNCH_SEAL_RECEIPT_V1",
        "review_key": REVIEW_KEY,
        "package": {"path": ZIP_PATH.name, **target},
        "fingerprint": {"path": "FINGERPRINT.json",
                        **ident(OUT / "FINGERPRINT.json")},
        "verified_member_count": len(payload),
        "tool_calls": {"compile": 0, "run": 0, "check": 0, "gowin": 0},
        "state": STATE,
    }
    (OUT / "SEAL_RECEIPT.json").write_bytes(canonical(receipt))
    print(json.dumps({
        "status": "SEALED", "review_key": REVIEW_KEY,
        "package": {"path": str(ZIP_PATH), **target},
        "scope_sha256": package_manifest["scope_sha256"],
        "evidence_sha256": package_manifest["evidence_sha256"],
        "members": len(payload), "tool_files": len(tools),
        "tool_calls": receipt["tool_calls"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
