"""Thin public CSV/sample bridge to pinned PinDecoder; no D3 intake clone."""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re

from common import decoder, identity, save

COLUMNS = "cycle epoch rst_n pll_locked audio_stable pa_en frame_tick cancel req_valid req_ready req_id req_payload lane_tick lane lane_req_id result_valid result_ready result_id left right clipped commit commit_id commit_left commit_right commit_clipped bclk ws din".split()
BITS = "rst_n pll_locked audio_stable pa_en frame_tick cancel req_valid req_ready lane_tick result_valid result_ready clipped commit commit_clipped bclk ws din".split()
HEX = {"req_id": 8, "req_payload": 16, "lane_req_id": 8, "result_id": 8, "commit_id": 8}
PCM = "left right commit_left commit_right".split()
BASIS = {"source_sha256", "rom_sha256", "input_sha256"}


class Refusal(ValueError):
    def __init__(self, code, line=None, cycle=None, epoch=None, request_id=None, expected=None, actual=None):
        self.detail = dict(code=code, csv_line=line, cycle=cycle, epoch=epoch,
                           request_id=request_id, expected=expected, actual=actual)
        super().__init__(json.dumps(self.detail))


def need(ok, code, row=None, expected=None, actual=None):
    if not ok:
        location = [row.get(k) for k in ("csv_line", "cycle", "epoch", "request_id")] if row else [None] * 4
        raise Refusal(code, *location, expected=expected, actual=actual)


def integer(value, label, minimum=0, maximum=None):
    need(type(value) is int and value >= minimum and (maximum is None or value <= maximum), "INTEGER_" + label)


def read_csv(path):
    rows = []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == COLUMNS, "CSV_PUBLIC_FIELDS", expected=COLUMNS, actual=reader.fieldnames)
        for raw in reader:
            row = {"csv_line": reader.line_num}
            need(None not in raw and all(v is not None for v in raw.values()), "CSV_ROW_WIDTH", row)
            for name, value in raw.items():
                if name in HEX:
                    need(re.fullmatch("[0-9a-fA-F]{" + str(HEX[name]) + "}", value) is not None,
                         "CSV_UNKNOWN_OR_HEX_" + name, row)
                    row[name] = int(value, 16)
                else:
                    need(re.fullmatch(r"-?(0|[1-9][0-9]*)", value) is not None, "CSV_UNKNOWN_OR_INTEGER_" + name, row)
                    row[name] = int(value)
            need(row["cycle"] == len(rows) + 1, "CSV_CYCLE_SEQUENCE", row, len(rows) + 1, row["cycle"])
            need(all(row[k] in (0, 1) for k in BITS), "CSV_BIT_RANGE", row)
            need(all(-(1 << 23) <= row[k] < (1 << 23) for k in PCM), "CSV_PCM24_RANGE", row)
            need(row["epoch"] >= 0 and row["lane"] in range(4), "CSV_EPOCH_LANE", row)
            rows.append(row)
    need(bool(rows), "CSV_EMPTY")
    return rows


def verify(paths, binding_sha, output):
    legacy = decoder()
    parse = legacy.parse_json
    frozen = {role: identity(p) for role, p in paths.items()}
    need(frozen["binding"]["sha256"] == binding_sha, "BINDING_SHA")
    binding = parse(paths["binding"].read_text(encoding="utf-8"))
    need(binding["schema"] == "B2_PUBLIC_SERIAL_ADAPTER_BINDING_V1", "BINDING_SCHEMA")
    need(binding["provenance"] in ("SYNTHETIC_ADAPTER_TEST", "B1_DECLARED_PENDING_M2"), "PROVENANCE")
    need(binding["clock_hz"] == 40000000 and type(binding["clock_hz"]) is int
         and binding["sampling_phase"] == "SYS_POSEDGE_PRE_NBA" and binding["request_domain"] == "frame_transaction",
         "CLOCK_PHASE_OR_ID_DOMAIN")
    need(binding.get("unused_fields_policy") == "ALL_COLUMNS_KNOWN_FAIL_CLOSED", "CSV_UNUSED_FIELD_POLICY")
    basis = binding["basis"]
    need(set(basis) == BASIS and all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v) for v in basis.values()), "BASIS_FORMAT")
    # Only bridge input hashes and declared B1/M1 basis equality live here.
    # Source/ROM file admission belongs to B1; no new generic artifact intake.
    for role in ("csv", "samples", "calendar", "oracle"):
        need(frozen[role]["sha256"] == binding["inputs_sha256"][role], "INPUT_SHA_" + role)
    samples_doc, calendar, oracle = [parse(paths[r].read_text(encoding="utf-8")) for r in ("samples", "calendar", "oracle")]
    for document in (samples_doc, calendar, oracle):
        need(document["basis"] == basis, "SOURCE_ROM_INPUT_BASIS_MISMATCH")
    need(samples_doc["schema"] == "B2_PUBLIC_TX_SAMPLES_V1" and calendar["schema"] == "B2_FRAME_LEDGER_V1"
         and oracle["schema"] == "B2_EXTERNAL_PCM_ORACLE_V1", "BRIDGE_INPUT_SCHEMA")
    rows = read_csv(paths["csv"])
    need(binding["capture_end_cycle"] == rows[-1]["cycle"], "DECLARED_WINDOW_END", rows[-1])
    by_cycle = {r["cycle"]: r for r in rows}
    samples = {}
    for s in samples_doc["samples"]:
        need(set(s) == {"cycle", "epoch", "frame_id", "identity_valid", "request_id", "left", "right", "clipped"}, "PUBLIC_SAMPLE_FIELDS")
        for name in ("cycle", "epoch", "frame_id", "identity_valid", "clipped"):
            integer(s[name], name)
        need(s["identity_valid"] in (0, 1) and s["clipped"] in (0, 1), "SAMPLE_BIT_RANGE")
        need(s["cycle"] not in samples and s["cycle"] in by_cycle, "SAMPLE_DUPLICATE_OR_OUTSIDE_CAPTURE")
        samples[s["cycle"]] = s
    golden = {}
    for item in oracle["records"]:
        need(set(item) == {"epoch", "request_id", "left", "right", "clipped"}, "EXTERNAL_ORACLE_FIELDS")
        integer(item["epoch"], "gold_epoch")
        integer(item["request_id"], "gold_id", maximum=0xFFFFFFFF)
        k = item["epoch"], item["request_id"]
        need(k not in golden and type(item["clipped"]) is int and item["clipped"] in (0, 1), "GOLD_ID_OR_CLIP")
        legacy.quantize(item["left"]); legacy.quantize(item["right"])
        golden[k] = item
    expected = {}
    for item in calendar["requests"]:
        need(set(item) == {"epoch", "request_id", "accept_cycle", "commit_cycle", "cancel_cycle"}, "FRAME_LEDGER_FIELDS")
        integer(item["epoch"], "ledger_epoch")
        integer(item["request_id"], "ledger_id", maximum=0xFFFFFFFF)
        integer(item["accept_cycle"], "accept_cycle", minimum=1)
        need((item["commit_cycle"] is None) != (item["cancel_cycle"] is None), "LEDGER_DISPOSITION")
        finish = item["commit_cycle"] if item["commit_cycle"] is not None else item["cancel_cycle"]
        integer(finish, "cleanup_cycle", minimum=item["accept_cycle"])
        need(finish - item["accept_cycle"] < 833, "SERVICE_DEADLINE", expected="<833", actual=finish - item["accept_cycle"])
        k = item["epoch"], item["request_id"]
        need(k not in expected and (item["commit_cycle"] is None or k in golden), "LEDGER_ID_OR_MISSING_GOLD")
        expected[k] = item
    frame_cycles = defaultdict(list)
    for r in rows:
        if r["rst_n"] and r["frame_tick"]:
            frame_cycles[r["epoch"]].append(r["cycle"])
    for key, item in expected.items():
        cycles = frame_cycles[key[0]]
        n = bisect_right(cycles, item["accept_cycle"])
        if n < len(cycles):
            finish = item["commit_cycle"] if item["commit_cycle"] is not None else item["cancel_cycle"]
            need(finish < cycles[n], "NEXT_TRUE_FRAME_DEADLINE", expected=cycles[n], actual=finish)
    ledger = {}
    pins = legacy.PinDecoder(ledger)
    accepted, committed, canceled = set(), set(), set()
    active_key = None
    sample_used = set()
    previous_rst = None
    observed_epoch = -1
    previous_frame = {}
    row_map = []
    frame_counts = Counter()
    for r in rows:
        c, e = r["cycle"], r["epoch"]
        if not r["rst_n"] and previous_rst != 0:
            observed_epoch += 1
        need(e == observed_epoch and observed_epoch >= 0, "CSV_RESET_EPOCH", r)
        previous_rst = r["rst_n"]
        if not r["rst_n"]:
            need(not any(r[k] for k in ("bclk", "ws", "din", "pa_en")), "RESET_SERIAL_NOT_SILENT", r)
            if active_key is not None:
                need(expected[active_key]["cancel_cycle"] == c, "RESET_ACTIVE_NOT_DECLARED", r)
                canceled.add(active_key)
                active_key = None
        if r["cancel"]:
            need(not r["commit"], "COMMIT_ON_CANCEL", r)
            if active_key is not None:
                need(expected[active_key]["cancel_cycle"] == c, "UNEXPECTED_CANCEL",
                     {**r, "request_id": active_key[1]})
                canceled.add(active_key)
                active_key = None
        if r["req_valid"] and r["req_ready"] and not r["cancel"] and r["rst_n"]:
            k = e, r["req_id"]
            need(active_key is None and k in expected and k not in accepted and c == expected[k]["accept_cycle"], "CSV_ACCEPT_ID_OR_CYCLE", r)
            accepted.add(k)
            active_key = k
            ledger[k] = {"epoch": e, "request_id": k[1], "request_cycle": c, "accept_csv_line": r["csv_line"]}
        if r["commit"]:
            k = e, r["commit_id"]
            need(k == active_key and k in accepted and k not in committed and k not in canceled
                 and c == expected[k]["commit_cycle"], "CSV_COMMIT_ID_OR_CYCLE", r)
            value = golden[k]
            need((r["commit_left"], r["commit_right"], r["commit_clipped"]) == (value["left"], value["right"], value["clipped"]),
                 "COMMIT_EXTERNAL_PCM_OR_CLIP", r)
            committed.add(k)
            active_key = None
            ledger[k].update(commit_cycle=c, commit_csv_line=r["csv_line"])
        try:
            pins.observe(r)
        except ValueError as exc:
            serial_id = pins.word_sample["id"] if pins.word_sample else None
            raise Refusal("PIN_" + str(exc), r["csv_line"], c, e, serial_id) from exc
        if r["rst_n"] and r["frame_tick"]:
            need(c in samples, "MISSING_PUBLIC_TX_SAMPLE", r)
            s = samples[c]
            diagnostic_row = {**r, "request_id": s["request_id"]}
            need(s["epoch"] == e, "PUBLIC_SAMPLE_EPOCH", r)
            last = previous_frame.get(e)
            need(last is None or s["frame_id"] == last["frame_id"] + 1, "PUBLIC_SAMPLE_FRAME_ID", r)
            if last is not None:
                need(c - last["cycle"] in (833, 834), "FRAME_CADENCE", r)
            previous_frame[e] = s
            sample_used.add(c)
            frame_counts[e] += 1
            legacy.quantize(s["left"]); legacy.quantize(s["right"])
            if s["identity_valid"]:
                integer(s["request_id"], "sample_id", maximum=0xFFFFFFFF)
                k = e, s["request_id"]
                need(k in committed and k not in canceled and expected[k]["commit_cycle"] < c,
                     "PUBLIC_SAMPLE_ID_NOT_COMMITTED", diagnostic_row)
                value = golden[k]
                need((s["left"], s["right"], s["clipped"]) == (value["left"], value["right"], value["clipped"]),
                     "SAMPLE_EXTERNAL_PCM_OR_CLIP", r)
                ledger[k].setdefault("sample_cycle", c)
                ledger[k].setdefault("sample_csv_line", r["csv_line"])
                sid = s["request_id"]
            else:
                need(s["request_id"] is None and s["left"] == s["right"] == s["clipped"] == 0, "STARTUP_SAMPLE_IDENTITY", r)
                sid = None
            # This is the independently OBSERVED selected TX PCM, never the
            # last result/commit inferred by this bridge. Original pre-NBA order.
            pins.current_sample = {"cycle": c, "epoch": e, "left": s["left"], "right": s["right"],
                                   "id": sid, "frame": s["frame_id"]}
        row_map.append({"csv_line": r["csv_line"], "cycle": c, "epoch": e,
                        "req_id": r["req_id"], "result_id": r["result_id"], "commit_id": r["commit_id"]})
    need(accepted == set(expected), "MISSING_EXPECTED_ACCEPT")
    need(committed == {k for k, v in expected.items() if v["commit_cycle"] is not None}, "MISSING_EXPECTED_COMMIT")
    need(canceled == {k for k, v in expected.items() if v["cancel_cycle"] is not None} and active_key is None,
         "MISSING_EXPECTED_CANCEL_OR_UNCLOSED")
    for k, item in expected.items():
        if item["cancel_cycle"] is not None:
            r = by_cycle.get(item["cancel_cycle"])
            need(r is not None and ((r["cancel"] and r["epoch"] == k[0])
                 or (not r["rst_n"] and r["epoch"] == k[0] + 1)), "MISSING_PUBLIC_CANCEL_OR_RESET", r)
    need(sample_used == set(samples), "SAMPLE_NOT_ON_FRAME")
    for e, times in frame_cycles.items():
        need(all(abs(3 * (t - times[0]) - 2500 * i) <= 3 for i, t in enumerate(times)), "FRAME_MEAN_RATIO")
    need(any(f["request_id"] is not None for f in pins.frames), "NO_COMPLETE_REQUEST_STEREO")
    for k, entry in ledger.items():
        complete = "serial_last_data_cycle" in entry
        later_reset = next((r for r in rows if r["epoch"] > k[0] and not r["rst_n"]), None)
        entry["serial_disposition"] = ("COMPLETE" if complete else
            "CANCELLED_BEFORE_COMMIT" if expected[k]["commit_cycle"] is None else
            "RESET_BEFORE_SERIAL_COMPLETE" if later_reset else "UNKNOWN_OBSERVATION_TAIL")
    need(frozen == {role: identity(p) for role, p in paths.items()}, "INPUT_CHANGED")
    save(output / "ROW_MAP.json", row_map)
    save(output / "SERIAL_FRAMES.json", pins.frames)
    save(output / "SERIAL_HALVES.json", pins.halves)
    return {"checks_passed": True, "status": "ADAPTER_L1_ONLY__PENDING_PRO_SOURCE_OR_TRACE", "level": "L1_NEW_ADAPTER_SELFTEST_ONLY",
            "basis": basis, "inputs": frozen, "cycles": len(rows), "frame_counts": dict(frame_counts),
            "complete_stereo": len(pins.frames), "request_ledger": list(ledger.values()),
            "serial_dispositions": dict(Counter(e["serial_disposition"] for e in ledger.values())),
            "source_file_admission": "B1_OWNED_NOT_REIMPLEMENTED_HERE", "B1_M1_real_admission": "PENDING",
            "window_completeness": "DECLARED_WINDOW_ONLY_NO_MONITOR_END_FINISH_CLAIM",
            "pro_dut_pass": False, "PCM_algorithm_pass": False, "physical_48k_PT8211_pass": False, "board_release_allowed": False}


def main():
    ap = argparse.ArgumentParser()
    for role in ("binding", "csv", "samples", "calendar", "oracle", "output"):
        ap.add_argument("--" + role, required=True, type=Path)
    ap.add_argument("--sha256", required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        result = verify({r: getattr(args, r) for r in ("binding", "csv", "samples", "calendar", "oracle")}, args.sha256, args.output)
        code = 0
    except (Refusal, ValueError, TypeError, KeyError, OSError) as exc:
        result = {"checks_passed": False, "first_difference": exc.detail if isinstance(exc, Refusal) else {"code": str(exc)},
                  "pro_dut_pass": False, "board_release_allowed": False}
        code = 1
    save(args.output / "RESULT.json", result)
    print(json.dumps({"checks_passed": result["checks_passed"], "first_difference": result.get("first_difference")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
