"""Seal existing audit outputs and source originals; no functional rerun."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import time
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OUT = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    started = time.monotonic()
    launch = {"argv": [sys.executable, *sys.argv], "cwd": str(Path.cwd()),
              "pid": os.getpid(), "start_utc": datetime.now(timezone.utc).isoformat(),
              "machine": platform.node(), "python_version": sys.version,
              "python_exe_sha256": sha(sys.executable),
              "seal_script_sha256": sha(__file__), "purpose": "PACKAGING_ONLY_NO_FUNCTIONAL_RERUN"}
    dump(OUT / "SEAL_LAUNCH.json", launch)
    audit = json.loads((OUT / "INTAKE.json").read_text(encoding="utf-8"))
    run = json.loads((OUT / "ROUND_01/RECEIPT.json").read_text(encoding="utf-8"))
    if run["exit_code"] != 0 or run["timeout"]:
        raise RuntimeError("Cannot seal failed audit as successful")
    for path, expected in run["source_sha256_after"].items():
        if sha(path) != expected:
            raise RuntimeError("Audit source changed after success")
    supplements = {
        "code/rtl/common/pcm_waveform_observer_candidate/pcm_waveform_observer_bridge.sv": r"pcm_frame_observer|frame_load|play_left|play_right",
        "code/docs/hardware/score_transfer_v1/PROTOCOL.md": r"5s|200000000|800000",
        "code/tb/audio_out/m3_clock40_pcm_serial_acceptance/tb_normal.sv": r"valid|pcm_left|pcm_right|frame_tick|serial_capture",
        "code/tb/audio_out/m3_clock40_pcm_serial_acceptance/serial_capture.sv": r"frame_tick|frame_load|A |pcm|play_left|play_right",
        "code/docs/test/m3_pro_waveform_successor_20261017/prepare.py": r"normal_capture|raw_dir|sealed_samples|ROOT",
    }
    citations = []
    for number, (relative, pattern) in enumerate(supplements.items()):
        source = ROOT / relative
        copy = OUT / "INPUT_ORIGINALS" / f"supplement_{number:02d}_{source.name}"
        shutil.copyfile(source, copy)
        if sha(copy) != sha(source):
            raise RuntimeError("Supplement copy mismatch")
        citations.append({"path": relative, "bytes": source.stat().st_size,
                          "sha256": sha(source), "copy": str(copy.relative_to(ROOT)),
                          "classification": "EXISTING_CONTRACT_NOT_NEW_PRO_BINDING",
                          "matches": [{"line": n, "text": text} for n, text in enumerate(
                              source.read_text(encoding="utf-8-sig").splitlines(), 1)
                              if re.search(pattern, text)]})
    dump(OUT / "SUPPLEMENT_SOURCE_LOCATIONS.json", citations)
    missing = [
        {"id": "PRO_ENGINE_IDENTITY", "owner": "M2", "state": "PENDING_PRO_SOURCE_OR_TRACE",
         "needed": "Exact Pro target/top/source list/ROM bytes and SHA; five named new candidate locations absent locally"},
        {"id": "PUBLIC_EVENT_LANE_MAPPING", "owner": "M2 + M3 B1", "state": "UNKNOWN",
         "needed": "MIDI/source/channel/note/generation, actual slot Release, lane_tick/frame_tick, ready/accept/cancel/backpressure, epoch and effect acceptance mapping"},
        {"id": "SAME_EXECUTION_PUBLIC_TRACE", "owner": "M2 provider, M3 B1/B2 consumer", "state": "NOT_RECEIVED",
         "needed": "Source/ROM/top-bound actual public cycle/epoch/ID/left/right/clip plus BCLK/WS/DIN; existing monitor CSV is synthetic selftest"},
        {"id": "PRO_PCM_GOLDEN", "owner": "M1", "state": "NOT_RECEIVED_AT_EXPECTED_LOCATION",
         "needed": "Same-source Pro golden adapter; old R05/R06 reference and ROM are present and remain read-only"},
        {"id": "E2_FORMAL_ADOPTION_DISPLAY", "owner": "M2 integration, M3 same-version screen evidence", "state": "PENDING",
         "needed": "Real Pro sender frame-load mapping, 40-to-25MHz CDC and unique video/TMDS integration, full STA, approved bitstream; earlier base/timbre/E1 gates first"},
        {"id": "E3_FORMAL_UART_DEFAULT5S", "owner": "M2 integration, M3 physical file upload", "state": "PENDING",
         "needed": "Pro UART ball/Bank/electrical/reset identity, behavioral-vs-BRAM selection and approved exact bitstream, actual default-5s and physical ACK/44 READ evidence; no reuse of 6/6 quota"},
    ]
    dump(OUT / "MISSING_ITEMS.json", {"scope": audit["scope"], "items": missing,
                                      "board_release_allowed": False})
    dump(OUT / "RECEIPT.json", {"task": "night_task5_task_day_B1_intake_E2_E3_dependencies",
          "status": "DONE_INTAKE_AUDIT__PENDING_PRO_SOURCE_OR_TRACE", "actual_level": "L0_STATIC_PLUS_L1_PYTHON_AUDIT",
          "head": (OUT / "ROUND_01/head.stdout").read_text().strip(),
          "origin_develop_local_only": (OUT / "ROUND_01/origin.stdout").read_text().strip(),
          "audit": {"exit_code": run["exit_code"], "seconds": run["elapsed_seconds"],
                    "receipt_path": "ROUND_01/RECEIPT.json", "source_identity_stable": run["source_identity_stable"],
                    "artifacts": len(audit["artifacts"]), "receipt_links": len(audit["receipt_link_checks"]),
                    "old_archives_crc_verified": len(audit["archive_checks"]), "new_self_checks": "9/9_PASS"},
          "rounds": {"this_window_consumed": 1, "this_window_limit": 2, "shared_B1_limit": 6, "night_task2_reserved": 4,
                     "old_E2": "3/6_SUCCESS_STOP_READ_ONLY", "old_E3": "6/6_EXHAUSTED_READ_ONLY"},
          "new_function_calls": {"Python_audit": 1, "Icarus": 0, "ModelSim": 0, "Gowin": 0, "device": 0},
          "self_review": "Main window and authorized read-only subagent; no reviewer/pre-reviewer system enabled",
          "functional_failures": [], "git_index_commit_push_gate_calls": 0,
          "publication_owner": "night_task1_coordinator", "submitted": False, "pushed": False,
          "M2_final_review": "待用户转发，尚未送达", "board_release_allowed": False})
    members = []
    paths = sorted(p for p in OUT.rglob("*") if p.is_file()) + sorted(HERE.glob("*.py"))
    for path in paths:
        members.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    manifest = {"task": "B1_INTAKE_AUDIT_ONLY", "members": members,
                "excluded_self_references": ["DELIVERY_MANIFEST.json", "M3_TASK5_INTAKE_ORIGINALS_20261017.zip", "DELIVERY_RECEIPT.json", "SEAL.stdout", "SEAL.stderr", "SEAL_EXECUTION.json"]}
    dump(OUT / "DELIVERY_MANIFEST.json", manifest)
    archive_path = OUT / "M3_TASK5_INTAKE_ORIGINALS_20261017.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in members:
            archive.write(ROOT / item["path"], item["path"])
        archive.write(OUT / "DELIVERY_MANIFEST.json", "MANIFEST.json")
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("New archive CRC failure")
        for item in members:
            raw = archive.read(item["path"])
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise RuntimeError("New archive member SHA/size failure")
    receipt = {"archive": str(archive_path), "bytes": archive_path.stat().st_size,
               "sha256": sha(archive_path), "payload_files": len(members), "zip_members": len(members) + 1,
               "crc_size_sha_verified": True, "manifest_sha256": sha(OUT / "DELIVERY_MANIFEST.json"),
               "status": "DONE_INTAKE_AUDIT__PENDING_PRO_SOURCE_OR_TRACE", "board_release_allowed": False,
               "submitted": False, "pushed": False, "publication_owner": "night_task1_coordinator"}
    dump(OUT / "DELIVERY_RECEIPT.json", receipt)
    message = json.dumps(receipt, ensure_ascii=False) + "\n"
    (OUT / "SEAL.stdout").write_text(message, encoding="utf-8", newline="\n")
    (OUT / "SEAL.stderr").write_bytes(b"")
    dump(OUT / "SEAL_EXECUTION.json", dict(launch, end_utc=datetime.now(timezone.utc).isoformat(),
          elapsed_seconds=time.monotonic() - started, exit_code=0,
          stdout_sha256=sha(OUT / "SEAL.stdout"), stderr_sha256=sha(OUT / "SEAL.stderr")))
    print(message, end="")


if __name__ == "__main__":
    main()
