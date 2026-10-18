"""Ten new file-only seams; callable by the coordinator, never auto-run."""
from __future__ import annotations

import argparse
import copy
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
SOFT = ROOT / "code/software/m3_pro_fourvoice_trace_20261016"
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016"
TB = ROOT / ("code/tb/board/m3_pro_fourvoice_trace_20261016/"
              "pro_basis_r07_20261017/public_capture_tb/c9_binding")
COMMON_PATH = SOFT / "pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py"
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
MODULES = {
    "stream": ("pro_basis_r07_20261017/public_capture_tb/c9_completion_r01/c9_stream.py",
               "5584ab7201544a8d30bfdd7603a51483d1c5340ccc219e853df0d146d042ebef"),
    "codec": ("pro_basis_r08_20261017/capture_csv_codec/c9_completion_r01/c9_codec.py",
              "9cc466db9324bb8d770af02e0b11a40ab3bc67f5febc46d044449d7a656832af"),
    "intake": ("pro_basis_r06_20261017/normalized_intake/c9_completion_r01/intake_adapter.py",
               "7cfaba5c19cefa408f30911f5a69b440302e7bca24d6a2352fce1e48ba2456c0"),
    "bundle": ("pro_basis_r07_20261017/oracle_bundle_bridge/c9_completion_r01/math_bundle.py",
               "83659169c25e5d77621e1649eeda25697b7f0eb4767d8321599144a19ceb3854"),
}
CASE_IDS = (
    "STREAM_GT64M_CSV_ROUNDTRIP", "STREAM_RAW_ENVELOPE_REJECT",
    "STREAM_RESET_FINISH_REJECT", "C9_CSV_ENVELOPE_REJECT",
    "C9_CSV_MISSING_FIELD_REJECT", "C9_CSV_X_NULL_LONG_CELL_ROUNDTRIP",
    "C9_INTAKE_UNIQUE_CALENDAR_SEAM", "C9_INTAKE_UNPROVEN_SEQ_REJECT",
    "C9_MATH_HISTORY_COMPLETE", "C9_MATH_INPUT_TAMPER_REJECT")
_COMMON = None


def support():
    global _COMMON
    if _COMMON is None:
        raw = COMMON_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
            raise ValueError("COMMON_SOURCE_CHANGED")
        module = ModuleType("_m3_c9_d4_common_cases")
        module.__file__ = str(COMMON_PATH)
        exec(compile(raw, str(COMMON_PATH), "exec"), module.__dict__)
        _COMMON = module
    return _COMMON


def _fixture_rows():
    c = support()
    source = TB / "C9_SYNTHETIC.raw.jsonl"
    c.require(c.identity(source)["sha256"] ==
              "422f23b11c91a3412bdb7b991ffc04a908d690295440b4335dde51439c661c28",
              "C9_SYNTHETIC_FIXTURE_CHANGED")
    return list(c.iter_jsonl(source))  # exactly seven frozen synthetic rows


def _write_rows(path, rows):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")


def _fixture(out, mode="small"):
    c = support()
    original = _fixture_rows()
    raw = out / "raw.jsonl"
    if mode == "large":
        template = copy.deepcopy(original[-1])
        template["finish"] = 0
        template["ports"]["obs_config_take"] = "0"
        template["ports"]["obs_upstream_clip_mask"] = "00"
        template["ports"]["obs_effect_clip_mask"] = "00"
        template["ports"]["obs_feedback_clip_mask"] = "00"
        count = 0
        with raw.open("xb") as sink:
            while sink.tell() <= 65 * 1024 * 1024:
                row = dict(template, source_line=count + 1, cycle=count,
                           time_ps=(count + 1) * 25000)
                sink.write((json.dumps(row, separators=(",", ":")) + "\n").encode())
                count += 1
            row = dict(template, source_line=count + 1, cycle=count,
                       time_ps=(count + 1) * 25000, finish=1)
            sink.write((json.dumps(row, separators=(",", ":")) + "\n").encode())
            count += 1
    elif mode == "calendar":
        template = copy.deepcopy(original[-1])
        template["ports"]["obs_config_take"] = "0"
        def rows():
            for cycle in range(836):
                row = copy.deepcopy(template)
                row.update(source_line=cycle + 1, cycle=cycle,
                           time_ps=(cycle + 1) * 25000, finish=int(cycle == 835))
                if cycle == 833:
                    row["ports"]["obs_frame_tick"] = "1"
                if cycle == 834:
                    row["ports"].update(obs_req_valid="1", obs_req_ready="1",
                                        obs_advance_mask="1111",
                                        obs_advance_frame_req_id="0" * 32)
                yield row
        _write_rows(raw, rows())
        count = 836
    else:
        if mode == "fx":
            original[5]["ports"].update(obs_effect_input_valid="1", obs_effect_input_ready="1",
                obs_effect_input_id=format(23, "032b"), obs_effect_input_left=format(123, "024b"),
                obs_advance_mask="1111", obs_advance_frame_req_id=format(23, "032b"),
                obs_cancel="1")
        if mode == "unknown":
            original[5]["ports"]["obs_result_left"] = "x" * 24
        if mode == "bad_raw":
            original[0]["schema"] = "M3_R7A_RAW_CORE_ROW_V1"
        _write_rows(raw, original)
        count = len(original)
    resets = TB / "C9_SYNTHETIC.resets.jsonl"
    c.require(c.identity(resets)["sha256"] ==
              "f57c3a9fe8454d12f90b8ea2ac03c4ac1b51bad2dec4bd5e7e21e659ed03b129",
              "C9_SYNTHETIC_RESETS_CHANGED")
    end = out / "end.json"
    c.write_json(end, {"schema": "M3_R7A_END_V1", "capture_id": original[0]["capture_id"],
        "plan_stop_id": "D4_SYNTHETIC_STOP", "finish_cycle": count - 1,
        "time_ps": count * 25000, "row_count": count, "reason": "PLANNED_WINDOW_END",
        "ledger_status": "NOT_CHECKED_R6_5_REQUIRED", "serial_tail_status": "UNKNOWN_R6_6_REQUIRED"})
    stdout = out / "capture_stdout.txt"
    stdout.write_text(
        f"MONITOR_END capture_id={original[0]['capture_id']} cycle={count - 1} "
        f"time_ps={count * 25000} rows={count} reason=PLANNED_WINDOW_END\n",
        encoding="utf-8", newline="\n")
    return {"raw": raw, "resets": resets, "end": end, "stdout": stdout, "rows": count}


def _reject(call, reason):
    try:
        call()
    except (ValueError, RuntimeError) as error:
        if reason not in str(error):
            raise
        return {"expected_reject": reason, "actual_error": str(error)}
    raise AssertionError("EXPECTED_REJECT:" + reason)


def _bundle_request(c, fixture, public):
    return {"schema": "M3_D4_C9_MATH_BUNDLE_REQUEST_V1", "inputs": {
        "public_rows": c.artifact(public), "raw_capture": c.artifact(fixture["raw"]),
        "reset_edges": c.artifact(fixture["resets"]), "end": c.artifact(fixture["end"]),
        "stdout": c.artifact(fixture["stdout"])}}


def run_case(case_id, output_dir):
    c = support()
    c.require(case_id in CASE_IDS, "UNKNOWN_D4_CASE")
    out = c.output_directory(output_dir)
    loaded = {name: c.load_source(SOFT / path, sha)
              for name, (path, sha) in MODULES.items()}
    stream, codec = loaded["stream"], loaded["codec"]
    mode = ("large" if case_id == "STREAM_GT64M_CSV_ROUNDTRIP" else
            "bad_raw" if case_id == "STREAM_RAW_ENVELOPE_REJECT" else
            "unknown" if case_id == "C9_CSV_X_NULL_LONG_CELL_ROUNDTRIP" else
            "calendar" if case_id == "C9_INTAKE_UNIQUE_CALENDAR_SEAM" else
            "fx" if case_id == "C9_MATH_HISTORY_COMPLETE" else "small")
    # The independent plan input is declared before raw generation or inspection.
    if mode == "calendar":
        anchor = out / "INDEPENDENT_SCENARIO.json"
        c.write_json(anchor, {"status": "SYNTHETIC_INDEPENDENT_SCENARIO",
                             "release": 0, "stop": 835, "expected_F": 833, "expected_A": 834})
        anchor_identity = c.artifact(anchor)
        plan_input = out / "PLAN_INPUT.json"
        c.write_json(plan_input, {
            "schema": "M3_R06_FRAME_PLAN_GENERATOR_INPUT_V1", "status": "FROZEN_INDEPENDENT_INPUT",
            "independent_of_observed_trace": True,
            "source_identities": [{"path": anchor_identity["path"],
                                   "sha256": anchor_identity["sha256"]}],
            "epochs": [{"epoch": 0, "window_kind": "ACTIVE", "reset_assert_cycle": 0,
                        "release_cycle": 0, "stop_cycle": 835}],
            "finish": {"epoch": 0, "cycle": 835}})
    fixture = _fixture(out, mode)
    c.write_json(out / "INPUTS.json", {
        name: c.artifact(path) for name, path in fixture.items() if name != "rows"})
    if case_id == "STREAM_RAW_ENVELOPE_REJECT":
        report = _reject(lambda: stream.convert_files(
            fixture["raw"], fixture["resets"], fixture["end"], fixture["stdout"], out / "converted"),
            "C9_RAW_SCHEMA_REQUIRED")
    elif case_id == "STREAM_RESET_FINISH_REJECT":
        bad_end = out / "wrong_end.json"
        value = c.read_json(fixture["end"])
        value["finish_cycle"] += 1
        c.write_json(bad_end, value)
        report = _reject(lambda: stream.convert_files(
            fixture["raw"], fixture["resets"], bad_end, fixture["stdout"], out / "converted"),
            "MONITOR_END_MISMATCH")
    else:
        converted = stream.convert_files(
            fixture["raw"], fixture["resets"], fixture["end"], fixture["stdout"], out / "converted")
        public = c.checked_descriptor(converted["artifacts"]["public_rows"])
        if case_id in {"STREAM_GT64M_CSV_ROUNDTRIP", "C9_CSV_X_NULL_LONG_CELL_ROUNDTRIP"}:
            source = public
            if mode == "unknown":
                changed = out / "LONG_METADATA_ROWS.jsonl"
                def rows():
                    for number, row in enumerate(c.iter_jsonl(public), 1):
                        if number == 6:
                            row["semantics"]["fixture_long_metadata"] = "q" * 140000
                        yield row
                _write_rows(changed, rows())
                source = changed
            encoded = codec.encode_file(source, out / "rows.csv")
            decoded = codec.decode_file(out / "rows.csv", out / "roundtrip.jsonl")
            count = 0
            for count, pair in enumerate(zip_longest(c.iter_jsonl(source),
                    c.iter_jsonl(out / "roundtrip.jsonl")), 1):
                c.require(pair[0] is not None and pair[0] == pair[1], "CSV_ROW_NOT_LOSSLESS")
            c.require(count == fixture["rows"], "CSV_ROW_COVERAGE")
            if mode == "large":
                c.require(c.identity(fixture["raw"])["bytes"] > 64 * 1024 * 1024,
                          "NOT_A_REAL_GT64M_FILE")
            else:
                sixth = next(row for row in c.iter_jsonl(out / "roundtrip.jsonl")
                             if row["source"]["line"] == 6)
                c.require(sixth["fields"]["result_left"] == "x" * 24
                          and sixth["fields"]["apply_event_seq"] is None
                          and len(sixth["semantics"]["fixture_long_metadata"]) == 140000,
                          "X_NULL_LONG_CELL_LOSS")
                bad_csv = out / "multiline_bad.csv"
                with (out / "rows.csv").open("r", encoding="utf-8") as src:
                    first = src.readline()
                bad_csv.write_text(first + '"unterminated\n', encoding="utf-8", newline="\n")
                _reject(lambda: codec.decode_file(bad_csv, out / "bad_decode.jsonl"),
                        "C9_CSV_RECORD_SYNTAX")
            report = {"converted": converted, "encoded": encoded, "decoded": decoded}
        elif case_id in {"C9_CSV_ENVELOPE_REJECT", "C9_CSV_MISSING_FIELD_REJECT",
                         "C9_INTAKE_UNPROVEN_SEQ_REJECT"}:
            changed = out / "changed_rows.jsonl"
            def rows():
                for number, row in enumerate(c.iter_jsonl(public), 1):
                    if number == 1:
                        if case_id == "C9_CSV_ENVELOPE_REJECT":
                            row["schema"] = "M3_R7A_PUBLIC_ROW_V1"
                        elif case_id == "C9_CSV_MISSING_FIELD_REJECT":
                            del row["fields"]["feedback_clip_mask"]
                        else:
                            row["fields"]["apply_event_seq"] = 7
                    yield row
            _write_rows(changed, rows())
            reason = ("C9_ROW_SCHEMA" if case_id == "C9_CSV_ENVELOPE_REJECT" else
                      "C9_FIELDS_74" if case_id == "C9_CSV_MISSING_FIELD_REJECT"
                      else "INDEPENDENT_PLAN_MAPPING_UNVERIFIED")
            call = (lambda: loaded["intake"].project_intake_files(changed, out / "intake")) \
                if case_id == "C9_INTAKE_UNPROVEN_SEQ_REJECT" else \
                (lambda: codec.encode_file(changed, out / "bad.csv"))
            report = _reject(call, reason)
        elif case_id == "C9_INTAKE_UNIQUE_CALENDAR_SEAM":
            intake = loaded["intake"].project_intake_files(public, out / "intake")
            generator = c.load_source(SOFT / "pro_basis_r06_20261017/event_calendar/frame_plan_generator_candidate.py",
                "38592faebeeeb0a2022668785453760a5b58babd24af6ff18a96f15790597191")
            calendar = c.load_source(SOFT / "pro_basis_r06_20261017/event_calendar/r07_fix/calendar_r07_fix_candidate.py",
                "9af7022b0a228e0f8e180fd6a3c58646757cb407dfb132726c8ae0ace28413a5")
            generator.generate(plan_input, ROOT / ("code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
                "r06_observer_20261017/FRAME_PLAN_RULES.json"), out / "unique_plan")
            canonical = c.read_json(out / "unique_plan/UNIQUE_FRAME_PLAN.json")
            ledger = c.read_json(c.checked_descriptor(intake["artifacts"]["ledger"]))
            actual = calendar.analyze(ledger, canonical)
            c.require(len(actual["frames"]) == 1 and actual["frames"][0]["F"]["cycle"] == 833
                      and actual["frames"][0]["A"]["cycle"] == 834, "CALENDAR_F_A_SEAM")
            c.require(len(list(c.iter_jsonl(c.checked_descriptor(
                intake["artifacts"]["c9_sidecar"])))) == 836, "C9_SIDECAR_COVERAGE")
            report = {"intake": intake, "calendar": actual,
                      "unique_generator": c.artifact(SOFT / "pro_basis_r06_20261017/event_calendar/frame_plan_generator_candidate.py")}
        elif case_id == "C9_MATH_HISTORY_COMPLETE":
            request = _bundle_request(c, fixture, public)
            bundle = loaded["bundle"].build_bundle(request, out / "math")
            indexes = list(c.iter_jsonl(c.checked_descriptor(bundle["artifacts"]["row_index"])))
            advances = list(c.iter_jsonl(c.checked_descriptor(bundle["artifacts"]["advance_history"])))
            fx = list(c.iter_jsonl(c.checked_descriptor(bundle["artifacts"]["fx_history"])))
            c.require(len(indexes) == 7 and all(len(row["canonical_row"]["fields"]) == 74
                      and row["expected_pcm"] is None for row in indexes), "MATH_ROWS_LOST")
            c.require(any(row["cancel_raw"] == 1 and row["commit_observed_same_row"] == 0
                      for row in advances), "UNPUBLISHED_CANCELLED_ADVANCE_LOST")
            c.require(any(row["actual_effect_input"]["effect_input_left"] == 123
                      and row["expected_fx_input"] is None for row in fx), "FX_HISTORY_LOST")
            report = bundle
        elif case_id == "C9_MATH_INPUT_TAMPER_REJECT":
            request = _bundle_request(c, fixture, public)
            request["inputs"]["public_rows"]["sha256"] = "0" * 64
            descriptor_reject = _reject(
                lambda: loaded["bundle"].build_bundle(request, out / "math"),
                "FILE_BYTES_CHANGED")
            unrelated_raw = out / "UNRELATED_RAW.original"
            unrelated_raw.write_bytes(b"different independently hashed raw capture\n")
            request_raw = _bundle_request(c, fixture, public)
            request_raw["inputs"]["raw_capture"] = c.artifact(unrelated_raw)
            raw_reject = _reject(
                lambda: loaded["bundle"].build_bundle(request_raw, out / "math_raw_mismatch"),
                "BUNDLE_RAW_CAPTURE_MISMATCH")
            unrelated_reset = out / "UNRELATED_RESET.original"
            unrelated_reset.write_bytes(b"different independently hashed reset capture\n")
            request_reset = _bundle_request(c, fixture, public)
            request_reset["inputs"]["reset_edges"] = c.artifact(unrelated_reset)
            reset_reject = _reject(
                lambda: loaded["bundle"].build_bundle(request_reset, out / "math_reset_mismatch"),
                "BUNDLE_RESET_EDGES_MISMATCH")
            report = {"descriptor": descriptor_reject, "raw_link": raw_reject,
                      "reset_link": reset_reject}
        else:
            raise AssertionError(case_id)
    result = {"case_id": case_id, "status": "PASS",
              "scope": "NEW_C9_FILE_SEAMS_ONLY_NOT_REAL_AUTHORITY",
              "report": report, "real_verified": False, "board_release_allowed": False}
    c.write_json(out / "RESULT.json", result)
    return {"case_id": case_id, "status": "PASS"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=CASE_IDS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run_case(args.case, args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
