"""Read final child receipts and select only authorized task2 publication files."""
import hashlib
import json
from pathlib import Path

COORD = Path(__file__).resolve().parent
ROOT = COORD.parents[5]
E1 = ROOT / "code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016"
E2 = ROOT / "code/docs/test/m3_pro_waveform_successor_20261017"
E3 = ROOT / "code/docs/test/m3_pro_min_transfer_successor_20261017"
E4 = ROOT / "code/docs/test/m3_n32_pro_candidate_20261017"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(path):
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def verify_link(value):
    if isinstance(value, dict):
        if all(key in value for key in ("path", "bytes", "sha256")):
            actual = identity(Path(value["path"]))
            assert actual["bytes"] == value["bytes"] and actual["sha256"] == value["sha256"], value["path"]
        for child in value.values():
            verify_link(child)
    elif isinstance(value, list):
        for child in value:
            verify_link(child)


def main():
    latest3 = read(E3 / "LATEST_RECEIPT.json")
    latest4 = read(E4 / "FINAL_ENTRY.json")
    verify_link(latest3)
    verify_link(latest4)
    status2 = read(E2 / "PACKAGE_STATUS.json")
    archive2 = identity(Path(status2["package"]))
    assert archive2["bytes"] == status2["bytes"] and archive2["sha256"] == status2["sha256"]
    e2 = read(E2 / "RESULT.json")
    e4 = read(E4 / "FINAL_RECEIPT.json")
    assert e2["isolated_status"] == "PASS" and latest3["rounds_consumed"] == 6
    assert e4["rounds_consumed"] == 5 and e4["physical_rounds_consumed"] == 0
    archives = [
        ("E1", E1 / "M3_DUAL_SLIDER_DEFAULT_FIFO32_ISOLATED_20261017.zip", E1 / "MANIFEST.json"),
        ("E2", Path(status2["package"]), E2 / "MANIFEST.json"),
        ("E3", Path(latest3["archive"]["path"]), Path(latest3["manifest"]["path"])),
        ("E4", Path(latest4["sealed_originals"]["path"]), E4 / "SEAL_MANIFEST.json")]
    original_archives = [{"package": name, **identity(path),
                          "manifest_path": manifest.relative_to(ROOT).as_posix()}
                         for name, path, manifest in archives]
    roots = [
        "code/rtl/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017",
        "code/tb/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017",
        "code/rtl/input/score_transfer_candidate/m3_pro_min_transfer_successor_20261017",
        "code/tb/input/score_transfer_candidate/m3_pro_min_transfer_successor_20261017",
        "code/software/score_transfer_trace_candidate_20261015/m3_pro_min_transfer_successor_20261017",
        "code/rtl/common/m3_n32_pro_candidate_20261017",
        "code/tb/audio/m3_n32_pro_candidate_20261017",
        "code/software/m3_n32_pro_candidate_20261017",
        "code/build/138k_polyphony_resource/m3_n32_pro_candidate_20261017"]
    selected = set()
    extensions = {".sv", ".v", ".py", ".ps1", ".json", ".md", ".tcl", ".sdc", ".cst", ".gprj"}
    for name in roots:
        base = ROOT / name
        if base.exists():
            selected.update(p.relative_to(ROOT).as_posix() for p in base.rglob("*")
                            if p.is_file() and p.suffix in extensions and "__pycache__" not in p.parts)
    for base in (E2, E3, E4):
        selected.update(p.relative_to(ROOT).as_posix() for p in base.iterdir()
                        if p.is_file() and p.suffix in {".md", ".json", ".py", ".mem", ".diff"}
                        and not p.name.startswith(("COMMUNICATION_", "SEAL_EXECUTION.")))
    # Post-seal links are useful to intake, while raw run streams remain inside
    # the four exact child archives. No work/VVP/WLF caches are selected.
    selected.update(p.relative_to(ROOT).as_posix() for p in
                    (E3 / "SEAL_R01/VERIFICATION.json", E3 / "SEAL_R01/MANIFEST.json"))
    results = {
        "E1": {"overall": "PARTIAL", "offline": "REUSED_L2_PLUS_NEW_L0_AUDIT",
               "new_rounds": 0, "new_round_limit": 6, "new_round_seconds": 0,
               "reused_old_rounds": 1, "reused_old_seconds": 100.282},
        "E2": {"overall": "PARTIAL", "offline": "L2_ISOLATED_REPLAY_PASS",
               "new_rounds": 3, "new_round_limit": 6,
               "new_round_seconds": sum(row["elapsed_seconds"] for row in e2["round_results"]),
               "source_frames": 14241, "real_source_frames": 5849, "actual_RTL_negatives": 5},
        "E3": {"overall": "PARTIAL", "offline": "L2_REAL_MIDI_UART_RAM_SUCCESSOR_PASS",
               "new_rounds": 6, "new_round_limit": 6,
               "new_round_seconds": latest3["round_seconds_total"],
               "real_midi_events": 44, "cases": 127, "replies": 112,
               "NACK8_successor_fixed": True, "round6_scope": "REPORT_CONTROL_SOFTWARE_ONLY"},
        "E4": {"overall": "PARTIAL", "offline": "L3_SHORT_MATH_TRANSPORT_AND_L2_RETIREMENT",
               "new_rounds": 5, "new_round_limit": 6,
               "new_round_seconds": e4["round_elapsed_s_total"],
               "normal_sizes": [4, 8, 16, 32], "actual_RTL_negatives": 11,
               "max_request_commit_cycles": [69, 109, 189, 349],
               "serial_complete_halves_per_size": {"left": 32, "right": 31},
               "Pro_physical": "NOT_RUN", "pure_sine_and_board_spectrum": "PENDING"}}
    value = {"schema": "M3_TASK2_FOUR_PACKAGE_FINAL_INTAKE_V1",
             "baseline": "ad2de2169230dc8fd9f4b6f8157d384306c2479a",
             "task_sha256": "b8e6372b7cd9261f276247754a8f2f9bc8841c31344edc3116a78827d964ed0e",
             "immutable_packages_received": ["E1", "E2", "E3", "E4"],
             "original_archives": original_archives, "package_results": results,
             "source_and_summary_publication_paths": sorted(selected),
             "physical_rounds": 0, "device_calls": 0, "board_release_allowed": False,
             "root_self_review_functional_calls": 0,
             "full_features_status": "PARTIAL", "human_handoff": "WAITING_FOR_USER_FORWARD"}
    with (COORD / "INTAKE_FINAL.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"source_summary_paths": len(selected), "packages": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
