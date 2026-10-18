"""Package the already executed R10 file-only unit and honest pending items."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[6]
REL = Path("m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017")
SW, DOC = ROOT / "code/software" / REL, ROOT / "code/docs/test" / REL
OUT = ROOT / "code/output/m3_c9_chain_night_r10_20261017"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    with path.open("xb") as stream:
        stream.write((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def ref(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    delivery = DOC / "DELIVERY"
    delivery.mkdir(exist_ok=False)
    ledger = read(DOC / "CONSUMPTION.json")
    def checked(desc):
        p = Path(desc["path"])
        p = p if p.is_absolute() else ROOT / p
        raw = p.read_bytes()
        if len(raw) != desc["bytes"] or hashlib.sha256(raw).hexdigest() != desc["sha256"]:
            raise ValueError("POST_LINK_FROZEN_OR_OUTPUT_BYTES_CHANGED:" + str(p))
        return p
    receipt = read(checked(ledger["initial"]["result"]))
    spec = read(checked(ledger["initial"]["spec"]))
    frozen = read(checked(spec["input_manifest"]))
    frozen_by_path = {}
    for item in frozen["files"]:
        p = checked(item)
        if p.is_relative_to(ROOT):
            frozen_by_path[p.relative_to(ROOT).as_posix()] = item
    def walk(value):
        if isinstance(value, dict):
            if {"path", "bytes", "sha256"} <= value.keys() and isinstance(value["path"], str):
                checked(value)
            else:
                for child in value.values():
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(receipt["actual_preparation"])
    if receipt["exit_code"] != 0:
        raise RuntimeError("NO_SUCCESSFUL_LINK_RECEIPT; seal failures separately")
    actual = OUT / "LINK_R01/source_preparation/handoff/INTEGRATION_HANDOFF.json"
    handoff = read(actual)
    # The direct entry is a byte copy of the real operation, not a rewritten
    # approval or a fabricated capture/result/FRAME document.
    (DOC / "INTEGRATION_HANDOFF.json").write_bytes(actual.read_bytes())
    start = read(DOC / "CONTINUATION_START_R01.json")
    result = {"schema": "N10_M3_FINAL_SOFTWARE_RESULT_V1", "utc": datetime.now(timezone.utc).isoformat(),
              "status": "PARTIAL_WAITING_M2_FINISH_PHASE_EXECUTION_AND_M1_MATH", "software_unit": "SOURCE_BOUND_PREPARATION_READY",
              "original_START": start["original_START"], "deadline": start["deadline"], "goal": start["goal"],
              "unique_executor_publisher": "night1", "new_LINK": {"planned": receipt["planned"], "matched": receipt["completed"],
                  "exit_code": receipt["exit_code"], "seconds": receipt["seconds"], "actual_preparation": receipt["actual_preparation"]["status"]},
              "old_114": "REUSED_NO_REPLAY", "old_budgets_restored": False,
              "actual_level": "L0 source identity and L1 pure-file software seams; no actual new HDL/EDA/device",
              "integration_handoff": ref(DOC / "INTEGRATION_HANDOFF.json"),
              "pending": handoff["missing_inputs_and_next_owner"],
              "FRAME_PLAN": "NOT_GENERATED_PENDING_FINISH_PHASE", "capture": "HDL_NOT_RUN", "math": "NOT_RUN_NO_ACTUAL_BUNDLE",
              "clock_model": "First core edge12500ps, period25000ps; nominal source derivation only",
              "finish_phase": "D or D+1 at1130660 driver stop unresolved; proposed argv does not freeze authority",
              "new_execution_permission": False, "real_verified": False, "math_verified": False, "board_release_allowed": False,
              "next_action": "M2 review one exact request and freeze stop/finish phase or approve exact TB successor and separately bind trusted executor/tool dependencies/HDL budget; M1 owns math once actual bundle exists",
              "stop_or_resume": "No old-group replay or arbitrary waiting; process verified new repository input only within original deadline and remaining explicit budgets",
              "M2_final_limited_review": "PENDING"}
    save(DOC / "RESULT.json", result)
    self_review = {"schema": "N10_M3_SELF_REVIEW_V1", "method": "Root plus own read-only subagents; member own static self-review",
                   "formal_review_windows": False, "source_window_boundary_preserved": True,
                   "all_owner_package_fields": len(read(ROOT / "code/docs/test/m2_night_r10_20261017/DELIVERY_CONTRACT.json")["package_fields"]),
                   "positive_negative_seams": result["new_LINK"], "no_false_authority": True,
                   "old_execution_receipts_not_current_capture": True, "no_empty_actual_RAW_FRAME_MATH_receipt": True}
    save(DOC / "SELF_REVIEW.json", self_review)
    files = [p for base in (SW, DOC, OUT) for p in base.rglob("*") if p.is_file()
             and "night_drill_r01" not in p.parts and "PUBLICATION_GATE" not in p.parts and not p.is_relative_to(delivery)]
    # Exact repository inputs are small and legally distributable project files;
    # external commercial executables/DLLs remain identity-only references.
    for item in read(DOC / "FROZEN_INPUTS.json")["files"]:
        p = Path(item["path"])
        p = p if p.is_absolute() else ROOT / p
        if p.is_relative_to(ROOT):
            files.append(p)
    files = sorted(set(files))
    identities = []
    for p in files:
        name = p.relative_to(ROOT).as_posix()
        expected = frozen_by_path.get(name)
        if expected is not None:
            checked(expected)
            identities.append({"path": name, "bytes": expected["bytes"], "sha256": expected["sha256"]})
        else:
            identities.append(ref(p))
    manifest = {"schema": "N10_M3_ORIGINALS_MANIFEST_V1", "files": identities,
                "external_tool_body": "Not redistributed; original executable/DLL paths and SHA are frozen in contract"}
    save(delivery / "ORIGINALS_MANIFEST.json", manifest)
    archive = delivery / "M3_NIGHT_R10_PREPARATION_20261018.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
        z.write(delivery / "ORIGINALS_MANIFEST.json", "ORIGINALS_MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("N10_ARCHIVE_CRC")
        for item in manifest["files"]:
            raw = z.read(item["path"])
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("N10_ARCHIVE_ORIGINAL_BYTES")
    save(delivery / "ARCHIVE_RECEIPT.json", {"schema": "N10_M3_ARCHIVE_RECEIPT_V1", "archive": ref(archive),
                                           "members": len(files) + 1, "CRC_and_each_member_SHA": "PASS"})
    machine_handoff = {"schema": "NIGHT_HANDOFF_V1", "handoff_id": "M3-N10-LINK-PREPARE-20261018-01", "task_id": "N10-M3-LINK",
        "plan_version": "R10", "producer": "M3", "consumer": "M2", "base_commit": start["base_commit"], "result_commit": None,
        "manifest": [ref(archive)], "validation": {"level": "L0/L1 SOURCE_BOUND_PREPARATION", "status": result["status"],
            "initial_LINK_exit": 0, "first_defect_increment": read(DOC / "CONSUMPTION.json")["first_defect_increment"],
            "new_HDL_EDA_devices": 0, "repository_gate": "REQUIRED_BEFORE_PUSH", "self_review": True},
        "ready_for": ["M2 exact stop/finish and executor/admission review", "M1 existing math adapter later consumes actual same-source capture"],
        "next_action": result["next_action"], "blockers": result["pending"], "receipts": [],
        "originals_resolution": "Top manifest resolves exact binary ZIP; internal raw descriptors resolve archive members preserving source path/bytes",
        "board_release_allowed": False}
    save(DOC / "HANDOFF.json", machine_handoff)
    print(json.dumps({"status": result["status"], "archive": ref(archive), "members": len(files) + 1}))


if __name__ == "__main__":
    main()
