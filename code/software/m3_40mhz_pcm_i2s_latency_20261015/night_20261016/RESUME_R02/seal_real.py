"""Seal actual R05 independent consumption, raw originals and full bad captures."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from consume_capture import sha256


def identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main():
    source = Path(__file__).resolve().parent
    root = source.parents[4]
    docs = root / "code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02"
    a = root / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R02"
    out = docs / "SEAL_R01"
    out.mkdir(exist_ok=False)
    for p in source.glob("*.py"):
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    frozen = json.loads((docs / "PREFLIGHT_INPUTS.json").read_text(encoding="utf-8"))
    for item in frozen["inputs"].values():
        assert identity(Path(item["path"])) == item
    for item in frozen["copies"]:
        assert identity(Path(item["original"]["path"])) == item["original"]
        assert identity(Path(item["copy"]["path"])) == item["copy"]
    result_path = docs / "CONSUME_R01/REAL_RESULT.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["passed"] is True
    runs = {}
    for name in ("CONSUME_R01", "real_negative_R01"):
        p = docs / name / "RUN_RECEIPT.json"
        r = json.loads(p.read_text(encoding="utf-8"))
        assert r["exit_code"] == 0 and r["source_sha256"] == r["source_after_sha256"]
        for stream in ("stdout", "stderr"):
            assert sha256(p.parent / (stream + ".txt")) == r[stream + "_sha256"]
        runs[name] = {"receipt": identity(p), "exit_code": 0, "seconds": r["elapsed_seconds"], "argv": r["command"]}
    negative_path = docs / "real_negative_R01/cases/RESULTS.json"
    negatives = json.loads(negative_path.read_text(encoding="utf-8"))
    assert len(negatives) == 10 and all(r["passed"] and r["exit_code"] == 1 for r in negatives)
    summary = {k: v for k, v in result.items() if k not in (
        "request_ledger", "serial_frames", "serial_half_frames", "sampled_frames", "input_timeline", "startup_segment")}
    summary.update(serial_stereo_frames=len(result["serial_frames"]), serial_half_frames=len(result["serial_half_frames"]),
        sampled_frames=len(result["sampled_frames"]), max_accept_to_commit_us=result["max_accept_to_commit_cycles"] / 40,
        max_request_to_serial_us=result["max_request_to_serial_cycles"] / 40,
        equal_channels_all_commits=all(r["left"] == r["right"] for r in result["request_ledger"]),
        actual_clip_commits=sum(r["clipped"] for r in result["request_ledger"]),
        committed_serial_reset_aborts=[r for r in result["request_ledger"] if r.get("serial_disposition")],
        first_valid="UNKNOWN_NOT_EXPORTED", anti_swap_actual_coverage="NOT_DISTINGUISHABLE_MONO_EQUAL_CHANNELS",
        reset_release_after_final_assertion="NOT_OBSERVED", analog_10ms="UNKNOWN_NOT_MEASURED")
    event_calendar = []
    for event in result["input_timeline"]["accepted_events"]:
        following = next((r for r in result["request_ledger"] if r["epoch"] == event["epoch"]
                          and r["request_cycle"] >= event["cycle"]), None)
        event_calendar.append({**event, "next_request_id": following["id"] if following else None,
            "next_request_cycle": following["request_cycle"] if following else None,
            "serial_last_data_cycle": following.get("serial_last_data_cycle") if following else None,
            "scope": "CHRONOLOGICAL_ONLY_NO_AUDIBLE_OR_ALGORITHM_CAUSALITY"})
    (docs / "DIGITAL_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (docs / "EVENT_CALENDAR.json").write_text(json.dumps(event_calendar, indent=2) + "\n", encoding="utf-8")
    producer_path = a / "RUN_01/RUN_RECEIPT.json"
    producer = json.loads(producer_path.read_text(encoding="utf-8"))
    support = {}
    def include(item):
        p = Path(item["path"])
        assert p.resolve().is_relative_to(root.resolve())
        assert identity(p) == item
        support[p.resolve()] = p
    for item in frozen["inputs"].values():
        include(item)
    for item in producer["source_snapshot_files"].values():
        include(item)
    for collection in ("functional_calls", "version_calls"):
        for call in producer[collection]:
            for stream in ("stdout", "stderr"):
                include(call[stream])
    for relative, item in producer["stage_before"].items():
        p = Path(producer["stage"]) / relative
        include(dict(item, path=str(p.resolve())))
    for key in ("frozen_input_binding", "candidate_changes", "REAL_CAPTURE.jsonl", "REAL_INPUTS.jsonl",
                "STARTUP_CAPTURE.jsonl", "STARTUP_INPUTS.jsonl", "STARTUP_BOUNDARY_RAW.json"):
        include(producer[key])
    marker = a / "RUN_01_CONSUMED.json"
    support[marker.resolve()] = marker
    include(json.loads(marker.read_text(encoding="utf-8"))["preflight"])
    changes = json.loads(Path(producer["candidate_changes"]["path"]).read_text(encoding="utf-8"))
    for change in changes["changes"]:
        include(change["candidate"])
        include(change["diff"])
    boundary = json.loads((a / "STARTUP_BOUNDARY.json").read_text(encoding="utf-8"))
    include(boundary["source_contract"])
    authorization = root / "code/docs/test/m3_r05_functional_integration_20261015/coordinator/night_20261016/RESUME_R02/AUTHORIZATION_AND_DISPATCH.md"
    support[authorization.resolve()] = authorization
    receipt = {"schema": "C_R02_REAL_R05_DIGITAL_RECEIPT_V1", "status": "LIMITED_MAIN_WINDOW_DIGITAL_PASS",
        "created_utc": datetime.now(timezone.utc).isoformat(), "baseline_head": "c12636c034be62e10c564217298564422a533b9c",
        "validation": "A_REAL_MODELSIM_L2_CAPTURE_WITH_C_L1_INDEPENDENT_PUBLIC_PCM_SERIAL_CHECKER",
        "result": identity(result_path), "digital_summary": summary, "runs": runs,
        "negative_cases": [{k: r[k] for k in ("name", "expected", "actual", "passed", "exit_code", "seconds", "damaged_capture_sha256")} for r in negatives],
        "ready": frozen["inputs"]["CAPTURE_READY.json"], "producer_receipt": identity(producer_path),
        "source": [identity(p) for p in source.iterdir() if p.is_file()],
        "python": identity(Path(sys.executable)), "inputs": list(frozen["inputs"].values()),
        "startup": result["startup_segment"], "old_86_reruns": 0, "C_RTL_or_EDA_invocations": 0,
        "C_hardware_actions": 0, "C_Git_write_actions": 0, "algorithm_or_interface_modified": False,
        "startup_signoff": "UNKNOWN_NOT_SIGNED", "analog_10ms": "UNKNOWN_NOT_MEASURED",
        "physical_PLL_HDMI_STA": "NOT_SIGNED_BY_C", "board_release_allowed": False,
        "old_sources_unchanged": True, "submitted": False, "pushed": False, "publication_owner": "night coordinator",
        "self_review": "Read-only local self-review found no concrete blocker within specified source/result/contract scope; no new execution, no full capture reread by subagent."}
    with (docs / "NIGHT_RUN_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    for base in (source, docs):
        for p in base.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and out not in p.parents:
                support[p.resolve()] = p
    manifest = {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in support.values()}
    manifest_path = out / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = out / "C_R02_REAL_R05_DIGITAL_EVIDENCE.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in list(support.values()) + [manifest_path]:
            z.write(p, p.relative_to(root).as_posix(), compress_type=zipfile.ZIP_STORED if p.suffix == ".zip" else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name, item in manifest.items():
            h = hashlib.sha256()
            size = 0
            with z.open(name) as stream:
                for block in iter(lambda: stream.read(1048576), b""):
                    h.update(block); size += len(block)
            assert size == item["bytes"] and h.hexdigest() == item["sha256"]
    final = {"archive": identity(archive), "manifest": identity(manifest_path),
             "payload_members": len(manifest), "all_payload_CRC_and_SHA": "PASS", "status": receipt["status"]}
    (out / "SEAL_RECEIPT.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(final))


if __name__ == "__main__":
    main()
