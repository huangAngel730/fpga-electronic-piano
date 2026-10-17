"""Only new CSV-bridge cases; reuse producer code, never run old test suites."""
import argparse
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from common import HERE, MONITOR, OLD, ROOT, identity, module, save


def write_csv(path, rows, columns):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: (f"{row[name]:0{8 if name != 'req_payload' else 16}x}" if name in
                             ("req_id", "req_payload", "lane_req_id", "result_id", "commit_id") else row[name]) for name in columns})


def build_base(out):
    out.mkdir()
    # Fresh 12k-cycle transport fixture, not the old38k test or monitor suite.
    producer = module("b2_readonly_fixture_producer", OLD / "fixture.py")
    from adapt_serial import COLUMNS
    vectors = [{"left": 256, "right": -512, "dac_left": 1, "dac_right": -2},
               {"left": -1234567, "right": 654321, "dac_left": -4823, "dac_right": 2556},
               {"left": 128, "right": -129, "dac_left": 1, "dac_right": -1},
               {"left": 8388607, "right": -8388608, "dac_left": 32767, "dac_right": -32768}] * 4
    plan = {"cycles": 12000, "fixture_stable_wait_cycles": 8, "fixture_commit_delay_cycles": 32,
            "vectors": vectors, "epochs": [
                {"epoch": 0, "reset_start": 1, "active_start": 5, "stable_start": 5, "end": 6000},
                {"epoch": 1, "reset_start": 6001, "active_start": 6005, "stable_start": 6005, "end": 12000}]}
    save(out / "NEW_SYNTHETIC_INPUT_PLAN.json", plan)
    source_sha = identity(OLD / "fixture.py")["sha256"]
    basis = {"source_sha256": source_sha, "rom_sha256": hashlib.sha256(json.dumps(vectors).encode()).hexdigest(),
             "input_sha256": identity(out / "NEW_SYNTHETIC_INPUT_PLAN.json")["sha256"]}
    mapping = lambda n: 0xFFFFFFFF if n == 1 else 0 if n == 2 else n + 14
    calendar, gold = [], []
    accept_by_cycle, lane_by_cycle = {}, {}
    for e in plan["epochs"]:
        n = 1
        while True:
            c = e["active_start"] - 1 + (n * 128 * (1 << 32) + producer.STEP - 1) // producer.STEP
            if c + 32 > e["end"]:
                break
            sid = mapping(n)
            entry = {"epoch": e["epoch"], "request_id": sid, "accept_cycle": c + 1,
                     "commit_cycle": c + 32, "cancel_cycle": None}
            calendar.append(entry)
            value = vectors[(n - 1) % 16]
            gold.append({"epoch": e["epoch"], "request_id": sid, "left": value["left"], "right": value["right"], "clipped": 0})
            accept_by_cycle[c + 1] = sid
            for lane in range(4):
                lane_by_cycle[c + 2 + lane] = (lane, sid)
            n += 1
    samples = []
    frame_counter = {0: 0, 1: 0}

    def csv_rows(fault=None):
        result = []
        for tick in producer.records(plan, fault):
            if tick["kind"] != "TICK":
                continue
            c, e = tick["cycle"], tick["epoch"]
            sid = mapping(tick["request_id"]) if tick["request_id"] else 0
            row = dict.fromkeys(COLUMNS, 0)
            row.update(cycle=c, epoch=e, rst_n=tick["rst_n"], pll_locked=tick["clock_stable"],
                       audio_stable=tick["clock_stable"], pa_en=tick["pa_en"], frame_tick=tick["frame_tick"],
                       req_valid=tick["request"], req_ready=tick["request"], req_id=sid, req_payload=sid,
                       result_valid=tick["commit"], result_ready=tick["commit"], result_id=sid,
                       left=tick["left"], right=tick["right"], commit=tick["commit"], commit_id=sid,
                       commit_left=tick["left"], commit_right=tick["right"],
                       bclk=tick["bclk"], ws=tick["ws"], din=tick["din"])
            if c in lane_by_cycle:
                row.update(lane_tick=1, lane=lane_by_cycle[c][0], lane_req_id=lane_by_cycle[c][1])
            if fault is None and tick["frame_tick"]:
                valid = int(tick["play_id"] != 0)
                samples.append({"cycle": c, "epoch": e, "frame_id": frame_counter[e], "identity_valid": valid,
                                "request_id": mapping(tick["play_id"]) if valid else None,
                                "left": tick["play_left"], "right": tick["play_right"], "clipped": 0})
                frame_counter[e] += 1
            result.append(row)
        return result

    rows = csv_rows()
    write_csv(out / "PUBLIC.csv", rows, COLUMNS)
    write_csv(out / "CHANNEL_SWAPPED_PUBLIC.csv", csv_rows("left_right_swap"), COLUMNS)
    save(out / "SAMPLES.json", {"schema": "B2_PUBLIC_TX_SAMPLES_V1", "basis": basis, "samples": samples})
    save(out / "CALENDAR.json", {"schema": "B2_FRAME_LEDGER_V1", "basis": basis, "requests": calendar})
    save(out / "ORACLE.json", {"schema": "B2_EXTERNAL_PCM_ORACLE_V1", "basis": basis,
                                "origin": "SYNTHETIC_HAND_VECTOR_ADAPTER_TEST_NOT_M1", "records": gold})
    binding = {"schema": "B2_PUBLIC_SERIAL_ADAPTER_BINDING_V1", "provenance": "SYNTHETIC_ADAPTER_TEST",
               "clock_hz": 40000000, "sampling_phase": "SYS_POSEDGE_PRE_NBA", "request_domain": "frame_transaction",
               "basis": basis, "capture_end_cycle": 12000,
               "source_admission": "SYNTHETIC_NO_PRO_SOURCE_OR_ROM", "inputs_sha256": {}}
    paths = {"csv": out / "PUBLIC.csv", "samples": out / "SAMPLES.json", "calendar": out / "CALENDAR.json", "oracle": out / "ORACLE.json"}
    return binding, paths, rows, samples, calendar, gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--start-case", default="positive")
    ap.add_argument("--reuse-base", type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.reuse_base:
        base = args.reuse_base
        binding = json.loads((base.parent / "positive/BINDING.json").read_text(encoding="utf-8"))
        paths = {"csv": base / "PUBLIC.csv", "samples": base / "SAMPLES.json", "calendar": base / "CALENDAR.json", "oracle": base / "ORACLE.json"}
        rows = []
        from adapt_serial import read_csv
        rows = read_csv(paths["csv"])
        samples = json.loads(paths["samples"].read_text(encoding="utf-8"))["samples"]
        calendar = json.loads(paths["calendar"].read_text(encoding="utf-8"))["requests"]
        gold = json.loads(paths["oracle"].read_text(encoding="utf-8"))["records"]
    else:
        base = args.output / "base"
        binding, paths, rows, samples, calendar, gold = build_base(base)
    cases = [("positive", None), ("wrong_csv_sha", "INPUT_SHA_csv"),
             ("wrong_source_basis", "SOURCE_ROM_INPUT_BASIS_MISMATCH"),
             ("missing_bclk", "CSV_PUBLIC_FIELDS"), ("missing_ws_edges", "PIN_FRAME_WS_BOUNDARY_PHASE"),
             ("missing_public_samples", "MISSING_PUBLIC_TX_SAMPLE"), ("missing_sample_pcm", "PUBLIC_SAMPLE_FIELDS"),
             ("wrong_sample_id", "PUBLIC_SAMPLE_ID_NOT_COMMITTED"), ("wrong_sample_epoch", "PUBLIC_SAMPLE_EPOCH"),
             ("wrong_sample_pcm", "SAMPLE_EXTERNAL_PCM_OR_CLIP"), ("physical_channels_swapped", "PIN_SERIAL_PCM_OR_CHANNEL_MISMATCH"),
             ("overdue_commit", "SERVICE_DEADLINE"), ("csv_cycle_gap", "CSV_CYCLE_SEQUENCE"),
             ("wrong_sample_clip", "SAMPLE_EXTERNAL_PCM_OR_CLIP"), ("old_monitor_zero_pins", "PIN_BCLK_STALLED_OR_MISSING_EDGE"),
             ("wrong_binding_sha", "BINDING_SHA"), ("lane_id_domain", "CLOCK_PHASE_OR_ID_DOMAIN"),
             ("wrong_commit_pcm", "COMMIT_EXTERNAL_PCM_OR_CLIP"), ("reset_serial_nonzero", "RESET_SERIAL_NOT_SILENT")]
    start = [c[0] for c in cases].index(args.start_case)
    results = []
    from adapt_serial import COLUMNS
    for name, diagnostic in cases[start:]:
        folder = args.output / name
        folder.mkdir()
        selected = dict(paths)
        b = deepcopy(binding)
        if name in ("missing_bclk", "missing_ws_edges", "csv_cycle_gap", "wrong_commit_pcm", "reset_serial_nonzero"):
            modified = deepcopy(rows)
            cols = list(COLUMNS)
            if name == "missing_bclk":
                cols.remove("bclk")
            elif name == "missing_ws_edges":
                for r in modified:
                    r["ws"] = 0
            elif name == "csv_cycle_gap":
                modified.pop(100)
            elif name == "wrong_commit_pcm":
                next(r for r in modified if r["commit"])["commit_left"] += 256
            else:
                modified[0]["din"] = 1
            selected["csv"] = folder / "PUBLIC.csv"
            write_csv(selected["csv"], modified, cols)
        elif name == "physical_channels_swapped":
            selected["csv"] = base / "CHANNEL_SWAPPED_PUBLIC.csv"
        elif name == "old_monitor_zero_pins":
            selected["csv"] = MONITOR / "ROUND_02/case_00.csv"
            b["capture_end_cycle"] = 5062
            for role, schema, key in (("samples", "B2_PUBLIC_TX_SAMPLES_V1", "samples"),
                                      ("calendar", "B2_FRAME_LEDGER_V1", "requests"),
                                      ("oracle", "B2_EXTERNAL_PCM_ORACLE_V1", "records")):
                selected[role] = folder / (role + ".json")
                save(selected[role], {"schema": schema, "basis": b["basis"], key: []})
        if name in ("missing_public_samples", "missing_sample_pcm", "wrong_sample_id", "wrong_sample_epoch", "wrong_sample_pcm", "wrong_sample_clip"):
            doc = json.loads(paths["samples"].read_text(encoding="utf-8"))
            s = next(s for s in doc["samples"] if s["identity_valid"])
            if name == "missing_public_samples":
                doc["samples"] = []
            elif name == "missing_sample_pcm":
                del s["left"]
            elif name == "wrong_sample_id":
                s["request_id"] = 42
            elif name == "wrong_sample_epoch":
                s["epoch"] += 1
            elif name == "wrong_sample_pcm":
                s["left"], s["right"] = s["right"], s["left"]
            else:
                s["clipped"] = 1
            selected["samples"] = folder / "SAMPLES.json"
            save(selected["samples"], doc)
        if name == "wrong_source_basis":
            doc = json.loads(paths["oracle"].read_text(encoding="utf-8"))
            doc["basis"]["source_sha256"] = "0" * 64
            selected["oracle"] = folder / "ORACLE.json"
            save(selected["oracle"], doc)
        if name == "overdue_commit":
            doc = json.loads(paths["calendar"].read_text(encoding="utf-8"))
            doc["requests"][0]["commit_cycle"] = doc["requests"][0]["accept_cycle"] + 833
            selected["calendar"] = folder / "CALENDAR.json"
            save(selected["calendar"], doc)
        if name == "lane_id_domain":
            b["request_domain"] = "lane_transaction"
        b["inputs_sha256"] = {role: identity(p)["sha256"] for role, p in selected.items()}
        if name == "wrong_csv_sha":
            b["inputs_sha256"]["csv"] = "0" * 64
        binding_path = folder / "BINDING.json"
        save(binding_path, b)
        sha = "0" * 64 if name == "wrong_binding_sha" else identity(binding_path)["sha256"]
        save(folder / "EXPECTED.json", {"expected_exit": 0 if diagnostic is None else 1, "first_difference": diagnostic,
             "scope": "NEW_CSV_ADAPTER_TEST_ONLY", "all_Pro_board_claims": False})
        argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "adapt_serial.py"), "--binding", str(binding_path), "--sha256", sha]
        for role, path in selected.items():
            argv += ["--" + role, str(path)]
        argv += ["--output", str(folder / "checked")]
        begin = time.monotonic()
        with (folder / "stdout.bin").open("xb") as stdout, (folder / "stderr.bin").open("xb") as stderr:
            call = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=90, check=False)
        result_file = folder / "checked/RESULT.json"
        result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.is_file() else {}
        actual = result.get("first_difference", {}).get("code")
        passed = call.returncode == (0 if diagnostic is None else 1) and actual == diagnostic
        if name == "positive" and passed:
            zero_ids = [r for r in result["request_ledger"] if r["request_id"] == 0 and r["serial_disposition"] == "COMPLETE"]
            passed = len(zero_ids) == 2 and result["cycles"] == 12000 and result["pro_dut_pass"] is False
        item = {"case": name, "argv": argv, "cwd": str(ROOT), "exit_code": call.returncode,
                "seconds": time.monotonic() - begin, "expected_diagnostic": diagnostic, "actual_diagnostic": actual,
                "passed": passed, "inputs": {role: identity(path) for role, path in selected.items()},
                "binding": identity(binding_path), "result": identity(result_file) if result_file.is_file() else None,
                "stdout": identity(folder / "stdout.bin"), "stderr": identity(folder / "stderr.bin")}
        save(folder / "CASE_RECEIPT.json", item)
        results.append(item)
        if not passed:
            break
    save(args.output / "RESULTS.json", results)
    passed = len(results) == len(cases[start:]) and all(r["passed"] for r in results)
    print(json.dumps({"passed": passed, "new_cases": len(results), "earlier_cases_not_reexecuted": start,
                      "old_selftests_reexecuted": 0, "first_failure": next((r["case"] for r in results if not r["passed"]), None)}))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
