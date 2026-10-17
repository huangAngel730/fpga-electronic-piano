"""C9 -> explicit 61+TX projection, retaining canonical evidence separately."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
COMMON_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py")
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
STREAM_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r07_20261017/public_capture_tb/c9_completion_r01/c9_stream.py")
STREAM_SHA = "5584ab7201544a8d30bfdd7603a51483d1c5340ccc219e853df0d146d042ebef"
OLD_PATH = Path(__file__).resolve().parents[1] / "r07_fix/intake_r07_fix_candidate.py"
OLD_SHA = "d8bae7b015e1fd19a9e7af917c3b238f828833abaf0b227db25407faa534831d"
MAX_LEDGER_EVENT_OBSERVATIONS = 1_000_000
_COMMON = None


def support():
    global _COMMON
    if _COMMON is None:
        raw = COMMON_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
            raise ValueError("COMMON_SOURCE_CHANGED")
        module = ModuleType("_m3_c9_d4_common_intake")
        module.__file__ = str(COMMON_PATH)
        exec(compile(raw, str(COMMON_PATH), "exec"), module.__dict__)
        _COMMON = module
    return _COMMON


class _PreservedSink:
    """Only append storage changes; old analyzer state/validation stays intact."""
    def __init__(self, sink, stream):
        self.sink = sink
        self.stream = stream
        self.count = 0

    def append(self, value):
        self.stream.json_line(self.sink, value)
        self.count += 1


def _streaming_analyzer(old, preserved_sink):
    c = support()
    raw = OLD_PATH.read_bytes()
    c.require(hashlib.sha256(raw).hexdigest() == OLD_SHA, "LEGACY_INTAKE_SOURCE_CHANGED")
    tree = ast.parse(raw.decode("utf-8"), filename=str(OLD_PATH))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "analyze")
    count = 0
    for node in function.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "preserved_rows"
                and isinstance(node.value, ast.List) and not node.value.elts):
            node.value = ast.Name(id="_d4_preserved_sink", ctx=ast.Load())
            count += 1
    c.require(count == 1, "LEGACY_PRESERVED_SINK_PATCH_SHAPE")
    derived = ast.Module(body=[function], type_ignores=[])
    context = dict(old.__dict__)
    context["_d4_preserved_sink"] = preserved_sink
    exec(compile(ast.fix_missing_locations(derived), str(OLD_PATH), "exec"), context)
    return context["analyze"], {
        "source": c.artifact(OLD_PATH),
        "change": "one preserved_rows=[] initializer -> append-only JSONL sink",
        "validation_and_transaction_algorithm_changed": False,
        "derived_function_AST_sha256": hashlib.sha256(
            ast.dump(derived, include_attributes=False).encode("utf-8")).hexdigest()}


def project_row(row, old, d):
    """All dropped-from-projection data remains in canonical/sidecar artifacts."""
    m = d["pure"]
    fields = row["fields"]
    names = d["bridge"].REQUIRED_FIELDS
    values = {name: m.scalar(row["raw_ports"][name], spec)
              for name, spec in d["port_map"]["raw_ports"].items()}
    ext_names = ("obs_core_clk", "obs_polyphonic_valid", "obs_tx_metadata_valid",
                 "obs_tx_req_id_valid", "obs_tx_clip_mask", "obs_metadata_error",
                 "obs_frame_id_overflow", "uart_tx")
    extensions = {name: values[name] for name in ext_names}
    extensions.update(schema=old.EXTENSION_SCHEMA,
                      raw_tx_req_id_bits=row["raw_ports"]["obs_tx_req_id"])
    projected = {
        "schema": old.ROW_SCHEMA, "capture_id": row["capture_id"],
        "origin": row["origin"], "source": dict(row["source"]),
        "fields": {name: fields[name] for name in names
                   if name in old.EXPECTED_FIELD_NAMES},
        "extensions": extensions,
        "missing_reasons": {name: value for name, value in row["missing_reasons"].items()
                            if name in old.EXPECTED_FIELD_NAMES},
        "events": row["events"],
    }
    extra = {
        "source": row["source"],
        "fields_not_in_legacy_61": {name: fields[name] for name in names
                                  if name not in old.EXPECTED_FIELD_NAMES},
        "raw_ports": row["raw_ports"], "missing_reasons": row["missing_reasons"],
        "semantics": row["semantics"], "events": row["events"],
        "canonical_row_schema": row["schema"],
    }
    return projected, extra


def project_intake_files(public_rows_path, output_dir):
    c = support()
    stream = c.load_source(STREAM_PATH, STREAM_SHA)
    old = c.load_source(OLD_PATH, OLD_SHA)
    d = stream.dependencies()
    d["pure"] = d["c9_capture"].legacy_pure()
    d["stream"] = stream
    original = c.artifact(public_rows_path)
    out = c.output_directory(output_dir)
    projection = out / "DERIVED_PUBLIC_ROWS_61_TX.jsonl"
    extra_path = out / "C9_COMPLETE_SIDECAR.jsonl"
    preserved_path = out / "LEGACY_PRESERVED_ROWS.jsonl"
    count = 0
    event_observations = 0
    try:
        with projection.open("xb") as legacy_sink, extra_path.open("xb") as extra_sink:
            def rows():
                nonlocal count, event_observations
                for count, row in enumerate(stream.iter_public_rows(public_rows_path, d), 1):
                    event_observations += sum(row["fields"][name] != 0 for name in (
                        "frame_tick", "req_valid", "result_valid", "commit",
                        "cancel", "tx_sample_valid"))
                    c.require(event_observations <= MAX_LEDGER_EVENT_OBSERVATIONS,
                              "LEGACY_LEDGER_EVENT_CAPACITY")
                    derived, extra = project_row(row, old, d)
                    stream.json_line(legacy_sink, derived)
                    stream.json_line(extra_sink, extra)
                    yield derived
            with preserved_path.open("xb") as preserved_file:
                sink = _PreservedSink(preserved_file, stream)
                analyze, derivation = _streaming_analyzer(old, sink)
                ledger = analyze(rows())
                c.require(ledger["preserved_rows"] is sink, "PRESERVED_SINK_IDENTITY")
                c.require(sink.count == count, "PRESERVED_ROW_COVERAGE")
                ledger["preserved_rows"] = []
        c.checked_descriptor(original, allow_external=True)
        ledger["preserved_rows_storage"] = "EXTERNAL_JSONL_NO_ROWS_DROPPED"
        ledger["preserved_rows_ref"] = c.artifact(preserved_path)
        ledger["canonical_c9_rows"] = original
        ledger["c9_complete_sidecar"] = c.artifact(extra_path)
        ledger["derived_legacy_rows"] = c.artifact(projection)
        ledger["projection_is_not_independent_evidence"] = True
        ledger["derivation"] = derivation
        c.write_json(out / "INTAKE_LEDGER.json", ledger)
        result = {
            "schema": "M3_D4_C9_INTAKE_ADAPTER_RECEIPT_V1",
            "status": "DERIVED_LEDGER_PENDING_REAL_PLAN_AND_AUTHORITY",
            "canonical_rows": original, "row_count": count,
            "artifacts": {"ledger": c.artifact(out / "INTAKE_LEDGER.json"),
                          "legacy_rows": c.artifact(projection),
                          "c9_sidecar": c.artifact(extra_path),
                          "preserved_rows": c.artifact(preserved_path)},
            "pending": ledger["pending_reasons"],
            "ledger_event_observations": event_observations,
            "ledger_event_capacity": MAX_LEDGER_EVENT_OBSERVATIONS,
            "legacy_d3_projection_status": "PENDING_UNSUPPORTED_PROFILE",
            "plan_generated": False, "real_verified": False, "board_release_allowed": False}
        c.write_json(out / "RECEIPT.json", result)
        return result
    except BaseException as error:
        c.write_json(out / "FAILURE.json", {
            "status": "REJECT_PARTIAL_ARTIFACTS_RETAINED",
            "error": type(error).__name__ + ":" + str(error),
            "canonical_rows": original, "real_verified": False})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-rows", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = project_intake_files(args.public_rows, args.output)
    print(json.dumps({"status": result["status"], "rows": result["row_count"]}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
