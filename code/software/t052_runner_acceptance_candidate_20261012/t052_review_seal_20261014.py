"""Seal the already-consumed T052 attempt for immutable read-only review.

This script only reads existing evidence, hashes current identities, and writes a
new ZIP plus sidecar metadata.  It never starts Icarus, VVP, the checker, Gowin,
or any project test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[3]
REVIEW_KEY = "T052-M3-20261014-FULL-R03"
STATE = "SEALED-UNCOMMITTED_NOT_REEXECUTED"
BASE = "33490aad60a0bc5fa7f723508d1050c796c6d2e2"
OUT = ROOT / "code/output/m3_t052_review_seal_20261014_r03"
ZIP_PATH = OUT / "T052_M3_FULL_R03.zip"

ATTEMPT = ROOT / "code/output/m3_t052_full_capture_prepare_20261014_03"
PARENT = ROOT / "code/output/m3_t052_full_capture_parent_20261014_03"
PREFLIGHT = ROOT / "code/output/m3_t052_env_preflight_prepare_20261014_01"
PREPARED_ONLY = ROOT / "code/output/m3_t052_full_capture_prepare_20261014_02"
OLD_ATTEMPT = ROOT / "code/output/m3_t052_full_capture_prepare_20261014_01"
OLD_PARENT = ROOT / "code/output/m3_t052_full_capture_parent_20261014_01"

RUNNER_DIR = ROOT / "code/software/t052_runner_acceptance_candidate_20261012"
CHECKER_DIR = ROOT / (
    "code/software/t052_publication_acceptance_candidate_20261012/"
    "rtl_capture_precheck_20261012/successor_20261013"
)
ONESHOT_DIR = ROOT / (
    "code/software/t052_publication_acceptance_candidate_20261012/"
    "rtl_capture_precheck_20261012/oneshot_20261013"
)
PLAN = ROOT / (
    "code/docs/test/t052_publication_acceptance_20261012/"
    "M2_CONTROL_PLAN_20261012/controls_proposed.jsonl"
)
CALENDAR = ROOT / (
    "code/software/t052_publication_acceptance_candidate_20261012/"
    "publication.py"
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ident(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def add_tree(payload: dict[str, bytes], prefix: str, root: Path) -> None:
    if not root.is_dir():
        raise FileNotFoundError(root)
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        name = prefix + "/" + path.relative_to(root).as_posix()
        if name in payload:
            raise ValueError("DUPLICATE_ARCHIVE_MEMBER:" + name)
        payload[name] = path.read_bytes()


def spec_identity(spec: dict) -> dict[str, object]:
    path = Path(spec["path"])
    if not path.is_absolute():
        path = ROOT / path
    if "member" not in spec:
        return ident(path)
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(spec["member"])
    return {"bytes": len(raw), "sha256": sha(raw)}


def compare_maps(before: dict, after: dict, specs: dict) -> dict:
    names = sorted(set(before) | set(after))
    mismatches = []
    current_mismatches = []
    current_rows = {}
    for name in names:
        if before.get(name) != after.get(name):
            mismatches.append(name)
        spec = specs.get(name)
        value = spec_identity(spec) if isinstance(spec, dict) else {"missing": True}
        current_rows[name] = {"spec": spec, "identity": value}
        if value != before.get(name):
            current_mismatches.append(name)
    return {
        "before_count": len(before),
        "after_count": len(after),
        "before_after_mismatch_count": len(mismatches),
        "before_after_mismatches": mismatches,
        "current_checked": True,
        "current_mismatch_count": len(current_mismatches),
        "current_mismatches": current_mismatches,
        "current": current_rows,
    }


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    actual_path = ATTEMPT / "prepared/actual_once/actual_run_receipt.json"
    actual = load(actual_path)
    preparation_manifest = load(ATTEMPT / "prepared/manifest.json")
    if not isinstance(actual, dict):
        raise ValueError("ACTUAL_RUN_RECEIPT_TYPE")

    source_audit = compare_maps(
        actual["sources_before"], actual["sources_after"],
        preparation_manifest["sources"])
    tool_audit = compare_maps(
        actual["tools_before"], actual["tools_after"],
        preparation_manifest["tools"])
    if (source_audit["before_after_mismatch_count"] != 0
            or source_audit["current_mismatch_count"] != 0
            or tool_audit["before_after_mismatch_count"] != 0
            or tool_audit["current_mismatch_count"] != 0):
        raise ValueError("IDENTITY_DRIFT_DURING_SEAL")

    identity_audit = {
        "schema": "T052_REVIEW_CURRENT_IDENTITY_AUDIT_V1",
        "review_key": REVIEW_KEY,
        "state": STATE,
        "sources": source_audit,
        "tools": tool_audit,
        "plan": {"path": relative(PLAN), **ident(PLAN)},
        "calendar": {"path": relative(CALENDAR), **ident(CALENDAR)},
        "expected_plan_sha256":
            "b2d0cb1ba0bf3cd4b2d636f3d4cb7ac286558238ae2b52c3e9e43ba54ee5ef02",
        "expected_calendar_sha256":
            "0fdf4bb1530453cbbce14136bcae082ca1ff28e04d96402065f4c916ecf36058",
    }
    if (identity_audit["plan"]["sha256"]
            != identity_audit["expected_plan_sha256"]):
        raise ValueError("PLAN_DRIFT")
    if (identity_audit["calendar"]["sha256"]
            != identity_audit["expected_calendar_sha256"]):
        raise ValueError("CALENDAR_DRIFT")

    independent_audit = {
        "schema": "T052_INDEPENDENT_READONLY_AUDIT_V1",
        "review_key": REVIEW_KEY,
        "auditor": "/root/audit_t052_compile_diag",
        "audit_mode": "READ_ONLY_NO_TOOL_INVOCATION",
        "status": "FAIL_PARTIAL",
        "T052_complete": False,
        "actual_calls": {"compile": 1, "run": 1, "check": 1, "gowin": 0},
        "automatic_retries": 0,
        "timeouts": 0,
        "checker": {
            "exit_code": 1,
            "diagnostic": "INDEPENDENT_PUBLICATION_LEDGER:7",
            "expected": {
                "event": "CANCEL", "cycle": 43, "time": 870,
                "epoch": 1, "serial": 4, "req_id": 12,
                "reason": "frame",
            },
            "actual": {
                "event": "CANCEL", "cycle": 43, "time": 870,
                "epoch": 1, "serial": 4, "req_id": 12,
                "reason": " frame",
            },
            "difference": "actual reason has one leading ASCII space",
            "other_publication_rows_mismatch_count": 0,
            "final_ledger": {
                "accepted": 6, "published": 3,
                "cancelled": 3, "open": 0,
            },
        },
        "capture_mismatch_counts": {
            "controls": 0, "observations": 0,
            "publications": 1, "resets": 0,
        },
        "source_before_after_current_mismatch_count": 0,
        "tool_before_after_current_mismatch_count": 0,
        "tool_file_count": len(actual["tools_before"]),
        "conclusion": "UNIQUE_FULL_ATTEMPT_CONSUMED; NO_RETRY; T052_PARTIAL",
    }

    payload: dict[str, bytes] = {}
    add_tree(payload, "attempt03", ATTEMPT)
    add_tree(payload, "parent03", PARENT)
    add_tree(payload, "preflight01", PREFLIGHT)
    add_tree(payload, "prepared_only02", PREPARED_ONLY)
    add_tree(payload, "old_failed_attempt01", OLD_ATTEMPT)
    add_tree(payload, "old_failed_parent01", OLD_PARENT)

    execution_sources = {
        "t052_environment_successor_20261014.py":
            RUNNER_DIR / "t052_environment_successor_20261014.py",
        "oneshot_20261013.py": ONESHOT_DIR / "oneshot.py",
        "checker_20261013.py": CHECKER_DIR / "checker.py",
        "supervisor_20261013.py": RUNNER_DIR / "supervisor_20261013.py",
        "runner_tail_20261013.py": RUNNER_DIR / "runner_tail_20261013.py",
        "runner.py": RUNNER_DIR / "runner.py",
        "windows_job.py": RUNNER_DIR / "windows_job.py",
        "t052_review_seal_20261014.py": Path(__file__).resolve(),
        "controls_proposed.jsonl": PLAN,
        "publication.py": CALENDAR,
    }
    for name, path in execution_sources.items():
        payload["execution_sources/" + name] = path.read_bytes()

    scope = {
        "schema": "T052_REVIEW_SCOPE_V1",
        "review_key": REVIEW_KEY,
        "repo": ROOT.as_posix(),
        "base_git_sha": BASE,
        "state": STATE,
        "task": "T052 unique full compile-run-check attempt final evidence",
        "result": "FAIL_PARTIAL",
        "T052_complete": False,
        "included_groups": [
            "attempt03 complete directory",
            "parent03 complete directory",
            "zero-tool preflight01 complete directory",
            "prepared-only unconsumed attempt02 complete directory",
            "old ENVIRONMENT_DRIFT attempt01 and parent complete directories",
            "execution sources, frozen plan, and frozen calendar",
            "independent read-only audit and current identity audit",
        ],
        "execution_prohibition":
            "No compile, VVP, checker, Gowin, retry, or replacement tool was run while sealing",
        "known_failure": "INDEPENDENT_PUBLICATION_LEDGER:7",
    }
    payload["review/SCOPE.json"] = canonical(scope)
    payload["review/IDENTITY_AUDIT.json"] = canonical(identity_audit)
    payload["review/INDEPENDENT_AUDIT.json"] = canonical(independent_audit)
    payload["review/INDEPENDENT_AUDIT_TRANSCRIPT.txt"] = (
        "Auditor: /root/audit_t052_compile_diag\n"
        "Mode: strict read-only; no compile/VVP/checker/Gowin; no file changes\n"
        "Conclusion: FAIL_PARTIAL; T052 remains PARTIAL; unique attempt consumed\n"
        "Calls: compile=1 exit0 0.094s; run=1 exit0 0.109s; "
        "check=1 exit1 0.468s; retries=0; timeouts=0\n"
        "Checker: INDEPENDENT_PUBLICATION_LEDGER:7\n"
        "Expected: {event:CANCEL,cycle:43,time:870,epoch:1,serial:4,"
        "req_id:12,reason:frame}\n"
        "Actual:   {event:CANCEL,cycle:43,time:870,epoch:1,serial:4,"
        "req_id:12,reason:' frame'}\n"
        "Only difference: one leading ASCII space in reason; other 12 "
        "publication rows and 6/3/3/0 ledger match.\n"
        "Controls, observations, resets mismatches: 0.\n"
        "Frozen 7 sources, plan, calendar, and 1014 tools "
        "before/after/current mismatches: 0.\n"
    ).encode("utf-8")

    evidence = {
        "schema": "T052_REVIEW_EVIDENCE_V1",
        "review_key": REVIEW_KEY,
        "members": {
            name: {"bytes": len(raw), "sha256": sha(raw)}
            for name, raw in sorted(payload.items())
        },
    }
    evidence_raw = canonical(evidence)
    payload["review/EVIDENCE.json"] = evidence_raw

    manifest = {
        "schema": "T052_IMMUTABLE_REVIEW_PACKAGE_V1",
        "review_key": REVIEW_KEY,
        "repo": ROOT.as_posix(),
        "base_git_sha": BASE,
        "state": STATE,
        "scope_sha256": sha(payload["review/SCOPE.json"]),
        "evidence_sha256": sha(evidence_raw),
        "member_count_excluding_manifest": len(payload),
        "members_excluding_manifest": {
            name: {"bytes": len(raw), "sha256": sha(raw)}
            for name, raw in sorted(payload.items())
        },
        "result": "FAIL_PARTIAL",
        "T052_complete": False,
    }
    payload["MANIFEST.json"] = canonical(manifest)

    with zipfile.ZipFile(ZIP_PATH, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100444 << 16
            archive.writestr(info, raw)

    target = ident(ZIP_PATH)
    fingerprint = {
        "schema": "REVIEW_FINGERPRINT_V1",
        "review_key": REVIEW_KEY,
        "repo": ROOT.as_posix(),
        "base": BASE,
        "target": target["sha256"],
        "target_bytes": target["bytes"],
        "scope": manifest["scope_sha256"],
        "evidence": manifest["evidence_sha256"],
        "state": STATE,
    }
    (OUT / "FINGERPRINT.json").write_bytes(canonical(fingerprint))
    receipt = {
        "schema": "T052_REVIEW_SEAL_RECEIPT_V1",
        "review_key": REVIEW_KEY,
        "package": {"path": ZIP_PATH.name, **target},
        "fingerprint": {
            "path": "FINGERPRINT.json", **ident(OUT / "FINGERPRINT.json")},
        "member_count": len(payload),
        "verified_member_count": 0,
        "state": STATE,
    }

    verified = 0
    with zipfile.ZipFile(ZIP_PATH) as archive:
        names = archive.namelist()
        if names != sorted(payload):
            raise ValueError("ARCHIVE_MEMBER_ORDER")
        for name, expected in payload.items():
            raw = archive.read(name)
            if raw != expected:
                raise ValueError("ARCHIVE_MEMBER_MISMATCH:" + name)
            verified += 1
    receipt["verified_member_count"] = verified
    (OUT / "SEAL_RECEIPT.json").write_bytes(canonical(receipt))
    print(json.dumps({
        "status": "SEALED",
        "review_key": REVIEW_KEY,
        "package": {**target, "path": str(ZIP_PATH)},
        "scope_sha256": manifest["scope_sha256"],
        "evidence_sha256": manifest["evidence_sha256"],
        "members": verified,
        "source_mismatches": source_audit["current_mismatch_count"],
        "tool_mismatches": tool_audit["current_mismatch_count"],
        "tool_files": tool_audit["before_count"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
