"""Freeze new representation fixtures, without running conversion or HDL."""
import copy
import json

from prepare import DOC, identity, save


def encoded(value):
    return (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")


def lines(values):
    return b"".join(encoded(value) for value in values)


def main():
    port_map = json.loads((DOC / "PORT_MAP.json").read_text(encoding="utf-8"))
    specs = port_map["raw_ports"]
    rows = []
    for cycle in range(8):
        ports = {name: "0" * spec["width"] for name, spec in specs.items()}
        ports.update(obs_core_clk="1", obs_polyphonic_valid="1",
                     obs_rst_n=str(int(cycle >= 2)), obs_pll_locked=str(int(cycle >= 2)))
        rows.append({"schema": "M3_R7A_RAW_CORE_ROW_V1", "capture_id": "SYNTHETIC_R7A",
                     "source_line": cycle + 1, "cycle": cycle, "time_ps": 12500 + 25000 * cycle,
                     "epoch": None, "epoch_reason": "BIND_FROM_INDEPENDENT_RESET_EDGES",
                     "finish": int(cycle == 7), "ports": ports})

    def values(cycle, **kwargs):
        for name, number in kwargs.items():
            width = specs[name]["width"]
            rows[cycle]["ports"][name] = format(number & ((1 << width) - 1), f"0{width}b")

    values(2, obs_frame_tick=1)
    values(3, obs_req_valid=1, obs_req_ready=1, obs_req_id=0, obs_event_valid=1,
           obs_event_ready=1, obs_event_data=(1 << 64) - 1)
    values(4, obs_result_valid=1, obs_result_ready=1, obs_result_id=0,
           obs_result_left=-(1 << 23), obs_result_right=(1 << 23) - 1, obs_result_clip_mask=2)
    values(5, obs_commit=1, obs_commit_id=0, obs_commit_left=-3, obs_commit_right=9)
    values(6, obs_tx_sample_valid=1, obs_tx_metadata_valid=1, obs_tx_req_id_valid=1,
           obs_tx_req_id=0, obs_tx_left=-3, obs_tx_right=9, obs_tx_clip_mask=2, obs_tx_clip_any=1)
    values(7, obs_tx_sample_valid=1, obs_tx_metadata_valid=0, obs_tx_req_id_valid=0,
           obs_tx_req_id=42, obs_tx_left=-3, obs_tx_right=9, obs_tx_hold=1, obs_metadata_error=1)
    resets = [
        {"schema": "M3_R7A_RESET_SNAPSHOT_V1", "capture_id": "SYNTHETIC_R7A",
         "edge_seq": 1, "time_ps": 0, "kind": "INITIAL",
         "values": {"sys_rst_n": "0", "obs_rst_n": "0", "obs_pll_locked": "0"}},
        {"schema": "M3_R7A_RESET_SNAPSHOT_V1", "capture_id": "SYNTHETIC_R7A",
         "edge_seq": 2, "time_ps": 50000, "kind": "CHANGE",
         "values": {"sys_rst_n": "1", "obs_rst_n": "1", "obs_pll_locked": "1"}},
    ]
    end = {"schema": "M3_R7A_END_V1", "capture_id": "SYNTHETIC_R7A", "plan_stop_id": "SYNTHETIC_STOP",
           "finish_cycle": 7, "time_ps": 187500, "row_count": 8, "reason": "PLANNED_WINDOW_END",
           "ledger_status": "NOT_CHECKED_R6_5_REQUIRED", "serial_tail_status": "UNKNOWN_R6_6_REQUIRED"}
    stdout = "MONITOR_END capture_id=SYNTHETIC_R7A cycle=7 time_ps=187500 rows=8 reason=PLANNED_WINDOW_END\n"
    base = {"rows": rows, "resets": resets, "end": end, "stdout": stdout,
            "origin": "SYNTHETIC_SCHEMA_FIXTURE"}
    target = DOC / "FIXTURES"
    target.mkdir(exist_ok=False)
    cases = []

    def case(name, expected, change=None, assertion=None):
        data = copy.deepcopy(base)
        if change:
            change(data)
        folder = target / name
        folder.mkdir()
        payloads = {"RAW_CAPTURE.jsonl": data.get("raw_override", lines(data["rows"])),
                    "RESET_EDGES.jsonl": data.get("reset_override", lines(data["resets"])),
                    "END.json": encoded(data["end"]), "stdout.log": data["stdout"].encode("utf-8")}
        for filename, payload in payloads.items():
            (folder / filename).write_bytes(payload)
        cases.append({"name": name, "expected": expected, "assertion": assertion,
                      "origin": data["origin"], "files": {n: identity(folder / n) for n in payloads}})

    def set_port(data, row, port, value):
        data["rows"][row]["ports"][port] = value

    case("public_baseline", "ACCEPT", assertion="BASELINE")
    case("modelsim_prefix", "ACCEPT", lambda d: d.update(stdout="# " + stdout), "BASELINE")
    case("xz_preserved", "ACCEPT", lambda d: set_port(d, 4, "obs_result_left", "x" + "0" * 22 + "Z"), "XZ")
    case("unknown_req_validity", "ACCEPT", lambda d: set_port(d, 6, "obs_tx_req_id_valid", "x"), "REQ_X")

    def asynchronous_reset(data):
        for time_ps, local in ((100000, "0"), (105000, "1")):
            snap = copy.deepcopy(data["resets"][-1])
            snap.update(time_ps=time_ps, edge_seq=len(data["resets"]) + 1)
            snap["values"]["obs_rst_n"] = local
            data["resets"].append(snap)
    case("async_reset_between_rows", "ACCEPT", asynchronous_reset, "ASYNC")

    def ambiguous(data):
        data["resets"][1]["time_ps"] = 112500
        for index in (2, 3, 4):
            data["rows"][index]["ports"]["obs_rst_n"] = "0"
        for local in ("0", "1"):
            snap = copy.deepcopy(data["resets"][-1])
            snap.update(edge_seq=len(data["resets"]) + 1)
            snap["values"]["obs_rst_n"] = local
            data["resets"].append(snap)
    case("same_time_phase_ambiguous", "ACCEPT", ambiguous, "AMBIGUOUS")

    def pre_nba(data):
        data["resets"][1]["time_ps"] = 62500
        data["rows"][2]["ports"]["obs_rst_n"] = "0"
    case("same_time_pre_nba", "ACCEPT", pre_nba, "PRE_NBA")
    case("no_reset_edges", "RESET_EDGES_REQUIRED", lambda d: d.update(reset_override=b""))
    case("initial_not_time_zero", "INITIAL_RESET_TIME_REQUIRED", lambda d: d["resets"][0].update(time_ps=1))
    case("reset_sequence_gap", "RESET_EDGE_SEQUENCE", lambda d: d["resets"][1].update(edge_seq=3))
    case("reset_capture_mismatch", "RESET_ID_OR_SCHEMA", lambda d: d["resets"][1].update(capture_id="OTHER"))
    case("reset_duplicate_state", "RESET_CHANGE_WITHOUT_CHANGE",
         lambda d: d["resets"][1].update(values=copy.deepcopy(d["resets"][0]["values"])))
    case("reset_wrong_level", "RESET_EDGE_LEVEL_MISMATCH", lambda d: set_port(d, 3, "obs_rst_n", "0"))
    case("public_port_missing", "RAW_PUBLIC_PORT_SET", lambda d: d["rows"][0]["ports"].pop("uart_tx"))
    case("port_width", "RAW_PORT_WIDTH_OR_BITS", lambda d: set_port(d, 4, "obs_result_left", "0"))
    case("port_invalid_symbol", "RAW_PORT_WIDTH_OR_BITS", lambda d: set_port(d, 0, "uart_tx", "Q"))
    case("wrong_mode", "NOT_PUBLIC_POLYPHONIC_MODE", lambda d: set_port(d, 2, "obs_polyphonic_valid", "0"))
    case("not_core_edge", "NOT_CORE_POSEDGE", lambda d: set_port(d, 2, "obs_core_clk", "0"))
    case("cycle_gap", "RAW_LINE_OR_CYCLE_GAP", lambda d: d["rows"][3].update(cycle=4))
    case("line_gap", "RAW_LINE_OR_CYCLE_GAP", lambda d: d["rows"][3].update(source_line=5))
    case("time_not_increasing", "RAW_TIME_NOT_STRICTLY_INCREASING", lambda d: d["rows"][3].update(time_ps=62500))
    case("raw_epoch_fabricated", "RAW_EPOCH_MUST_BE_UNBOUND", lambda d: d["rows"][0].update(epoch=0))
    case("finish_missing", "ACTUAL_FINISH_OR_ROW_COUNT_MISSING", lambda d: d["rows"][-1].update(finish=0))
    case("finish_wrong_cycle", "END_NOT_ACTUAL_FINISH", lambda d: d["rows"][6].update(finish=1))

    def after_finish(data):
        row = copy.deepcopy(data["rows"][-1])
        row.update(source_line=9, cycle=8, time_ps=212500, finish=0)
        data["rows"].append(row)
    case("row_after_finish", "ROW_AFTER_FINISH", after_finish)
    case("end_row_count", "ACTUAL_FINISH_OR_ROW_COUNT_MISSING", lambda d: d["end"].update(row_count=9))
    # Keep stdout consistent with the modified END so this reaches row-count check.
    p = target / "end_row_count/stdout.log"
    p.write_text(stdout.replace("rows=8", "rows=9"), encoding="utf-8", newline="\n")
    cases[-1]["files"]["stdout.log"] = identity(p)
    case("unsupported_end_claim", "UNSUPPORTED_END_CLAIM", lambda d: d["end"].update(ledger_status="PASS"))
    case("monitor_missing", "MONITOR_END_UNIQUE_REQUIRED", lambda d: d.update(stdout=""))
    case("monitor_duplicate", "MONITOR_END_UNIQUE_REQUIRED", lambda d: d.update(stdout=stdout * 2))
    case("monitor_malformed_extra", "MONITOR_END_UNIQUE_REQUIRED", lambda d: d.update(stdout=stdout + "# MONITOR_END broken\n"))
    case("monitor_bad_format", "MONITOR_END_FORMAT", lambda d: d.update(stdout="MONITOR_END broken\n"))
    case("monitor_mismatch", "MONITOR_END_MISMATCH", lambda d: d.update(stdout=stdout.replace("cycle=7", "cycle=6")))
    case("fatal_stdout", "CAPTURE_FAILED_DIAGNOSTIC", lambda d: d.update(stdout=stdout + "# ** Fatal: synthetic failure\n"))
    case("unsupported_origin", "ORIGIN", lambda d: d.update(origin="APPROVED"))
    case("duplicate_json_key", "DUPLICATE_JSON_KEY", lambda d: d.update(raw_override=b'{"schema":1,"schema":2}\n'))
    case("nonfinite_json", "NONFINITE_JSON", lambda d: d.update(raw_override=b'{"schema":NaN}\n'))
    save(DOC / "CASE_SPEC.json", {"schema": "M3_R7A_CASE_SPEC_V1", "cases": cases,
        "scope": "NEW_SYNTHETIC_REPRESENTATION_ONLY_NOT_FRAME_PLAN_OR_HDL", "old_R06_groups": 0,
        "board_release_allowed": False})
    print(json.dumps({"fixtures_written": len(cases), "functional_groups_run": 0}))


if __name__ == "__main__":
    main()
