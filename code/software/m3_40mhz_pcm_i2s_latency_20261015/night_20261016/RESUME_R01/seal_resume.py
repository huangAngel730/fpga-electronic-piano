"""Seal C resume software and the actual rejected producer receipt unchanged."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

from consume_capture import sha256


def identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main():
    source = Path(__file__).resolve().parent
    root = source.parents[4]
    docs = root / "code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R01"
    a_docs = root / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R01"
    seal = docs / "SEAL_R02"
    seal.mkdir(exist_ok=False)
    old = json.loads((docs / "COPY_BASELINE.json").read_text(encoding="utf-8"))
    for item in old:
        assert sha256(root / item["original"]) == item["original_sha256"]
    for path in source.glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert b"\r" not in path.read_bytes()
    producer_path = a_docs / "RUN_04/RUN_RECEIPT.json"
    assert sha256(producer_path) == "96f07239ee7f755865989cf9068fa33f62c28cfa907dbf96308d4f87d4133d2f"
    producer = json.loads(producer_path.read_text(encoding="utf-8"))
    paths = [a_docs / n for n in ("STARTUP_SCHEMA.json", "CAPTURE_INTERFACE.md", "CAPTURE_BLOCKED.json", "NIGHT_RUN_RECEIPT.json")]
    paths += [producer_path]
    for call in producer["functional_calls"]:
        paths += [Path(call[k]["path"]) for k in ("stdout", "stderr")]
    for name in ("STARTUP_CAPTURE.jsonl", "STARTUP_INPUTS.jsonl", "REAL_CAPTURE.jsonl", "REAL_INPUTS.jsonl"):
        path = Path(producer["stage"]) / name
        if path.exists():
            paths.append(path)
    input_copies = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        tag = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
        target = seal / "read_only_inputs" / (tag + "_" + path.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        assert sha256(target) == sha256(path)
        input_copies.append({"original": identity(path), "copy": identity(target)})
    (seal / "INPUT_COPY_MAP.json").write_text(json.dumps(input_copies, indent=2) + "\n", encoding="utf-8")
    runs = {}
    for name in ("mapping_R01", "startup_guards_R01", "startup_adapter_R01", "startup_adapter_R02", "startup_adapter_R03", "real_failed_receipt_R01"):
        path = docs / name / "RUN_RECEIPT.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        assert run["source_sha256"] == run["source_after_sha256"]
        for stream in ("stdout", "stderr"):
            assert sha256(path.parent / (stream + ".txt")) == run[stream + "_sha256"]
        runs[name] = {"receipt": identity(path), "exit_code": run["exit_code"],
                      "seconds": run["elapsed_seconds"], "command": run["command"]}
    rejected = json.loads((docs / "real_failed_receipt_R01/REAL_REJECTION_RESULT.json").read_text(encoding="utf-8"))
    assert rejected["passed"] is False and rejected["diagnostic"] == "PRODUCER_RUN_NOT_SUCCESSFUL"
    receipt = {"schema": "C_RESUME_PARTIAL_V1", "status": "PARTIAL_NO_SUCCESSFUL_A_CAPTURE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_head": "c12636c034be62e10c564217298564422a533b9c",
        "validation": "L0_STATIC_L1_NEW_SOFTWARE_ONLY_REAL_FAILED_ORIGIN_REJECTION",
        "final_flat_mapping_tests": 8, "final_startup_adapter_tests": 19,
        "actual_failed_producer_rejection": rejected,
        "rejected_producer_receipt": identity(producer_path),
        "runs": runs, "python": identity(Path(sys.executable)),
        "source": [identity(p) for p in source.iterdir() if p.is_file()],
        "read_only_inputs": [identity(p) for p in paths],
        "old_source_hashes_unchanged": True, "old_86_suite_reruns": 0,
        "C_EDA_invocations": 0, "C_hardware_actions": 0, "C_Git_write_actions": 0,
        "A_functional_groups_consumed": 3, "A_final_failure": "R05_STARTUP_OVER_64_EDGES",
        "real_success_branch": "UNKNOWN_NOT_EXECUTED", "real_serial_and_deadline": "UNKNOWN",
        "startup_signoff": "UNKNOWN_NOT_SIGNED", "analog_10ms": "UNKNOWN_NOT_MEASURED",
        "board_release_allowed": False, "submitted": False, "pushed": False,
        "publication_owner": "night coordinator", "new_execution_allowance_restored": False}
    with (docs / "NIGHT_RUN_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    files = [p for base in (source, docs) for p in base.rglob("*") if p.is_file()
             and "__pycache__" not in p.parts and p.suffix != ".zip"
             and p.name not in ("MANIFEST.json", "SEAL_RECEIPT.json")]
    manifest = {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in files}
    manifest_path = seal / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = seal / "C_RESUME_PARTIAL_R02.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in files + [manifest_path]:
            z.write(p, p.relative_to(root).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name, expected in manifest.items():
            raw = z.read(name)
            assert len(raw) == expected["bytes"] and hashlib.sha256(raw).hexdigest() == expected["sha256"]
    result = {"archive": identity(archive), "manifest": identity(manifest_path),
              "payload_members": len(manifest), "CRC_all_SHA": "PASS", "status": receipt["status"]}
    (seal / "SEAL_RECEIPT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
