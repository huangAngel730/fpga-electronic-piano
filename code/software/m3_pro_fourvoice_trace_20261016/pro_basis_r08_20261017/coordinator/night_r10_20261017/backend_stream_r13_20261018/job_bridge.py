"""Root-owned one-shot Windows Job launcher for R13 workers.

The frozen R12 owner is extracted by AST and executes in this disposable
supervisor process.  The long-lived coordinator must launch this file as a
separate process because the inherited disaster watchdog uses os._exit(124).
"""
from __future__ import annotations

import argparse
import ast
import builtins
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import types

from finalize import atomic_json
from stream_bridge import CHUNK, read_control, require, strict_child

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
OUTPUT = ROOT / "code/output/m3_backend_stream_r13_20261018"
R12_SELFTEST = HERE.parent / "frontend_close_r12_20261018/selftest.py"
R12_SELFTEST_SHA = "5ce7234c457e8c53cdcbe857e40cc2c1235ad171bd95d647a13a8c04a5930c1c"
WINDOWS_JOB = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
WINDOWS_JOB_SHA = "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"
CAPS = {"P0": 60, "P1": 60, "K": 120, "V": 120, "B": 120, "W": 900, "R": 120}
B_ACTUAL_CAP = 100
B_DESCENDANT_CAP = 5
B_TIMEOUT_CAP = 5


def _frozen(path, sha):
    raw = path.read_bytes()
    require(len(raw) <= CHUNK and hashlib.sha256(raw).hexdigest() == sha,
            "FROZEN_OWNER_SOURCE")
    return raw


def _small_bytes(path):
    with Path(path).open("rb", buffering=0) as stream:
        raw = stream.read(CHUNK)
        require(not stream.read(1), "FIXTURE_STDOUT_TOO_LARGE")
    return raw


class _TreePeakObserver:
    """Own-Job PID identities and sum of final OS lifetime peaks, fail closed.

    Polling cannot guarantee catching a short-lived PID. Therefore only exact
    reconciliation with the original cumulative Job total can prove coverage.
    Held query handles are closed immediately after exit/final peak capture,
    before the old owner's Job0 drain; its original root handle stays separate.
    """
    MAX_MEMBERS = 256
    MAX_OPEN_ATTEMPTS = 2048
    ACCESS = 0x100000 | 0x0400 | 0x0010  # synchronize/query-information/VM-read

    class Accounting(ctypes.Structure):
        _fields_ = [(name, ctypes.c_int64) for name in
                    ("user", "kernel", "period_user", "period_kernel")] + [
                        (name, wintypes.DWORD) for name in ("faults", "total", "active", "terminated")]

    class Memory(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("peak", "working", "peak_paged", "paged",
             "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]

    def __init__(self, deadline):
        self.deadline, self.job_handle, self.root_pid = deadline, None, None
        self.members, self.live, self.closed_pid_total = [], {}, {}
        self.pending, self.failures = [], []
        self.last_total, self.query_count, self.open_attempts = 0, 0, 0
        self.lookup_closes, self.lookup_close_failures = 0, 0
        self.failed_pids = set()
        self.lock, self.stop = threading.RLock(), threading.Event()
        self.thread, self.assigned = None, False
        self.job_closed = False
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.psapi = ctypes.WinDLL("psapi", use_last_error=True)
        specs = {
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "GetCurrentProcess": ([], wintypes.HANDLE),
            "GetProcessId": ([wintypes.HANDLE], wintypes.DWORD),
            "GetProcessTimes": ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
            "IsProcessInJob": ([wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "QueryInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "DuplicateHandle": ([wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                 ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                                 wintypes.BOOL, wintypes.DWORD], wintypes.BOOL),
        }
        for name, (args, result) in specs.items():
            api = getattr(self.kernel, name)
            api.argtypes, api.restype = args, result
        self.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        self.psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    def note(self, message, *, failed=False):
        target = self.failures if failed else self.pending
        if message not in target and len(target) < 32:
            target.append(message)

    def _times(self, handle):
        values = [wintypes.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
            raise ctypes.WinError(ctypes.get_last_error())
        convert = lambda value: (value.dwHighDateTime << 32) | value.dwLowDateTime
        return convert(values[0]), convert(values[1])

    def _peak(self, handle, *, final=True):
        value = self.Memory()
        value.cb = ctypes.sizeof(value)
        if not self.psapi.GetProcessMemoryInfo(handle, ctypes.byref(value), value.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.sizeof(ctypes.c_void_p) != 8 or (final and value.peak <= 0):
            raise RuntimeError("FINAL_PEAK_64BIT_NONZERO_REQUIRED")
        return int(value.peak)

    def _belongs(self, handle):
        result = wintypes.BOOL()
        if not self.kernel.IsProcessInJob(handle, self.job_handle, ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(result.value)

    def _close(self, handle):
        # Each acquired HANDLE gets exactly one CloseHandle attempt, no retry.
        ctypes.set_last_error(0)
        try:
            result = self.kernel.CloseHandle(handle)
        except BaseException as error:
            self.note("MONITOR_NATIVE_CLOSE_EXCEPTION:" + str(error), failed=True)
            return 0, int(ctypes.get_last_error())
        error = 0 if result else ctypes.get_last_error()
        if not result:
            self.note("MONITOR_CLOSE_FAILED:" + str(error), failed=True)
        return int(result), int(error)

    def _register(self, handle, pid, *, root=False):
        entry = {"pid": pid, "monitor_handle": int(handle), "creation_time_100ns": None,
                 "exit_time_100ns": None, "root": root, "membership_verified": False,
                 "alive_peak_bytes": None, "final_peak_bytes": None,
                 "opened_at": time.monotonic(), "exit_observed_at": None,
                 "final_peak_at": None, "close_at": None,
                 "exit_signaled": False, "close_attempted": False,
                 "close_bool": None, "close_winerror": None}
        self.members.append(entry)
        self.live[pid] = entry
        try:
            actual_pid = int(self.kernel.GetProcessId(handle))
            creation, _ = self._times(handle)
            if actual_pid != pid or creation <= 0:
                raise RuntimeError("PID_CREATION_IDENTITY_INVALID")
            entry["creation_time_100ns"] = creation
        except BaseException as error:
            self.note("MEMBER_IDENTITY_QUERY:" + str(pid) + ":" + str(error))
        return entry

    def bind_root(self, process):
        with self.lock:
            self.root_pid = process.pid
            duplicate = wintypes.HANDLE()
            current = self.kernel.GetCurrentProcess()
            if not self.kernel.DuplicateHandle(current, int(process._handle), current,
                    ctypes.byref(duplicate), self.ACCESS, False, 0):
                self.note("ROOT_QUERY_HANDLE_DUPLICATION:" + str(ctypes.get_last_error()))
                return
            self._register(duplicate.value, process.pid, root=True)

    def _job_snapshot(self):
        info, length = self.Accounting(), wintypes.DWORD()
        if ctypes.sizeof(info) != 48:
            raise RuntimeError("JOB_ACCOUNTING_ABI")
        query = self.kernel.QueryInformationJobObject
        if not query(self.job_handle, 1, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        if length.value != 48 or info.total < self.last_total:
            raise RuntimeError("JOB_ACCOUNTING_LENGTH_OR_MONOTONIC_TOTAL")
        self.last_total = int(info.total)
        if info.total > self.MAX_MEMBERS:
            raise RuntimeError("TREE_MEMBER_BOUND_EXCEEDED")
        capacity = 16
        for _ in range(3):
            raw = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
            returned = wintypes.DWORD()
            ok = query(self.job_handle, 3, raw, len(raw), ctypes.byref(returned))
            assigned = wintypes.DWORD.from_buffer(raw, 0).value
            count = wintypes.DWORD.from_buffer(raw, 4).value
            if ok:
                if (count > capacity or assigned < count or returned.value > len(raw)
                        or returned.value < 8 + count * ctypes.sizeof(ctypes.c_size_t)):
                    raise RuntimeError("JOB_PID_LIST_LENGTH")
                pids = [int(ctypes.c_size_t.from_buffer(raw, 8 + index * ctypes.sizeof(ctypes.c_size_t)).value)
                        for index in range(count)]
                if not all(pids) or len(set(pids)) != len(pids):
                    raise RuntimeError("JOB_PID_LIST_INVALID")
                self.query_count += 1
                return pids
            error = ctypes.get_last_error()
            if error not in (122, 234):
                raise ctypes.WinError(error)
            capacity = max(capacity * 2, int(assigned))
            if capacity > self.MAX_MEMBERS:
                raise RuntimeError("JOB_PID_LIST_CAPACITY")
        raise RuntimeError("JOB_PID_LIST_UNSTABLE")

    def _capture(self, pid):
        if pid in self.live or pid in self.failed_pids:
            return
        if self.closed_pid_total.get(pid, -1) >= self.last_total:
            return  # same cumulative total cannot conceal a new PID incarnation
        if self.open_attempts >= self.MAX_OPEN_ATTEMPTS or len(self.members) >= self.MAX_MEMBERS:
            self.note("TREE_DISCOVERY_BOUND_EXCEEDED")
            return
        self.open_attempts += 1
        handle = self.kernel.OpenProcess(self.ACCESS, False, pid)
        if not handle:
            self.failed_pids.add(pid)
            self.note("OPEN_PROCESS_DENIED_OR_FAST_EXIT:" + str(pid) + ":" + str(ctypes.get_last_error()))
            return
        try:
            if not self._belongs(handle):
                self.note("PID_REUSED_OUTSIDE_OWN_JOB:" + str(pid))
                self.failed_pids.add(pid)
                self._close(handle)
                self.lookup_closes += 1
                return
            creation, _ = self._times(handle)
            prior = next((member for member in self.members if member["pid"] == pid and
                          member["creation_time_100ns"] == creation), None)
            if prior is not None:
                closed, _ = self._close(handle)
                self.lookup_closes += 1
                self.lookup_close_failures += int(not closed)
                self.closed_pid_total[pid] = self.last_total
                return
        except BaseException as error:
            # Retain this acquired process handle until exit, even if its
            # identity/membership cannot be proved. Such a run stays PENDING.
            self.note("DISCOVERY_QUERY_FAILED:" + str(pid) + ":" + str(error))
            self._register(handle, pid)
            return
        entry = self._register(handle, pid)
        entry["membership_verified"] = True

    def _reap(self):
        for pid, entry in list(self.live.items()):
            handle = entry["monitor_handle"]
            try:
                wait = self.kernel.WaitForSingleObject(handle, 0)
                if wait not in (0, 258):
                    raise RuntimeError("PROCESS_WAIT_QUERY:" + str(wait))
                if wait == 0:
                    entry["exit_signaled"] = True
                    entry["exit_observed_at"] = time.monotonic()
                if (not entry["membership_verified"] and self.job_handle is not None
                        and not self.job_closed):
                    if self._belongs(handle):
                        entry["membership_verified"] = True
                    elif self.assigned or wait == 0:
                        self.note("MEMBER_OWN_JOB_IDENTITY_NOT_PROVED:" + str(pid))
                if wait == 258:
                    if entry["membership_verified"] and (not entry["root"] or self.assigned):
                        entry["alive_peak_bytes"] = self._peak(handle, final=False)
                    continue
                creation, exit_time = self._times(handle)
                if creation != entry["creation_time_100ns"] or exit_time <= 0:
                    raise RuntimeError("FINAL_MEMBER_CREATION_OR_EXIT_TIME")
                entry["exit_time_100ns"] = exit_time
                entry["final_peak_bytes"] = self._peak(handle)
                if entry["alive_peak_bytes"] is not None and entry["final_peak_bytes"] < entry["alive_peak_bytes"]:
                    raise RuntimeError("LIFETIME_PEAK_DECREASED")
                entry["final_peak_at"] = time.monotonic()
            except BaseException as error:
                self.note("MEMBER_QUERY_FAILED:" + str(pid) + ":" + str(error))
            if entry["exit_signaled"] and not entry["close_attempted"]:
                entry["close_attempted"] = True
                entry["close_bool"], entry["close_winerror"] = self._close(handle)
                entry["close_at"] = time.monotonic()
                if entry["close_bool"]:
                    self.live.pop(pid, None)
                    self.closed_pid_total[pid] = self.last_total

    def poll(self, *, query_job=True):
        with self.lock:
            if query_job and self.job_handle is not None:
                try:
                    for pid in self._job_snapshot():
                        if pid in self.live:
                            continue
                        self._capture(pid)
                except BaseException as error:
                    self.note("OWN_JOB_PID_QUERY_FAILED:" + str(error))
            self._reap()

    def start(self, handle):
        self.job_handle = int(handle)
        self.poll()
        def monitor():
            while not self.stop.is_set():
                if time.monotonic() >= self.deadline:
                    self.note("TREE_OBSERVER_ORIGINAL_DEADLINE")
                    break
                try:
                    self.poll()
                except BaseException as error:
                    self.note("TREE_MONITOR_POLL_EXCEPTION:" + str(error))
                    break
                self.stop.wait(0.005)
        self.thread = threading.Thread(target=monitor, name="r13-own-job-peak", daemon=True)
        self.thread.start()

    def before_job_close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=max(0, min(0.25, self.deadline - time.monotonic())))
        if self.thread is not None and self.thread.is_alive():
            self.note("TREE_MONITOR_NOT_JOINED")
            return
        self.poll()

    def seal(self):
        # No Job queries after the original Job handle closed. Exit-only
        # cleanup may reap handles whose processes were killed by that close.
        until = min(self.deadline, time.monotonic() + 0.5)
        while self.live:
            self.poll(query_job=False)
            remaining = until - time.monotonic()
            if not self.live or remaining <= 0:
                break
            # before_job_close has already set stop; stop.wait would return
            # immediately. Wait on an actual retained member instead, within
            # the unchanged original deadline, for delayed console cleanup.
            handle = next(iter(self.live.values()))["monitor_handle"]
            self.kernel.WaitForSingleObject(handle, max(1, min(20, int(remaining * 1000))))
        supervisor = None
        try:
            supervisor = {"metric": "PeakWorkingSet64", "bytes": self._peak(self.kernel.GetCurrentProcess()),
                          "scope": "SUPERVISOR_LIFETIME_UP_TO_PROOF_SEAL_NOT_MEMBER_SUM"}
        except BaseException as error:
            self.note("SUPERVISOR_PEAK_QUERY:" + str(error))
        identities = {(item["pid"], item["creation_time_100ns"]) for item in self.members}
        complete = (bool(self.members) and len(identities) == len(self.members)
                    and any(item["root"] and item["pid"] == self.root_pid for item in self.members)
                    and not self.live and not self.pending and not self.failures
                    and (self.thread is None or not self.thread.is_alive()) and
                    all(item["creation_time_100ns"] and item["membership_verified"] and
                        item["exit_signaled"] and item["exit_time_100ns"] and
                        type(item["final_peak_bytes"]) is int and item["final_peak_bytes"] > 0 and
                        type(item["close_bool"]) is int and item["close_bool"] != 0 and
                        item["close_winerror"] == 0
                        for item in self.members))
        return {"kind": "TREE_PEAK_PROOF", "metric": "SUM_OF_MEMBER_FINAL_LIFETIME_PEAK_WORKING_SETS",
                "interpretation": "CONSERVATIVE_UPPER_BOUND_ON_CONCURRENT_TREE_PEAK",
                "job_handle": self.job_handle, "root_pid": self.root_pid,
                "capture_complete_before_original_total_reconciliation": complete,
                "captured_identity_count": len(identities), "last_observed_job_total": self.last_total,
                "sum_final_peaks_upper_bound_bytes": sum(item["final_peak_bytes"] for item in self.members)
                    if complete else None,
                "members": [dict(item) for item in self.members],
                "live_monitor_handles": len(self.live), "lookup_handle_closes": self.lookup_closes,
                "lookup_close_failures": self.lookup_close_failures,
                "job_pid_list_queries": self.query_count, "open_process_attempts": self.open_attempts,
                "pending": list(self.pending), "failures": list(self.failures),
                "supervisor_peak_separate": supervisor,
                "supervisor_final_exit_peak": "REQUIRES_OUTER_PARENT_OBSERVATION_IF_NEEDED",
                "original_deadline_monotonic": self.deadline}


def make_native_close_observation(deadline_monotonic):
    events = []
    tree = _TreePeakObserver(deadline_monotonic)
    root_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    root_close_api = root_kernel.CloseHandle
    root_close_api.argtypes = [wintypes.HANDLE]
    root_close_api.restype = wintypes.BOOL

    def hvalue(value):
        return int(value.value if hasattr(value, "value") else value)

    def native_once(role, value, api):
        handle = hvalue(value)
        ctypes.set_last_error(0)
        try:
            result = api(wintypes.HANDLE(handle))
        except BaseException as error:
            events.append({"kind": "NATIVE_CLOSE", "role": role,
                           "handle": handle, "bool_return": None,
                           "error": type(error).__name__ + ":" + str(error),
                           "at": time.monotonic()})
            raise
        winerror = ctypes.get_last_error() if not result else 0
        events.append({"kind": "NATIVE_CLOSE", "role": role,
                       "handle": handle, "bool_return": int(result),
                       "winerror": int(winerror), "at": time.monotonic()})
        return result, winerror

    def private_owner_exec(code, namespace):
        if (namespace.get("__name__") != "_r12_unchanged_job_owner" or
                not isinstance(code, types.CodeType) or
                code.co_filename != str(WINDOWS_JOB)):
            raise RuntimeError("ONLY_PINNED_PRIVATE_JOB_OWNER_EXEC")
        builtins.exec(code, namespace)
        original_job = namespace["WindowsJob"]

        class ObservedJob(original_job):
            def __init__(self):
                super().__init__()
                try:
                    original_api = self.kernel.CloseHandle
                    original_api.restype = wintypes.BOOL
                    observed_handle = hvalue(self.handle)

                    def observed_job_close(value):
                        result, _ = native_once("job", value, original_api)
                        return result

                    self.kernel.CloseHandle = observed_job_close
                    events.append({"kind": "HOOK_INSTALLED", "role": "job",
                                   "handle": observed_handle})
                except BaseException as error:
                    events.append({"kind": "HOOK_INSTALL_FAILED", "role": "job",
                                   "error": type(error).__name__ + ":" +
                                            str(error)})

            def attach_and_resume(self, process):
                # The real root handle was duplicated while Popen's process
                # was suspended. Start only an observer thread before calling
                # the unchanged assign-and-resume method, not a new process.
                try:
                    tree.start(self.handle)
                except BaseException as error:
                    tree.note("MONITOR_START_FAILED:" + str(error))
                super().attach_and_resume(process)
                tree.assigned = True
                try:
                    tree.poll()
                except BaseException as error:
                    tree.note("AFTER_RESUME_OBSERVATION:" + str(error))

            def close(self):
                try:
                    tree.before_job_close()
                except BaseException as error:
                    tree.note("MONITOR_PRE_CLOSE:" + str(error))
                try:
                    super().close()  # original native Job close remains sole owner
                finally:
                    tree.job_closed = True
                    try:
                        events.append(tree.seal())
                    except BaseException as error:
                        events.append({"kind": "TREE_PEAK_PROOF", "pending": [
                            "TREE_PROOF_SEAL_FAILED:" + str(error)], "failures": []})

        namespace["WindowsJob"] = ObservedJob

    def private_popen(*args, **kwargs):
        process = subprocess.Popen(*args, **kwargs)
        try:
            handle = process._handle
            original_close = handle.Close
            observed_handle = int(handle)

            def root_native_callback(value):
                result, winerror = native_once("root", value, root_close_api)
                if not result:
                    raise ctypes.WinError(winerror)
                return None

            def observed_root_close():
                try:
                    # Reap exited query handles before the original root
                    # handle is released and the frozen Job0 drain starts.
                    tree.poll()
                except BaseException as error:
                    tree.note("ROOT_PRE_CLOSE_OBSERVATION:" + str(error))
                return original_close(CloseHandle=root_native_callback)

            handle.Close = observed_root_close
            events.append({"kind": "HOOK_INSTALLED", "role": "root",
                           "handle": observed_handle, "pid": process.pid})
        except BaseException as error:
            events.append({"kind": "HOOK_INSTALL_FAILED", "role": "root",
                           "error": type(error).__name__ + ":" + str(error)})
        try:
            if not kwargs.get("creationflags", 0) & 0x4:
                tree.note("ROOT_NOT_CREATED_SUSPENDED", failed=True)
            tree.bind_root(process)
        except BaseException as error:
            tree.note("ROOT_QUERY_PIN_FAILED:" + str(error))
        return process

    private_builtins = dict(vars(builtins))
    private_builtins["exec"] = private_owner_exec
    private_subprocess = types.SimpleNamespace(
        Popen=private_popen, DEVNULL=subprocess.DEVNULL,
        TimeoutExpired=subprocess.TimeoutExpired)
    return {"__builtins__": private_builtins,
            "subprocess": private_subprocess}, events


def frozen_owned_call(deadline_monotonic):
    raw = _frozen(R12_SELFTEST, R12_SELFTEST_SHA)
    _frozen(WINDOWS_JOB, WINDOWS_JOB_SHA)
    tree = ast.parse(raw, filename=str(R12_SELFTEST))
    wanted = {"JobAccounting", "job_accounting", "peak_working_set", "owned_call"}
    nodes = [node for node in tree.body if isinstance(
        node, (ast.ClassDef, ast.FunctionDef)) and node.name in wanted]
    require({node.name for node in nodes} == wanted, "FROZEN_OWNER_DEFINITIONS")
    module = types.ModuleType("_r13_frozen_owned_call")
    module.__dict__.update({
        "ctypes": ctypes, "wintypes": wintypes, "datetime": datetime,
        "timezone": timezone, "hashlib": hashlib, "json": json, "os": os,
        "Path": Path, "subprocess": subprocess, "threading": threading,
        "time": time, "types": types, "ROOT": ROOT, "OUTPUT": OUTPUT})
    observation_bindings, close_events = make_native_close_observation(deadline_monotonic)
    module.__dict__.update(observation_bindings)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(R12_SELFTEST),
                 "exec", dont_inherit=True), module.__dict__)
    return module.owned_call, close_events


def assess(record, cap, close_events, *, expected_exit="NATURAL",
           expected_code=0, require_descendant=False):
    issues, pending = [], []
    for field in ("job_handle_closed", "root_process_handle_closed",
                  "job_zero_observed_before_job_close", "within_cap"):
        if record.get(field) is not True:
            issues.append(field)
    if (record.get("exit_class") != expected_exit or
            record.get("exit_code") != expected_code):
        issues.append("EXPECTED_EXIT:" + expected_exit + ":" +
                      str(expected_code))
    samples = record.get("samples", [])
    if not samples or samples[-1].get("active") != 0:
        issues.append("JOB_ZERO_SAMPLE")
    observations = [record.get("before_root_handle_close", {})] + samples
    totals = {item.get("total") for item in observations
              if isinstance(item, dict) and
              isinstance(item.get("total"), int)}
    if not observations or any(not isinstance(item, dict) or
                               not isinstance(item.get("total"), int)
                               or item.get("returned_bytes") != 48
                               for item in observations):
        issues.append("JOB_TOTAL_OBSERVATION_MALFORMED")
    if require_descendant:
        if not any(isinstance(total, int) and total >= 2 for total in totals):
            issues.append("DESCENDANT_NOT_OBSERVED:" + str(sorted(totals)))
    # Descendants are allowed only with complete member identities and an OS
    # lifetime-peak upper bound. A sampled working-set maximum is not used.
    peak = record.get("peak_working_set", {})
    if (type(peak.get("bytes")) is not int or peak["bytes"] <= 0 or
            peak.get("pointer_bits") != 64 or
            "PeakWorkingSet64" not in str(peak.get("metric", ""))):
        issues.append("WORKER_64BIT_PEAK_MISSING")
    elif peak["bytes"] > 512 * 1024 * 1024:
        issues.append("WORKER_PEAK_512MIB")
    for role in ("root", "job"):
        hooks = [item for item in close_events
                 if item.get("kind") == "HOOK_INSTALLED" and
                 item.get("role") == role]
        closes = [item for item in close_events
                  if item.get("kind") == "NATIVE_CLOSE" and
                  item.get("role") == role]
        if (len(hooks) != 1 or len(closes) != 1 or
                hooks[0].get("handle") != closes[0].get("handle") or
                type(closes[0].get("bool_return")) is not int or
                closes[0].get("bool_return") == 0 or
                closes[0].get("winerror") != 0):
            issues.append("NATIVE_CLOSE_PROOF:" + role)
        if role == "root" and hooks and hooks[0].get("pid") != record.get("pid"):
            issues.append("NATIVE_CLOSE_ROOT_PID_BINDING")
    if any(item.get("kind") == "HOOK_INSTALL_FAILED"
           for item in close_events):
        issues.append("NATIVE_CLOSE_HOOK_FAILED")
    job_close = [item for item in close_events
                 if item.get("kind") == "NATIVE_CLOSE" and
                 item.get("role") == "job"]
    if (job_close and samples and
            job_close[0].get("at", 0) < samples[-1].get("monotonic", 1)):
        issues.append("JOB_CLOSED_BEFORE_JOB_ZERO")
    tree_proofs = [item for item in close_events if item.get("kind") == "TREE_PEAK_PROOF"]
    tree_proof = tree_proofs[0] if len(tree_proofs) == 1 else {}
    if len(tree_proofs) != 1:
        pending.append("EXACTLY_ONE_MEMBER_TREE_PROOF_REQUIRED")
    pending.extend(tree_proof.get("pending", []))
    issues.extend(tree_proof.get("failures", []))
    final_total = samples[-1].get("total") if samples else None
    members = tree_proof.get("members", [])
    identities = {(item.get("pid"), item.get("creation_time_100ns")) for item in members}
    job_hooks = [item for item in close_events if item.get("kind") == "HOOK_INSTALLED" and item.get("role") == "job"]
    if (tree_proof.get("capture_complete_before_original_total_reconciliation") is not True
            or type(final_total) is not int or final_total <= 0
            or tree_proof.get("captured_identity_count") != final_total
            or tree_proof.get("last_observed_job_total") != final_total
            or len(identities) != final_total or len(members) != final_total
            or tree_proof.get("root_pid") != record.get("pid")
            or not job_hooks or tree_proof.get("job_handle") != job_hooks[0].get("handle")):
        pending.append("JOB_CUMULATIVE_TOTAL_MEMBER_IDENTITIES_NOT_COMPLETE")
    upper = tree_proof.get("sum_final_peaks_upper_bound_bytes")
    if type(upper) is not int or upper <= 0:
        pending.append("MEMBER_FINAL_LIFETIME_PEAK_SUM_MISSING")
    elif upper > 512 * 1024 * 1024:
        issues.append("TREE_LIFETIME_PEAK_SUM_UPPER_BOUND_OVER_512MIB")
    if (not all(type(item.get("final_peak_bytes")) is int and item["final_peak_bytes"] > 0
                for item in members) or not members or
            upper != sum(item.get("final_peak_bytes", 0) or 0 for item in members)):
        pending.append("FINAL_MEMBER_PEAK_SUM_NOT_RECONCILED")
    for item in members:
        if (not item.get("membership_verified") or not item.get("exit_signaled")
                or type(item.get("final_peak_bytes")) is not int or item["final_peak_bytes"] <= 0
                or not item.get("creation_time_100ns") or not item.get("exit_time_100ns")
                or not item.get("close_bool") or item.get("close_winerror") != 0
                or item.get("final_peak_at") is None or item.get("close_at") is None
                or item["close_at"] < item["final_peak_at"]
                or (job_close and item["close_at"] > job_close[0].get("at", 0))):
            pending.append("FINAL_MEMBER_PEAK_EXIT_AND_QUERY_CLOSE_ORDER:" + str(item.get("pid")))
    root_hooks = [item for item in close_events if item.get("kind") == "HOOK_INSTALLED"
                  and item.get("role") == "root"]
    root_closes = [item for item in close_events if item.get("kind") == "NATIVE_CLOSE"
                   and item.get("role") == "root"]
    roots = [item for item in members if item.get("root") and item.get("pid") == record.get("pid")]
    if (len(roots) != 1 or not root_hooks or not root_closes or
            roots[0].get("monitor_handle") == root_hooks[0].get("handle") or
            roots[0].get("close_at") is None or
            roots[0]["close_at"] > root_closes[0].get("at", 0)):
        pending.append("ROOT_MONITOR_DUPLICATE_NOT_CLOSED_BEFORE_ORIGINAL_ROOT_HANDLE")
    if roots and type(peak.get("bytes")) is int and (
            type(roots[0].get("final_peak_bytes")) is not int or
            roots[0]["final_peak_bytes"] < peak["bytes"]):
        pending.append("ROOT_MEMBER_FINAL_PEAK_BELOW_ORIGINAL_OWNER_PEAK")
    if tree_proof.get("supervisor_peak_separate") is None:
        pending.append("SUPERVISOR_PEAK_SEPARATE_RECORD_MISSING")
    return {"status": "FAIL" if issues else "PENDING" if pending else "PASS",
            "issues": issues, "pending": pending,
            "tree_peak_proof": tree_proof,
            "native_close_events": close_events,
            "this_owned_call_parent_observation": True}


def execute(admission_path, admission_sha, owner_output):
    record = read_control(admission_path, admission_sha)["value"]
    group = record.get("group")
    require(group in CAPS and record.get("state") == "CONSUMED_RUNNING" and
            record.get("absolute_cap_seconds") == CAPS[group],
            "CONSUMED_ADMISSION")
    owner_output = strict_child(OUTPUT, owner_output)
    actual_owner = owner_output / "B02" if group == "B" else owner_output
    worker_output = actual_owner / "worker"
    require(not owner_output.exists(), "FRESH_OWNER_OUTPUT")
    argv_template = record.get("argv")
    expected = [str(Path(sys.executable).resolve()), "-X", "utf8", "-B",
                str((HERE / "selftest.py").resolve()), "--worker", "--group",
                group, "--admission", str(Path(admission_path).resolve()),
                "--admission-sha256", "@ADMISSION_SHA256@", "--output",
                str(worker_output.resolve())]
    require(argv_template == expected and worker_output != owner_output,
            "FROZEN_WORKER_ARGV")
    # The external digest binds this entire template. Embedding the digest in
    # the document it hashes would require an impossible SHA fixed point.
    argv = [admission_sha if value == "@ADMISSION_SHA256@" else value
            for value in argv_template]
    started = time.monotonic()
    root_deadline = record.get("root_deadline_monotonic")
    require(type(root_deadline) in (float, int), "ROOT_ABSOLUTE_DEADLINE_REQUIRED")
    owned_call, close_events = frozen_owned_call(root_deadline)
    # The parent reserve covers source loading, Job0/close and final receipts.
    # Never start a fresh full-cap clock in the nested owner.
    actual_cap = min(B_ACTUAL_CAP if group == "B" else CAPS[group],
                     root_deadline - time.monotonic() - 7)
    require(actual_cap > 5, "NO_PARENT_CLOSE_RESERVE")
    result = owned_call(argv, ROOT, actual_owner, actual_cap)
    actual_assessment = assess(result, actual_cap, close_events)
    parent_cases = {"B02": {"owned": result,
                             "assessment": actual_assessment}}
    if group == "B" and actual_assessment["status"] == "PASS":
        fixture_base = [str(Path(sys.executable).resolve()), "-X", "utf8", "-B",
                        str(Path(__file__).resolve()), "--fixture"]
        for case_id, fixture, cap, natural_wait, exit_class, exit_code in (
                ("B03", "descendant", B_DESCENDANT_CAP, None, "NATURAL", 0),
                ("B04", "timeout", B_TIMEOUT_CAP, 1.0,
                 "OWNED_TERMINATED_TIMEOUT", 124)):
            require(time.monotonic() + cap + 4 < root_deadline and
                    time.monotonic() - started + cap + 5 < CAPS["B"],
                    "B_PARENT_ABSOLUTE_BUDGET")
            call, events = frozen_owned_call(root_deadline)
            case_result = call(fixture_base + [fixture], ROOT,
                               owner_output / case_id, cap,
                               natural_wait=natural_wait)
            case_assessment = assess(
                case_result, cap, events, expected_exit=exit_class,
                expected_code=exit_code, require_descendant=True)
            stdout = _small_bytes(owner_output / case_id / "stdout.bin")
            require(b"R13_PARENT_READY child_pid=" in stdout and
                    b"R13_CHILD_READY" in stdout,
                    "FIXTURE_READY_EVIDENCE:" + case_id)
            if case_id == "B03":
                require(b"R13_PARENT_DONE" in stdout and
                        b"R13_CHILD_DONE" in stdout,
                        "FIXTURE_NATURAL_EVIDENCE")
            else:
                require(b"R13_PARENT_DONE" not in stdout and
                        b"R13_CHILD_DONE" not in stdout,
                        "FIXTURE_TIMEOUT_EVIDENCE")
            parent_cases[case_id] = {"owned": case_result,
                                     "assessment": case_assessment}
            if case_assessment["status"] != "PASS":
                break
    assessments = [item["assessment"] for item in parent_cases.values()]
    overall = ("PASS" if len(parent_cases) == 3 and
               all(item["status"] == "PASS" for item in assessments)
               else "FAIL" if any(item["status"] == "FAIL"
                                  for item in assessments) else "PENDING")
    receipt = {"schema": "M3_R13_OWNED_GROUP_RESULT_V1",
               "group": group, "owned": result,
               "assessment": actual_assessment,
               "parent_cases": parent_cases if group == "B" else {},
               "status": overall if group == "B" else
                         actual_assessment["status"],
               "B02_B03_B04_parent_observation":
                   (group == "B" and len(parent_cases) == 3 and
                    all(item["assessment"]["status"] == "PASS"
                        for item in parent_cases.values())),
               "elapsed_seconds": time.monotonic() - started}
    if group == "B" and receipt["elapsed_seconds"] > CAPS["B"]:
        receipt["status"] = "FAIL"
        receipt["budget_error"] = "B_PARENT_ABSOLUTE_CAP_EXCEEDED"
    if receipt["status"] == "PASS":
        atomic_json(owner_output / "GROUP_COMPLETE.json", receipt)
    return receipt


def fixture(kind):
    require(kind in {"descendant", "timeout"}, "FIXTURE_KIND")
    child_code = ("import time; print('R13_CHILD_READY', flush=True); "
                  "time.sleep(" + ("0.2" if kind == "descendant" else "60") +
                  "); print('R13_CHILD_DONE', flush=True)")
    child = subprocess.Popen([str(Path(sys.executable).resolve()), "-X", "utf8",
                              "-B", "-c", child_code])
    print("R13_PARENT_READY child_pid=" + str(child.pid), flush=True)
    if kind == "descendant":
        require(child.wait(timeout=2) == 0, "FIXTURE_CHILD_EXIT")
        print("R13_PARENT_DONE", flush=True)
        return 0
    time.sleep(60)
    return 99


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--execute-one", action="store_true")
    actions.add_argument("--fixture", choices=("descendant", "timeout"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--admission-sha256")
    parser.add_argument("--owner-output", type=Path)
    args = parser.parse_args()
    if args.fixture:
        return fixture(args.fixture)
    require(args.admission is not None and args.admission_sha256 and
            args.owner_output is not None, "EXECUTE_ARGUMENTS")
    result = execute(args.admission, args.admission_sha256, args.owner_output)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] == "PASS":
        return 0
    return 3 if result["status"] == "PENDING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
