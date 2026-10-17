"""Mechanical R7-A raw/public conversion. Never creates expected FRAME_PLAN."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re

from prepare import DOC


class Reject(ValueError):
    pass


def need(ok, code):
    if not ok:
        raise Reject(code)


def pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, "DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def load(raw):
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Reject("NONFINITE_JSON")))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise Reject("JSON_SYNTAX") from error


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_digest(raw):
    if type(raw) is bytes:
        return digest(raw)
    h = hashlib.sha256()
    with Path(raw).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def exact(obj, keys, code):
    need(type(obj) is dict and set(obj) == set(keys), code)


def scalar(bits, spec):
    need(type(bits) is str and len(bits) == spec["width"] and
         re.fullmatch("[01xXzZ]+", bits) is not None, "RAW_PORT_WIDTH_OR_BITS")
    if re.search("[xXzZ]", bits):
        return bits
    number = int(bits, 2)
    if spec["signed"] and number & (1 << (spec["width"] - 1)):
        number -= 1 << spec["width"]
    return number


def reset_states(raw, capture_id):
    states = []
    last_values = None
    epoch = -1
    known = True
    last_time = -1
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        item = load(line)
        exact(item, ("schema", "capture_id", "edge_seq", "time_ps", "kind", "values"), "RESET_FIELDS")
        need(item["schema"] == "M3_R7A_RESET_SNAPSHOT_V1" and item["capture_id"] == capture_id, "RESET_ID_OR_SCHEMA")
        need(integer(item["edge_seq"], 1) and item["edge_seq"] == line_no, "RESET_EDGE_SEQUENCE")
        now = item["time_ps"]
        need(integer(now) and now >= last_time, "RESET_TIME_ORDER")
        need(item["kind"] == ("INITIAL" if line_no == 1 else "CHANGE"), "RESET_KIND")
        if line_no == 1:
            need(now == 0, "INITIAL_RESET_TIME_REQUIRED")
        exact(item["values"], ("sys_rst_n", "obs_rst_n", "obs_pll_locked"), "RESET_VALUES")
        values = item["values"]
        for bit in values.values():
            need(type(bit) is str and re.fullmatch("[01xXzZ]", bit) is not None, "RESET_RAW_BIT")
        if last_values is not None:
            need(values != last_values, "RESET_CHANGE_WITHOUT_CHANGE")
        local = values["obs_rst_n"]
        previous = last_values["obs_rst_n"] if last_values is not None else None
        if local == "0" and previous != "0":
            epoch += 1
        if local.lower() in ("x", "z") and epoch >= 0:
            known = False
        states.append({"time_ps": now, "local": local, "epoch": epoch if epoch >= 0 and known else None})
        last_values, last_time = dict(values), now
    need(states, "RESET_EDGES_REQUIRED")
    return states


def bind_epoch(states, now, sampled_reset):
    if sampled_reset not in (0, 1) or type(sampled_reset) is not int:
        return None, "PENDING_RESET_PHASE_RAW_XZ"
    before = None
    equal = []
    for state in states:
        if state["time_ps"] < now:
            before = state
        elif state["time_ps"] == now:
            equal.append(state)
        else:
            break
    candidates = [state for state in [before, *equal] if state is not None and
                  state["local"] == str(sampled_reset)]
    # No equal-time change: only the last actual snapshot can represent now.
    if not equal:
        candidates = [before] if before is not None and before["local"] == str(sampled_reset) else []
    need(candidates, "RESET_EDGE_LEVEL_MISMATCH")
    epochs = {state["epoch"] for state in candidates}
    if len(epochs) != 1 or None in epochs:
        return None, "PENDING_RESET_PHASE_AMBIGUOUS_OR_UNKNOWN"
    return next(iter(epochs)), None


def stream_rows(raw, resets, end_raw, stdout, port_map, origin, receipt):
    need(origin in ("SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"), "ORIGIN")
    end = load(end_raw)
    exact(end, ("schema", "capture_id", "plan_stop_id", "finish_cycle", "time_ps", "row_count",
                "reason", "ledger_status", "serial_tail_status"), "END_FIELDS")
    need(end["schema"] == "M3_R7A_END_V1" and end["reason"] == "PLANNED_WINDOW_END", "END_SCHEMA_OR_REASON")
    capture_id = end["capture_id"]
    need(type(capture_id) is str and re.fullmatch("[A-Za-z0-9_-]+", capture_id), "CAPTURE_ID")
    need(type(end["plan_stop_id"]) is str and re.fullmatch("[A-Za-z0-9_-]+", end["plan_stop_id"]), "STOP_ID")
    for name in ("finish_cycle", "time_ps", "row_count"):
        need(integer(end[name]), "END_NUMERIC")
    need(end["ledger_status"] == "NOT_CHECKED_R6_5_REQUIRED" and end["serial_tail_status"] == "UNKNOWN_R6_6_REQUIRED", "UNSUPPORTED_END_CLAIM")
    stdout_text = stdout.decode("utf-8")
    markers = [(number, line) for number, line in enumerate(stdout_text.splitlines(), 1)
               if re.search(r"\bMONITOR_END\b", line)]
    need(len(markers) == 1, "MONITOR_END_UNIQUE_REQUIRED")
    monitor = re.fullmatch(r"(?:#\s*)?MONITOR_END capture_id=(\S+) cycle=(\d+) time_ps=(\d+) rows=(\d+) reason=PLANNED_WINDOW_END\s*", markers[0][1])
    need(monitor is not None, "MONITOR_END_FORMAT")
    need(monitor.groups() == (capture_id, str(end["finish_cycle"]), str(end["time_ps"]), str(end["row_count"])), "MONITOR_END_MISMATCH")
    need(not re.search(r"(?m)^(?:#\s*)?\*\*\s*(?:Fatal|Error):", stdout_text), "CAPTURE_FAILED_DIAGNOSTIC")
    states = reset_states(resets, capture_id)
    mapping = port_map["normalized_mapping"]
    specs = port_map["raw_ports"]
    names = set(mapping) | set(port_map["unimplemented"]) | {"cycle", "epoch", "finish"}
    need(len(names) == 61, "NORMALIZED_61_MAP_REQUIRED")
    raw_sha, reset_sha = raw_digest(raw), digest(resets)
    row_count = 0
    last_time = -1
    finish_count = 0
    tx_count = 0
    raw_stream = io.BytesIO(raw) if type(raw) is bytes else Path(raw).open("rb")
    try:
        for line_no, line in enumerate(raw_stream, 1):
            item = load(line)
            exact(item, ("schema", "capture_id", "source_line", "cycle", "time_ps", "epoch", "epoch_reason", "finish", "ports"), "RAW_ROW_FIELDS")
            need(item["schema"] == "M3_R7A_RAW_CORE_ROW_V1" and item["capture_id"] == capture_id, "RAW_ID_OR_SCHEMA")
            need(item["epoch"] is None and item["epoch_reason"] == "BIND_FROM_INDEPENDENT_RESET_EDGES", "RAW_EPOCH_MUST_BE_UNBOUND")
            need(integer(item["source_line"], 1) and item["source_line"] == line_no and
                 integer(item["cycle"]) and item["cycle"] == line_no - 1, "RAW_LINE_OR_CYCLE_GAP")
            now = item["time_ps"]
            need(integer(now) and now > last_time, "RAW_TIME_NOT_STRICTLY_INCREASING")
            need(type(item["finish"]) is int and item["finish"] in (0, 1), "FINISH_BIT")
            need(not finish_count, "ROW_AFTER_FINISH")
            exact(item["ports"], specs, "RAW_PUBLIC_PORT_SET")
            values = {name: scalar(item["ports"][name], spec) for name, spec in specs.items()}
            need(values["obs_core_clk"] == 1 and type(values["obs_core_clk"]) is int, "NOT_CORE_POSEDGE")
            need(values["obs_polyphonic_valid"] == 1, "NOT_PUBLIC_POLYPHONIC_MODE")
            fields = {name: values[entry["port"]] for name, entry in mapping.items()}
            fields.update({name: None for name in port_map["unimplemented"]})
            reasons = dict(port_map["unimplemented"])
            for name in mapping:
                if type(fields[name]) is str:
                    reasons[name] = "OBSERVED_PUBLIC_XZ"
            epoch, epoch_reason = bind_epoch(states, now, fields["rst_n"])
            fields.update(cycle=item["cycle"], epoch=epoch, finish=item["finish"])
            if epoch_reason:
                reasons["epoch"] = epoch_reason
            if values["obs_tx_req_id_valid"] != 1:
                fields["tx_req_id"] = None
                reasons["tx_req_id"] = "NO_KNOWN_VALID_TX_REQUEST_ID_RAW_BITS_RETAINED"
            extensions = {name: values[name] for name in ("obs_core_clk", "obs_polyphonic_valid", "obs_tx_metadata_valid",
                "obs_tx_req_id_valid", "obs_tx_clip_mask", "obs_metadata_error", "obs_frame_id_overflow", "uart_tx")}
            extensions.update(schema="M3_R7A_TX_EXTENSION_V1", raw_tx_req_id_bits=item["ports"]["obs_tx_req_id"])
            events = []
            if fields["rst_n"] == 1:
                flags = (("FRAME_F", fields["frame_tick"] == 1),
                         ("ACCEPT_A", fields["req_valid"] == 1 and fields["req_ready"] == 1),
                         ("RESULT_TRANSFER", fields["result_valid"] == 1 and fields["result_ready"] == 1),
                         ("COMMIT", fields["commit"] == 1), ("TX_ADOPT", fields["tx_sample_valid"] == 1))
                events = [name for name, active in flags if active]
            if item["finish"]:
                events.append("FINISH")
                finish_count += 1
                need(item["cycle"] == end["finish_cycle"] and now == end["time_ps"], "END_NOT_ACTUAL_FINISH")
            tx_count += "TX_ADOPT" in events
            row_count += 1
            yield {"schema": "M3_R7A_PUBLIC_ROW_V1", "capture_id": capture_id, "origin": origin,
                "source": {"raw_sha256": raw_sha, "reset_edges_sha256": reset_sha, "line": line_no,
                    "cycle": item["cycle"], "epoch": epoch, "time_ps": now, "sampling_phase": "POSEDGE_PRE_NBA"},
                "fields": fields, "extensions": extensions, "missing_reasons": reasons, "events": events}
            last_time = now
    finally:
        raw_stream.close()
    need(finish_count == 1 and row_count == end["row_count"], "ACTUAL_FINISH_OR_ROW_COUNT_MISSING")
    need(raw_digest(raw) == raw_sha, "RAW_CHANGED_DURING_READ")
    receipt.update({"status": "SOFTWARE_ASSEMBLED_PENDING_M1_AND_REAL_EXECUTION", "rows": row_count,
        "tx_adoptions": tx_count, "origin": origin, "raw_sha256": raw_sha, "reset_edges_sha256": reset_sha,
        "FRAME_PLAN_generated": False, "pro_dut_pass": False, "real_finish_pass": False,
        "HDL_status": "NOT_RUN_OR_EXTERNAL_RECEIPT_REQUIRED", "board_release_allowed": False})


def assemble(raw, resets, end_raw, stdout, port_map, origin):
    """Small synthetic callers may collect rows; production CLI streams them."""
    receipt = {}
    rows = list(stream_rows(raw, resets, end_raw, stdout, port_map, origin, receipt))
    return rows, receipt


def main():
    ap = argparse.ArgumentParser()
    for name in ("raw", "resets", "end", "stdout", "output"):
        ap.add_argument("--" + name, required=True, type=Path)
    ap.add_argument("--origin", choices=("SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"), default="HDL_PUBLIC_CAPTURE_UNVERIFIED")
    ap.add_argument("--port-map", type=Path, default=DOC / "PORT_MAP.json")
    args = ap.parse_args()
    try:
        receipt = {}
        rows = stream_rows(args.raw, args.resets.read_bytes(), args.end.read_bytes(),
                           args.stdout.read_bytes(), load(args.port_map.read_bytes()), args.origin, receipt)
        args.output.mkdir(exist_ok=False)
        with (args.output / "PUBLIC_ROWS.jsonl").open("x", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        (args.output / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(receipt))
        return 0
    except (Reject, OSError, UnicodeError, TypeError, KeyError) as error:
        print(json.dumps({"status": "REJECT", "first_failure": str(error), "pro_dut_pass": False,
                          "board_release_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
