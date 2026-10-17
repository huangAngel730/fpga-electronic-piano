"""Read-only identity inventory for task-day B1, with E2/E3 dependencies.

This does not build a project, evaluate PCM, or admit a Pro DUT. Only the
intake documentation directory is writable. Missing inputs are observations,
not an invitation to infer their identity from a similarly named candidate.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016"
OUT = DOC / "pro_binding_20261017/intake_20261017"
E2 = ROOT / "code/docs/test/m3_pro_waveform_successor_20261017"
E3 = ROOT / "code/docs/test/m3_pro_min_transfer_successor_20261017"
TASK = Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/task-day")


def identity(path):
    """Return raw-byte identity; absent files never receive an inferred hash."""
    path = Path(path)
    value = {"path": str(path), "present": path.is_file()}
    if value["present"]:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        value.update(bytes=path.stat().st_size, sha256=digest.hexdigest())
    return value


def compare(actual, expected):
    if not actual["present"]:
        return "MISSING_FILE"
    if actual["sha256"] != expected["sha256"]:
        return "SHA_MISMATCH"
    if "bytes" in expected and actual["bytes"] != expected["bytes"]:
        return "SIZE_MISMATCH"
    return "MATCH"


def walk_links(value):
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            yield value
        for item in value.values():
            yield from walk_links(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_links(item)


def dump(name, value):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    if ROOT.name != "fpga-electronic-piano" or not (ROOT / "AGENTS.md").is_file():
        raise RuntimeError("Unexpected repository root")
    originals = OUT / "INPUT_ORIGINALS"
    originals.mkdir(exist_ok=False)
    records, copies, citations, links, archives = [], [], [], [], []
    specs = []

    def add(path, kind, pattern=None):
        specs.append((Path(path), kind, pattern))

    for name in ("M3_当日任务单_2026-10-17.md", "M3_完赛任务单_2026-10-15.md"):
        add(TASK / name, "USER_TASK_ORIGINAL")
    add(OUT.parent / "coordinator_20261017/DAY_PLAN.md", "COORDINATOR_PLAN")
    add(OUT.parent / "coordinator_20261017/USER_COMMUNICATION_AUTH.md", "AUTH_EVIDENCE")
    for group in ("C", "D"):
        for name in ("RESULT.md", "LATEST_RECEIPT.json", "NIGHT_RUN_RECEIPT.json"):
            add(DOC / group / name, "TOY_DIAGNOSTIC_FIXTURE")
    for name in ("CALENDAR_CONTRACT.json", "CALENDAR.json", "CALENDAR.jsonl",
                 "SOURCE_REFRESH_01/SOURCE_REFRESH.json"):
        add(DOC / "C" / name, "TOY_DIAGNOSTIC_FIXTURE")
    monitor = DOC / "D/pro_monitor_20261017"
    for name in ("RESULT.md", "CONTRACT.md", "INPUT_IDENTITIES.json",
                 "HANDOFF_FINAL/HANDOFF_RECEIPT.json", "DELIVERY/RECEIPT.json",
                 "ROUND_02/RECEIPT.json", "ROUND_02/case_00.csv"):
        add(monitor / name, "PASSIVE_MONITOR_SELFTEST_ONLY")
    for name in ("README.md", "RESULT.json", "INPUT_IDENTITY.json",
                 "PRO_INTEGRATION_DELTA.md", "MANIFEST.json", "PACKAGE_STATUS.json",
                 "normal_capture.original.txt", "catalogue.mem", "golden.mem"):
        add(E2 / name, "HISTORICAL_PCM_ISOLATED_REPLAY")
    for name in ("RESULT.md", "FORMAL_INTEGRATION_GAPS.md", "LATEST_RECEIPT.json",
                 "NIGHT_RUN_RECEIPT.json", "RTL_PATCH_PROVENANCE.json", "ROUND_06/delta/RESULT.json"):
        add(E3 / name, "REAL_MIDI_ISOLATED_UART_RAM")
    add(ROOT / "code/software/score_midi_real_input_acceptance_20261015/inputs/MIDI_sample_2018-03-21.mid",
        "REAL_MIDI_FILE_NOT_PRO_TRACE")
    add(E3 / "ROUND_05/inputs/records.bin", "ENCODED_RECORDS_NOT_PRO_TRACE")
    sources = {
        "code/rtl/board/electronic_piano_top.sv":
            ("EXISTING_SHARED_TOP_NOT_NEW_PRO_BINDING", r"u_i2s_tx|buffered_left|buffered_right|frame_tick|pa_en"),
        "code/rtl/audio_out/i2s_tx.sv":
            ("EXISTING_SENDER_NOT_PRO_BINDING", r"frame_start|frame_tick|next_left|next_right|left_latch|right_latch"),
        "code/rtl/common/pcm_waveform_observer_candidate/pcm_frame_observer.sv":
            ("READ_ONLY_OBSERVER_CANDIDATE", r"pre-NBA|frame_load|observed_left|observed_right"),
        "code/rtl/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017/m3_pro_fixed_left_waveform.sv":
            ("ISOLATED_E2_WRAPPER", r"frame_load|pcm_frame_observer|play_left|play_right|audio_clk|pixel_clk"),
        "code/tb/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017/tb_pro_fixed_left_waveform.sv":
            ("ISOLATED_E2_TB", r"frame_load|catalogue|HISTOR|audio_clk|pixel_clk"),
        "code/rtl/input/score_transfer_candidate/m3_pro_min_transfer_successor_20261017/score_transfer_e3_successor.sv":
            ("ISOLATED_E3_BEHAVIORAL_RAM", r"SESSION_TIMEOUT|CLK_HZ|BAUD|FRAME_TIMEOUT|module |uart_rx_i|uart_tx_o"),
        "code/tb/input/score_transfer_candidate/m3_pro_min_transfer_successor_20261017/tb_e3_file_uart.sv":
            ("ISOLATED_E3_50MS_TB", r"SESSION_TIMEOUT|CLK_HZ|BAUD|FRAME_TIMEOUT"),
        "code/tb/board/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/pro_frame_monitor.sv":
            ("PASSIVE_MONITOR_NOT_PRO_DUT", r"module |frame_tick|commit|bclk|ws|din|req_payload"),
        "code/docs/test/m1_r05_pcm_oracle_20261016/REFERENCE_CONTRACT.json":
            ("OLD_M1_REFERENCE_NOT_PRO_GOLDEN", r"lane|snapshot|NBA|source|ROM|rom"),
        "code/model/m1_r05_pcm_oracle_20261016/DEPENDENCIES.json":
            ("OLD_M1_DEPENDENCIES_NOT_PRO_BINDING", None),
        "code/rtl/138K_Pro/tang_mega_138k-pro_pins.cst":
            ("PRO_PIN_REFERENCE_NOT_ENGINE", None),
    }
    for path, (kind, pattern) in sources.items():
        add(ROOT / path, kind, pattern)
    for name in ("piano_band_4x256_8191.mem", "triangle_wavetable.hex", "velocity_gain_rom.mem"):
        add(ROOT / "code/model/m1_r05_pcm_oracle_20261016/frozen/rom" / name,
            "OLD_R06_ROM_NOT_NEW_PRO_BINDING")

    linked_seen = set()
    archive_seen = set()
    for index, (path, kind, pattern) in enumerate(specs):
        item = identity(path)
        item.update(classification=kind, accepted_as_new_pro=False)
        records.append(item)
        if not item["present"]:
            continue
        destination = originals / f"{index:03d}_{path.name}"
        shutil.copyfile(path, destination)
        assert compare(identity(destination), item) == "MATCH"
        copies.append({"original": item, "copy": identity(destination)})
        if pattern:
            matches = [{"line": n, "text": line} for n, line in enumerate(
                path.read_text(encoding="utf-8-sig").splitlines(), 1)
                if re.search(pattern, line)]
            citations.append({"source": item, "pattern": pattern, "matches": matches})
        if path.suffix == ".json" and (path.name in {
                "LATEST_RECEIPT.json", "HANDOFF_RECEIPT.json", "RECEIPT.json", "PACKAGE_STATUS.json"}
                or path == E3 / "NIGHT_RUN_RECEIPT.json"):
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if path.name == "PACKAGE_STATUS.json":
                value = {"archive": {"path": value["package"], "bytes": value["bytes"], "sha256": value["sha256"]},
                         "manifest": {"path": str(E2 / "MANIFEST.json"), "sha256": value["manifest_sha256"]}}
            elif path == E3 / "NIGHT_RUN_RECEIPT.json":
                value = {key: value[key] for key in ("real_midi", "records", "source")}
            for link in walk_links(value):
                target = Path(link["path"])
                if not target.is_absolute():
                    target = ROOT / target
                key = (str(target), link["sha256"])
                if key in linked_seen:
                    continue
                linked_seen.add(key)
                actual = identity(target)
                links.append({"receipt": str(path), "expected": link,
                              "actual": actual, "result": compare(actual, link)})
                if actual["present"] and target.suffix == ".zip" and str(target) not in archive_seen:
                    archive_seen.add(str(target))
                    with zipfile.ZipFile(target) as archive:
                        bad = archive.testzip()
                        archives.append({"identity": actual, "members": len(archive.infolist()),
                                         "crc": "PASS" if bad is None else "FAIL", "bad_member": bad})
                    archive_copy = originals / f"archive_{len(archives):02d}_{target.name}"
                    shutil.copyfile(target, archive_copy)
                    assert compare(identity(archive_copy), actual) == "MATCH"
                    copies.append({"original": actual, "copy": identity(archive_copy)})

    # E2's archive is a direct original rather than a LATEST_RECEIPT link.
    direct_archive = E2 / "M3_FIXED_LEFT_WAVEFORM_ISOLATED_20261017.zip"
    if direct_archive.is_file() and str(direct_archive) not in archive_seen:
        actual = identity(direct_archive)
        with zipfile.ZipFile(direct_archive) as archive:
            bad = archive.testzip()
            archives.append({"identity": actual, "members": len(archive.infolist()),
                             "crc": "PASS" if bad is None else "FAIL", "bad_member": bad})
        dst = originals / f"archive_{len(archives):02d}_{direct_archive.name}"
        shutil.copyfile(direct_archive, dst)
        assert compare(identity(dst), actual) == "MATCH"
        copies.append({"original": actual, "copy": identity(dst)})

    required = [
        "code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016",
        "code/constraints/m2_138k_pro_fourvoice_candidate_20261016",
        "code/build/138k_pro_fourvoice_candidate_20261016",
        "code/tb/board/m2_138k_pro_fourvoice_candidate_20261016",
        "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016",
        "code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016",
        "code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016",
    ]
    locations = []
    for relative in required:
        path = ROOT / relative
        files = [identity(p) for p in sorted(path.rglob("*")) if p.is_file()] if path.is_dir() else []
        locations.append({"path": relative, "directory_present": path.is_dir(), "files": files,
                          "state": "STRUCTURE_PRESENT_REQUIRES_M2_BINDING" if files else "NOT_RECEIVED_AT_EXPECTED_LOCATION"})
    pin_only = ROOT / "code/rtl/138K_Pro"
    locations.append({"path": "code/rtl/138K_Pro", "directory_present": pin_only.is_dir(),
                      "top_level_files": [identity(p) for p in sorted(pin_only.iterdir()) if p.is_file()],
                      "state": "SCHEMATICS_AND_PIN_REFERENCE_ONLY_NOT_SOURCE_ROM_TRACE"})

    sample = {"present": True, "bytes": 3, "sha256": "a" * 64}
    checks = [
        ("exact_byte_identity", compare(sample, sample) == "MATCH"),
        ("wrong_sha_rejected", compare(sample, {"sha256": "b" * 64}) == "SHA_MISMATCH"),
        ("wrong_size_rejected", compare(sample, {"sha256": "a" * 64, "bytes": 4}) == "SIZE_MISMATCH"),
        ("missing_file_rejected", compare({"present": False}, sample) == "MISSING_FILE"),
        ("isolated_and_old_never_admitted", all(not r["accepted_as_new_pro"] for r in records)),
        ("original_copies_exact", all(compare(identity(c["copy"]["path"]), c["original"]) == "MATCH" for c in copies)),
        ("archives_crc_clean", all(a["crc"] == "PASS" for a in archives)),
        ("received_receipt_links_consistent", all(link["result"] not in {"SHA_MISMATCH", "SIZE_MISMATCH"} for link in links)),
        ("sources_stable_after_audit", all(compare(identity(r["path"]), r) == "MATCH" for r in records if r["present"])),
    ]
    dump("INTAKE.json", {"schema_version": 1, "utc": datetime.now(timezone.utc).isoformat(),
                         "status": "PENDING_PRO_SOURCE_OR_TRACE", "board_release_allowed": False,
                         "scope": "Local task-day originals and named repository locations only; not a claim about other members' machines.",
                         "new_pro_binding": None, "artifacts": records, "expected_locations": locations,
                         "receipt_link_checks": links, "archive_checks": archives,
                         "old_rounds_read_only": {"C": "2/6", "D": "3/4", "monitor": "2/3", "E2": "3/6_SUCCESS_STOP", "E3": "6/6_EXHAUSTED"},
                         "missing_binding_fields": ["M2 new Pro source list and exact target/top", "ROM bytes plus SHA list", "public port mapping and reset/cancel/lane/Release semantics", "same execution public trace with cycle/epoch/request/result/PCM/serial pins", "M1 same-source PCM/clip golden", "formal UART/default-5s and display adoption integration"]})
    dump("SOURCE_LOCATIONS.json", citations)
    dump("COPY_MAP.json", copies)
    dump("SELF_CHECKS.json", [{"name": name, "pass": passed} for name, passed in checks])
    print(json.dumps({"artifacts": len(records), "copied_originals": len(copies),
                      "link_results": {key: sum(link["result"] == key for link in links) for key in sorted({link["result"] for link in links})},
                      "archives": len(archives), "checks_passed": sum(ok for _, ok in checks),
                      "checks_total": len(checks), "status": "PENDING_PRO_SOURCE_OR_TRACE"}))
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
