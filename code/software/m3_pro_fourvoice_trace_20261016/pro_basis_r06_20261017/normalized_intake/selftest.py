"""One bounded software group for the R06 normalized intake CLI."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_trace(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")


def make_rows(fields: list[str]) -> list[dict]:
    rows = []
    for cycle in range(836):
        row = {name: 0 for name in fields}
        row.update({
            "cycle": cycle,
            "epoch": 0,
            "rst_n": 0 if cycle == 0 else 1,
            "pll_locked": 0 if cycle == 0 else 1,
            "audio_stable": 0 if cycle == 0 else 1,
            "pa_en": 0 if cycle == 0 else 1,
            "frame_tick": int(cycle in (1, 834)),
            "finish": int(cycle == 835),
            "_b2": {"req_payload": 0, "lane_tick": 0, "lane": 0, "lane_req_id": 0},
        })
        if cycle == 0:
            row["_event_order"] = ["RESET"]
        elif cycle == 1:
            row.update({"req_valid": 1, "req_ready": 1, "req_id": 7})
            row["_b2"]["req_payload"] = 0x1234
            row["_event_order"] = ["FRAME", "REQUEST"]
        elif cycle == 2:
            row.update({"advance_mask": 15, "advance_frame_req_id": 7})
        elif cycle == 3:
            row.update({
                "result_valid": 1,
                "result_ready": 1,
                "result_id": 7,
                "result_left": 100,
                "result_right": -100,
                "result_clip_mask": 0,
            })
            row["_event_order"] = ["RETURN"]
        elif cycle == 4:
            row.update({
                "commit": 1,
                "commit_id": 7,
                "commit_left": 100,
                "commit_right": -100,
                "commit_clip": 0,
            })
            row["_event_order"] = ["COMMIT"]
        elif cycle == 834:
            row.update({
                "tx_sample_valid": 1,
                "tx_frame_id": 1,
                "tx_req_id": 7,
                "tx_left": 100,
                "tx_right": -100,
                "tx_clip": 0,
                "tx_hold": 0,
                "tx_startup_zero": 0,
            })
            row["_event_order"] = ["FRAME", "TX"]
        elif cycle == 835:
            row["_event_order"] = ["FINISH"]
        rows.append(row)
    return rows


def base_binding(trace: Path, references: list[dict]) -> dict:
    return {
        "schema": "M3_R06_NORMALIZED_INTAKE_BINDING_V1",
        "trace": {"path": str(trace), "sha256": "0" * 64},
        "references": references,
        "provenance": {
            "kind": "SYNTHETIC_FIXTURE",
            "authority_verified": True,
            "source_manifest_sha256": "1" * 64,
            "source_rom_sha256": "2" * 64,
            "input_plan_sha256": "3" * 64,
            "reason": "bounded synthetic selftest; not a Pro capture",
        },
        "contracts": {
            "same_edge_order_frozen": True,
            "same_edge_priority": ["RESET", "FRAME", "CANCEL", "REQUEST", "RETURN", "COMMIT", "TX", "FINISH"],
            "frame_plan_frozen": True,
            "frame_plan": [
                {"cycle": 1, "epoch": 0, "frame_id": 0},
                {"cycle": 834, "epoch": 0, "frame_id": 1},
            ],
            "finish_contract_frozen": True,
        },
        "projection": {"clip_reduce": "OR", "d3_mapping_frozen": True, "expected_lane_mask": 15},
        "upstream_dependencies": {
            "source_target_audit": "READY",
            "midi_stimulus": "READY",
            "m2_public_capture_contract": "READY",
        },
    }


def run_case(
    cli: Path,
    case_dir: Path,
    rows: list[dict],
    binding: dict,
    bad_trace_sha: bool = False,
) -> tuple[int, dict, str, str]:
    case_dir.mkdir(parents=True)
    trace = case_dir / "trace.jsonl"
    write_trace(trace, rows)
    binding["trace"] = {"path": str(trace.resolve()), "sha256": sha256(trace)}
    if bad_trace_sha:
        binding["trace"]["sha256"] = "0" * 64
    binding_path = case_dir / "binding.json"
    write_json(binding_path, binding)
    output = case_dir / "output"
    process = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(cli), "--binding", str(binding_path), "--output", str(output)],
        cwd=cli.parents[5],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    stdout = process.stdout.decode("utf-8")
    stderr = process.stderr.decode("utf-8")
    (case_dir / "stdout.bin").write_bytes(process.stdout)
    (case_dir / "stderr.bin").write_bytes(process.stderr)
    payload = json.loads((stdout if process.returncode == 0 else stderr).strip().splitlines()[-1])
    return process.returncode, payload, stdout, stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    cli = Path(spec["cli"]).resolve()
    contract = next(item for item in spec["references"] if item["role"] == "observation_contract")
    fields = [item["name"] for item in json.loads(Path(contract["path"]).read_text(encoding="utf-8"))["fields"]]
    args.output.mkdir(parents=True)
    results = []
    for case in cases:
        name = case["name"]
        rows = make_rows(fields)
        case_root = args.output / name
        trace_placeholder = case_root / "trace.jsonl"
        binding = base_binding(trace_placeholder, copy.deepcopy(spec["references"]))
        mutation = case["mutation"]
        if mutation == "pending_contracts":
            binding["provenance"].update({
                "kind": "DECLARED_REAL_PENDING_M2",
                "authority_verified": False,
                "source_manifest_sha256": None,
                "source_rom_sha256": None,
                "input_plan_sha256": None,
                "reason": "source_target_audit, midi_stimulus and M2-R6-1 are pending",
            })
            binding["contracts"].update({
                "same_edge_order_frozen": False,
                "same_edge_priority": None,
                "frame_plan_frozen": False,
                "frame_plan": None,
                "finish_contract_frozen": False,
            })
            binding["projection"]["d3_mapping_frozen"] = False
            binding["upstream_dependencies"] = {
                "source_target_audit": "PENDING",
                "midi_stimulus": "PENDING_IN_PROGRESS",
                "m2_public_capture_contract": "PENDING",
            }
        elif mutation == "idle_x":
            rows[10]["_b2"]["lane"] = "x"
            rows[10]["_b2_reasons"] = {"lane": "idle monitor lane is unknown"}
        elif mutation == "controlled_x":
            rows[10]["req_valid"] = "x"
            rows[10]["_missing_reasons"] = {"req_valid": "injected active control unknown"}
        elif mutation == "wrong_id":
            rows[3]["result_id"] = 8
        elif mutation == "wrong_epoch":
            rows[10]["epoch"] = 1
        elif mutation == "dropped_line":
            del rows[10]
        elif mutation == "same_edge_order":
            rows[1]["_event_order"] = ["REQUEST", "FRAME"]
        elif mutation == "bad_provenance":
            pass
        elif mutation == "finish_eof":
            rows[835]["finish"] = 0
            rows[835].pop("_event_order")
        elif mutation == "frame_plan_pending":
            binding["contracts"]["frame_plan_frozen"] = False
            binding["contracts"]["frame_plan"] = None
            binding["projection"]["d3_mapping_frozen"] = False
        elif mutation == "frame_drop":
            rows[834]["frame_tick"] = 0
            rows[834]["_event_order"] = ["TX"]
        elif mutation == "finish_pending":
            binding["contracts"]["finish_contract_frozen"] = False
            rows[835]["finish"] = 0
            rows[835].pop("_event_order")
            binding["projection"]["d3_mapping_frozen"] = False
        elif mutation == "cancel_active":
            rows[2].update({"advance_mask": 0, "advance_frame_req_id": 0,
                            "cancel": 1, "cancel_reason": 99,
                            "_event_order": ["CANCEL"]})
            rows[3].update({"result_valid": 0, "result_ready": 0,
                            "result_id": 0, "result_left": 0,
                            "result_right": 0, "result_clip_mask": 0})
            rows[3].pop("_event_order")
            rows[4].update({"commit": 0, "commit_id": 0,
                            "commit_left": 0, "commit_right": 0,
                            "commit_clip": 0})
            rows[4].pop("_event_order")
            rows[834].update({"tx_sample_valid": 0, "tx_frame_id": 0,
                              "tx_req_id": 0, "tx_left": 0,
                              "tx_right": 0, "tx_clip": 0,
                              "_event_order": ["FRAME"]})
        elif mutation == "cancel_without_active":
            rows[1].update({"req_valid": 0, "req_ready": 0, "req_id": 0,
                            "_event_order": ["FRAME"]})
            rows[1]["_b2"]["req_payload"] = 0
            rows[2].update({"advance_mask": 0, "advance_frame_req_id": 0,
                            "cancel": 1, "cancel_reason": 99,
                            "_event_order": ["CANCEL"]})
        else:
            if mutation != "none":
                raise ValueError("unknown mutation " + mutation)

        code, payload, stdout, stderr = run_case(
            cli,
            case_root,
            rows,
            binding,
            bad_trace_sha=mutation == "bad_provenance",
        )

        expected_exit = case["expected_exit"]
        if code != expected_exit:
            raise AssertionError(f"{name}: exit {code} expected {expected_exit}: {payload}")
        if expected_exit == 0:
            pending = set(payload["pending"])
            if not set(case.get("expected_pending", [])) <= pending:
                raise AssertionError(f"{name}: pending {pending}")
            output = case_root / "output"
            if case.get("expect_b2_csv") is not None:
                if (output / "B2_PUBLIC.csv").is_file() != case["expect_b2_csv"]:
                    raise AssertionError(f"{name}: b2 csv presence")
            if case.get("expect_d3") is not None:
                if (output / "D3.jsonl").is_file() != case["expect_d3"]:
                    raise AssertionError(f"{name}: d3 presence")
            if case.get("expect_cancel_req_id") is not None:
                d3_rows = [
                    json.loads(line)
                    for line in (output / "D3.jsonl").read_text(encoding="utf-8").splitlines()
                ]
                cancel_ids = [row["req_id"] for row in d3_rows if row["kind"] == "CANCEL"]
                if cancel_ids != [case["expect_cancel_req_id"]]:
                    raise AssertionError(f"{name}: cancel ids {cancel_ids}")
        else:
            if case["failure_contains"] not in payload.get("first_failure", ""):
                raise AssertionError(f"{name}: wrong failure {payload}")
        results.append({
            "name": name,
            "exit_code": code,
            "status": payload["status"],
            "pending": payload.get("pending", []),
            "first_failure": payload.get("first_failure"),
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        })

    summary = {
        "schema": "M3_R06_NORMALIZED_INTAKE_SELFTEST_V1",
        "status": "PASS",
        "cases": results,
        "case_count": len(results),
        "accepted": sum(item["exit_code"] == 0 for item in results),
        "rejected": sum(item["exit_code"] != 0 for item in results),
        "functional_scope": "new Python normalization only",
        "old_checkers_or_mappers_run": 0,
        "hdl_eda_hardware_runs": 0,
        "pro_dut_pass": False,
        "board_release_allowed": False,
    }
    write_json(args.output / "SELFTEST_RESULT.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
