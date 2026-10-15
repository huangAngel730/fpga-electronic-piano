"""Proposed one-shot T052 runner. Execution needs NEW exact M2 approval.

Importing this file never starts a process. Fake tests use Python only.
Job membership is established before child execution, without taskkill/PID races.
Direct simulator files have a 50ms detection interval, NOT an NTFS hard quota.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import time

from win_job import JobProcess

MIB = 1 << 20
CAPTURE_NAMES = {"observations.hex", "publications.jsonl", "resets.jsonl"}
MAXIMA = {"compile": 90, "run": 300, "check": 300, "total": 900,
          "capture_bytes": 750*MIB, "output_bytes": 1200*MIB,
          "stream_bytes": 16*MIB, "poll_seconds": 0.05}


def sha(path, deadline=None):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            if deadline is not None and time.monotonic() >= deadline:
                raise ValueError("TOTAL_TIMEOUT_DURING_HASH")
            digest.update(block)
    return digest.hexdigest()


def identity(path, deadline=None):
    return {"bytes": path.stat().st_size, "sha256": sha(path, deadline)}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def environment_sha():
    """Identity only; do not put credentials/environment values in logs."""
    raw = json.dumps(dict(os.environ), sort_keys=True, ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def scan_sizes(directory):
    total = capture = 0
    for path in directory.rglob("*"):
        if path.is_symlink() or (path.stat().st_file_attributes & 0x400):
            raise ValueError("OUTPUT_REPARSE_POINT:" + str(path))
        if path.is_file():
            size = path.stat().st_size
            total += size
            if path.name in CAPTURE_NAMES or path.name.endswith((".stdout.bin", ".stderr.bin")):
                capture += size
    return total, capture


def supervise(argv, cwd, name, seconds, total_deadline, limits):
    """One bounded process tree. Receipt is written on every handled failure."""
    started = time.monotonic()
    receipt = {"name": name, "argv": argv, "cwd": str(cwd),
               "started_utc": timestamp(), "status": "FAIL",
               "diagnostic": "NOT_STARTED", "pid": None,
               "timed_out": False, "resource_terminated": False,
               "environment_sha256": environment_sha(),
               "dynamic_loaded_dependencies": "UNKNOWN",
               "job_empty_after_termination": False}
    process = None
    threads = []
    overflow = threading.Event()
    pipe_error = []
    raw_paths = [cwd / (name + suffix) for suffix in
                 (".stdout.bin", ".stderr.bin")]

    def pump(source, destination):
        try:
            with destination.open("xb", buffering=0) as target:
                written = 0
                while True:
                    block = source.read(65536)
                    if not block:
                        break
                    room = max(0, limits["stream_bytes"] - written)
                    if room:
                        target.write(block[:room])
                        written += min(room, len(block))
                    if len(block) > room:
                        overflow.set()
                        # Drain until the supervisor kills the job. Never
                        # allocate unbounded memory or silently claim full logs.
        except BaseException as exc:
            pipe_error.append(repr(exc))
        finally:
            source.close()

    try:
        write_json(cwd / (name + ".started.json"), receipt)
        process = JobProcess(argv, cwd)
        receipt["pid"] = process.pid
        receipt["job_assigned_before_resume"] = True
        write_json(cwd / (name + ".launched.json"),
                   {"pid": process.pid, "utc": timestamp(), "argv": argv,
                    "cwd": str(cwd), "job_assigned_before_resume": True})
        for source, destination in zip(process.streams, raw_paths):
            thread = threading.Thread(target=pump, args=(source, destination),
                                      daemon=True)
            thread.start()
            threads.append(thread)
        deadline = min(started + seconds, total_deadline)
        root_exit_seen = None
        while True:
            now = time.monotonic()
            total, capture = scan_sizes(cwd)
            receipt["observed_output_bytes"] = total
            receipt["observed_capture_bytes"] = capture
            if overflow.is_set():
                raise ValueError("STREAM_LIMIT")
            if pipe_error:
                raise ValueError("RAW_PIPE_ERROR:" + repr(pipe_error))
            if total > limits["output_bytes"]:
                raise ValueError("OUTPUT_LIMIT")
            if capture > limits["capture_bytes"]:
                raise ValueError("CAPTURE_LIMIT")
            if now >= deadline:
                receipt["timed_out"] = True
                raise ValueError("TOTAL_TIMEOUT" if now >= total_deadline else "STEP_TIMEOUT")
            code = process.poll()
            if code is not None:
                receipt["exit_code"] = code
                if code not in ((0, 3) if name == "check" else (0,)):
                    raise ValueError("PROCESS_EXIT_NONZERO")
                # A signaled process handle can precede Job accounting update.
                # A <=100ms drain grace is INSIDE both original deadlines and
                # retains the same file/pipe checks on every loop iteration.
                if process.active():
                    if root_exit_seen is None:
                        root_exit_seen = now
                    if now-root_exit_seen >= 0.1:
                        raise ValueError("DESCENDANTS_REMAIN")
                    time.sleep(min(limits["poll_seconds"], max(0, deadline-now)))
                    continue
                receipt["status"], receipt["diagnostic"] = "PROCESS_EXIT_ACCEPTABLE", "NONE"
                break
            time.sleep(min(limits["poll_seconds"], max(0, deadline-now)))
    except BaseException as exc:
        receipt["status"], receipt["diagnostic"] = "FAIL", str(exc)
        receipt["resource_terminated"] = any(word in str(exc) for word in
                                              ("LIMIT", "TIMEOUT"))
    finally:
        if process is not None:
            try:
                process.terminate()  # also on success, no escaped descendant
                until = time.monotonic() + 2
                while (process.active() or process.poll() is None) and time.monotonic() < until:
                    time.sleep(0.01)
                receipt["job_empty_after_termination"] = process.active() == 0
                if not receipt["job_empty_after_termination"]:
                    receipt["status"], receipt["diagnostic"] = "FAIL", "JOB_NOT_EMPTY"
                if "exit_code" not in receipt:
                    receipt["exit_code"] = process.poll()
                if receipt.get("exit_code") is None:
                    receipt["status"], receipt["diagnostic"] = "FAIL", "EXIT_STATUS_UNAVAILABLE"
            except BaseException as exc:
                receipt["status"], receipt["diagnostic"] = "FAIL", "JOB_CLEANUP:" + repr(exc)
            finally:
                process.close()
        for thread in threads:
            thread.join(2)
        if any(t.is_alive() for t in threads):
            receipt["status"], receipt["diagnostic"] = "FAIL", "PIPE_NOT_CLOSED"
        # Final check catches overflow/race after root exit, including a fast
        # fake writer that finishes before the first periodic poll.
        if overflow.is_set() or pipe_error:
            receipt["status"], receipt["diagnostic"] = "FAIL", "STREAM_LIMIT_OR_PIPE_ERROR"
            receipt["resource_terminated"] = overflow.is_set()
        for raw_path in raw_paths:
            if raw_path.is_file() and re.search(
                    rb"(?im)^.*\b(?:error|fatal|failure):", raw_path.read_bytes()):
                receipt["status"], receipt["diagnostic"] = "FAIL", "ERROR_DIAGNOSTIC"
        try:
            total, capture = scan_sizes(cwd)
            receipt["final_output_bytes"], receipt["final_capture_bytes"] = total, capture
            if total > limits["output_bytes"] or capture > limits["capture_bytes"]:
                receipt["status"], receipt["diagnostic"] = "FAIL", "FINAL_FILE_LIMIT"
                receipt["resource_terminated"] = True
        except BaseException as exc:
            receipt["status"], receipt["diagnostic"] = "FAIL", str(exc)
        receipt["streams"] = {p.name: identity(p) for p in raw_paths if p.is_file()}
        receipt["streams_complete"] = (len(receipt["streams"]) == 2 and
                                        not overflow.is_set() and not pipe_error and
                                        not any(t.is_alive() for t in threads))
        receipt["finished_utc"] = timestamp()
        receipt["elapsed_seconds"] = time.monotonic() - started
        write_json(cwd / (name + ".receipt.json"), receipt)
    return receipt


def consume(path, value):
    """Persistent exclusive creation; never removed on FAIL/crash/success."""
    write_json(path, value)


def read_unique(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def validate_approval(approval):
    if approval.get("schema") != "T052_LONG_ONE_SHOT_M2_V1" or approval.get("approved") is not True:
        raise ValueError("M2_APPROVAL_REQUIRED")
    if approval.get("machine") != os.environ.get("COMPUTERNAME"):
        raise ValueError("MACHINE_IDENTITY")
    if approval.get("format") != "T052_LONG_PUBLIC_HEX_V1":
        raise ValueError("FORMAT_IDENTITY")
    if not approval.get("decision_reference") or not approval.get("approval_id"):
        raise ValueError("APPROVAL_REFERENCE")
    for name, maximum in MAXIMA.items():
        value = approval["limits"][name]
        if type(value) not in (int, float) or not 0 < value <= maximum:
            raise ValueError("BUDGET:" + name)
    for key in ("output", "allowance_directory"):
        path = Path(approval[key])
        if not path.is_absolute() or not str(path).isascii():
            raise ValueError("ABSOLUTE_ASCII_PATH:" + key)
        root = Path(__file__).resolve().parents[4] / "code/output"
        if path != path.resolve() or not path.is_relative_to(root):
            raise ValueError("OUTPUT_SCOPE_OR_REPARSE:" + key)
    if set(approval["commands"]) != {"compile", "run", "check"}:
        raise ValueError("THREE_EXACT_COMMANDS_REQUIRED")
    for name, argv in approval["commands"].items():
        if not isinstance(argv, list) or not argv or not all(type(x) is str for x in argv):
            raise ValueError("ARGV:" + name)
        executable = str(Path(argv[0]).resolve())
        if not Path(argv[0]).is_absolute() or executable not in approval["identities"]:
            raise ValueError("UNBOUND_EXECUTABLE:" + name)
    if not approval["identities"] or not approval["copies"]:
        raise ValueError("INPUT_IDENTITY_REQUIRED")
    for src, rel in approval["copies"].items():
        dest = Path(rel)
        if src not in approval["identities"] or dest.is_absolute() or ".." in dest.parts:
            raise ValueError("COPY_SCOPE")
        if str(dest) in {"receipt.json", "approval.json"} or dest.name.endswith(
                (".receipt.json", ".started.json", ".stdout.bin", ".stderr.bin")):
            raise ValueError("RESERVED_OUTPUT_NAME")
    if len(set(approval["copies"].values())) != len(approval["copies"]):
        raise ValueError("DUPLICATE_COPY_TARGET")
    for rel in approval["copies"].values():
        if rel not in {"controls.hex", "M1_INPUT_CONFIRMATION.md", "tb_t052_long.sv",
                       "t052_long_observer.sv", "readonly/t052_polyphony_test_source.sv",
                       "readonly/dds_oscillator.sv", "readonly/pcm_mixer_4voice.sv",
                       "readonly/sine_1024_8192.mem"}:
            raise ValueError("UNEXPECTED_INPUT_COPY")
    copied = {rel: approval["identities"][src]["sha256"]
              for src, rel in approval["copies"].items()}
    frozen = {
        "controls.hex": "fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0",
        "M1_INPUT_CONFIRMATION.md": "56574246ebd7fe75bf59ea7f583ffe2c00f5593b8567230dbb6992cfe857b555",
        "readonly/t052_polyphony_test_source.sv": "89ddb8b73bda6e5c83c7b617640cddf3294fb194a9b7955746c28a2e0f2eddeb",
        "readonly/dds_oscillator.sv": "3cd758e28da8f76a30da38cb2dfcd458db5743d4ea4f38e072a43d7f83719f04",
        "readonly/pcm_mixer_4voice.sv": "93fb6e88e55ea84f2e322b0cf8b94a1a2c2e13618e302e7d24ec8657c92bb99a",
        "readonly/sine_1024_8192.mem": "5e1dbd3797f353686f5e567831b56d6dcf9bee55c423097b471ade93203e84b2",
    }
    if any(copied.get(name) != digest for name, digest in frozen.items()):
        raise ValueError("FROZEN_INPUT_IDENTITY")
    here = Path(__file__).resolve().parent
    for path in here.glob("*.py"):
        if str(path) not in approval["identities"]:
            raise ValueError("UNBOUND_RUNNER_OR_CHECKER_SOURCE:" + path.name)
    if approval.get("supervisor_source_sha256") != sha(here / "bounded_runner.py"):
        raise ValueError("SUPERVISOR_IDENTITY")
    tb = here.parents[3] / "code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"
    for name in ("tb_t052_long.sv", "t052_long_observer.sv"):
        source = str((tb / name).resolve())
        if approval["copies"].get(source) != name:
            raise ValueError("CURRENT_TB_REQUIRED:" + name)


def verify_identities(approval, deadline=None):
    if approval.get("environment_sha256") != environment_sha():
        raise ValueError("ENVIRONMENT_DRIFT")
    for path, expected in approval["identities"].items():
        source = Path(path)
        if not source.is_absolute() or source.is_symlink() or identity(source, deadline) != expected:
            raise ValueError("IDENTITY_DRIFT:" + path)


def verify_copies(approval, output, deadline):
    for source, relative in approval["copies"].items():
        if identity(output / relative, deadline) != approval["identities"][source]:
            raise ValueError("WORKING_INPUT_DRIFT:" + relative)


def validate_required_artifacts(output, name):
    if name == "compile":
        if not (output / "long.vvp").is_file() or not (output / "long.vvp").stat().st_size:
            raise ValueError("COMPILE_ARTIFACT_MISSING")
    elif name == "run":
        raw = (output / "run.stdout.bin").read_bytes()
        marker = b"T052_LONG_CAPTURE_FINISHED_NOT_ACCEPTANCE_PASS"
        if raw.splitlines().count(marker) != 1:
            raise ValueError("RUN_FINISH_MARKER_MISSING_OR_DUPLICATE")
        for required in CAPTURE_NAMES:
            if not (output / required).is_file() or not (output / required).stat().st_size:
                raise ValueError("CAPTURE_MISSING_OR_EMPTY:" + required)


def execute(approval_path):
    """NOT CALLED in this delivery. Approval is a human boundary, not a signature."""
    preflight_start = time.monotonic()
    approval = read_unique(approval_path)
    approval_identity = identity(approval_path)
    validate_approval(approval)
    verify_identities(approval)
    output = Path(approval["output"])
    allowance = Path(approval["allowance_directory"])
    # M2 pins a single existing allowance directory in the signed scope.
    if not allowance.is_dir() or output.exists():
        raise ValueError("ALLOWANCE_DIRECTORY_OR_OUTPUT")
    if shutil.disk_usage(output.parent).free < 2*1024*MIB:
        raise ValueError("DISK_SPACE_BELOW_2_GIB")
    claim = allowance / "attempt.consumed.json"
    consume(claim, {"approval_sha256": sha(approval_path), "utc": timestamp(),
                    "approval_id": approval["approval_id"], "status": "CONSUMED_NO_RETRY"})
    # A failed mkdir after claim STILL consumes the attempt.
    total_start = time.monotonic()
    output.mkdir()  # exclusive new working directory; no reuse
    deadline = total_start + approval["limits"]["total"]
    final = {"status": "FAIL", "new_rtl_acceptance": "NOT_VERIFIED",
             "approval_sha256": sha(approval_path), "steps": [],
             "preflight_seconds": total_start-preflight_start,
             "dynamic_loaded_dependencies": "UNKNOWN",
             "direct_file_enforcement": "POLL_AND_KILL_NOT_FILESYSTEM_QUOTA"}
    try:
        shutil.copyfile(approval_path, output / "approval.json")
        for src, rel in approval["copies"].items():
            dest = output / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Path(src).open("rb") as incoming, dest.open("xb") as outgoing:
                for block in iter(lambda: incoming.read(MIB), b""):
                    if time.monotonic() >= deadline:
                        raise ValueError("TOTAL_TIMEOUT_DURING_COPY")
                    outgoing.write(block)
            if identity(dest, deadline) != approval["identities"][src]:
                raise ValueError("COPY_IDENTITY:" + rel)
            total, capture = scan_sizes(output)
            if total > approval["limits"]["output_bytes"] or time.monotonic() >= deadline:
                raise ValueError("PREPARATION_LIMIT")
        for name in ("compile", "run", "check"):
            if identity(approval_path, deadline) != approval_identity:
                raise ValueError("APPROVAL_DRIFT")
            verify_identities(approval, deadline)
            verify_copies(approval, output, deadline)
            if time.monotonic() >= deadline:
                raise ValueError("TOTAL_TIMEOUT_BEFORE:" + name)
            consume(allowance / (name + ".consumed.json"),
                    {"utc": timestamp(), "approval_sha256": sha(approval_path),
                     "argv": approval["commands"][name]})
            receipt = supervise(approval["commands"][name], output, name,
                                approval["limits"][name], deadline, approval["limits"])
            final["steps"].append(receipt)
            if receipt["status"] != "PROCESS_EXIT_ACCEPTABLE":
                raise ValueError(name + ":" + receipt["diagnostic"])
            validate_required_artifacts(output, name)
            if name == "compile":
                final["compiled_artifact"] = identity(output / "long.vvp", deadline)
            elif identity(output / "long.vvp", deadline) != final["compiled_artifact"]:
                raise ValueError("COMPILED_ARTIFACT_DRIFT")
        review = read_unique(output / "capture_review.json")
        # exit3 is not automatically success. Keep original offline conclusion.
        if (final["steps"][-1].get("exit_code") != 3 or
                review.get("transaction_comparison") != "PASS" or
                review.get("status") != "NOT_VERIFIABLE" or
                review.get("diagnostic") != "PROVENANCE_NOT_VERIFIED" or
                review.get("rows") != 8536336 or review.get("accepted") != 8207 or
                review.get("published") != 8201 or review.get("cancelled") != 6 or
                review.get("open") != 0 or review.get("exit_code") != 3):
            raise ValueError("TRANSACTION_COMPARISON_NOT_PASS")
        if set(review["inputs"]) != {str(output / name) for name in CAPTURE_NAMES}:
            raise ValueError("CHECKER_INPUT_SET")
        for path, digest in review["inputs"].items():
            if sha(Path(path), deadline) != digest:
                raise ValueError("CHECKER_CAPTURE_DRIFT")
        verify_identities(approval, deadline)
        verify_copies(approval, output, deadline)
        if identity(output / "long.vvp", deadline) != final["compiled_artifact"]:
            raise ValueError("COMPILED_ARTIFACT_DRIFT")
        final["status"] = "RAW_ATTEMPT_FINISHED_PENDING_M2_PROVENANCE_REVIEW"
    except BaseException as exc:
        final["diagnostic"] = str(exc)
    finally:
        final["supervised_seconds"] = time.monotonic()-total_start
        post_start = time.monotonic()
        final["output_files"] = {str(p.relative_to(output)): identity(p)
                                 for p in output.rglob("*") if p.is_file()}
        final["post_hash_seconds"] = time.monotonic()-post_start
        final["finished_utc"] = timestamp()
        write_json(output / "receipt.json", final)
    return 3 if final["status"].startswith("RAW_ATTEMPT") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--refusal-receipt", type=Path)
    parser.add_argument("--approval-sha256")
    args = parser.parse_args()
    if not args.execute:
        print("LOCKED: M2 must review exact combination; no process started")
        return 3
    if args.refusal_receipt is None or args.refusal_receipt.exists():
        print("REFUSED: new --refusal-receipt path required")
        return 1
    audit = args.refusal_receipt.resolve()
    if not audit.is_relative_to(Path(__file__).resolve().parents[4] / "code/output"):
        print("REFUSED: refusal receipt must be under code/output")
        return 1
    try:
        if not args.approval_sha256 or sha(args.approval) != args.approval_sha256:
            raise ValueError("APPROVAL_SHA_REQUIRED_OR_MISMATCH")
        return execute(args.approval.resolve())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        refusal = {"status": "REFUSED_WITHOUT_RETRY", "diagnostic": str(exc),
                   "utc": timestamp(), "approval": str(args.approval),
                   "actual_argv": sys.argv, "exit_code": 1}
        write_json(args.refusal_receipt, refusal)
        print(json.dumps(refusal))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
