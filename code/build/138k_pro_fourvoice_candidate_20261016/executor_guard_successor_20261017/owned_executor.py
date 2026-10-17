"""Software-only successor: every launched process belongs to a new Windows Job.

The CLI cannot run HDL, Pro, EDA, or arbitrary commands.  Future tool use needs a
separately reviewed implementation and precise permission, not an environment flag.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HELPER = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
HELPER_SHA = "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"
DUMMY = HERE / "software_dummy.py"
PYTHON = Path(sys.executable).resolve()
EVIDENCE = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/executor_guard_successor_20261017"
ALLOWED_MODES = frozenset({"normal", "error7", "timeout_tree", "parent_exit_tree", "overflow"})


def identity(path):
    raw = Path(path).read_bytes()
    return {"path": str(Path(path).resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")


def snapshot():
    return {name: identity(path) for name, path in {
        "executor": Path(__file__), "dummy": DUMMY, "python": PYTHON,
        "job_helper": HELPER}.items()}


def validate_argv(argv):
    if (len(argv) != 6 or argv[:5] != [str(PYTHON), "-I", "-S", "-B", str(DUMMY)]
            or argv[5] not in ALLOWED_MODES):
        raise PermissionError("SOFTWARE_FIXTURE_ONLY: unapproved tool/command rejected before launch")


class OwnedJob:
    """Use the pinned helper; inspect only membership of this fresh owned Job."""

    def __init__(self):
        if os.name != "nt" or identity(HELPER)["sha256"] != HELPER_SHA:
            raise PermissionError("WINDOWS_OR_PINNED_HELPER_IDENTITY_REQUIRED")
        spec = importlib.util.spec_from_file_location("m2_executor_guard_job", HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.job = module.WindowsJob()
        self.kernel = self.job.kernel
        self.kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryInformationJobObject.restype = wintypes.BOOL
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                               ctypes.POINTER(wintypes.BOOL)]
        self.kernel.IsProcessInJob.restype = wintypes.BOOL

    def capture_owned_handles(self):
        """Open synchronize handles from fresh Job membership; never terminate by PID."""
        buffer = ctypes.create_string_buffer(65536)
        length = wintypes.DWORD()
        if not self.kernel.QueryInformationJobObject(self.job.handle, 3, buffer,
                                                     len(buffer), ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        assigned, count = struct.unpack_from("II", buffer.raw, 0)
        if count > assigned or count > 4096:
            raise RuntimeError("OWNED_JOB_MEMBERSHIP_INVALID")
        pointer_format = "Q" if ctypes.sizeof(ctypes.c_void_p) == 8 else "I"
        members = struct.unpack_from(pointer_format * count, buffer.raw, 8) if count else ()
        handles = []
        try:
            for pid in members:
                # Synchronize/query only, never PROCESS_TERMINATE. Recheck membership
                # using the opened handle so a recycled PID cannot be mistaken for ours.
                handle = self.kernel.OpenProcess(0x00101000, False, pid)
                if handle:
                    handles.append((int(pid), handle))
                    member = wintypes.BOOL()
                    if not self.kernel.IsProcessInJob(handle, self.job.handle, ctypes.byref(member)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    if not member.value:
                        raise RuntimeError("OWNED_JOB_MEMBERSHIP_CHANGED_BEFORE_HANDLE_OPEN")
                elif ctypes.get_last_error() != 87:  # process can exit after membership query
                    raise ctypes.WinError(ctypes.get_last_error())
            return handles
        except Exception:
            for _, handle in handles:
                self.kernel.CloseHandle(handle)
            raise

    def close_and_verify(self, handles, seconds):
        self.job.close()  # last Job handle; kill-on-close covers surviving descendants
        deadline = time.monotonic() + seconds
        verified = []
        try:
            for pid, handle in handles:
                remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                result = self.kernel.WaitForSingleObject(handle, remaining_ms)
                verified.append({"pid_from_owned_job": pid, "wait_result": int(result),
                                 "terminated": result == 0})
            if any(not item["terminated"] for item in verified):
                raise RuntimeError("OWNED_HANDLE_TERMINATION_UNCONFIRMED")
            return verified
        finally:
            for _, handle in handles:
                self.kernel.CloseHandle(handle)


def run_software_case(label, mode, output_root, expected_identity, group_deadline,
                      step_seconds=4, observed_log_limit=1048576):
    """No tool launch path. Logs and receipt are preserved even if process start fails."""
    argv = [str(PYTHON), "-I", "-S", "-B", str(DUMMY), mode]
    validate_argv(argv)
    if not label.replace("_", "").isalnum() or label.startswith("_"):
        raise ValueError("INVALID_CASE_LABEL")
    if not (0 < step_seconds <= 10 and 1024 <= observed_log_limit <= 1048576):
        raise ValueError("SOFTWARE_BUDGET_OUT_OF_RANGE")
    output_root = Path(output_root).resolve()
    if (output_root not in {(EVIDENCE / "RUN_01").resolve(), (EVIDENCE / "RUN_02").resolve(),
                            (EVIDENCE / "RUN_03").resolve()}
            or not output_root.is_dir()
            or output_root.is_symlink()):
        raise ValueError("CALLER_OWNED_NEW_GROUP_ROOT_REQUIRED")
    case = output_root / label
    case.mkdir(exist_ok=False)
    if case.is_symlink() or case.resolve().parent != output_root:
        raise ValueError("CASE_SCOPE_ESCAPE")
    record = {"schema": "m2_owned_software_case_v1", "case": label, "argv": argv,
        "cwd": str(case), "software_only": True, "tool_launches": 0,
        "board_release_allowed": False, "created_utc": datetime.now(timezone.utc).isoformat(),
        "pid": None, "root_exit_code": None, "root_handle_signaled": False,
        "job_attached_successfully": False, "unattached_handle_cleanup": None,
        "base_exception_re_raised": False,
        "timed_out": False,
        "log_limit_observed": False, "observed_log_limit_bytes": observed_log_limit,
        "log_limit_semantics": "detected after overflow, then stop owned Job; not hard byte cap",
        "owned_handles_after_wait": [], "cleanup": None, "error": None,
        "inputs_before": snapshot()}
    write_json(case / "START.json", record)
    if record["inputs_before"] != expected_identity:
        record["error"] = "PRELAUNCH_IDENTITY_MISMATCH"
        write_json(case / "RECEIPT.json", record)
        raise PermissionError(record["error"])
    job = None
    process = None
    owned_handles = []
    start = time.monotonic()
    try:
        remaining = group_deadline - start
        if remaining <= 3 or remaining > 90:
            raise TimeoutError("GROUP_DEADLINE_BEFORE_LAUNCH")
        deadline = min(group_deadline - 3, start + step_seconds)
        job = OwnedJob()
        with (case / "stdout.raw").open("xb") as stdout, (case / "stderr.raw").open("xb") as stderr:
            process = subprocess.Popen(argv, cwd=case, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 4)
            record["pid"] = process.pid
            record["tool_launches"] = 1
            job.job.attach_and_resume(process)
            record["job_attached_successfully"] = True
            # No fallible metadata writing may occur between creation and Job
            # ownership. If attachment fails, the except path owns Popen's handle.
            write_json(case / "LAUNCHED_ATTACHED.json", record)
            while process.poll() is None:
                bytes_now = sum((case / name).stat().st_size for name in ("stdout.raw", "stderr.raw"))
                if bytes_now > observed_log_limit:
                    record["log_limit_observed"] = True
                    break
                if time.monotonic() >= deadline:
                    record["timed_out"] = True
                    break
                time.sleep(0.01)
            owned_handles = job.capture_owned_handles()
            record["owned_members_captured"] = len(owned_handles)
            if record["timed_out"] or record["log_limit_observed"]:
                record["cleanup"] = job.job.terminate()
            else:
                record["cleanup"] = {"mechanism": "KILL_ON_JOB_CLOSE", "owned_job": True}
            record["owned_handles_after_wait"] = job.close_and_verify(owned_handles, 2.5)
            owned_handles = []
            record["root_exit_code"] = process.wait(timeout=0.5)
    except BaseException as error:
        record["error"] = type(error).__name__ + ": " + str(error)
        if not isinstance(error, Exception):
            record["base_exception_re_raised"] = True
            raise
    finally:
        # Runs for ordinary exceptions and cancellation/SystemExit alike. A
        # suspended root outside the Job can only be cleaned by its own handle.
        if process is not None and not record["job_attached_successfully"]:
            try:
                if process.poll() is None:
                    process.kill()  # Popen's current handle, never a stored PID
                record["root_exit_code"] = process.wait(timeout=0.5)
                record["unattached_handle_cleanup"] = "Popen.kill_and_wait_current_handle"
            except Exception as root_cleanup_error:
                record["error"] += "; UNATTACHED_ROOT_CLEANUP: " + str(root_cleanup_error)
        if job is not None:
            try:
                if job.job.handle:
                    if not owned_handles:
                        owned_handles = job.capture_owned_handles()
                    record["cleanup"] = {"mechanism": "KILL_ON_JOB_CLOSE", "owned_job": True}
                    record["owned_handles_after_wait"] = job.close_and_verify(owned_handles, 2.5)
                    owned_handles = []
                if process is not None:
                    record["root_exit_code"] = process.wait(timeout=0.5)
                    record["root_handle_signaled"] = (
                        job.kernel.WaitForSingleObject(wintypes.HANDLE(int(process._handle)), 0) == 0)
            except Exception as cleanup_error:
                record["error"] = (record["error"] or "") + "; CLEANUP: " + str(cleanup_error)
            finally:
                job.job.close()
        record["elapsed_seconds"] = round(time.monotonic() - start, 6)
        record["inputs_after"] = snapshot()
        record["inputs_unchanged"] = record["inputs_before"] == record["inputs_after"]
        record["logs"] = {name: identity(case / name) for name in ("stdout.raw", "stderr.raw")
                          if (case / name).exists()}
        record["group_deadline_kept"] = time.monotonic() <= group_deadline
        write_json(case / "RECEIPT.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="*")
    args = parser.parse_args()
    print(json.dumps({"result": "DENIED_UNAPPROVED_TOOL", "argv": args.command,
        "process_launches": 0, "reason": "CLI has no Pro/HDL/arbitrary-command execution route",
        "board_release_allowed": False}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
