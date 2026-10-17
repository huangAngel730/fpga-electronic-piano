"""New synthetic R7-A representation assertions; never invokes HDL or old suites."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from assemble import Reject, assemble, digest, load
from prepare import DOC, SOFT, identity, save


def check(ok, label):
    if not ok:
        raise AssertionError(label)


def schema_matches(value, schema):
    """Test-only assertion subset, covers every keyword in this frozen schema.

    No claim of implementing general draft2020-12 validation or provenance.
    """
    allowed = {"$schema", "$id", "title", "description", "x-contract", "type", "anyOf",
               "const", "enum", "minimum", "maximum", "pattern", "minLength", "maxLength",
               "properties", "required", "additionalProperties", "items", "uniqueItems"}
    check(set(schema) <= allowed, "UNSUPPORTED_SCHEMA_ASSERTION_KEYWORD")
    if "anyOf" in schema and not any(schema_matches(value, sub) for sub in schema["anyOf"]):
        return False
    types = {"object": type(value) is dict, "array": type(value) is list,
             "integer": type(value) is int, "string": type(value) is str,
             "null": value is None, "boolean": type(value) is bool}
    if "type" in schema:
        requested = schema["type"] if type(schema["type"]) is list else [schema["type"]]
        if not any(types[t] for t in requested):
            return False
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if type(value) is int:
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            return False
    if type(value) is str:
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            return False
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            return False
    if type(value) is dict:
        properties = schema.get("properties", {})
        if not set(schema.get("required", [])) <= set(value):
            return False
        for name, content in value.items():
            if name in properties:
                if not schema_matches(content, properties[name]):
                    return False
            elif schema.get("additionalProperties") is False:
                return False
            elif type(schema.get("additionalProperties")) is dict:
                if not schema_matches(content, schema["additionalProperties"]):
                    return False
    if type(value) is list:
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            return False
        if "items" in schema and not all(schema_matches(v, schema["items"]) for v in value):
            return False
    return True


def assertions(rows, receipt, kind, port_map, schema, raw, resets):
    check(len(rows) == 8 and receipt["rows"] == 8, "ALL_ROWS_RETAINED")
    check(not receipt["board_release_allowed"] and not receipt["pro_dut_pass"] and
          not receipt["real_finish_pass"] and not receipt["FRAME_PLAN_generated"], "NO_PROMOTION")
    for i, row in enumerate(rows):
        check(schema_matches(row, schema), f"FROZEN_SCHEMA_ROW_{i}")
        check(set(row["fields"]) == set(schema["properties"]["fields"]["required"]), "BARE_61_KEYS")
        check(row["source"]["raw_sha256"] == digest(raw) and
              row["source"]["reset_edges_sha256"] == digest(resets), "ORIGINAL_SHA")
        check(row["source"]["line"] == i + 1 and row["source"]["cycle"] == i and
              row["fields"]["cycle"] == i, "LINE_AND_CYCLE")
        check(row["fields"]["epoch"] == row["source"]["epoch"], "EPOCH_LINK")
        check(all(row["fields"][n] is None and row["missing_reasons"][n] == reason
                  for n, reason in port_map["unimplemented"].items()), "MISSING23_NO_FILL")
    if kind == "BASELINE":
        check(rows[2]["events"] == ["FRAME_F"] and rows[3]["events"] == ["ACCEPT_A"], "F_A_DISTINCT")
        check(rows[4]["events"] == ["RESULT_TRANSFER"] and rows[5]["events"] == ["COMMIT"], "RESULT_COMMIT_DISTINCT")
        check(rows[4]["fields"]["result_left"] == -(1 << 23) and
              rows[4]["fields"]["result_right"] == (1 << 23) - 1 and
              rows[4]["fields"]["result_clip_mask"] == 2, "SIGNED24_STEREO_CLIP")
        check(rows[3]["fields"]["event_data"] == (1 << 64) - 1, "UNSIGNED64")
        check(rows[6]["fields"]["tx_req_id"] == 0 and rows[6]["extensions"]["obs_tx_req_id_valid"] == 1, "VALID_ID_ZERO")
        check(rows[6]["extensions"]["obs_tx_clip_mask"] == 2 and rows[6]["fields"]["tx_clip"] == 1, "TX_BOTH_CLIP_AND_ANY")
        check(rows[7]["fields"]["tx_req_id"] is None and rows[7]["fields"]["tx_left"] == -3 and
              rows[7]["extensions"]["raw_tx_req_id_bits"] == format(42, "032b") and
              rows[7]["events"] == ["TX_ADOPT", "FINISH"] and rows[7]["fields"]["tx_hold"] == 1 and
              rows[7]["extensions"]["obs_metadata_error"] == 1, "INVALID_METADATA_TX_RETAINED")
        check([r["source"]["epoch"] for r in rows] == [0] * 8, "INITIAL_RESET_EPOCH")
    elif kind == "XZ":
        check(rows[4]["fields"]["result_left"] == "x" + "0" * 22 + "Z" and
              rows[4]["missing_reasons"]["result_left"] == "OBSERVED_PUBLIC_XZ", "XZ_NOT_ZERO")
    elif kind == "REQ_X":
        check(rows[6]["fields"]["tx_req_id"] is None and "TX_ADOPT" in rows[6]["events"], "XZ_QUALIFIER_NO_ID")
    elif kind == "ASYNC":
        check([r["source"]["epoch"] for r in rows] == [0, 0, 0, 0, 1, 1, 1, 1], "ASYNC_LOCAL_RESET_EPOCH")
    elif kind == "AMBIGUOUS":
        check(rows[4]["source"]["epoch"] is None and "AMBIGUOUS" in rows[4]["missing_reasons"]["epoch"], "SAME_TIME_FAIL_CLOSED")
    elif kind == "PRE_NBA":
        check(rows[2]["source"]["epoch"] == 0 and rows[2]["fields"]["rst_n"] == 0 and
              "FRAME_F" not in rows[2]["events"], "PRE_NBA_RESET_PREFIX")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(exist_ok=False)
    cases = load((DOC / "CASE_SPEC.json").read_bytes())["cases"]
    port_map = load((DOC / "PORT_MAP.json").read_bytes())
    schema = load((DOC / "CAPTURE_SCHEMA.json").read_bytes())
    results = []
    for case in cases:
        folder = DOC / "FIXTURES" / case["name"]
        inputs = [(folder / n).read_bytes() for n in ("RAW_CAPTURE.jsonl", "RESET_EDGES.jsonl", "END.json", "stdout.log")]
        actual = "ACCEPT"
        try:
            rows, receipt = assemble(*inputs, port_map, case["origin"])
            check(case["expected"] == "ACCEPT", "EXPECTED_REJECTION_WAS_ACCEPTED")
            assertions(rows, receipt, case["assertion"], port_map, schema, inputs[0], inputs[1])
            with (args.output / (case["name"] + ".PUBLIC_ROWS.jsonl")).open("x", encoding="utf-8", newline="\n") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            save(args.output / (case["name"] + ".receipt.json"), receipt)
        except Reject as error:
            actual = str(error)
            check(actual == case["expected"], f"{case['name']}: expected={case['expected']} actual={actual}")
        results.append({"name": case["name"], "expected": case["expected"], "actual": actual,
                        "passed": actual == case["expected"], "execution": "IN_PROCESS_ASSERTION_NOT_SEPARATE_EXIT_CODE"})
        save(args.output / (case["name"] + ".result.json"), results[-1])
    # Actual CLI process boundaries, within the parent's supervised Windows Job.
    processes = []
    for name, expected_exit in (("public_baseline", 0), ("monitor_malformed_extra", 2)):
        folder = DOC / "FIXTURES" / name
        argv = [sys.executable, "-B", str(SOFT / "assemble.py")]
        for option, filename in (("raw", "RAW_CAPTURE.jsonl"), ("resets", "RESET_EDGES.jsonl"),
                                 ("end", "END.json"), ("stdout", "stdout.log")):
            argv.extend(["--" + option, str(folder / filename)])
        argv.extend(["--origin", "SYNTHETIC_SCHEMA_FIXTURE", "--output", str(args.output / (name + ".CLI"))])
        started_utc = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        proc = subprocess.Popen(argv, cwd=SOFT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        timed_out = False
        cleanup_timeout = False
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Frozen assemble.py creates no descendants. The inherited parent
            # Job remains the tree-wide backstop until all this work completes.
            proc.kill()
            try:
                out, err = proc.communicate(timeout=3)
            except subprocess.TimeoutExpired as error:
                cleanup_timeout = True
                out, err = error.output or b"", error.stderr or b""
        record = {"argv": argv, "cwd": str(SOFT), "pid": proc.pid, "start_utc": started_utc,
                  "end_utc": datetime.now(timezone.utc).isoformat(), "elapsed_s": time.monotonic() - started,
                  "exit_code": proc.returncode, "expected_exit": expected_exit, "timeout": timed_out,
                  "cleanup_timeout": cleanup_timeout,
                  "tree_policy": "INHERITED_PARENT_WINDOWS_JOB", "stdout_bytes": len(out), "stderr_bytes": len(err)}
        for label, data in (("stdout", out), ("stderr", err)):
            p = args.output / (name + ".CLI." + label + ".log")
            p.write_bytes(data)
            record[label] = identity(p)
        save(args.output / (name + ".CLI.process.json"), record)
        processes.append(record)
        check(not timed_out and not cleanup_timeout and proc.returncode == expected_exit and not err,
              "CLI_ACTUAL_EXIT_OR_STDERR_OR_TIMEOUT")
        if expected_exit == 0:
            actual = [load(line) for line in (args.output / (name + ".CLI/PUBLIC_ROWS.jsonl")).read_bytes().splitlines()]
            expected = [load(line) for line in (args.output / (name + ".PUBLIC_ROWS.jsonl")).read_bytes().splitlines()]
            check(actual == expected, "STREAMING_CLI_EQUALS_SYNTHETIC_BATCH")
        else:
            check(load(out)["first_failure"] == "MONITOR_END_UNIQUE_REQUIRED", "CLI_FAIL_CLOSED")
            check(not (args.output / (name + ".CLI/RECEIPT.json")).exists(), "NO_FAILED_SUCCESS_RECEIPT")
    summary = {"status": "PASS_SYNTHETIC_SOFTWARE_ONLY", "cases": len(results),
               "positive": sum(r["expected"] == "ACCEPT" for r in results),
               "negative": sum(r["expected"] != "ACCEPT" for r in results),
               "cli_processes": len(processes), "HDL": "NOT_RUN", "old_R06_groups": 0,
               "real_capture": "PENDING", "M1_semantics": "PENDING", "board_release_allowed": False}
    save(args.output / "SUMMARY.json", summary)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
