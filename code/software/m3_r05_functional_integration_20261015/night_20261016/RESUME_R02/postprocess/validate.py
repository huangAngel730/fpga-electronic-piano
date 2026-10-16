"""Read raw successful evidence and bind the unchanged segmented contract."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOFT = HERE.parent
sys.path.insert(0, str(SOFT.parent.parent))
from common import ROOT, DOCS, identity, write_new, json_load

spec = importlib.util.spec_from_file_location("r02_ledger", SOFT / "public_ledger.py")
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)
BASE = DOCS / "night_20261016/RESUME_R02"
RUN = BASE / "RUN_01"


def rows(path):
    return [json_load(line) for line in path.read_bytes().splitlines()]


def main():
    receipt_path = RUN / "RUN_RECEIPT.json"
    r = json_load(receipt_path.read_bytes())
    assert r["exit_code"] == 0 and r["functional_attempt_consumed"]
    assert r["status"] == "REAL_CAPTURE_TOOL_PASS_PENDING_INDEPENDENT_VALIDATION"
    assert r["source_before"] == r["source_after"]
    assert r["tool_before"] == r["tool_after"]
    assert r["source_snapshot_layout"] == "FLAT_RELATIVE_SHA_MAP_V1"
    assert set(r["source_before"]) == set(r["source_snapshot_files"])
    for key, original in r["source_before"].items():
        copied = identity(r["source_snapshot_files"][key]["path"])
        assert copied == r["source_snapshot_files"][key]
        assert (copied["bytes"], copied["sha256"]) == (original["bytes"], original["sha256"])
        assert identity(original["path"]) == original
    stage = Path(r["stage"])
    assert r["stage_before"] == r["stage_after"]
    for rel, expected in r["stage_before"].items():
        actual = identity(stage / rel)
        assert (actual["bytes"], actual["sha256"]) == (expected["bytes"], expected["sha256"])
    for c in r["version_calls"] + r["functional_calls"]:
        assert not c["timeout"] and c["elapsed_s"] <= 300
        for stream in ("stdout", "stderr"):
            assert identity(c[stream]["path"]) == c[stream]
    assert r["elapsed_s"] <= 900
    assert len(list(BASE.glob("RUN_*_CONSUMED.json"))) == 1
    for name in ("REAL_CAPTURE.jsonl", "REAL_INPUTS.jsonl", "STARTUP_CAPTURE.jsonl", "STARTUP_INPUTS.jsonl", "STARTUP_BOUNDARY_RAW.json"):
        assert identity(stage / name) == r[name]
    result = ledger.analyze((stage / "REAL_CAPTURE.jsonl").read_bytes())
    audio = rows(stage / "REAL_CAPTURE.jsonl")
    inputs = rows(stage / "REAL_INPUTS.jsonl")
    at = [a for a in audio if a["kind"] == "TICK"]
    it = [i for i in inputs if i["kind"] == "TICK"]
    assert len(at) == len(it) == result["ticks"]
    assert inputs[0] == {"kind":"HEADER", "schema":"M3_R05_INPUT_PRE_NBA_V1", "clock_hz":40000000}
    assert inputs[1] == {"kind":"INITIAL_INPUTS", "time_ns":0, "midi_rx":1, "sys_rst_n":0}
    assert inputs[-1] == {"kind":"END", "cycle":len(it)}
    schema = json_load((BASE / "STARTUP_SCHEMA.json").read_bytes())
    raw = json_load((stage / "STARTUP_BOUNDARY_RAW.json").read_bytes())
    assert set(raw) == set(schema["boundary_raw_exact_keys"])
    assert all(type(v) is int for v in raw.values())
    count = raw["startup_edges"]
    assert 0 <= count < 64 and raw["main_first_absolute_cycle"] == count + 1
    assert raw["main_first_relative_cycle"] == 1
    assert raw["main_first_time_ps"] == 12500 + count * 25000
    assert raw["main_first_time_ns"] == (raw["main_first_time_ps"] + 500) // 1000
    for n, (a, i) in enumerate(zip(at, it), 1):
        assert a["cycle"] == i["cycle"] == n and a["rst_n"] == i["rst_n"]
        assert i["time_ns"] == (raw["main_first_time_ps"] + (n - 1) * 25000 + 500) // 1000
        assert all(type(i[k]) is int and i[k] in (0, 1) for k in ("rst_n", "midi_rx", "event_valid", "event_ready", "config_valid", "config_ready"))
        assert len(i["event_data_hex"]) == 16 and all(c in "0123456789abcdefABCDEF" for c in i["event_data_hex"])
        assert type(i["active_voice_count"]) is int and 0 <= i["active_voice_count"] <= 4
    assert at[0]["epoch"] == 0 and at[0]["rst_n"] == 0
    prefixes = []
    for key, name in (("startup_capture", "STARTUP_CAPTURE.jsonl"), ("startup_inputs", "STARTUP_INPUTS.jsonl")):
        data = rows(stage / name)
        definition = schema[key]
        assert data[0] == definition["header"]
        ticks = [x for x in data if x["kind"] == "STARTUP_TICK"]
        assert len(ticks) == count and data[-1]["absolute_edges"] == count
        if key == "startup_capture":
            assert data[-1]["main_first_absolute_cycle"] == count + 1
        for n, tick in enumerate(ticks, 1):
            assert set(tick) == set(definition["binary_field_widths"]) | {"kind", "absolute_cycle", "time_ps"}
            assert tick["absolute_cycle"] == n and tick["time_ps"] == 12500 + (n - 1) * 25000
            for field, width in definition["binary_field_widths"].items():
                assert len(tick[field]) == width and all(c in "01xXzZ" for c in tick[field])
        prefixes.append(ticks)
    unknown = 0
    for a, i in zip(*prefixes):
        assert a["time_ps"] == i["time_ps"] and a["rst_n"] == i["rst_n"]
        known = all(all(c in "01" for c in row[k]) for row, key in ((a,"startup_capture"),(i,"startup_inputs")) for k in schema[key]["binary_field_widths"])
        assert not (known and a["rst_n"] == "0")
        assert not (a["rst_n"] == "1" and i["event_valid"] == i["event_ready"] == "1")
        unknown += int(not known)
    boundary = dict(raw, schema=schema["boundary_schema"], startup_unknown=True, clock_hz=40000000, clock_period_ps=25000,
        absolute_cycle_offset=count, selection_predicate="FIRST_ALL_PUBLIC_BITS_KNOWN_AND_RESET_LOW_WITHIN_64_BEFORE_BUSINESS_ACCEPT",
        source_contract=identity(BASE / "CAPTURE_INTERFACE.md"), producer_receipt=identity(receipt_path), startup_has_xz=bool(unknown), prefix_contiguous=True, early_business_accepts=0, limits=schema["limits"])
    for key, name in (("startup_capture","STARTUP_CAPTURE.jsonl"),("startup_inputs","STARTUP_INPUTS.jsonl"),("boundary_raw","STARTUP_BOUNDARY_RAW.json"),("main_capture","REAL_CAPTURE.jsonl"),("main_inputs","REAL_INPUTS.jsonl")):
        boundary[key] = identity(stage / name)
    assert set(boundary) == set(schema["boundary_post_identity_keys"])
    write_new(BASE / "STARTUP_BOUNDARY.json", boundary)
    write_new(BASE / "PUBLIC_LEDGER.json", result)
    audit = {"status":"RAW_CAPTURE_STRUCTURE_AND_SOURCE_IDENTITY_PASS", "source_files":len(r["source_before"]), "staged_inputs":len(r["stage_before"]), "raw_streams":2*(len(r["version_calls"])+len(r["functional_calls"])), "main_ticks":len(at), "startup_edges":count, "startup_unknown_edges":unknown, "main_clipped_values":sorted(set(x["clipped"] for x in at)), "raw_initial_inputs":inputs[1], "input_kinds":{k:sum(i["kind"]==k for i in inputs) for k in sorted(set(i["kind"] for i in inputs))}, "functional_groups_consumed":1,"remaining_unspent":2,"stop_at_first_success":True,"board_release_allowed":False}
    write_new(BASE / "FINAL_AUDIT.json", audit)
    ready = {"status":"REAL_CAPTURE_READY_FOR_C_INDEPENDENT_CONSUMPTION", "receipt":identity(receipt_path), "boundary":identity(BASE / "STARTUP_BOUNDARY.json"), "schema":identity(BASE / "STARTUP_SCHEMA.json"), "schema_diff":identity(BASE / "STARTUP_SCHEMA.diff"), "ledger":identity(BASE / "PUBLIC_LEDGER.json"), "audit":identity(BASE / "FINAL_AUDIT.json"), "limits":schema["limits"]}
    ready.update({key:boundary[key] for key in ("main_capture","main_inputs","startup_capture","startup_inputs","boundary_raw")})
    write_new(BASE / "CAPTURE_READY.json", ready)
    print(json.dumps(audit, ensure_ascii=False))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
