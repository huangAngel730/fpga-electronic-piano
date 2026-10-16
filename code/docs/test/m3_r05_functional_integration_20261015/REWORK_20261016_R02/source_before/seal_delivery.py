"""Read-only collect the A BLOCKED_TOOL/software package, excluding coordinator."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

from common import HERE, ROOT, DOCS, TB_DIR, R05, PHYSICAL, identity, json_load, json_bytes, sha, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != DOCS.resolve() or output.name == "coordinator":
        raise ValueError("new owned output required")
    tested = json_load((DOCS / "SOFTWARE_02/RUN_RECEIPT.json").read_bytes())
    if tested["status"] != "SOFTWARE_SELFTEST_PASS" or tested["source_before"] != tested["source_after"]:
        raise ValueError("software run not stable/PASS")
    for item in tested["source_after"].values():
        if identity(item["path"]) != item:
            raise ValueError("tested execution source changed: " + item["path"])
    source_files = list(HERE.glob("*.py")) + list(HERE.glob("*.md")) + list(TB_DIR.glob("*.sv"))
    new_static = [str(p.relative_to(ROOT)) for p in source_files if str(p.relative_to(ROOT)).replace("\\", "/") not in tested["source_after"]]
    payload = {p.relative_to(ROOT).as_posix(): p for p in source_files}
    for p in DOCS.rglob("*"):
        if p.is_file() and "coordinator" not in p.relative_to(DOCS).parts and p.parent != output:
            payload[p.relative_to(ROOT).as_posix()] = p
    for archive in (R05, PHYSICAL):
        payload[archive.relative_to(ROOT).as_posix()] = archive
    # Verify every recorded original stream before packaging; missing earlier
    # transient diagnostic stdout files are not invented here.
    for receipt_file in list(DOCS.glob("*/RUN_RECEIPT.json")) + list(DOCS.glob("SYNTHETIC_JOB_*/RECEIPT.json")):
        receipt = json_load(receipt_file.read_bytes())
        def verify_streams(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ("stdout", "stderr") and isinstance(item, dict) and set(item) == {"path", "bytes", "sha256"}:
                        if identity(item["path"]) != item:
                            raise ValueError("original stream identity differs")
                    else:
                        verify_streams(item)
            elif isinstance(value, list):
                for item in value:
                    verify_streams(item)
        verify_streams(receipt)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "scope": "A_PARTIAL_BLOCKED_TOOL_SOFTWARE_L0_L1_ONLY",
        "board_release_allowed": False, "ModelSim_functional_starts": 0,
        "functional_attempt_consumed": False,
        "new_post_test_static_files": new_static,
        "files": {name: {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for name, p in sorted(payload.items())},
    }
    zip_path = output / "M3_A_R05_SOFTWARE_BLOCKED_TOOL_20261016.zip"
    with zipfile.ZipFile(zip_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("MANIFEST.json", json_bytes(manifest))
        for name, path in sorted(payload.items()):
            archive.writestr(name, path.read_bytes())
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for name, item in manifest["files"].items():
            raw = archive.read(name)
            if len(raw) != item["bytes"] or sha(raw) != item["sha256"]:
                raise ValueError("ZIP member SHA failure")
    write_new(output / "MANIFEST.json", manifest)
    receipt = {
        "status": "SEALED_A_PARTIAL_BLOCKED_TOOL", "archive": identity(zip_path),
        "members": len(payload), "software_run": identity(DOCS / "SOFTWARE_02/RUN_RECEIPT.json"),
        "functional_attempt_consumed": False, "ModelSim_functional_starts": 0,
        "board_release_allowed": False,
    }
    write_new(output / "SEAL_RECEIPT.json", receipt)
    write_new(output / "NIGHT_RUN_RECEIPT.json", {
        **receipt, "head": "8b64a352464932a28df565038cafc8d623dea5c9",
        "scope": "A_ONLY_C_SEPARATELY_SEALED", "actual_version_queries_attempted": 4,
        "version_query_process_creation": "UNKNOWN_OLD_SUPERVISOR_DID_NOT_RECORD_API_STAGE",
        "known_tool_identity_static_only": "2020.4_UNVERIFIED_RUNTIME_VERSION",
        "dynamic_loaded_dependencies": "UNKNOWN", "license_available": "UNKNOWN",
        "real_public_capture": "NONE", "per_request_deadline": "UNKNOWN",
        "candidate_observer": "L0_NOT_COMPILED", "analog_latency": "UNKNOWN",
    })
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
