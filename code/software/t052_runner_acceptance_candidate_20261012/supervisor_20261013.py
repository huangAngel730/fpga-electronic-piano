"""Parent-owned, source-bound observations of a real software child exit.

No API accepts a caller-supplied exit code. This is provenance validation,
not a cryptographic attestation against an attacker rewriting every file.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner_tail_20261013 as runner  # noqa: E402


def _identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=runner.legacy._pairs,
                      parse_constant=lambda value: runner.require(False, "NONFINITE_JSON:" + value))


def _completion_files(output, record):
    """Collect every large artifact before the final budget decision."""
    evidence = Path(record["receipt_path"]).parent
    paths = {output / "child.receipt.json",
             output / "child.stdout.bin", output / "child.stderr.bin",
             Path(record["receipt_path"]), Path(record["argv"][0])}
    paths.update(Path(path) for path in record["sources_before"])
    paths.update(path for path in evidence.rglob("*") if path.is_file())
    files = {str(path.resolve()): _identity(path.read_bytes()) for path in paths}
    for path, expected in record["sources_after"].items():
        runner.require(files[str(Path(path).resolve())] == expected, "COMPLETION_SOURCE_DRIFT")
    runner.require(files[str(Path(record["argv"][0]).resolve())] == record["executable_after"],
                   "COMPLETION_TOOL_DRIFT")
    runner.require(files[str(Path(record["receipt_path"]).resolve())] == record["receipt_identity"],
                   "COMPLETION_RECEIPT_DRIFT")
    return files


def _completion(output, files):
    """Only the small final observation hash and exclusive commit remain."""
    files[str((output / "observation.json").resolve())] = _identity(
        (output / "observation.json").read_bytes())
    payload = {
        "schema": "T052_OBSERVATION_COMPLETION_V1", "files": files,
        "scope": "POST_FINAL_BUDGET_DECISION_PROVENANCE_COMMIT_ONLY",
    }
    expected = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    destination = output / "completion.json"
    try:
        runner.write_json(destination, payload)
    except Exception:
        # A completed commit is authoritative even if its write acknowledgement
        # failed. A missing/partial/different file cannot turn into success.
        if not destination.is_file() or destination.read_bytes() != expected:
            raise


def _sources(snapshot):
    runner.require(all(Path(path).is_absolute() for path in snapshot),
                   "SUPERVISOR_SOURCE_PATH_RELATIVE")
    actual = {path: runner.identity(path) for path in snapshot}
    runner.require(actual == snapshot, "SUPERVISOR_SOURCE_DRIFT")
    return actual


def observe_run(output, argv, cwd, receipt_path, source_snapshot, *,
                total_seconds=300, step_seconds=90):
    """Run argv in an owned process tree and write only parent-owned evidence."""
    output, cwd = Path(output).resolve(), Path(cwd).resolve()
    receipt_path = Path(receipt_path).resolve()
    runner.require(not output.exists(), "SUPERVISOR_OUTPUT_EXISTS")
    runner.require(not receipt_path.exists(), "SUPERVISOR_CHILD_RECEIPT_EXISTS")
    runner.require(not output.is_relative_to(receipt_path.parent),
                   "SUPERVISOR_MUST_BE_OUTSIDE_CHILD_EVIDENCE")
    output.mkdir(parents=True)
    budget = runner.Budget(total_seconds)
    record = {"schema": "T052_PARENT_OBSERVATION_V1", "status": "FAIL_PARTIAL",
              "exit_code": 1, "failure": None, "argv": list(map(str, argv)),
              "cwd": str(cwd), "receipt_path": str(receipt_path),
              "total_seconds": total_seconds, "automatic_retries": 0}
    try:
        record["sources_before"] = _sources(source_snapshot)
        runner.require(Path(record["argv"][0]).is_absolute(), "SUPERVISOR_TOOL_RELATIVE")
        record["executable_before"] = runner.identity(record["argv"][0])
        step = runner._run_process(output, "child", record["argv"], cwd,
                                   step_seconds, budget)
        record["step"] = step
        record["step_receipt"] = runner.identity(output / "child.receipt.json")
        record["sources_after"] = _sources(source_snapshot)
        record["executable_after"] = runner.identity(record["argv"][0])
        runner.require(record["executable_before"] == record["executable_after"],
                       "SUPERVISOR_TOOL_DRIFT")
        record["receipt_identity"] = runner.identity(receipt_path)
        runner.require(not step["timed_out"] and step["launch_error"] is None,
                       "SUPERVISOR_CHILD_TIMEOUT_OR_LAUNCH")
        runner.require(step["exit_code"] == 0, "SUPERVISOR_CHILD_NONZERO")
        record.update(status="OBSERVED_ZERO_EXIT", exit_code=0)
    except Exception as error:
        runner._fail(record, type(error).__name__ + ":" + str(error))
    files = None
    if record["exit_code"] == 0:
        try:
            files = _completion_files(output, record)
        except Exception as error:
            runner._fail(record, "COMPLETION_COLLECTION:" + str(error))
    result = runner.finalize_receipt(output / "observation.json", record, budget)
    if result["exit_code"] == 0:
        try:
            _completion(output, files)
        except Exception as error:
            runner._fail(result, "COMPLETION_WRITE:" + str(error))
    return result


def require_supervisor(evidence, supervisor_receipt, expected_argv,
                       source_snapshot, *, expected_cwd=None,
                       expected_total=300, expected_step=90):
    """Return verified immutable byte snapshots, never paths to reread for sealing."""
    evidence = Path(evidence).resolve()
    supervisor_receipt = Path(supervisor_receipt).resolve()
    parent = supervisor_receipt.parent
    completion_path = parent / "completion.json"
    runner.require(completion_path.is_file(), "SUPERVISOR_COMPLETION_MISSING")
    completion_raw = completion_path.read_bytes()
    completion = _json(completion_raw)
    canonical = (json.dumps(completion, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    runner.require(completion_raw == canonical, "SUPERVISOR_COMPLETION_ENCODING")
    runner.require(completion.get("schema") == "T052_OBSERVATION_COMPLETION_V1",
                   "SUPERVISOR_COMPLETION_SCHEMA")
    files = {}
    allowed = {str(Path(path).resolve()) for path in source_snapshot}
    allowed.add(str(Path(expected_argv[0]).resolve()))
    allowed.update(str((parent / name).resolve()) for name in
                   ("observation.json", "child.receipt.json", "child.stdout.bin", "child.stderr.bin"))
    for path, expected in completion["files"].items():
        resolved = Path(path).resolve()
        runner.require(path == str(resolved) and (path in allowed or resolved.is_relative_to(evidence)),
                       "SUPERVISOR_COMPLETION_PATH")
        raw = resolved.read_bytes()
        runner.require(_identity(raw) == expected, "SUPERVISOR_COMMIT_SHA:" + path)
        files[path] = raw
    required = allowed | {str(evidence / "receipt.json")}
    runner.require(required <= files.keys(), "SUPERVISOR_COMPLETION_MISSING_MEMBER")
    files[str(completion_path)] = completion_raw

    def raw(path):
        return files[str(Path(path).resolve())]

    record = _json(raw(supervisor_receipt))
    runner.require(record.get("schema") == "T052_PARENT_OBSERVATION_V1",
                   "SUPERVISOR_SCHEMA")
    runner.require(record.get("status") == "OBSERVED_ZERO_EXIT"
                   and type(record.get("exit_code")) is int and record["exit_code"] == 0
                   and record.get("failure") is None, "SUPERVISOR_NOT_ZERO_EXIT")
    expected_argv = list(map(str, expected_argv))
    runner.require(record["argv"] == expected_argv, "SUPERVISOR_ARGV")
    runner.require(record["executable_before"] == record["executable_after"]
                   == _identity(raw(expected_argv[0])), "SUPERVISOR_TOOL_BINDING")
    runner.require(record["receipt_path"] == str(evidence / "receipt.json"),
                   "SUPERVISOR_OUTPUT_BINDING")
    runner.require(record["receipt_identity"] == _identity(raw(evidence / "receipt.json")),
                   "SUPERVISOR_RECEIPT_SHA")
    if expected_cwd is not None:
        runner.require(record["cwd"] == str(Path(expected_cwd).resolve()), "SUPERVISOR_CWD")
    actual_sources = {path: _identity(raw(path)) for path in source_snapshot}
    runner.require(record["sources_before"] == record["sources_after"]
                   == actual_sources == source_snapshot, "SUPERVISOR_SOURCE_BINDING")
    runner.require(record["step_receipt"] == _identity(raw(parent / "child.receipt.json")),
                   "SUPERVISOR_STEP_SHA")
    step = _json(raw(parent / "child.receipt.json"))
    runner.require(step == record["step"], "SUPERVISOR_STEP_BINDING")
    runner.require(type(step["exit_code"]) is int and step["exit_code"] == 0
                   and step["timed_out"] is False and step["launch_error"] is None,
                   "SUPERVISOR_STEP_NOT_ZERO")
    runner.require(step["argv"] == expected_argv and step["cwd"] == record["cwd"],
                   "SUPERVISOR_STEP_COMMAND")
    runner.require(type(step["pid"]) is int and step["pid"] > 0,
                   "SUPERVISOR_PROCESS_NOT_OBSERVED")
    for stream in ("stdout", "stderr"):
        runner.require(step[stream] == _identity(raw(parent / ("child." + stream + ".bin"))),
                       "SUPERVISOR_LOG_SHA:" + stream)
    runner.require(type(record["total_seconds"]) in (int, float)
                   and record["total_seconds"] == expected_total
                   and type(step["timeout_cap_seconds"]) in (int, float)
                   and step["timeout_cap_seconds"] == expected_step,
                   "SUPERVISOR_EXACT_BUDGET")
    runner.require(type(record["elapsed_seconds"]) in (int, float)
                   and math.isfinite(record["elapsed_seconds"])
                   and 0 <= record["elapsed_seconds"] < expected_total
                   and type(step["effective_timeout_seconds"]) in (int, float)
                   and 0 < step["effective_timeout_seconds"] <= min(expected_total, expected_step)
                   and record["automatic_retries"] == 0,
                   "SUPERVISOR_TOTAL_BUDGET")
    return {"record": record, "files": files}
