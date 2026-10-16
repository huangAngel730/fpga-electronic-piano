"""Seal the exact static/software batch, explicitly without a real capture."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import ROOT, DOCS, TB_DIR, R05, identity, write_new

OUT = DOCS / "night_20261016"
SEAL = OUT / "SEAL_PARTIAL_R03"
BOARD = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016"


def main():
    assert not (OUT / "CAPTURE_READY.json").exists()
    assert not (OUT / "REAL_CAPTURE.jsonl").exists()
    assert not (OUT / "RUN_02").exists()
    assert not list(OUT.glob("*_CONSUMED.json"))
    failed = json.loads((OUT / "RUN_01/RUN_RECEIPT.json").read_text(encoding="utf-8"))
    assert failed["functional_attempt_consumed"] is False and not failed["functional_calls"]
    assert failed["version_calls"][0]["process_created"] is False
    assert failed["version_calls"][0]["winerror"] == 623
    software = json.loads((OUT / "SOFTWARE_R04/RUN_RECEIPT.json").read_text(encoding="utf-8"))
    tests = json.loads((OUT / "SOFTWARE_R04/cases/TEST_RESULTS.json").read_text(encoding="utf-8"))
    assert software["call"]["exit_code"] == 0 and software["source_before"] == software["source_after"]
    assert tests["status"] == "PASS" and len(tests["cases"]) == 14
    SEAL.mkdir(exist_ok=False)
    sources = list(HERE.glob("*.py")) + list((TB_DIR / "night_20261016").glob("*.sv")) + list(BOARD.glob("*.sv"))
    receipt = {
        "schema": "M3_R05_NIGHT_PARTIAL_RECEIPT_V1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "head": "c12636c034be62e10c564217298564422a533b9c", "role": "night_task_2_A",
        "task": "R05 UART MIDI board public pre-NBA capture/deadline increment",
        "status": "PARTIAL_BLOCKED_PLATFORM_APPROVAL", "functional_process_count": 0,
        "functional_allowance_consumed": False, "new_modelsim_compile_run": False,
        "probe": identity(OUT / "RUN_01/RUN_RECEIPT.json"), "probe_winerror": 623,
        "probe_exit_code": None, "probe_process_created": False,
        "platform_denials": identity(OUT / "PLATFORM_REJECTIONS.json"), "platform_denials_count": 2,
        "software_receipt": identity(OUT / "SOFTWARE_R04/RUN_RECEIPT.json"),
        "software_test_count": 14, "software_exit_code": software["call"]["exit_code"],
        "software_elapsed_s": software["call"]["elapsed_s"],
        "software_logs": {k: software["call"][k] for k in ("stdout", "stderr")},
        "static_checks": tests["static_checks"], "source_identities": [identity(p) for p in sources],
        "frozen_r05": identity(R05), "input_binding": identity(OUT / "INPUT_BINDING.json"),
        "changes": identity(OUT / "CANDIDATE_CHANGES_R04.json"),
        "prior_run01_preparation_limit": "Source bodies of initial failed runner were not frozen then; staged HDL/initial source SHA survive. No reconstructed source is represented as original.",
        "missing_platform_original_file": "Inline original tool errors only; PLATFORM_REJECTIONS.json is a transcription, not raw subprocess output",
        "limits": {"new_observation_rtl": "L0_STATIC_ONLY", "ledger": "L1_SYNTHETIC_SOFTWARE_ONLY",
            "real_capture": "UNKNOWN_NOT_GENERATED", "real_per_request_deadline": "UNKNOWN",
            "real_serial_sample_decode": "UNKNOWN", "first_valid": "UNKNOWN_NOT_EXPORTED",
            "analog_latency": "UNKNOWN_NOT_MEASURED", "physical_signoff": False,
            "board_release_allowed": False},
        "git": {"committed": False, "pushed": False, "owner": "night_coordinator"},
        "delivery": "Files prepared for coordinator; M2 human handoff pending user forwarding, not delivered",
        "next_owner": "Night coordinator seals all packages; M2 reviews later. Actual capture requires effective platform permission before running.",
    }
    write_new(OUT / "NIGHT_RUN_RECEIPT.json", receipt)
    paths = []
    for directory in (HERE, TB_DIR / "night_20261016", BOARD, OUT):
        for path in directory.rglob("*"):
            if path.is_file() and SEAL not in path.parents and "__pycache__" not in path.parts:
                paths.append(path)
    # Include exact archive and immutable imported source bodies for review.
    paths += [R05]
    paths += list(HERE.parent.glob("*.py"))
    # Old pass/failure remain old evidence; no rerun and no new-grade inference.
    for old_name in ("REWORK_AUTHORIZED_RUN_01", "REWORK_WATCHDOG_RUN_02"):
        old = DOCS / old_name
        paths += [old / "RUN_RECEIPT.json"]
        paths += list((old / "functional_logs").glob("*.log"))
        paths += list((old / "tool_probe_00").glob("*.log"))
    paths = sorted(set(p for p in paths if p.is_file()))
    members = {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}
    write_new(SEAL / "MANIFEST.json", {"schema": "M3_NIGHT_A_SEAL_MANIFEST_V1", "members": members})
    target = SEAL / "M3_NIGHT_A_STATIC_SOFTWARE_PARTIAL_R03.zip"
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in paths:
            z.write(path, path.relative_to(ROOT).as_posix())
        z.write(SEAL / "MANIFEST.json", "MANIFEST.json")
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name, item in members.items():
            raw = z.read(name)
            assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
    write_new(SEAL / "SEAL_RECEIPT.json", {"package": identity(target), "manifest": identity(SEAL / "MANIFEST.json"),
        "members_verified": len(members), "status": "ZIP_MEMBERS_VERIFIED", "real_capture": False})
    print(json.dumps({"package": identity(target), "members": len(members)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
