"""Seal this exact C increment, raw software cases and necessary read-only inputs."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from consume_capture import sha256


def identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[3]
    docs = root / "code/docs/test/m3_40mhz_pcm_i2s_latency_20261015/night_20261016"
    seal = docs / "SEAL_PARTIAL_R01"
    seal.mkdir(exist_ok=False)
    inputs = [root / p for p in (
        "AGENTS.md", "code/AGENTS.md", "code/rtl/input/AGENTS.md", "code/docs/协作入口.md",
        "code/docs/M3_夜间八小时任务单_2026-10-15.md",
        "code/docs/M3_夜间M2候选权限预授权_2026-10-15.md",
        "code/docs/test/m3_r05_functional_integration_20261015/coordinator/night_20261016/DISPATCH.md",
        "code/rtl/audio_out/i2s_tx.sv", "code/rtl/audio_out/pcm_frame_buffer.sv",
        "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv",
        "code/rtl/common/pcm_clip_counter.sv",
        "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/CAPTURE_INTERFACE.md",
        "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/INPUT_BINDING.json",
        "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/CAPTURE_BLOCKED.json",
        "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/NIGHT_RUN_RECEIPT.json",
        "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESULT.md",
        "code/docs/test/m3_r05_functional_integration_20261015/night_20261016/PLATFORM_REJECTIONS.json",
    )]
    for path in inputs:
        target = seal / "read_only_inputs" / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    receipts = {}
    for name in ("software_R01", "software_R02", "binding_R01", "binding_R02", "binding_R03", "marker_R01"):
        path = docs / name / "RUN_RECEIPT.json"
        item = json.loads(path.read_text(encoding="utf-8"))
        assert item["exit_code"] == 0 and item["source_sha256"] == item["source_after_sha256"]
        assert sha256(path.parent / "stdout.txt") == item["stdout_sha256"]
        assert sha256(path.parent / "stderr.txt") == item["stderr_sha256"]
        receipts[name] = {"receipt": identity(path), "exit_code": item["exit_code"],
                          "seconds": item["elapsed_seconds"], "command": item["command"]}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    result = {"schema": "M3_C_NIGHT_PARTIAL_RECEIPT_V1", "status": "PARTIAL_REAL_CAPTURE_BLOCKED",
        "baseline_head": "c12636c034be62e10c564217298564422a533b9c", "head_at_seal": head,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "INDEPENDENT_REAL_CAPTURE_CONSUMER_SOFTWARE_ONLY",
        "validation_level": "L0_STATIC_AND_L1_SOFTWARE_SELFTEST_ONLY",
        "python": identity(Path(sys.executable)), "python_version": sys.version,
        "software_tests": {"consumer_final": 49, "binding_timeline_final": 26, "exact_pass_marker": 11},
        "runs": receipts, "actual_C_ModelSim_invocations": 0, "actual_C_Gowin_invocations": 0,
        "old_fixture_reruns": 0, "hardware_actions": 0, "git_write_actions": 0,
        "new_real_R05_capture_consumed": False, "real_provenance_positive": "UNKNOWN_NOT_AVAILABLE",
        "actual_R05_serial_decode": "UNKNOWN_NO_NEW_REAL_CAPTURE",
        "actual_R05_per_request_deadline": "UNKNOWN_NO_NEW_REAL_CAPTURE",
        "analog_end_to_end_10ms": "UNKNOWN_NOT_MEASURED", "board_release_allowed": False,
        "first_valid": "UNKNOWN_NOT_EXPORTED", "committed_clip_math": "UNKNOWN_METADATA_ONLY",
        "inputs": [identity(p) for p in inputs],
        "source": [identity(p) for p in here.iterdir() if p.is_file()],
        "failure_history": [{"path": str(docs / "START_FAILURE_01.json"),
                             "kind": "WINDOWSAPPS_ALIAS_START_FAILED_NO_PROCESS"}],
        "self_review": ["RESET_then_END_requires_low_tick", "first_request_must_commit_before_next_frame",
                        "per_tick_BCLK_and_frame_stall_bounds", "known_reset_cancel_before_sample",
                        "full_real_TB_PASS_marker_exact_once"],
        "snapshot_limitation": "software_R01 checker bytes were reconstructed after guards changed by removing exactly three added guards; SHA matches original preflight. Not a contemporaneous snapshot. Other R01 files unchanged; subsequent runs snapshot before launch.",
        "submitted": False, "pushed": False, "publication_owner": "night coordinator",
        "M2_handoff": "待用户转发，尚未送达",
        "next_required": ["effective platform permission for A", "A CAPTURE_READY + full new capture/input/receipt/source/log originals",
                          "run this independent consumer on exact bytes", "M2 final review", "analog timing remains physical work"]}
    with (docs / "NIGHT_RUN_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    paths = []
    for base in (here, docs):
        for p in base.rglob("*"):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            if p.suffix == ".zip" or p.name in ("SEAL_RECEIPT.json", "MANIFEST.json"):
                continue
            paths.append(p)
    manifest = {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in paths}
    (seal / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    archive = seal / "M3_NIGHT_C_REAL_CONSUMER_SOFTWARE_PARTIAL_R01.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in paths + [seal / "MANIFEST.json"]:
            z.write(p, p.relative_to(root).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for member, expected in manifest.items():
            import hashlib
            raw = z.read(member)
            assert len(raw) == expected["bytes"] and hashlib.sha256(raw).hexdigest() == expected["sha256"]
    info = {"archive": identity(archive), "manifest": identity(seal / "MANIFEST.json"),
            "payload_members": len(manifest), "crc_and_all_member_shas": "PASS",
            "status": "PARTIAL_SOFTWARE_ONLY", "board_release_allowed": False}
    (seal / "SEAL_RECEIPT.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info))


if __name__ == "__main__":
    main()
