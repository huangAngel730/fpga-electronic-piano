"""Seal A rework evidence and bounded software receipt audits; no EDA/Git writes."""
import argparse
import difflib
import json
from pathlib import Path
import sys
import time
import zipfile

from common import HERE, ROOT, DOCS, TB_DIR, R05, PHYSICAL, identity, json_load, sha, write_new, json_bytes
from supervised_process import invoke
from watchdog_candidate import CANDIDATE, MEMBER, OLD, NEW


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    if output.parent != DOCS.resolve() or not output.name.startswith("SEAL_REWORK_"):
        raise ValueError("new owned seal directory required")
    output.mkdir(exist_ok=False)
    start = time.monotonic()
    audits = []
    for run, expected in (("REWORK_AUTHORIZED_RUN_01", 2), ("REWORK_WATCHDOG_RUN_02", 0)):
        result = invoke([sys.executable, "-B", "-X", "utf8", str(HERE / "audit_receipt.py"),
                         str(DOCS / run / "RUN_RECEIPT.json")], ROOT, output,
                        "audit_" + run, start + 300, step_budget=90)
        result["expected_exit_code"] = expected
        audits.append(result)
        if result["exit_code"] != expected or result["timeout"] or result["error"]:
            write_new(output / "FAILED_AUDIT.json", audits)
            raise ValueError("receipt self-audit failed")
    success = json_load((DOCS / "REWORK_WATCHDOG_RUN_02/RUN_RECEIPT.json").read_bytes())
    software = json_load((DOCS / "REWORK_SOFTWARE_08/RUN_RECEIPT.json").read_bytes())
    if software["status"] != "SOFTWARE_PASS":
        raise ValueError("software tests not PASS")
    for receipt in (success, software):
        if receipt["source_before"] != receipt["source_after"]:
            raise ValueError("execution source drift")
        for item in receipt["source_after"].values():
            if identity(item["path"]) != item:
                raise ValueError("tested file changed after execution")
    with zipfile.ZipFile(R05) as archive:
        original = archive.read(MEMBER)
    candidate = CANDIDATE.read_bytes()
    if candidate != original.replace(OLD, NEW, 1):
        raise ValueError("candidate changes more than watchdog")
    diff = "".join(difflib.unified_diff(original.decode().splitlines(True),
                                      candidate.decode().splitlines(True),
                                      fromfile="frozen_R05_TB", tofile="isolated_7ms_TB"))
    with (output / "WATCHDOG_ONLY.diff").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(diff)
    write_new(output / "SELF_AUDIT.json", {
        "audits": audits, "software_receipt": identity(DOCS / "REWORK_SOFTWARE_08/RUN_RECEIPT.json"),
        "actual_success_receipt": identity(DOCS / "REWORK_WATCHDOG_RUN_02/RUN_RECEIPT.json"),
        "candidate_changed_bytes": sum(a != b for a, b in zip(original, candidate)),
        "equal_length": len(original) == len(candidate),
        "new_RTL_invocations_during_seal": 0,
        "read_only_agent_review": "No blocking finding in exact candidate diff, two raw runs and consumption; no execution",
        "board_release_allowed": False,
    })
    payload = {}
    omitted = []
    for base in (HERE, TB_DIR, DOCS):
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if "coordinator" in path.relative_to(base).parts:
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if "work" in path.parts or path.suffix == ".wlf":
                omitted.append({"path": relative, "reason": "generated compiled library/waveform; original inputs and raw logs retained"})
                continue
            payload[relative] = path
    for archive in (R05, PHYSICAL):
        payload[archive.relative_to(ROOT).as_posix()] = archive
    # Validate all original stream byte identities referenced by retained receipts.
    def verify(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("stdout", "stderr") and isinstance(item, dict) and set(item) == {"path", "bytes", "sha256"}:
                    if identity(item["path"]) != item:
                        raise ValueError("original stream changed")
                else:
                    verify(item)
        elif isinstance(value, list):
            for item in value:
                verify(item)
    for path in payload.values():
        if path.name in ("RUN_RECEIPT.json", "RECEIPT.json", "SELF_AUDIT.json"):
            verify(json_load(path.read_bytes()))
    manifest = {
        "scope": "A_WATCHDOG_7MS_ISOLATED_FUNCTIONAL_PASS_PENDING_M2",
        "original_R05_6ms_result": "FAILED_RETAINED",
        "git_published": False, "board_release_allowed": False,
        "functional_rounds": 2, "functional_tool_processes": 6,
        "version_probe_attempts_including_history": 11,
        "post_execution_static_files": [str(Path(__file__).relative_to(ROOT))],
        "omitted_generated_files": omitted,
        "files": {name: {"bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}
                  for name, path in sorted(payload.items())},
    }
    archive_path = output / "M3_A_R05_WATCHDOG_REPAIR_20261016.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("MANIFEST.json", json_bytes(manifest))
        for name, path in sorted(payload.items()):
            archive.writestr(name, path.read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for name, item in manifest["files"].items():
            raw = archive.read(name)
            if len(raw) != item["bytes"] or sha(raw) != item["sha256"]:
                raise ValueError("ZIP member identity failure")
    write_new(output / "MANIFEST.json", manifest)
    receipt = {"status": "SEALED_ISOLATED_FUNCTIONAL_PASS_PENDING_M2",
               "archive": identity(archive_path), "members": len(payload),
               "wall_s": time.monotonic() - start,
               "software_audits": audits, "ModelSim_invocations_during_seal": 0,
               "git_published": False, "board_release_allowed": False}
    write_new(output / "SEAL_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
