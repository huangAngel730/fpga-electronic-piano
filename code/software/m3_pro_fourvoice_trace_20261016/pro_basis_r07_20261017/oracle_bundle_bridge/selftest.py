"""Bounded synthetic checks for the R07 oracle bundle bridge."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def descriptor(role: str, path: Path, root: Path) -> dict[str, Any]:
    return {
        "role": role,
        "path": path.resolve().relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def line_index_sha256(path: Path) -> str:
    payload = b"".join(
        str(line_number).encode("ascii")
        + b":"
        + hashlib.sha256(raw).hexdigest().encode("ascii")
        + b"\n"
        for line_number, raw in enumerate(path.read_bytes().splitlines(), start=1)
    )
    return hashlib.sha256(payload).hexdigest()


def bind_trace(
    base: dict[str, Any],
    trace: Path,
    root: Path,
    binding_path: Path,
) -> dict[str, Any]:
    result = copy.deepcopy(base)
    trace_desc = descriptor("normalized_trace", trace, root)
    plan_desc = next(item for item in result["inputs"] if item["role"] == "midi_plan")
    frame_desc = next(item for item in result["inputs"] if item["role"] == "frame_plan")
    capture_binding = {
        "schema": "M3_R07_ORACLE_BRIDGE_CAPTURE_BINDING_V1",
        "trace": {
            "sha256": trace_desc["sha256"],
            "bytes": trace_desc["bytes"],
            "row_count": len(trace.read_bytes().splitlines()),
            "line_index_sha256": line_index_sha256(trace),
        },
        "input_plan_sha256": plan_desc["sha256"],
        "frame_plan_sha256": frame_desc["sha256"],
        "record_schema_sha256": next(
            item["sha256"]
            for item in result["inputs"]
            if item["role"] == "r7a_record_schema"
        ),
        "authority": "SYNTHETIC_FIXTURE_ONLY",
        "real_capture_authenticated": False,
    }
    write_json(binding_path, capture_binding)
    binding_desc = descriptor("normalized_binding", binding_path, root)
    result["inputs"] = [
        item
        for item in result["inputs"]
        if item["role"] not in {"normalized_trace", "normalized_binding"}
    ]
    result["inputs"].extend([trace_desc, binding_desc])
    return result


def run_case(
    cli: Path,
    root: Path,
    case_root: Path,
    binding: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    binding_path = case_root / "binding.json"
    write_json(binding_path, binding)
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(cli),
            "--binding",
            str(binding_path),
            "--root",
            str(root),
            "--output",
            str(case_root / "bundle"),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    (case_root / "stdout.bin").write_bytes(process.stdout)
    (case_root / "stderr.bin").write_bytes(process.stderr)
    stream = process.stdout if process.returncode == 0 else process.stderr
    payload = json.loads(stream.decode("utf-8").strip().splitlines()[-1])
    return process.returncode, payload


def write_r7a_trace(
    source: Path,
    destination: Path,
    capture_id: str,
    required_fields: list[str],
    mutation: str,
) -> None:
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    if mutation == "hold_startup":
        target = next(row for row in rows if row["tx_sample_valid"] == 1)
        target["tx_hold"] = 1
        target["tx_startup_zero"] = 1
    elif mutation == "unknown_handshake":
        rows[10]["req_valid"] = "x"
        rows[10]["req_ready"] = 1
        rows[10]["req_id"] = 77
        rows[10]["advance_mask"] = "z"
    elif mutation == "missing_hold":
        rows[0].pop("tx_hold")
    elif mutation == "cycle_regression":
        rows[1]["cycle"] = rows[0]["cycle"]
    elif mutation == "drop_non_frame":
        target = next(
            index
            for index, row in enumerate(rows)
            if row["frame_tick"] == 0 and row["finish"] == 0 and index > 1
        )
        del rows[target]
    else:
        if mutation != "none":
            raise AssertionError("unknown mutation " + mutation)
    event_names = {
        "FRAME": "FRAME_F",
        "REQUEST": "ACCEPT_A",
        "RETURN": "RESULT_TRANSFER",
        "COMMIT": "COMMIT",
        "TX": "TX_ADOPT",
        "FINISH": "FINISH",
    }
    source_sha = sha256(source)
    records = []
    for line_number, row in enumerate(rows, start=1):
        fields = {name: row[name] for name in required_fields if name in row}
        raw_req_id = fields.get("tx_req_id")
        if type(raw_req_id) is int:
            raw_req_bits = format(raw_req_id & 0xFFFFFFFF, "032b")
        elif type(raw_req_id) is str and len(raw_req_id) <= 32:
            raw_req_bits = raw_req_id.rjust(32, "x")
        else:
            raw_req_bits = "x" * 32
        events = []
        for name in row.get("_event_order", []):
            mapped = event_names.get(name)
            if mapped is not None and mapped not in events:
                events.append(mapped)
        records.append(
            {
                "schema": "M3_R7A_PUBLIC_ROW_V1",
                "capture_id": capture_id,
                "origin": "SYNTHETIC_SCHEMA_FIXTURE",
                "source": {
                    "raw_sha256": source_sha,
                    "reset_edges_sha256": source_sha,
                    "line": line_number,
                    "cycle": fields.get("cycle"),
                    "epoch": fields.get("epoch"),
                    "time_ps": fields.get("cycle", 0) * 25000,
                    "sampling_phase": "POSEDGE_PRE_NBA",
                },
                "fields": fields,
                "extensions": {
                    "schema": "M3_R7A_TX_EXTENSION_V1",
                    "obs_core_clk": 1,
                    "obs_polyphonic_valid": 1,
                    "obs_tx_metadata_valid": fields.get("tx_sample_valid", 0),
                    "obs_tx_req_id_valid": fields.get("tx_sample_valid", 0),
                    "obs_tx_clip_mask": fields.get("tx_clip", 0),
                    "obs_metadata_error": 0,
                    "obs_frame_id_overflow": 0,
                    "uart_tx": 1,
                    "raw_tx_req_id_bits": raw_req_bits,
                },
                "missing_reasons": row.get("_missing_reasons", {}),
                "events": events,
            }
        )
    destination.write_text(
        "".join(
            json.dumps(record, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    root = Path(spec["cwd"]).resolve()
    cli = root / spec["cli"]
    base = copy.deepcopy(spec["binding"])
    args.output.mkdir(parents=True, exist_ok=False)
    fixture_desc = spec["fixture_source_trace"]
    base_trace = root / fixture_desc["path"]
    if (
        base_trace.stat().st_size != fixture_desc["bytes"]
        or sha256(base_trace) != fixture_desc["sha256"]
    ):
        raise AssertionError("fixture source identity")
    schema_desc = next(
        item for item in base["inputs"] if item["role"] == "r7a_record_schema"
    )
    record_schema = json.loads(
        (root / schema_desc["path"]).read_text(encoding="utf-8")
    )
    required_fields = record_schema["properties"]["fields"]["required"]
    results = []

    for case in cases:
        case_root = args.output / case["name"]
        case_root.mkdir()
        binding = copy.deepcopy(base)
        mutation = case["mutation"]
        trace = case_root / "PUBLIC_ROWS.jsonl"
        if mutation in {
            "none", "hold_startup", "unknown_handshake", "missing_hold",
            "cycle_regression",
        }:
            write_r7a_trace(
                base_trace, trace, binding["capture_id"], required_fields, mutation
            )
            binding = bind_trace(binding, trace, root, case_root / "capture_binding.json")
        elif mutation == "drop_non_frame":
            write_r7a_trace(
                base_trace, trace, binding["capture_id"], required_fields, "none"
            )
            binding = bind_trace(binding, trace, root, case_root / "capture_binding.json")
            write_r7a_trace(
                base_trace, trace, binding["capture_id"], required_fields, mutation
            )
            replacement = descriptor("normalized_trace", trace, root)
            binding["inputs"] = [
                replacement if item["role"] == "normalized_trace" else item
                for item in binding["inputs"]
            ]
        elif mutation == "tampered_sha":
            write_r7a_trace(
                base_trace, trace, binding["capture_id"], required_fields, "none"
            )
            binding = bind_trace(binding, trace, root, case_root / "capture_binding.json")
            target = next(item for item in binding["inputs"] if item["role"] == "normalized_trace")
            target["sha256"] = "0" * 64
        else:
            raise AssertionError("unknown mutation " + mutation)

        exit_code, payload = run_case(cli, root, case_root, binding)
        if exit_code != case["expected_exit"]:
            raise AssertionError((case["name"], exit_code, payload))
        if payload["status"] != case["expected_status"]:
            raise AssertionError((case["name"], payload))
        if "error_contains" in case and case["error_contains"] not in payload.get("error", ""):
            raise AssertionError((case["name"], payload))
        if exit_code == 0:
            bundle_root = case_root / "bundle"
            bundle = json.loads((bundle_root / "BUNDLE.json").read_text(encoding="utf-8"))
            gaps = json.loads((bundle_root / "CONTRACT_GAPS.json").read_text(encoding="utf-8"))
            index = [json.loads(line) for line in (bundle_root / "ROW_INDEX.jsonl").read_text(encoding="utf-8").splitlines()]
            if bundle["row_count"] != 99 or len(index) != 99:
                raise AssertionError((case["name"], "row count"))
            if gaps["legacy_b0_status"] != "PENDING_UNSUPPORTED_PROFILE":
                raise AssertionError((case["name"], "legacy profile was not held pending"))
            copied_trace = next(item for item in bundle["inputs"] if item["role"] == "normalized_trace")
            if not copied_trace["byte_exact"]:
                raise AssertionError((case["name"], "raw trace was not byte exact"))
            delayed = [
                item
                for item in index
                if item["midi_event_association"]["status"]
                == "PLAN_PAYLOAD_UNIQUE_OUTSIDE_ARRIVAL_WINDOW"
            ]
            if not delayed:
                raise AssertionError("backpressure-delayed event association was lost")
            if mutation == "hold_startup":
                tx = [item["tx"] for item in index if item["tx"]["sample_valid"] == 1]
                if not any(item["hold"] == 1 and item["startup_zero"] == 1 for item in tx):
                    raise AssertionError("HOLD/startup metadata lost")
            if mutation == "unknown_handshake":
                unknown_rows = [item for item in index if item["request_a"] is None]
                if not unknown_rows or "REQUEST_A_UNKNOWN" not in unknown_rows[0]["signals"]:
                    raise AssertionError("unknown request handshake collapsed")
                if unknown_rows[0]["common_advance"] is not None:
                    raise AssertionError("unknown advance mask collapsed")
        results.append(
            {
                "name": case["name"],
                "exit_code": exit_code,
                "status": payload["status"],
                "error": payload.get("error"),
            }
        )

    summary = {
        "schema": "M3_R07_ORACLE_BRIDGE_SELFTEST_V1",
        "status": "PASS",
        "cases": results,
        "case_count": len(results),
        "accepted": sum(item["exit_code"] == 0 for item in results),
        "rejected": sum(item["exit_code"] != 0 for item in results),
        "real_capture_cases": 0,
        "m1_math_or_oracle_runs": 0,
        "hdl_eda_hardware_runs": 0,
        "board_release_allowed": False,
    }
    write_json(args.output / "SELFTEST_RESULT.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
