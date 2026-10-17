"""Seal existing drill originals; no candidate/test/transport execution."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[7]
REL = "m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/night_drill_r01"
DOC = ROOT / "code/docs/test" / REL
SW = ROOT / "code/software" / REL
OUT = ROOT / "code/output/m3_m2_night_drill_20261017"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ref(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    delivery = DOC / "DELIVERY"
    delivery.mkdir(exist_ok=False)
    ready = read(DOC / "M3_READY_RECEIPT.json")
    local = read(OUT / "runs/local_group_01/RESULT.json")
    worker = read(OUT / "runs/worker_group_01/RESULT.json")
    actual = read(OUT / "runs/local_group_01/ACTUAL_SAMPLE_RECEIVE.json")
    network = read(OUT / "runs/post_worker_fetch_01/RESULT.json")
    if not (local["exit_code"] == worker["exit_code"] == network["exit_code"] == 0):
        raise ValueError("SEAL_REQUIRES_ACTUAL_OUTCOMES; do not invent missing result")
    result = {"schema": "M3_NIGHT_DRILL_RESULT_R01", "task_id": ready["task_id"],
        "utc": datetime.now(timezone.utc).isoformat(), "status": "PARTIAL", "queue_status": "WAITING_INPUT",
        "original_START": ready["original_START"], "deadline": ready["deadline"], "goal": ready["goal"],
        "unique_publisher": ready["unique_publisher"], "assignment_commit": ready["assignment_result_commit"],
        "sample_commit": ready["sample_result_commit"], "result_commit": None, "receipt_commit": None,
        "four_classes": {
            "normal": {"actual": "REAL_GIT_SAMPLE_RECEIVED_DURABLY", "receive_count": 1,
                       "M3_machine": ready["M3"], "sample_payloads": 8,
                       "real_two_machine_complete": False, "pending": ["M2 explicit host/session binding", "M2 limited review"],
                       "evidence": ref(OUT / "runs/local_group_01/ACTUAL_SAMPLE_RECEIVE.json")},
            "duplicate": {"actual": "REAL_SAMPLE_LOCAL_RELOAD_DUPLICATE_NO_REPLAY", "receipt_count": len(actual["final_state"]["receipts"]),
                          "advance_count": actual["final_state"]["advance_count"], "additional_Goals": 0,
                          "synthetic_group": "PASS", "real_two_machine_complete": False,
                          "pending": ["M2 identity/receiving confirmation"], "same_sample_not_repushed": True},
            "failure_unknown": {"local_adapter": "PASS_LOCAL_SYNTHETIC", "real_sample_remote_ancestor_exit": 0,
                                "actual_send_failure_cross_machine_recovery": "PENDING", "real_two_machine_complete": False,
                                "no_real_fault_push_created": True, "error_and_exact_target_retained": True},
            "interruption_recovery": {"actual_owned_worker_interrupt": "PASS", "state_origin": "LOCAL_SYNTHETIC",
                                     "seconds": worker["elapsed_seconds"], "owned_processes_closed": worker["owned_processes_closed"],
                                     "original_START_Goal_consumption_retained": True,
                                     "real_post_recovery_fetch": network, "sample_ancestor_exit": 0,
                                     "ancestor_tool_capture": {"chunk_id": "fd122a", "exit_code": 0, "output": ""},
                                     "App_restart_verified": False, "machine_restart_verified": False,
                                     "real_two_machine_complete": False}},
        "local_group": {"matched": local["completed"], "planned": local["planned"], "exit_code": local["exit_code"],
                        "seconds": local["elapsed_seconds"], "source_version": ref(OUT / "runs/local_group_01/SPEC.json")},
        "worker_group": {"exit_code": worker["exit_code"], "seconds": worker["elapsed_seconds"],
                         "actual_level": "L1_PROCESS_LIFECYCLE_ONLY", "evidence": ref(OUT / "runs/worker_group_01/RESULT.json"),
                         "wall_time_boundary": "Original monotonic launch/time budget records plus filesystem creation metadata; no fabricated restart interval"},
        "first_failure": {"phase": "input tree verifier", "error": "SOURCE_TREE_MISMATCH", "retained": "failure_01/",
                          "targeted_repair": "CONSUMED_PASS, 0.125s", "original_exec_capture": "merged tool output, not separate raw child streams",
                          "input_exit_evidence_amendment": "INPUT_READ_EVIDENCE_AMENDMENT.json"},
        "self_review": {"method": "Root and own read-only subagents; night2/night3 own static self-review",
                        "not_formal_review_windows": True, "findings_fixed_before_groups": ["deadline covers evidence writes and sealing", "owned Job before worker resume", "runtime pure-file audit hook", "actual vs reconstructed exit evidence separated"]},
        "actual_levels": ["L0 Git/input byte verification", "L1 local file/adaptor and owned process tests"],
        "new_Pro_HDL_EDA_devices": 0, "business_budget_restored": False, "board_release_allowed": False,
        "polling": {"status": "POLLING_NOT_VERIFIED", "actual_active_session_queries": ["startup_fetch_01", "post_worker_fetch_01"],
                    "background_scheduler": "NOT_DEPLOYED", "pre_drill_interval": "No claim of verified periodic scheduling from original START",
                    "missed_interval": "Worker interrupt/resume is subsecond; no App/machine outage was exercised"},
        "stop_reason": "No further authorized real failure/restart/remote identity inputs; do not wait indefinitely",
        "resume_conditions": ready["missing"],
        "next_authorized_queue": "Continue latest M3 R10 independent ready items within same original START/deadline/Goal and old budgets",
        "M2_limited_review": "PENDING", "overall_Pro": "PARTIAL"}
    save(DOC / "DRILL_RESULT.json", result)
    self_review = {"schema": "M3_DRILL_SELF_REVIEW_R01", "actual_source_readonly_review": True,
        "assignment_10_sample_8_originals": "PASS", "source_archive_7_CRC": "PASS", "source_gate_9_pass_exit0": "SAMPLE_TREE_ONLY",
        "M2_sender_identity": "MISSING", "new_real_HDL_EDA_device": 0,
        "local_group": result["local_group"], "worker_group": result["worker_group"],
        "no_4_of_4_claim": True, "no_accepted_or_integrated_claim": True,
        "exact_input_verifier_exit_amendment": ref(DOC / "INPUT_READ_EVIDENCE_AMENDMENT.json")}
    save(DOC / "SELF_REVIEW.json", self_review)
    # Include all own sources/receipts/run outputs, including ignored binary raw
    # streams. Upstream originals are copied as bytes, never reformatted.
    files = [p for base in (SW, DOC, OUT) for p in base.rglob("*") if p.is_file()
             and not p.is_relative_to(delivery) and "PUBLICATION_GATE" not in p.parts]
    source = ROOT / "code/docs/test/m2_night_drill_r01_20261017"
    files.extend(p for p in source.iterdir() if p.is_file())
    files.append(ROOT / "code/docs/M3_夜间协作双机演练任务单_R01_2026-10-17.md")
    files.append(DOC.parent / "START.md")
    manifest = {"schema": "M3_DRILL_ORIGINALS_MANIFEST_R01", "files": [ref(p) for p in sorted(set(files))]}
    save(delivery / "ORIGINALS_MANIFEST.json", manifest)
    archive = delivery / "M3_NIGHT_DRILL_RESULT_R01_20261018.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(set(files)):
            zf.write(p, p.relative_to(ROOT).as_posix())
        zf.write(delivery / "ORIGINALS_MANIFEST.json", "ORIGINALS_MANIFEST.json")
    with zipfile.ZipFile(archive) as zf:
        if zf.testzip() is not None:
            raise ValueError("DELIVERY_CRC_FAILURE")
        for item in manifest["files"]:
            raw = zf.read(item["path"])
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("DELIVERY_BYTES_MISMATCH")
    archive_receipt = {"schema": "M3_DRILL_ARCHIVE_RECEIPT_R01", "archive": ref(archive),
                       "manifest": ref(delivery / "ORIGINALS_MANIFEST.json"), "members": len(files) + 1,
                       "CRC_and_each_payload_SHA": "PASS"}
    save(delivery / "ARCHIVE_RECEIPT.json", archive_receipt)
    handoff = {"schema": "NIGHT_HANDOFF_V1", "handoff_id": "M3-NIGHT-DRILL-R01-RESULT-20261018-01",
        "task_id": ready["task_id"], "plan_version": "R01", "producer": "M3", "consumer": "M2",
        "base_commit": "358c16c2a927e3684c075dfc5ede70a6a67e036a", "result_commit": None,
        "manifest": [ref(archive), ref(delivery / "ARCHIVE_RECEIPT.json"), ref(DOC / "DRILL_RESULT.json")],
        "validation": {"status": "PARTIAL_WAITING_INPUT", "level": "L0/L1 limited", "self_review": True,
                       "local_group_exit": 0, "worker_group_exit": 0, "new_Pro_HDL_EDA_devices": 0,
                       "repo_gate": "REQUIRED_BEFORE_PUSH; publication receipt separately binds actual gate"},
        "ready_for": ["M2 limited original review and sender identity/completion evidence"],
        "next_action": "M2 read DRILL_RESULT missing/resume conditions; root continues independent R10 without reset",
        "blockers": result["resume_conditions"], "receipts": [], "board_release_allowed": False}
    save(DOC / "HANDOFF.json", handoff)
    print(json.dumps({"status": result["status"], "archive": archive_receipt["archive"], "members": archive_receipt["members"]}))


if __name__ == "__main__":
    main()
