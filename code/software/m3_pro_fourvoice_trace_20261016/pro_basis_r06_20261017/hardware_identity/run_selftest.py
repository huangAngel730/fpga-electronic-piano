#!/usr/bin/env python3
"""Run the single frozen pure-software self-test group for hardware_identity."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from hardware_identity import ValidationError, validate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_scope(scope: dict[str, Any], repo_root: Path, output: Path) -> None:
    if scope.get("schema_version") != "hardware-identity-selftest-scope-v1":
        raise RuntimeError("unsupported self-test scope")
    if scope.get("group_count") != 1 or scope.get("timeout_seconds") != 90:
        raise RuntimeError("scope must freeze one group with a 90 second limit")
    frozen_output = (repo_root / scope["output_directory"]).resolve()
    if output.resolve() != frozen_output:
        raise RuntimeError("output directory differs from frozen scope")
    for item in scope["inputs"]:
        path = (repo_root / item["path"]).resolve()
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise RuntimeError(f"frozen input mismatch: {item['path']}")


def make_complete_fixture(
    pending: dict[str, Any], index: dict[str, Any], repo_root: Path, output: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = copy.deepcopy(pending)
    record["record_id"] = "fixture-complete-observed"
    record["fixture_only"] = True
    record["unit_id"] = "SELFTEST_UNIT"
    record["session_id"] = "SELFTEST_SESSION"
    physical_dir = output / "fixture_evidence"
    physical_dir.mkdir(parents=True)
    fixture_payloads = {
        "fixture_photo": ("PHYSICAL_PHOTO", b"SELFTEST FIXTURE PHOTO BYTES\n"),
        "fixture_measurement": (
            "RAW_MEASUREMENT_CSV",
            b"test_point,voltage_v,unit\nBANK3,3.30,V\nBANK4,3.30,V\nBANK5,3.30,V\nMIDI,3.30,V\n",
        ),
        "fixture_continuity": (
            "CONTINUITY_LOG",
            b"SELFTEST continuity only: GND,BCK,WS,DIN,PA_EN\n",
        ),
        "fixture_waveform": (
            "WAVEFORM_CSV",
            b"sample,bck,ws,din,pa_en\n0,0,0,0,1\n1,1,0,1,1\n",
        ),
        "fixture_tool_binary": ("TOOL_FILE_IDENTITY", b"SELFTEST TOOL IDENTITY\n"),
        "fixture_tool_runtime": ("TOOL_RUNTIME_RECEIPT", b"SELFTEST RUNTIME OK NO SECRET\n"),
    }
    sources = copy.deepcopy(index["sources"])
    for source_id, (kind, payload) in fixture_payloads.items():
        path = physical_dir / f"{source_id}.dat"
        path.write_bytes(payload)
        sources.append(
            {
                "id": source_id,
                "kind": kind,
                "path": path.relative_to(repo_root).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "applicability": "SELFTEST_ONLY",
                "authority": "synthetic validator fixture; never production evidence",
                "fixture_only": True,
                "unit_id": "SELFTEST_UNIT",
                "session_id": "SELFTEST_SESSION",
                "captured_at": "2026-10-17T00:00:00+08:00",
                "raw_metadata": {"generator": "run_selftest.py", "synthetic": True},
            }
        )
    fixture_index = {"schema_version": "hardware-evidence-index-v1", "sources": sources}

    for claim in record["identity"].values():
        claim.update(status="OBSERVED", value="SELFTEST_MARKING", evidence=["fixture_photo"])
    for bank in record["banks"]:
        bank["measurement"] = {
            "status": "OBSERVED",
            "value": {
                "voltage_v": 3.3,
                "unit": "V",
                "test_point": f"SELFTEST_BANK{bank['bank']}",
                "ground_reference": "SELFTEST_GND",
                "instrument": "SELFTEST_DMM",
                "range": "6V",
                "captured_at": "2026-10-17T00:00:00+08:00",
            },
            "evidence": ["fixture_measurement"],
            "note": "synthetic self-test measurement",
        }
        bank["assessment"] = "MATCH"
    for name, value in {
        "direction": "ADAPTER_OUTPUT_TO_FPGA_INPUT",
        "fpga_side_voltage": {
            "idle_v": 3.3,
            "high_v": 3.3,
            "low_v": 0.0,
            "unit": "V",
            "connector_pin": "SELFTEST_J22_5"
        },
        "common_ground": True,
    }.items():
        evidence = ["fixture_continuity"] if name == "common_ground" else ["fixture_measurement"]
        record["midi_input"][name] = {
            "status": "OBSERVED",
            "value": value,
            "evidence": evidence,
            "note": "synthetic self-test measurement",
        }
    audio_values = {
        "pt8211_identity": {
            "value": {"component": "PT8211", "reference_designator": "U6", "marking": "SELFTEST"},
            "evidence": ["fixture_photo"],
        },
        "serial_wiring": {
            "value": {"bck": "E22", "ws": "F24", "din": "G24", "method": "SELFTEST_CONTINUITY"},
            "evidence": ["fixture_continuity"],
        },
        "pa_path": {
            "value": {"component": "XPT4809", "enable_pin": "H17", "enable_polarity": "HIGH_TO_WORK", "method": "SELFTEST_WAVEFORM"},
            "evidence": ["fixture_waveform"],
        },
        "safe_load": {
            "value": {"connector": "J29", "load_type": "SELFTEST_HEADPHONE", "rated_impedance": "32ohm"},
            "evidence": ["fixture_photo"],
        },
    }
    for name, payload in audio_values.items():
        record["audio_path"][name] = {
            "status": "OBSERVED",
            "value": payload["value"],
            "evidence": payload["evidence"],
            "note": "synthetic self-test evidence",
        }
    for tool in record["commercial_tools"]:
        tool["binary_identity"] = {
            "status": "OBSERVED",
            "value": {
                "path": "SELFTEST/tool.exe",
                "bytes": 23,
                "sha256": "1" * 64,
                "version": "SELFTEST-1.0"
            },
            "evidence": ["fixture_tool_binary"],
            "note": "synthetic self-test identity",
        }
        tool["runtime_license"] = {
            "status": "OBSERVED",
            "value": {
                "status": "AVAILABLE",
                "command": ["SELFTEST", "--probe"],
                "exit_code": 0,
                "captured_at": "2026-10-17T00:00:00+08:00"
            },
            "evidence": ["fixture_tool_runtime"],
            "note": "synthetic receipt without license material",
        }
    return record, fixture_index


def mutate_missing(record: dict[str, Any], _: dict[str, Any]) -> None:
    del record["identity"]["dock_revision"]


def mutate_wrong_board(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["board_family"] = "TANG_MEGA_138K_C"


def mutate_voltage_conflict(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["banks"][1]["assessment"] = "CONFLICT"


def mutate_fake_measurement(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["banks"][0]["measurement"] = {
        "status": "OBSERVED",
        "value": {
            "voltage_v": 3.3,
            "unit": "V",
            "test_point": "PDF_ONLY",
            "ground_reference": "PDF_ONLY",
            "instrument": "NONE",
            "range": "NONE",
            "captured_at": "2026-10-17T00:00:00+08:00",
        },
        "evidence": ["pro_core_schematic_4072"],
        "note": "must reject reference-only observation",
    }


def mutate_incomplete_measurement(record: dict[str, Any], _: dict[str, Any]) -> None:
    del record["banks"][0]["measurement"]["value"]["instrument"]


def mutate_sensitive(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["commercial_tools"][0]["license_server"] = "prohibited-example"


def mutate_stale_sha(_: dict[str, Any], index: dict[str, Any]) -> None:
    index["sources"][0]["sha256"] = "0" * 64


def mutate_release(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["board_release_allowed"] = True


def mutate_not_applicable(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["identity"]["chip_stepping"]["status"] = "NOT_APPLICABLE"


def mutate_duplicate_bank(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["banks"][2]["bank"] = 4


def mutate_fixture_into_production(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["fixture_only"] = False


def mutate_other_session(_: dict[str, Any], index: dict[str, Any]) -> None:
    for source in index["sources"]:
        if source["id"] == "fixture_photo":
            source["session_id"] = "OTHER_SESSION"


def mutate_midi_shape(record: dict[str, Any], _: dict[str, Any]) -> None:
    del record["midi_input"]["fpga_side_voltage"]["value"]["connector_pin"]


def mutate_sensitive_index(_: dict[str, Any], index: dict[str, Any]) -> None:
    index["sources"][0]["access_token"] = "prohibited-example"


def mutate_nonfinite_voltage(record: dict[str, Any], _: dict[str, Any]) -> None:
    record["banks"][0]["measurement"]["value"]["voltage_v"] = float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repair-after", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    scope = load_json(args.scope)
    verify_scope(scope, repo_root, args.output)
    output = args.output.resolve()
    if output.exists():
        if not args.repair_after or not args.repair_after.resolve().is_file():
            raise RuntimeError("existing output requires a preserved --repair-after receipt")
        execution_output = output / "ATTEMPT_02_REPAIRED"
        if execution_output.exists():
            raise RuntimeError("repaired attempt output already exists; refusing to overwrite")
        execution_output.mkdir(parents=True)
    else:
        output.mkdir(parents=True)
        execution_output = output
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    pending_path = repo_root / scope["production_record"]
    index_path = repo_root / scope["evidence_index"]
    pending = load_json(pending_path)
    index = load_json(index_path)
    complete, fixture_index = make_complete_fixture(
        pending, index, repo_root, execution_output
    )
    cases: list[tuple[str, dict[str, Any], dict[str, Any], bool, str | None]] = [
        ("pending_production_record", pending, index, False, None),
        ("complete_synthetic_fixture", complete, fixture_index, True, None),
    ]
    negative: list[tuple[str, Callable[[dict[str, Any], dict[str, Any]], None], str]] = [
        ("missing_required_field", mutate_missing, "missing required field"),
        ("wrong_board_type", mutate_wrong_board, "wrong board_family"),
        ("voltage_conflict", mutate_voltage_conflict, "voltage conflict"),
        ("fake_measurement_from_schematic", mutate_fake_measurement, "reference evidence only"),
        ("incomplete_measurement", mutate_incomplete_measurement, "missing required field"),
        ("sensitive_field", mutate_sensitive, "sensitive field prohibited"),
        ("stale_source_sha", mutate_stale_sha, "sha256 mismatch"),
        ("release_authority_escalation", mutate_release, "cannot grant board release"),
        ("mandatory_not_applicable", mutate_not_applicable, "cannot be NOT_APPLICABLE"),
        ("duplicate_bank", mutate_duplicate_bank, "exactly one each"),
        ("fixture_mixed_into_production", mutate_fixture_into_production, "fixture evidence prohibited"),
        ("different_physical_session", mutate_other_session, "different physical unit/session"),
        ("malformed_midi_value", mutate_midi_shape, "missing required field"),
        ("sensitive_index_field", mutate_sensitive_index, "sensitive field prohibited"),
        ("nonfinite_voltage", mutate_nonfinite_voltage, "numeric voltage in V"),
    ]
    for name, mutator, phrase in negative:
        record = copy.deepcopy(complete)
        evidence_index = copy.deepcopy(fixture_index)
        mutator(record, evidence_index)
        cases.append((name, record, evidence_index, True, phrase))

    results = []
    failures = []
    for name, record, evidence_index, allow_fixture, reject_phrase in cases:
        case_started = time.monotonic()
        actual = "ACCEPTED"
        detail = ""
        exit_code = 0
        try:
            validated = validate(record, evidence_index, repo_root, allow_fixture)
            detail = validated["result"]
        except ValidationError as exc:
            actual = "REJECTED"
            detail = str(exc)
            exit_code = 2
        expected = "REJECTED" if reject_phrase else "ACCEPTED"
        passed = actual == expected and (not reject_phrase or reject_phrase in detail)
        if not passed:
            failures.append(name)
        results.append(
            {
                "case": name,
                "expected": expected,
                "actual": actual,
                "detail": detail,
                "exit_code": exit_code,
                "passed": passed,
                "elapsed_seconds": round(time.monotonic() - case_started, 6),
            }
        )

    elapsed = time.monotonic() - started
    if elapsed > scope["timeout_seconds"]:
        failures.append("GROUP_TIMEOUT")
    report = {
        "schema_version": "hardware-identity-selftest-result-v1",
        "group": "RUN_01",
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 6),
        "timeout_seconds": scope["timeout_seconds"],
        "python": sys.executable,
        "python_version": platform.python_version(),
        "case_count": len(results),
        "cases": results,
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "group_exit_code": 0 if not failures else 1,
    }
    write_json(execution_output / "SELFTEST_RESULT.json", report)
    if execution_output != output:
        write_json(output / "FINAL_SELFTEST_RESULT.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report["group_exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
