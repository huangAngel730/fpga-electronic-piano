"""Seal the attempt-09 pre-worker failure without invoking the HDL toolchain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[3]
ATTEMPT = ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_09"
PARENT = ROOT / "code/output/m3_t052_observer_repair_parent_20261014_09"
PRELAUNCH = ROOT / "code/output/m3_t052_observer_repair_prelaunch_seal_20261014_r07"
OUT = ROOT / "code/output/m3_t052_observer_repair_attempt09_failure_seal_20261014"
ZIP_PATH = OUT / "T052_OBSERVER_REPAIR_ATTEMPT09_FAILURE.zip"
CONTROLLER = ROOT / (
    "code/software/t052_runner_acceptance_candidate_20261012/"
    "t052_observer_repair_successor_20261014.py"
)
MANIFEST = ATTEMPT / "prepared/manifest.json"
CONFIG = ATTEMPT / "prepared/config.json"
OBSERVATION = PARENT / "observation.json"
OUTER = ATTEMPT / "outer_consumed.json"
WORKER = ATTEMPT / "worker_entry_consumed.json"
CHILD = ATTEMPT / "prepared/consumed.json"
ACTUAL = ATTEMPT / "prepared/actual_once"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def identity_bytes(raw: bytes) -> dict[str, object]:
    return {"bytes": len(raw), "sha256": sha(raw)}


def identity(path: Path) -> dict[str, object]:
    return identity_bytes(path.read_bytes())


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def spec_raw(spec: dict) -> bytes:
    path = Path(spec["path"])
    if not path.is_absolute():
        path = ROOT / path
    if "member" not in spec:
        return path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        return archive.read(spec["member"])


def main() -> None:
    need(not OUT.exists(), "SEAL_OUTPUT_EXISTS")
    observation = load(OBSERVATION)
    need(observation["exit_code"] == 1, "OBSERVATION_EXIT")
    need(observation["failure"] == "RunnerFailure:SUPERVISOR_SOURCE_DRIFT",
         "OBSERVATION_FAILURE")
    need(OUTER.is_file() and not WORKER.exists() and not CHILD.exists()
         and not ACTUAL.exists(), "FAILURE_PHASE")

    manifest = load(MANIFEST)
    config = load(CONFIG)
    source_audit = {}
    containers = {}
    for role, spec in sorted(manifest["sources"].items()):
        raw = spec_raw(spec)
        actual = identity_bytes(raw)
        expected = {"bytes": spec["bytes"], "sha256": spec["sha256"]}
        need(actual == expected, "SOURCE_MEMBER_DRIFT:" + role)
        source_audit[role] = {
            "spec": spec, "actual": actual, "matches": True,
        }
        if "member" in spec:
            path = Path(spec["path"])
            if not path.is_absolute():
                path = ROOT / path
            containers[str(path.resolve())] = identity(path)

    tool_mismatches = []
    for name, spec in manifest["tools"].items():
        if identity(Path(spec["path"])) != {
                "bytes": spec["bytes"], "sha256": spec["sha256"]}:
            tool_mismatches.append(name)
    need(not tool_mismatches, "TOOL_DRIFT")

    software_mismatches = []
    for path_text, expected in config["software"].items():
        if identity(Path(path_text)) != expected:
            software_mismatches.append(path_text)
    need(not software_mismatches, "SOFTWARE_DRIFT")

    receipt = {
        "schema": "T052_OBSERVER_REPAIR_ATTEMPT_FAILURE_V1",
        "attempt": 1,
        "review_key": "T052-M3-20261014-OBSERVER-REPAIR-PRELAUNCH-R07",
        "status": "FAIL_PARTIAL_BEFORE_WORKER",
        "failure": observation["failure"],
        "exit_code": observation["exit_code"],
        "elapsed_seconds": observation["elapsed_seconds"],
        "actual_tool_calls": {"compile": 0, "run": 0, "check": 0,
                              "gowin": 0},
        "phase_evidence": {
            "outer_marker_exists": OUTER.exists(),
            "worker_marker_exists": WORKER.exists(),
            "child_marker_exists": CHILD.exists(),
            "actual_output_exists": ACTUAL.exists(),
        },
        "diagnosis": {
            "code": "ARCHIVE_MEMBER_IDENTITY_USED_FOR_CONTAINER_PATH",
            "detail": (
                "outer source snapshot compared ZIP-member bytes/SHA against "
                "the containing ZIP path before worker launch"
            ),
            "frozen_members_match": True,
            "container_identities": containers,
        },
        "source_audit": source_audit,
        "software_files": len(config["software"]),
        "software_mismatches": software_mismatches,
        "tool_files": len(manifest["tools"]),
        "tool_mismatches": tool_mismatches,
        "controller": identity(CONTROLLER),
    }

    payload: dict[str, bytes] = {}
    add_tree(payload, "attempt09", ATTEMPT)
    add_tree(payload, "parent09", PARENT)
    add_tree(payload, "prelaunch_r07", PRELAUNCH)
    add_file(payload, "implementation/controller.py", CONTROLLER)
    payload["FAILURE_RECEIPT.json"] = canonical(receipt)
    package_manifest = {
        "schema": "T052_FAILURE_SEAL_MANIFEST_V1",
        "members": {name: identity_bytes(raw)
                    for name, raw in sorted(payload.items())},
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

    result = {
        "status": "SEALED_FAILURE",
        "package": {"path": str(ZIP_PATH), **identity(ZIP_PATH)},
        "members": len(payload),
        "actual_tool_calls": receipt["actual_tool_calls"],
        "tool_files": len(manifest["tools"]),
        "frozen_members": len(manifest["sources"]),
    }
    (OUT / "SEAL_RECEIPT.json").write_bytes(canonical(result))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
