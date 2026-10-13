"""Bounded qualification/seal for the three new receipt-tail software cases."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runner_tail_20261013 as runner  # noqa: E402
import delivery as legacy_delivery  # noqa: E402
import supervisor_20261013 as supervisor  # noqa: E402

ROOT = HERE.parents[2]
DOC = ROOT / "code/docs/test/t052_runner_acceptance_20261012"
SOURCE_NAMES = (
    "runner.py", "windows_job.py", "delivery.py", "test_runner.py",
    "runner_tail_20261013.py", "delivery_tail_20261013.py", "test_tail_20261013.py",
    "supervisor_20261013.py", "test_seal_guard_20261013.py",
    "test_observation_guard_20261013.py",
    "test_completion_ack_20261013.py",
    "test_completion_encoding_20261013.py",
)


def sources():
    return {name: runner.identity(HERE / name) for name in SOURCE_NAMES}


def qualify(output, *, command=None, total_seconds=300, step_seconds=90,
            increment_only=False):
    """The optional command seam is for the new timeout fake-tool test only."""
    output = legacy_delivery.fresh_output(output)
    budget = runner.Budget(total_seconds)
    receipt = {
        "status": "FAIL_PARTIAL", "exit_code": 1, "failure": None,
        "qualification_tools": ["PYTHON_FAKE_TOOL_ONLY"],
        "ModelSim_runs": 0, "Icarus_runs": 0, "VVP_runs": 0, "Gowin_runs": 0,
        "T052_complete": False, "old_nine_cases": "REUSED_NOT_RERUN",
        "total_limit_seconds": total_seconds, "per_step_limit_seconds": step_seconds,
        "automatic_retries": 0,
    }
    try:
        runner.require(0 < total_seconds <= 300 and 0 < step_seconds <= 90,
                       "QUALIFICATION_LIMIT")
        receipt["sources_before"] = sources()
        test_name = "test_completion_encoding_20261013.py" if increment_only else "test_tail_20261013.py"
        if increment_only:
            receipt["original_three_cases"] = {
                "status": "REUSED_NOT_RERUN",
                "seal": runner.identity(DOC / "SEALED_TAIL_20261013_01/seal.json"),
                "archive": runner.identity(DOC / "SEALED_TAIL_20261013_01/evidence.zip.b64"),
            }
            receipt["child_exit_guard"] = {
                "status": "REUSED_NOT_RERUN",
                "seal": runner.identity(DOC / "SEALED_TAIL_20261013_02/seal.json"),
                "archive": runner.identity(DOC / "SEALED_TAIL_20261013_02/evidence.zip.b64"),
            }
            receipt["observation_guard"] = {
                "status": "REUSED_NOT_RERUN",
                "seal": runner.identity(DOC / "SEALED_TAIL_20261013_03/seal.json"),
                "archive": runner.identity(DOC / "SEALED_TAIL_20261013_03/evidence.zip.b64"),
            }
            receipt["complete_write_ack_guard"] = {
                "status": "REUSED_NOT_RERUN",
                "seal": runner.identity(DOC / "SEALED_TAIL_20261013_04/seal.json"),
                "archive": runner.identity(DOC / "SEALED_TAIL_20261013_04/evidence.zip.b64"),
            }
        command = command or [sys.executable, "-I", "-S", "-B", "-X", "utf8",
                              str(HERE / test_name),
                              "--evidence-dir", str(output / "cases"), "-v"]
        receipt["command"] = list(command)
        step = runner._run_process(output, "tests", command, output,
                                   step_seconds, budget)
        receipt["step"] = step
        receipt["test_exit_code"] = step["exit_code"]
        receipt["stdout"] = runner.identity(output / "tests.stdout.bin")
        receipt["stderr"] = runner.identity(output / "tests.stderr.bin")
        receipt["sources_after"] = sources()
        runner.require(not step["timed_out"], "QUALIFICATION_TIMEOUT")
        runner.require(step["launch_error"] is None, "QUALIFICATION_LAUNCH")
        runner.require(step["exit_code"] == 0, "QUALIFICATION_NONZERO")
        runner.require(receipt["sources_before"] == receipt["sources_after"], "SOURCE_DRIFT")
        receipt.update(status="SOFTWARE_TAIL_INCREMENT_PASS", exit_code=0)
    except Exception as error:
        runner._fail(receipt, type(error).__name__ + ":" + str(error))
    return runner.finalize_receipt(output / "receipt.json", receipt, budget)


def source_snapshot():
    snapshot = {str((HERE / name).resolve()): runner.identity(HERE / name)
                for name in SOURCE_NAMES}
    for suffix in ("01", "02", "03", "04"):
        for name in ("seal.json", "evidence.zip.b64"):
            path = DOC / ("SEALED_TAIL_20261013_" + suffix) / name
            snapshot[str(path.resolve())] = runner.identity(path)
    return snapshot


def qualification_command(evidence):
    return [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(Path(__file__).resolve()),
            "qualify-increment", "--output", str(Path(evidence).resolve())]


def supervise(output):
    output = legacy_delivery.fresh_output(output)
    evidence = output / "evidence"
    return supervisor.observe_run(
        output / "supervisor", qualification_command(evidence), ROOT,
        evidence / "receipt.json", source_snapshot(), total_seconds=300, step_seconds=90,
    )


def seal(evidence, target, supervisor_receipt):
    evidence, target = Path(evidence).resolve(), Path(target).resolve()
    runner.require(target.parent == DOC and not target.exists(), "SEAL_SCOPE_OR_EXISTS")
    verified = supervisor.require_supervisor(
        evidence, supervisor_receipt, qualification_command(evidence),
        source_snapshot(), expected_cwd=ROOT,
    )
    files = verified["files"]

    def raw(path):
        return files[str(Path(path).resolve())]

    receipt = supervisor._json(raw(evidence / "receipt.json"))
    runner.require(receipt["status"] == "SOFTWARE_TAIL_INCREMENT_PASS"
                   and receipt["exit_code"] == 0, "QUALIFICATION_NOT_PASS")
    frozen_sources = {name: supervisor._identity(raw(HERE / name)) for name in SOURCE_NAMES}
    runner.require(frozen_sources == receipt["sources_before"] == receipt["sources_after"],
                   "SOURCE_DRIFT")
    payload = {"source/" + name: raw(HERE / name) for name in SOURCE_NAMES}
    payload.update({"evidence/" + Path(path).relative_to(evidence).as_posix(): value
                    for path, value in files.items() if Path(path).is_relative_to(evidence)})
    parent = Path(supervisor_receipt).resolve().parent
    for name in ("observation.json", "completion.json", "child.receipt.json", "child.stdout.bin", "child.stderr.bin"):
        payload["supervisor/" + name] = raw(parent / name)
    for suffix, key in (("01", "original_three_cases"), ("02", "child_exit_guard"),
                        ("03", "observation_guard"), ("04", "complete_write_ack_guard")):
        for name, identity_key in (("seal.json", "seal"), ("evidence.zip.b64", "archive")):
            path = DOC / ("SEALED_TAIL_20261013_" + suffix) / name
            runner.require(supervisor._identity(raw(path)) == receipt[key][identity_key],
                           "REUSED_IDENTITY:" + suffix + "/" + name)
            payload["REUSED/" + suffix + "/" + name] = raw(path)
    payload["docs/TAIL_20261013.md"] = (DOC / "TAIL_20261013.md").read_bytes()
    raw, members = legacy_delivery.make_zip(payload)
    target.mkdir()
    (target / "evidence.zip.b64").write_bytes(base64.b64encode(raw) + b"\n")
    result = {"status": "SEALED_SOFTWARE_TAIL_INCREMENT", "zip_bytes": len(raw),
              "zip_sha256": hashlib.sha256(raw).hexdigest(), "members": len(members) + 1,
              "sources": frozen_sources, "qualification_receipt": receipt,
              "parent_observation": verified["record"],
              "T052_complete": False}
    runner.write_json(target / "seal.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["qualify", "qualify-increment", "supervise", "seal"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--supervisor-receipt", type=Path)
    args = parser.parse_args()
    if args.mode in ("qualify", "qualify-increment", "supervise"):
        result = (supervise(args.output) if args.mode == "supervise"
                  else qualify(args.output, increment_only=args.mode == "qualify-increment"))
        print(json.dumps({key: result[key] for key in ("status", "exit_code", "failure")}))
        raise SystemExit(result["exit_code"])
    if args.supervisor_receipt is None:
        parser.error("seal requires --supervisor-receipt")
    result = seal(args.evidence, args.target, args.supervisor_receipt)
    print(json.dumps({key: result[key] for key in ("status", "zip_bytes", "zip_sha256")}))
