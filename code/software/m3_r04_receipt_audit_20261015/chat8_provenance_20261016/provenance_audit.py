"""Read-only provenance audit for the night R05 A-to-C evidence chain."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import zipfile


class AuditError(ValueError):
    """Raised when a required provenance relation is not true."""


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise AuditError(diagnostic)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise AuditError(f"NONFINITE_JSON:{path}:{value}")

    with path.open(encoding="utf-8") as stream:
        return json.load(
            stream,
            object_pairs_hook=_unique_object,
            parse_constant=reject_constant,
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"MISSING_FILE:{path}")
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_identity(item: Any, expected_path: Path | None = None) -> Path:
    require(type(item) is dict, "IDENTITY_NOT_OBJECT")
    require(set(item) >= {"path", "bytes", "sha256"}, "IDENTITY_FIELDS")
    path = Path(item["path"])
    if expected_path is not None:
        require(path.resolve() == expected_path.resolve(), "IDENTITY_PATH_MISMATCH")
    actual = identity(path)
    require(type(item["bytes"]) is int, "IDENTITY_BYTES_TYPE")
    require(actual["bytes"] == item["bytes"], f"IDENTITY_BYTES:{path}")
    require(actual["sha256"] == item["sha256"], f"IDENTITY_SHA256:{path}")
    return path


def verify_index(
    root: Path,
    before: Any,
    after: Any,
    diagnostic: str,
) -> int:
    require(type(before) is dict and before, f"{diagnostic}_BEFORE")
    require(before == after, f"{diagnostic}_CHANGED")
    for relative, item in before.items():
        path = root / relative
        require(path.is_file(), f"{diagnostic}_MISSING:{relative}")
        actual = identity(path)
        require(
            actual == {"bytes": item["bytes"], "sha256": item["sha256"]},
            f"{diagnostic}_IDENTITY:{relative}",
        )
    return len(before)


def verify_calls(receipt: dict[str, Any], key: str, probe: bool) -> dict[str, Any]:
    calls = receipt.get(key)
    require(type(calls) is list and len(calls) == 3, f"{key.upper()}_COUNT")
    expected = ("vlib", "vlog", "vsim")
    streams = 0
    versions: dict[str, str] = {}
    logs: dict[str, str] = {}
    for name, call in zip(expected, calls):
        require(type(call) is dict, f"{key.upper()}_{name}_OBJECT")
        argv = call.get("argv")
        require(type(argv) is list and argv, f"{key.upper()}_{name}_ARGV")
        require(Path(argv[0]).name.lower() == f"{name}.exe", f"{key.upper()}_{name}_EXE")
        require(call.get("process_created") is True, f"{key.upper()}_{name}_NOT_CREATED")
        require(call.get("create_process_returned") is True, f"{key.upper()}_{name}_CREATE_RETURN")
        require(call.get("exit_code") == 0, f"{key.upper()}_{name}_EXIT")
        require(call.get("timeout") is False, f"{key.upper()}_{name}_TIMEOUT")
        require(call.get("log_limit_exceeded") is False, f"{key.upper()}_{name}_LOG_LIMIT")
        require(call.get("error") is None, f"{key.upper()}_{name}_ERROR")
        for stream_name in ("stdout", "stderr"):
            stream_path = verify_identity(call.get(stream_name))
            streams += 1
            text = stream_path.read_text(encoding="utf-8", errors="replace")
            logs[f"{name}.{stream_name}"] = text
            if probe:
                versions[name] = versions.get(name, "") + text
    if probe:
        require("2020.4" in versions["vlog"], "VLOG_VERSION_NOT_2020_4")
        require("2020.4" in versions["vsim"], "VSIM_VERSION_NOT_2020_4")
    else:
        combined = "\n".join(logs.values())
        counts = re.findall(r"(?im)^#?\s*Errors:\s*([0-9]+)\b", combined)
        require(counts and all(set(value) <= {"0"} for value in counts), "FUNCTIONAL_ERROR_COUNT")
        forbidden = re.compile(
            r"(?im)^\s*(?:#\s*)?(?:\*\*\s*)?(?:error|fatal)(?:\s*[:(]|\b)"
            r"|assert(?:ion)?\s+failed|\*\*\s+failure\s*[:(]"
        )
        require(forbidden.search(combined) is None, "FUNCTIONAL_ERROR_DIAGNOSTIC")
        require(
            "# PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY" in logs["vsim.stdout"],
            "FUNCTIONAL_EXACT_PASS_MISSING",
        )
    return {"calls": len(calls), "streams": streams, "versions": versions}


def scan_jsonl(path: Path, schema: str) -> dict[str, Any]:
    header = 0
    ticks = 0
    end = 0
    last_cycle = 0
    kind_counts: dict[str, int] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            require(line.endswith("\n"), f"JSONL_NO_LF:{path}:{line_number}")
            value = json.loads(
                line,
                object_pairs_hook=_unique_object,
                parse_constant=lambda x: (_ for _ in ()).throw(
                    AuditError(f"NONFINITE_JSONL:{path}:{line_number}:{x}")
                ),
            )
            require(type(value) is dict, f"JSONL_NOT_OBJECT:{path}:{line_number}")
            kind = value.get("kind")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            if kind == "HEADER":
                header += 1
                require(line_number == 1 and value.get("schema") == schema, "JSONL_HEADER")
            elif kind == "TICK":
                ticks += 1
                cycle = value.get("cycle")
                require(type(cycle) is int and cycle == last_cycle + 1, "JSONL_TICK_ORDER")
                last_cycle = cycle
            elif kind == "END":
                end += 1
                require(value.get("cycle") == last_cycle, "JSONL_END_CYCLE")
    require(header == 1 and end == 1, "JSONL_BOUNDARIES")
    return {"ticks": ticks, "last_cycle": last_cycle, "kinds": kind_counts}


def verify_archive(archive: Path, manifest_path: Path) -> dict[str, int]:
    manifest = strict_json(manifest_path)
    if type(manifest) is dict and type(manifest.get("members")) is dict:
        members = manifest["members"]
    else:
        members = manifest
    require(type(members) is dict and members, "ARCHIVE_MANIFEST_EMPTY")
    with zipfile.ZipFile(archive) as package:
        require(package.testzip() is None, "ARCHIVE_CRC")
        names = set(package.namelist())
        require(set(members).issubset(names), "ARCHIVE_MEMBER_MISSING")
        for name, item in members.items():
            data = package.read(name)
            require(len(data) == item["bytes"], f"ARCHIVE_BYTES:{name}")
            require(hashlib.sha256(data).hexdigest() == item["sha256"], f"ARCHIVE_SHA:{name}")
    return {"manifest_members": len(members), "zip_members": len(names)}


def audit(a_root: Path, c_root: Path) -> dict[str, Any]:
    a_receipt_path = a_root / "RUN_01/RUN_RECEIPT.json"
    a_receipt_sha = sha256(a_receipt_path)
    a = strict_json(a_receipt_path)
    require(a.get("schema") == "M3_R05_NIGHT_OBSERVATION_RUN_V1", "A_SCHEMA")
    require(a.get("status") == "REAL_CAPTURE_TOOL_PASS_PENDING_INDEPENDENT_VALIDATION", "A_STATUS")
    require(a.get("exit_code") == 0, "A_EXIT")
    require(a.get("functional_attempt_consumed") is True, "A_NOT_CONSUMED")
    require(a.get("new_batch_candidate") == 1, "A_ROUND")
    require(a.get("board_release_allowed") is False, "A_SCOPE")

    stage = Path(a["stage"])
    source_count = verify_index(Path.cwd(), a["source_before"], a["source_after"], "A_SOURCE")
    stage_count = verify_index(stage, a["stage_before"], a["stage_after"], "A_STAGE")
    require(a["tool_before"] == a["tool_after"], "A_TOOL_CHANGED")
    for item in a["tool_before"].values():
        verify_identity(item)

    probe = verify_calls(a, "version_calls", True)
    functional = verify_calls(a, "functional_calls", False)
    require(a.get("argv") == [x["argv"] for x in a["functional_calls"]], "A_ARGV_MISMATCH")

    marker_path = a_root / "RUN_01_CONSUMED.json"
    marker = strict_json(marker_path)
    require(marker.get("round") == 1 and marker.get("new_batch_only") is True, "A_MARKER_SCOPE")
    require(Path(marker["output"]).resolve() == (a_root / "RUN_01").resolve(), "A_MARKER_OUTPUT")
    verify_identity(marker["preflight"], a_root / "RUN_01/PREFLIGHT.json")
    verify_identity(marker["authorization"])
    require(marker.get("pid") == a["functional_calls"][0].get("created_pid"), "A_MARKER_PID")

    capture_path = verify_identity(a["REAL_CAPTURE.jsonl"])
    inputs_path = verify_identity(a["REAL_INPUTS.jsonl"])
    capture = scan_jsonl(capture_path, "M3_R05_PUBLIC_PRE_NBA_V1")
    inputs = scan_jsonl(inputs_path, "M3_R05_INPUT_PRE_NBA_V1")
    require(capture["ticks"] == 253456, "A_CAPTURE_TICK_COUNT")
    require(inputs["ticks"] == 253456, "A_INPUT_TICK_COUNT")

    ready = strict_json(a_root / "CAPTURE_READY.json")
    verify_identity(ready["receipt"], a_receipt_path)
    verify_identity(ready["main_capture"], capture_path)
    verify_identity(ready["main_inputs"], inputs_path)
    require(ready["receipt"]["sha256"] == a_receipt_sha, "A_READY_RECEIPT_SHA")

    c_run_path = c_root / "CONSUME_R01/RUN_RECEIPT.json"
    c_run = strict_json(c_run_path)
    command = c_run.get("command")
    require(type(command) is list and len(command) >= 13, "C_COMMAND")
    require(c_run.get("execution_kind") == "SOFTWARE_ONLY", "C_KIND")
    require(c_run.get("EDA_executions") == 0, "C_EDA_SCOPE")
    require(c_run.get("exit_code") == 0 and c_run.get("timed_out") is False, "C_EXIT")
    require(c_run["source_sha256"] == c_run["source_after_sha256"], "C_SOURCE_CHANGED")
    require(c_run.get("stdout_sha256") == sha256(c_root / "CONSUME_R01/stdout.txt"), "C_STDOUT")
    require(c_run.get("stderr_sha256") == sha256(c_root / "CONSUME_R01/stderr.txt"), "C_STDERR")
    require(command[command.index("--receipt-sha256") + 1] == a_receipt_sha, "C_PRODUCER_ARG")
    require(
        Path(command[command.index("--producer-receipt") + 1]).resolve() == a_receipt_path.resolve(),
        "C_PRODUCER_PATH",
    )
    for filename, digest in c_run["source_sha256"].items():
        require(sha256(Path(filename)) == digest, f"C_SOURCE_IDENTITY:{filename}")

    c_result_path = c_root / "CONSUME_R01/REAL_RESULT.json"
    c_result = strict_json(c_result_path)
    require(c_result.get("passed") is True, "C_RESULT")
    require(c_result.get("ticks") == capture["ticks"], "C_CAPTURE_TICK_BINDING")
    require(c_result.get("capture_sha256") == sha256(capture_path), "C_CAPTURE_SHA_BINDING")
    require(c_result.get("producer_receipt_sha256") == a_receipt_sha, "C_RECEIPT_BINDING")

    c_night = strict_json(c_root / "NIGHT_RUN_RECEIPT.json")
    verify_identity(c_night["result"], c_result_path)
    verify_identity(c_night["runs"]["CONSUME_R01"]["receipt"], c_run_path)
    require(c_night["producer_receipt"]["sha256"] == a_receipt_sha, "C_NIGHT_PRODUCER")
    require(c_night["digital_summary"]["capture_sha256"] == sha256(capture_path), "C_NIGHT_CAPTURE")
    require(c_night.get("board_release_allowed") is False, "C_SCOPE")

    a_seal = strict_json(a_root / "SEAL_SUCCESS/SEAL_RECEIPT.json")
    c_seal = strict_json(c_root / "SEAL_R01/SEAL_RECEIPT.json")
    a_archive = verify_identity(a_seal.get("archive", a_seal.get("package")))
    c_archive = verify_identity(c_seal["archive"])
    a_archive_result = verify_archive(a_archive, a_root / "SEAL_SUCCESS/MANIFEST.json")
    c_archive_result = verify_archive(c_archive, c_root / "SEAL_R01/MANIFEST.json")

    gaps = [
        "A_CONSUMPTION_MARKER_BINDS_PROCESS_CREATION_AND_PREFLIGHT_BUT_NOT_FINAL_RECEIPT_SHA",
        "C_CHILD_RUN_RECEIPT_BINDS_COMMAND_STREAMS_AND_SOURCES_BUT_RESULT_SHA_IS_BOUND_BY_NIGHT_RECEIPT_AND_SEAL",
        "DYNAMIC_LOADED_MODELSIM_DEPENDENCIES_UNKNOWN_NOT_MEASURED",
        "SELF_GENERATED_RECEIPTS_AND_MANIFESTS_DO_NOT_INDEPENDENTLY_AUTHENTICATE_HISTORICAL_PROCESS_EXECUTION",
        "FIRST_VALID_STARTUP_CLIP_ENDPOINTS_AND_ANALOG_BOARD_RESULTS_REMAIN_OUT_OF_SCOPE",
    ]
    return {
        "status": "PROVENANCE_BYTE_CHAIN_CONSISTENT_LIMITED",
        "level": "L0_STATIC_IDENTITY_PLUS_SOFTWARE_CHECKS_NO_HDL_L1",
        "a": {
            "receipt_sha256": a_receipt_sha,
            "source_files": source_count,
            "staged_inputs": stage_count,
            "probe_calls": probe["calls"],
            "probe_streams": probe["streams"],
            "functional_calls": functional["calls"],
            "functional_streams": functional["streams"],
            "capture_sha256": sha256(capture_path),
            "capture_ticks": capture["ticks"],
            "input_sha256": sha256(inputs_path),
            "input_ticks": inputs["ticks"],
            "archive_sha256": sha256(a_archive),
            **a_archive_result,
        },
        "c": {
            "run_receipt_sha256": sha256(c_run_path),
            "result_sha256": sha256(c_result_path),
            "producer_receipt_sha256": c_result["producer_receipt_sha256"],
            "capture_sha256": c_result["capture_sha256"],
            "consumed_ticks": c_result["ticks"],
            "archive_sha256": sha256(c_archive),
            **c_archive_result,
        },
        "cross_binding": {
            "producer_receipt": "EXACT",
            "capture": "EXACT",
            "tick_count": "EXACT_253456",
            "consumer_command": "EXACT",
            "consumer_result": "BOUND_BY_NIGHT_RECEIPT_AND_SEAL",
        },
        "gaps": gaps,
        "mathematics_reviewed": False,
        "new_rtl_or_eda_invocations": 0,
        "board_release_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a-root", type=Path, required=True)
    parser.add_argument("--c-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "REFUSE_OVERWRITE")
    result = audit(args.a_root.resolve(), args.c_root.resolve())
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
