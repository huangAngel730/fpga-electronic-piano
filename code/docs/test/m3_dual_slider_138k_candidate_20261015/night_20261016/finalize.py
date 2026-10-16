"""Seal local D PARTIAL without running any RTL/EDA or writing Git."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TB = ROOT / "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/night_20261016/tb_slider_audio_coexist.sv"
DECODER = ROOT / "code/software/m3_40mhz_pcm_i2s_latency_20261015/check_capture.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    receipts = [json.loads((HERE / f"RUN_{n:02d}/NIGHT_RUN_RECEIPT.json").read_text()) for n in (1, 2, 3)]
    positive = json.loads((HERE / "SOFTWARE_R02/POSITIVE_CHECK.json").read_text())
    software = json.loads((HERE / "SOFTWARE_R02/RECEIPT.json").read_text())
    decoder_sha = sha(DECODER)
    frozen_decoder = HERE / "RUN_03/execution_sources/check_capture.py"
    if decoder_sha != sha(frozen_decoder):
        raise RuntimeError("FINAL_DECODER_DRIFT")
    final = {
        "status": "PARTIAL", "task_complete": False,
        "git_baseline": "c12636c034be62e10c564217298564422a533b9c",
        "git_head_at_seal": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "utc": datetime.now(timezone.utc).isoformat(),
        "modified_write_sets": [str(HERE.relative_to(ROOT)), str(TB.relative_to(ROOT))],
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (TB, HERE / "run_coexist.py", HERE / "check_coexist.py", HERE / "postprocess.py")},
        "actual_tool_groups_consumed": 3, "old_allowances_restored": False,
        "actual_compile_starts": 3, "actual_simulation_starts": 2,
        "actual_runner_child_processes": sum(len(r["calls"]) for r in receipts),
        "simulation_seconds": sum(r["simulation_seconds"] for r in receipts),
        "per_tool_limit_seconds": 300, "per_group_limit_seconds": 300,
        "new_batch_simulation_limit_seconds": 900,
        "groups": [{"folder": f"RUN_{i+1:02d}", "passed": r["passed"], "error": r["error"],
                    "elapsed_seconds": r["elapsed_seconds"], "simulation_seconds": r["simulation_seconds"],
                    "receipt_sha256": sha(HERE / f"RUN_{i+1:02d}/NIGHT_RUN_RECEIPT.json")} for i, r in enumerate(receipts)],
        "positive_evidence": {
            "level": "L2_DIAGNOSTIC_PCM_ORIGINAL_AUDIO_AND_VISUAL_MODULES",
            "actual_compile_exit": 0, "actual_simulate_exit": 0,
            "simulation_tb_checks": 58, "raw_capture_rows": positive["cycles"],
            "decoded_stereo_frames": positive["decoded_stereo_frames"],
            "complete_serial_requests": sum(x["status"] == "SERIAL_OBSERVED" for x in positive["request_ledger"]),
            "underflows": positive["expected_diagnostic_underflows"],
            "visual_audio_coverage": positive["visual_audio_coverage"],
            "reset_cancelled_request_ids_epoch1": positive["reset_cancelled_request_ids_epoch1"],
            "reset_interrupted_serial_ids_epoch1": positive["reset_interrupted_serial_ids_epoch1"],
            "frame_distribution": positive["frame_distribution"],
            "max_diagnostic_digital_cycles": positive["max_digital_request_to_serial_cycles"],
            "software_postcheck_exit": 0,
        },
        "software_negative_cases": software["cases"],
        "software_dependency_boundary": "C decoder not separately listed in SOFTWARE_R02 before/after; frozen in RUN_03 and statically matched at seal",
        "final_static_decoder_sha256": decoder_sha,
        "rtl_behavioral_negative_cases": {str(i): "UNKNOWN_NOT_EXECUTED" for i in (1, 2, 3, 4)},
        "remaining_required_work": "Explicit new exact permission needed for four unexecuted TB fault injection variants; no fourth group authorized in this batch",
        "board_release_allowed": False, "r05_true_algorithm": "NOT_EXECUTED",
        "full_board_top": "NOT_TESTED", "gowin_invocations": 0,
        "modelsim_invocations": 0, "hardware_invocations": 0, "git_writes": 0,
        "hit_flash": "KNOWN_FAIL_DEFERRED_NOT_TESTED", "old_99_and_4": "REUSED_NOT_RERUN",
        "communications": {"direct_message": "AUTO_REVIEW_REJECTED_NOT_DELIVERED",
                           "handoff": "WAITING_USER_FORWARD_NOT_DELIVERED"},
        "negative_history_retained": True,
    }
    write(HERE / "NIGHT_RUN_RECEIPT.json", final)
    paths = sorted(p for p in HERE.rglob("*") if p.is_file()) + [TB]
    manifest = {p.relative_to(ROOT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in paths}
    write(HERE / "MANIFEST.json", {"kind": "D_PARTIAL_SOURCE_AND_ORIGINAL_EVIDENCE", "files": manifest})
    archive = HERE / "D_AUDIO_VISUAL_COEXIST_PARTIAL_20261016.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in paths + [HERE / "MANIFEST.json"]:
            z.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("ZIP_CRC")
        for name, item in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest() != item["sha256"]:
                raise RuntimeError("ZIP_MEMBER_SHA:" + name)
    write(HERE / "DELIVERY.json", {"status": "PARTIAL", "archive": str(archive), "bytes": archive.stat().st_size,
          "sha256": sha(archive), "member_files": len(paths)+1, "crc_and_all_member_sha": "PASS",
          "submitted": False, "pushed": False, "sent": False, "board_release_allowed": False})
    print(json.dumps({"status": "PARTIAL", "zip_bytes": archive.stat().st_size,
                      "sha256": sha(archive), "member_files": len(paths)+1}))


if __name__ == "__main__":
    main()
