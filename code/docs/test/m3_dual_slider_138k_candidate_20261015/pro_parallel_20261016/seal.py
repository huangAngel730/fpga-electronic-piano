"""Seal completed new isolated package without further RTL/EDA/Git writes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    run = json.loads((HERE / "ROUND_01/NIGHT_RUN_RECEIPT.json").read_text(encoding="utf-8"))
    preflight = json.loads((HERE / "PREFLIGHT_01/NIGHT_RUN_RECEIPT.json").read_text(encoding="utf-8"))
    geometry = json.loads((HERE / "RECORDED_GEOMETRY_AUDIT.json").read_text(encoding="utf-8"))
    assert run["passed"] and preflight["passed"] and geometry["passed"]
    assert run["before"] == run["after"] and len(run["results"]) == 5
    assert len(list(HERE.glob("ROUND_*/CONSUMED.json"))) == 1
    assert len(run["calls"]) == 6 and run["elapsed_seconds"] < 240
    for folder, record in (("PREFLIGHT_01", preflight), ("ROUND_01", run)):
        for call in record["calls"]:
            for stream in ("stdout", "stderr"):
                path = HERE / folder / (call["label"] + "." + stream)
                assert sha(path) == call[stream + "_sha256"]
    original = HERE / "INPUT_ORIGINALS"
    original.mkdir(exist_ok=False)
    copied = {}
    for i, (name, info) in enumerate(run["before"]["inputs"].items()):
        source = Path(name)
        assert sha(source) == info["sha256"], name
        dest = original / (f"{i:02d}_" + source.name)
        shutil.copyfile(source, dest)
        assert sha(dest) == info["sha256"]
        copied[str(dest.relative_to(ROOT))] = {"source": name, **info}
    write(HERE / "INPUT_ORIGINALS_MAP.json", copied)
    summary = {
        "status": "DONE_ISOLATED_DUAL_SLIDER_PACKAGE", "authorized_offline_scope_complete": True,
        "pro_dut_or_hardware_complete": False, "level": run["level"],
        "initial_head": preflight["head"], "execution_head": run["head"],
        "head_at_seal": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "utc": datetime.now(timezone.utc).isoformat(),
        "rounds_consumed": 1, "round_limit": 6, "batch_closed_on_first_success": True,
        "old_allowance_restored": False, "verification_seconds": run["elapsed_seconds"],
        "verification_calls": run["calls"], "preflight_seconds": preflight["elapsed_seconds"],
        "preflight_calls": preflight["calls"], "input_and_tool_identity": "BEFORE_AFTER_IDENTICAL",
        "source_sha256": {p: info["sha256"] for p, info in run["before"]["inputs"].items()},
        "tool_identity": run["before"]["tools"], "positive_and_negative_results": run["results"],
        "recorded_geometry_audit": {k: v for k, v in geometry.items() if k not in ("before", "after", "geometry")},
        "normal_scope": "DEFAULT_GEOMETRY_FIFO32_HANDSHAKE_RESET_RASTER_AUDIO_CADENCE_COMMIT_UNDERRUN",
        "pending": ["FORMAL_MODE_PRODUCER", "FORMAL_SCORE_PRODUCER_FRAME_ORIGIN_EPOCH",
                    "NEW_PRO_SOURCE_ROM_TOP_TRACE_IDENTITY", "FORMAL_GEOMETRY_REFERENCE_BODY_NOT_PROVIDED",
                    "PRO_CDC_PHYSICAL_STA_BITSTREAM_SCREEN_ANALOG", "HIT_FLASH_KNOWN_FAIL_DEFERRED"],
        "m1_old_r05_five_directories": "PUBLISHED_AND_RESTORED_NOT_USED_OR_RERUN",
        "audio_limit": "DIAGNOSTIC_PCM_MODULES_ONLY_NO_SERIAL_SAMPLE_COMPARISON",
        "rgb_limit": "BLANKING_BLACK_ONLY_NO_SCREEN_OR_COLOR_PIXEL_CLAIM",
        "board_release_allowed": False, "modelsim_gowin_hardware_invocations": 0,
        "git_writes_gate_number_state_updates": 0, "submitted": False, "pushed": False,
        "handoff_target": "01a14050-cd98-7c41-8004-5d3e25765167",
        "direct_communication_user_message": "01a1459a-bede-7c23-b456-5f246ceb02dc",
        "sent_at_seal": False,
    }
    write(HERE / "NIGHT_RUN_RECEIPT.json", summary)
    rtl = ROOT / "code/rtl/input/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016"
    tb = ROOT / "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016"
    paths = sorted(p for directory in (HERE, rtl, tb) for p in directory.rglob("*") if p.is_file())
    manifest = {p.relative_to(ROOT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in paths}
    write(HERE / "MANIFEST.json", {"kind": summary["status"], "files": manifest})
    archive = HERE / "M3_DUAL_SLIDER_DEFAULT_FIFO32_ISOLATED_20261017.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for p in paths + [HERE / "MANIFEST.json"]:
            zipped.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert len(zipped.namelist()) == len(paths)+1
        for name, item in manifest.items():
            assert hashlib.sha256(zipped.read(name)).hexdigest() == item["sha256"]
    delivery = {"status": summary["status"], "archive": str(archive), "bytes": archive.stat().st_size,
        "sha256": sha(archive), "member_files": len(paths)+1, "crc_and_member_sha": "PASS",
        "submitted": False, "pushed": False, "board_release_allowed": False}
    write(HERE / "DELIVERY.json", delivery)
    print(json.dumps(delivery))


if __name__ == "__main__":
    main()
