"""Seal the attempt-10 compile crash without running any generated VVP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[3]
ATTEMPT = ROOT / "code/output/m3_t052_observer_repair_prepare_20261014_10"
PARENT = ROOT / "code/output/m3_t052_observer_repair_parent_20261014_10"
PRELAUNCH = ROOT / "code/output/m3_t052_observer_repair_prelaunch_seal_20261014_r08"
PREVIOUS_FAILURE = ROOT / "code/output/m3_t052_observer_repair_attempt09_failure_seal_20261014"
OUT = ROOT / "code/output/m3_t052_observer_repair_attempt10_failure_seal_20261014"
ZIP_PATH = OUT / "T052_OBSERVER_REPAIR_ATTEMPT10_COMPILE_CRASH.zip"
CONTROLLER = ROOT / (
    "code/software/t052_runner_acceptance_candidate_20261012/"
    "t052_observer_repair_successor_20261014.py"
)
MANIFEST = ATTEMPT / "prepared/manifest.json"
CONFIG = ATTEMPT / "prepared/config.json"
OBSERVATION = PARENT / "observation.json"
RECEIPT = ATTEMPT / "prepared/actual_once/receipt.json"
COMPILE_RECEIPT = ATTEMPT / "prepared/actual_once/compile.receipt.json"
VVP = ATTEMPT / "prepared/actual_once/work/t052_control_v2.vvp"
WER_ROOT = Path("C:/ProgramData/Microsoft/Windows/WER/ReportArchive")


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


def readable_wer_reports() -> tuple[list[dict], dict[str, bytes]]:
    records = []
    payload = {}
    if not WER_ROOT.is_dir():
        return records, payload
    for directory in sorted(WER_ROOT.glob("AppCrash_cmd.exe*")):
        report = directory / "Report.wer"
        try:
            raw = report.read_bytes()
        except OSError:
            continue
        text = raw.decode("utf-16", errors="replace") if raw.startswith(
            (b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8", errors="replace")
        if "msvcrt.dll_unloaded" not in text or "c0000005" not in text.lower():
            continue
        records.append({"path": str(report), **identity_bytes(raw)})
        payload[f"windows_wer/{directory.name}/Report.wer"] = raw
    return records, payload


def main() -> None:
    need(not OUT.exists(), "SEAL_OUTPUT_EXISTS")
    observation = load(OBSERVATION)
    receipt = load(RECEIPT)
    compile_receipt = load(COMPILE_RECEIPT)
    need(observation["exit_code"] == 1
         and observation["failure"] == "RunnerFailure:SUPERVISOR_CHILD_NONZERO",
         "PARENT_FAILURE")
    need(receipt["failure"] == "ValueError:STEP_FAILED:compile"
         and len(receipt["steps"]) == 1, "CHILD_FAILURE")
    need(compile_receipt["exit_code"] == 3221225477
         and not compile_receipt["timed_out"]
         and compile_receipt["stdout"]["bytes"] == 0
         and compile_receipt["stderr"]["bytes"] == 0, "COMPILE_SIGNATURE")
    need(VVP.is_file(), "FAILED_COMPILE_VVP_MISSING")
    actual_dir = RECEIPT.parent
    need(not (actual_dir / "run.receipt.json").exists()
         and not (actual_dir / "check.receipt.json").exists(),
         "LATER_STAGE_PRESENT")
    need(observation["sources_before"] == observation["sources_after"],
         "OUTER_SOURCE_DRIFT")
    for path_text, expected in observation["sources_after"].items():
        need(identity(Path(path_text)) == expected,
             "CURRENT_SOURCE_DRIFT:" + path_text)

    manifest = load(MANIFEST)
    config = load(CONFIG)
    source_audit = {}
    for role, spec in sorted(manifest["sources"].items()):
        actual = identity_bytes(spec_raw(spec))
        expected = {"bytes": spec["bytes"], "sha256": spec["sha256"]}
        need(actual == expected, "FROZEN_SOURCE_DRIFT:" + role)
        source_audit[role] = {"spec": spec, "actual": actual, "matches": True}
    tool_mismatches = [name for name, spec in manifest["tools"].items()
                       if identity(Path(spec["path"])) != {
                           "bytes": spec["bytes"], "sha256": spec["sha256"]}]
    need(not tool_mismatches, "TOOL_DRIFT")
    software_mismatches = [path for path, expected in config["software"].items()
                           if identity(Path(path)) != expected]
    need(not software_mismatches, "SOFTWARE_DRIFT")

    wer_records, wer_payload = readable_wer_reports()
    failure_receipt = {
        "schema": "T052_OBSERVER_REPAIR_ATTEMPT10_FAILURE_V1",
        "review_key": "T052-M3-20261014-OBSERVER-REPAIR-PRELAUNCH-R08",
        "attempt": 2,
        "status": "FAIL_PARTIAL_COMPILE_CRASH",
        "parent_failure": observation["failure"],
        "child_failure": receipt["failure"],
        "compile": compile_receipt,
        "actual_tool_calls": {"compile": 1, "run": 0, "check": 0,
                              "gowin": 0},
        "failed_compile_vvp": {
            "path": str(VVP.resolve()), **identity(VVP),
            "execution_prohibited": True,
        },
        "four_captures_present": {
            name: (actual_dir / f"{name}.jsonl").exists()
            for name in ("controls", "observations", "publications", "resets")
        },
        "diagnosis": {
            "boundary": "OS/tool process crash; not an RTL diagnostic",
            "unsigned_exit": 3221225477,
            "hex_exit": "0xC0000005",
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "wer_signature": "cmd.exe / msvcrt.dll_unloaded / c0000005",
            "matching_readable_wer_reports": wer_records,
            "third_attempt_not_used": True,
        },
        "source_audit": source_audit,
        "outer_sources_stable": True,
        "software_files": len(config["software"]),
        "software_mismatches": software_mismatches,
        "tool_files": len(manifest["tools"]),
        "tool_mismatches": tool_mismatches,
        "controller": identity(CONTROLLER),
    }
    need(not any(failure_receipt["four_captures_present"].values()),
         "UNEXPECTED_CAPTURE")

    payload: dict[str, bytes] = {}
    add_tree(payload, "attempt10", ATTEMPT)
    add_tree(payload, "parent10", PARENT)
    add_tree(payload, "prelaunch_r08", PRELAUNCH)
    add_tree(payload, "attempt09_failure_seal", PREVIOUS_FAILURE)
    add_file(payload, "implementation/controller.py", CONTROLLER)
    payload.update(wer_payload)
    payload["FAILURE_RECEIPT.json"] = canonical(failure_receipt)
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
        "status": "SEALED_COMPILE_CRASH",
        "package": {"path": str(ZIP_PATH), **identity(ZIP_PATH)},
        "members": len(payload),
        "actual_tool_calls": failure_receipt["actual_tool_calls"],
        "failed_vvp": failure_receipt["failed_compile_vvp"],
        "tool_files": len(manifest["tools"]),
        "frozen_members": len(manifest["sources"]),
        "third_attempt_used": False,
    }
    (OUT / "SEAL_RECEIPT.json").write_bytes(canonical(result))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
