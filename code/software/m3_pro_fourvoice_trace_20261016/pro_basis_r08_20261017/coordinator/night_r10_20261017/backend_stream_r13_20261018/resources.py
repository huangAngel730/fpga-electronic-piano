"""Resource admission and post-run accounting for R13 workers."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import shutil
import math
import time
import hashlib
import sys

from stream_bridge import require

MIB = 1024 * 1024
GIB = 1024 * MIB
WORKER_LIMIT = 512 * MIB
WORKSPACE_LIMIT = 24 * GIB
START_FREE = 32 * GIB
END_RESERVE = 8 * GIB


def allocation_unit(path: Path) -> dict:
    """Actual volume query when root executes P0; no guessed cluster size."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    volume_path = kernel.GetVolumePathNameW
    volume_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    volume_path.restype = wintypes.BOOL
    target = ctypes.create_unicode_buffer(32768)
    if not volume_path(str(Path(path).absolute()), target, len(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    query = kernel.GetDiskFreeSpaceW
    query.argtypes = [wintypes.LPCWSTR] + [ctypes.POINTER(wintypes.DWORD)] * 4
    query.restype = wintypes.BOOL
    sectors, sector_bytes, free, total = (wintypes.DWORD() for _ in range(4))
    if not query(target.value, ctypes.byref(sectors), ctypes.byref(sector_bytes),
                 ctypes.byref(free), ctypes.byref(total)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"metric": "GetDiskFreeSpaceW", "volume": target.value,
            "sectors_per_allocation_unit": sectors.value,
            "bytes_per_sector": sector_bytes.value,
            "allocation_unit_bytes": sectors.value * sector_bytes.value}


def file_allocation(path: Path) -> dict:
    """Observe FILE_STANDARD_INFO.AllocationSize; always close the query handle."""
    class StandardInfo(ctypes.Structure):
        _fields_ = [("allocation", ctypes.c_int64), ("eof", ctypes.c_int64),
                    ("links", wintypes.DWORD), ("delete_pending", ctypes.c_ubyte),
                    ("directory", ctypes.c_ubyte)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    query = kernel.GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    query.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes, close.restype = [wintypes.HANDLE], wintypes.BOOL
    handle = create(str(path), 0x80, 7, None, 3, 0, None)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    primary = None
    try:
        data = StandardInfo()
        if not query(handle, 1, ctypes.byref(data), ctypes.sizeof(data)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"allocation_bytes": int(data.allocation),
                "end_of_file_bytes": int(data.eof), "links": int(data.links),
                "metric": "FILE_STANDARD_INFO.AllocationSize"}
    except BaseException as error:
        primary = error
        raise
    finally:
        if not close(handle):
            close_error = ctypes.WinError(ctypes.get_last_error())
            if primary is None:
                raise close_error
            if _ACTIVE_BUDGET is not None:
                _ACTIVE_BUDGET.secondary(close_error)
            elif hasattr(primary, "add_note"):
                primary.add_note("Allocation observation handle close failed: " + str(close_error))


def disk_snapshot(path: Path) -> dict:
    """Current whole-tree observation; not a historical peak or MFT theorem."""
    path = Path(path).absolute()
    usage = shutil.disk_usage(path if path.exists() else path.parent)
    files, total, allocated = 0, 0, 0
    errors, observations = [], []
    unit = None
    try:
        unit = allocation_unit(path)
    except (OSError, AttributeError) as error:
        errors.append("ALLOCATION_UNIT:" + str(error))
    pending = [path] if path.exists() else []
    while pending:
        directory = pending.pop()
        info = directory.lstat()
        require(not (info.st_file_attributes & 0x400) if hasattr(info, "st_file_attributes")
                else not directory.is_symlink(), "SNAPSHOT_REPARSE")
        with os.scandir(directory) as entries:
            for entry in entries:
                item, info = Path(entry.path), entry.stat(follow_symlinks=False)
                require(not stat.S_ISLNK(info.st_mode) and not (
                    getattr(info, "st_file_attributes", 0) & 0x400), "SNAPSHOT_REPARSE")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(item)
                elif stat.S_ISREG(info.st_mode):
                    files += 1
                    total += info.st_size
                    try:
                        observed = file_allocation(item)
                        require(observed["end_of_file_bytes"] == info.st_size,
                                "SNAPSHOT_FILE_CHANGED")
                        allocated += observed["allocation_bytes"]
                        observations.append({"path": str(item), **observed})
                    except (OSError, AttributeError) as error:
                        errors.append("FILE_ALLOCATION:" + str(item) + ":" + str(error))
                else:
                    errors.append("SPECIAL_FILE:" + str(item))
    return {"path": str(path), "files": files, "tree_bytes": total,
            "allocation_size_bytes": allocated if not errors else None,
            "allocation_unit": unit,
            "allocation_unit_bytes": None if unit is None else unit["allocation_unit_bytes"],
            "allocation_observations": observations, "observation_errors": errors,
            "allocation_observation_complete": not errors,
            "metric_scope": "CURRENT_REGULAR_ARTIFACT_FILES_NOT_VOLUME_METADATA",
            "disk_total": usage.total, "disk_used": usage.used,
            "disk_free": usage.free}


def preflight(path: Path, *, full_window: bool) -> dict:
    snap = disk_snapshot(_OUTPUT if full_window else path)
    configured = (_ACTIVE_BUDGET is not None and _ACTIVE_BUDGET.configured)
    decision = "GO" if (not full_window or (
        configured and _ACTIVE_BUDGET.full_window and snap["disk_free"] >= START_FREE
        and snap["allocation_observation_complete"]
        and max(snap["tree_bytes"], snap["allocation_size_bytes"]) <= WORKSPACE_LIMIT)) else "NO_GO"
    return {"schema": "M3_R13_RESOURCE_PREFLIGHT_V1", **snap,
            "full_window": full_window, "required_start_free": START_FREE,
            "workspace_limit": WORKSPACE_LIMIT, "end_reserve": END_RESERVE,
            "accounting_configured": configured,
            "decision": decision}


def process_peak(process_handle: int) -> dict:
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in
            ("peak_working_set", "working_set", "peak_paged", "paged",
             "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
    api = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    api.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    api.restype = wintypes.BOOL
    data = Counters()
    data.cb = ctypes.sizeof(data)
    if not api(wintypes.HANDLE(process_handle), ctypes.byref(data), data.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"metric": "PROCESS_MEMORY_COUNTERS.PeakWorkingSetSize",
            "bytes": int(data.peak_working_set), "limit": WORKER_LIMIT}


def finalize_resources(path: Path, peak: dict, job: dict) -> dict:
    actual_path = Path(path).absolute()
    snap = disk_snapshot(_OUTPUT if actual_path.is_relative_to(_OUTPUT) else actual_path)
    accounting = job.get("accounting_receipt")
    if not isinstance(accounting, dict) and _ACTIVE_BUDGET is not None:
        accounting = _ACTIVE_BUDGET.receipt()
    observations = [job.get("before_root_handle_close")] + list(
        job.get("samples", []))
    totals = []
    malformed = False
    for observation in observations:
        if not isinstance(observation, dict):
            malformed = True
            continue
        total = observation.get("total")
        if type(total) is not int or total < 0:
            malformed = True
            continue
        totals.append(total)
    no_descendants = (not malformed and bool(totals) and
                      set(totals) <= {0, 1} and 1 in totals)
    child_count = (max(totals) - 1 if no_descendants else None)
    native_close_bool = job.get("native_close_bool_recorded") is True
    result = {"schema": "M3_R13_RESOURCE_RESULT_V1", **snap,
              "worker_peak": peak, "job": job,
              "observed_job_totals": totals,
              "job_observations_malformed": malformed,
              "child_processes_inferred": child_count,
              "worker_peak_is_tree_peak": no_descendants,
              "native_close_bool_recorded": native_close_bool,
              "accounting": accounting,
              "scope": "RESOURCE_OBSERVATIONS_REQUIRES_ROOT_FROZEN_WRITER_CLOSURE",
              "workspace_limit": WORKSPACE_LIMIT,
              "end_reserve": END_RESERVE}
    result["observation_pass"] = (type(peak.get("bytes")) is int and
                      0 < peak["bytes"] <= WORKER_LIMIT and
                      snap["tree_bytes"] <= WORKSPACE_LIMIT and
                      snap["allocation_observation_complete"] and
                      snap["allocation_size_bytes"] <= WORKSPACE_LIMIT and
                      snap["disk_free"] >= END_RESERVE and
                      no_descendants and native_close_bool and
                      job.get("job_zero_observed_before_job_close") is True and
                      job.get("root_process_handle_closed") is True and
                      job.get("job_handle_closed") is True)
    accounting_ok = (isinstance(accounting, dict) and accounting.get("configured") is True
                     and accounting.get("unclosed_writers") == 0
                     and type(accounting.get("total_reserved_upper_bytes")) is int
                     and 0 <= accounting["total_reserved_upper_bytes"] <= WORKSPACE_LIMIT
                     and type(accounting.get("max_physical_write")) is int
                     and 0 <= accounting["max_physical_write"] <= CHUNK
                     and type(accounting.get("max_physical_read")) is int
                     and 0 <= accounting["max_physical_read"] <= CHUNK
                     and not accounting.get("secondary_errors"))
    result["pass"] = result["observation_pass"] and accounting_ok
    result["resource_status"] = "PASS_LIMIT_OBSERVATIONS" if result["pass"] else "PENDING_OR_FAILED"
    return result


# Root-adopted R13 global accounting candidate; original L0 handoff retained.
"""R13 W-only global prewrite candidate; static, unexecuted support artifact.

Every store and plain writer in ONE worker must share the same instance.
External parent logs require a frozen finite escrow, never an unfunded second
budget. This is not a runner, process monitor, or an execution permission.
"""

import io
import os
from pathlib import Path
import shutil
import stat
import threading


MIB = 1024 * 1024
GIB = 1024 * MIB
CHUNK = MIB
LIMITS = {
    "gzip_payload": 8 * GIB,
    "delivery_copy": 8 * GIB,
    "plain_raw": 4631191552,
    "baseline": 512 * MIB,
    "plain_aux": 5 * GIB // 2,
    "control": 480 * MIB,
    "failure": 32 * MIB,
    "fs_allowance": 200646656,
}
MAX_FILES = 16384
MAX_PAYLOAD_PARTS = 2048
MAX_DELIVERY_PARTS = 2048
MAX_ORDINARY_FILES = 8192
MAX_FAILURE_FILES = 128  # included within ordinary; normal ordinary <=3968
MAX_DIRS = 8192
LOG_ROLES = {"owner_stdout", "owner_stderr", "owner_result", "parent_summary"}


class R13BudgetViolation(ValueError):
    pass


def _count(value, label):
    if type(value) is not int or value < 0:
        raise R13BudgetViolation("NONNEGATIVE_INTEGER:" + label)
    return value


class R13GlobalBudget:
    def __init__(self, root, *, allocation_unit_bytes,
                 file_metadata_bound_bytes, directory_bound_bytes,
                 filesystem_bound_evidence, initial_roles=None,
                 external_log_escrows=None, deadline_monotonic=None,
                 full_window=True, configured=True, scan_baseline=True):
        self.root = Path(os.path.abspath(root))
        self.configured, self.full_window = configured, full_window
        self._deadline = deadline_monotonic
        if configured and self.root.name != "m3_backend_stream_r13_20261018":
            raise R13BudgetViolation("WHOLE_R13_OUTPUT_ROOT_REQUIRED")
        self._owner_pid = os.getpid()
        self._lock = threading.RLock()
        self._files, self._dirs, self._external = {}, set(), {}
        self._counts = {"payload_part": 0, "delivery_part": 0,
                        "ordinary": 0, "failure": 0}
        self.reserved = {key: 0 for key in LIMITS}
        self.actual_io = {key: 0 for key in LIMITS}
        self.unknown_actual_upper = {key: 0 for key in LIMITS}
        self._errors, self._rejections = [], 0
        self._writes, self._max_write, self._short_writes = 0, 0, 0
        self._reads, self._max_read = 0, 0
        self._baseline_bytes, self._baseline_files = 0, 0
        self._baseline_allocated, self._baseline_allocation_excess = 0, 0
        self._allocation_unit = _count(allocation_unit_bytes, "allocation_unit")
        file_meta = _count(file_metadata_bound_bytes, "file_metadata")
        dir_bound = _count(directory_bound_bytes, "directory_bound")
        self._file_metadata_bound, self._directory_bound = file_meta, dir_bound
        if (self._allocation_unit <= 0
                or self._allocation_unit & (self._allocation_unit - 1)
                or not filesystem_bound_evidence):
            raise R13BudgetViolation("FROZEN_FILESYSTEM_BOUNDS_REQUIRED")
        self.fs_bound = (MAX_FILES * (self._allocation_unit - 1 + file_meta)
                         + MAX_DIRS * dir_bound)
        if self.fs_bound > LIMITS["fs_allowance"]:
            raise R13BudgetViolation("ALLOCATION_AND_METADATA_ALLOWANCE_EXCEEDED")
        self.fs_evidence = filesystem_bound_evidence
        # Whole allowance is permanently charged up front; no deletion,
        # truncation, rename or IO failure can refund any part of it.
        self.reserved["fs_allowance"] = LIMITS["fs_allowance"]
        self._path(self.root, allow_root=True)
        if configured and not self.root.is_dir():
            raise R13BudgetViolation("EXISTING_WORKSPACE_ROOT_REQUIRED")
        initial_roles = initial_roles or {}
        # Parent freezes these BEFORE launching the original owner. The worker
        # imports the already-funded finite envelopes, not a second permission
        # to spend the same workspace budget. Files can already exist here.
        for relative, escrow in (external_log_escrows or {}).items():
            path = self._path(self.root / relative)
            if relative in initial_roles:
                raise R13BudgetViolation("EXTERNAL_AND_BASELINE_ROLE_OVERLAP")
            self._validate_external(escrow["role"], escrow["byte_cap"],
                                    escrow["evidence"], escrow["max_physical_write"])
            key = str(path).casefold()
            if key in self._external:
                raise R13BudgetViolation("DUPLICATE_EXTERNAL_PATH")
            self._register_file(path, "failure", "ordinary")
            self._charge("failure", escrow["byte_cap"])
            self._external[key] = {
                "path": str(path), "role": escrow["role"],
                "reserved": escrow["byte_cap"], "actual": None,
                "evidence": escrow["evidence"],
                "max_physical_write": escrow["max_physical_write"]}
        visited = set()
        pending = [self.root] if scan_baseline else []
        while pending:
            self.check()
            directory = pending.pop()
            self._register_dir(directory)
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = self._path(entry.path)
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(path)
                    elif stat.S_ISREG(info.st_mode):
                        relative = path.relative_to(self.root).as_posix()
                        key = str(path).casefold()
                        category = ("failure" if key in self._external else
                                    initial_roles.get(relative, "baseline"))
                        kind = ("payload_part" if category == "gzip_payload" else
                                "delivery_part" if category == "delivery_copy" else
                                "ordinary")
                        state = self._register_file(path, category, kind, info.st_size)
                        state["extent"], state["present"] = info.st_size, True
                        if key in self._external:
                            if info.st_size > self._external[key]["reserved"]:
                                raise R13BudgetViolation("EXTERNAL_BOUND_BROKEN_AT_START")
                        else:
                            self._charge(category, info.st_size)
                        self._baseline_bytes += info.st_size
                        self._baseline_files += 1
                        if configured:
                            allocation = file_allocation(path)
                            allocated = allocation["allocation_bytes"]
                            require(allocated >= 0, "NEGATIVE_ALLOCATION_SIZE")
                            self._baseline_allocated += allocated
                            self._baseline_allocation_excess += max(
                                0, allocated - info.st_size - (self._allocation_unit - 1))
                            if self.fs_bound + self._baseline_allocation_excess > LIMITS["fs_allowance"]:
                                self._reject("BASELINE_ALLOCATION_EXCESS_OVER_FS_ALLOWANCE")
                        visited.add(relative)
                    else:
                        raise R13BudgetViolation("SPECIAL_BASELINE_FILE")
        if set(initial_roles) - visited:
            raise R13BudgetViolation("UNMATCHED_BASELINE_ROLE")
        free_root = self.root
        while not free_root.exists():
            free_root = free_root.parent
        self.initial_free = shutil.disk_usage(free_root).free
        self.min_free_observed = self.initial_free
        if full_window and self.initial_free < 32 * GIB:
            raise R13BudgetViolation("INITIAL_FREE_BELOW_32GIB")

    def _same_owner(self):
        if os.getpid() != self._owner_pid:
            raise R13BudgetViolation("BUDGET_COPY_OR_CROSS_PROCESS_USE_FORBIDDEN")
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise TimeoutError("R13_ABSOLUTE_MONOTONIC_DEADLINE")

    def check(self):
        self._same_owner()
        if sum(self.reserved.values()) > WORKSPACE_LIMIT:
            self._reject("GLOBAL_RESERVED_OVER_24GIB")
        return {"configured": self.configured, "full_window": self.full_window,
                "deadline_monotonic": self._deadline,
                "reserved_bytes": sum(self.reserved.values())}

    def _path(self, value, *, allow_root=False):
        self._same_owner()
        path = Path(os.path.abspath(value))
        if self.configured and ((path == self.root and not allow_root)
                                or not path.is_relative_to(self.root)):
            raise R13BudgetViolation("PATH_OUTSIDE_GLOBAL_WORKSPACE")
        reserved_names = {"CON", "PRN", "AUX", "NUL"} | {
            prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)}
        parts = (path.relative_to(self.root).parts if path.is_relative_to(self.root)
                 else path.parts[1:])
        for part in parts:
            if (":" in part or part.endswith((" ", ".")) or "\x00" in part
                    or part.split(".", 1)[0].upper() in reserved_names):
                raise R13BudgetViolation("WINDOWS_ALIAS_OR_STREAM_PATH")
        for component in (path, *path.parents):
            try:
                info = component.lstat()
            except FileNotFoundError:
                continue
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise R13BudgetViolation("REPARSE_OR_SYMLINK")
            if stat.S_ISREG(info.st_mode) and getattr(info, "st_nlink", 1) > 1:
                raise R13BudgetViolation("HARD_LINK_NOT_SUPPORTED")
        return path

    def _reject(self, reason):
        self._rejections += 1
        raise R13BudgetViolation(reason)

    def _charge(self, category, count):
        _count(count, "reserve")
        if category not in LIMITS or category == "fs_allowance":
            self._reject("UNKNOWN_OR_NONWRITE_BUCKET")
        if self.reserved[category] + count > LIMITS[category]:
            self._reject("GLOBAL_QUOTA_REJECTED:" + category)
        self.reserved[category] += count

    def _register_dir(self, path):
        key = str(path).casefold()
        if key not in self._dirs:
            if len(self._dirs) >= MAX_DIRS:
                self._reject("DIRECTORY_COUNT_LIMIT")
            self._dirs.add(key)

    def _register_file(self, path, category, kind, size=0, file_limit=None):
        key = str(path).casefold()
        if key in self._files:
            item = self._files[key]
            if item["category"] != category or item["kind"] != kind:
                self._reject("PATH_CATEGORY_CHANGE_FORBIDDEN")
            return item
        if category not in LIMITS or category == "fs_allowance":
            self._reject("FILE_CATEGORY")
        if kind not in ("payload_part", "delivery_part", "ordinary"):
            self._reject("FILE_KIND")
        if ((kind == "payload_part") != (category == "gzip_payload")
                or (kind == "delivery_part") != (category == "delivery_copy")):
            self._reject("PART_BUCKET_KIND_MISMATCH")
        if sum(self._counts[key] for key in ("payload_part", "delivery_part", "ordinary")) >= MAX_FILES:
            self._reject("GLOBAL_FILE_COUNT_LIMIT")
        limit = {"payload_part": MAX_PAYLOAD_PARTS,
                 "delivery_part": MAX_DELIVERY_PARTS,
                 "ordinary": MAX_ORDINARY_FILES}[kind]
        if self._counts[kind] >= limit:
            self._reject("FILE_KIND_COUNT_LIMIT:" + kind)
        if kind == "ordinary":
            if category == "failure":
                if self._counts["failure"] >= MAX_FAILURE_FILES:
                    self._reject("FAILURE_FILE_COUNT_LIMIT")
                self._counts["failure"] += 1
            elif self._counts["ordinary"] - self._counts["failure"] >= (
                MAX_ORDINARY_FILES - MAX_FAILURE_FILES
            ):
                self._reject("NORMAL_FILES_CANNOT_SPEND_FAILURE_RESERVE")
        self._counts[kind] += 1
        item = {"path": str(path), "category": category, "kind": kind,
                "extent": size, "present": path.exists(),
                "file_limit": file_limit, "open": False}
        self._files[key] = item
        return item

    def _free_check(self, count=0):
        free_root = self.root
        while not free_root.exists():
            free_root = free_root.parent
        free = shutil.disk_usage(free_root).free
        self.min_free_observed = min(self.min_free_observed, free)
        if self.configured and free - count < 8 * GIB:
            self._reject("FREE_RESERVE_BELOW_8GIB")

    def mkdir(self, path, *, parents=False, exist_ok=False):
        with self._lock:
            path = self._path(path, allow_root=True)
            wanted = [path]
            if parents:
                wanted = [*reversed(path.parents), path]
            for item in wanted:
                if self.configured and not item.is_relative_to(self.root):
                    continue
                if item.exists():
                    if not item.is_dir():
                        self._reject("DIRECTORY_EXPECTED")
                    if item == path and not exist_ok:
                        raise FileExistsError(str(path))
                    self._register_dir(item)
                    continue
                if str(item).casefold() in self._dirs:
                    self._reject("DIRECTORY_RECREATION_WITHOUT_NEW_SLOT_FORBIDDEN")
                self._register_dir(item)  # failed mkdir still spends its slot
                self._free_check(self._directory_bound)
                item.mkdir()

    def open(self, path, category, mode="xb", *, kind="ordinary", file_limit=None):
        with self._lock:
            path = self._path(path)
            if mode not in ("xb", "wb", "ab", "r+b"):
                self._reject("EXPLICIT_BINARY_WRITE_MODE_REQUIRED")
            if file_limit is not None:
                _count(file_limit, "file_limit")
            key = str(path).casefold()
            existed = path.exists()
            if existed and key not in self._files:
                if self.configured:
                    self._reject("UNREGISTERED_EXISTING_WRITER")
                self._register_file(path, category, kind, path.stat().st_size, file_limit)
                self._charge(category, path.stat().st_size)
            if not self.configured:
                for parent in (path.parent, *path.parent.parents):
                    if parent.is_dir():
                        self._register_dir(parent)
            if not path.parent.is_dir() or str(path.parent).casefold() not in self._dirs:
                self._reject("UNREGISTERED_PARENT_DIRECTORY")
            previous = self._files.get(key)
            if previous is not None and not existed:
                if (previous["open"] or key in self._external
                        or previous["category"] != category or previous["kind"] != kind):
                    self._reject("RECREATION_SCOPE_OR_WRITER_CONFLICT")
                if file_limit is None:
                    file_limit = previous["file_limit"]
                del self._files[key]  # counters/reserved bytes NEVER removed
            item = self._register_file(path, category, kind, 0, file_limit)
            if item["open"] or key in self._external:
                self._reject("CONCURRENT_OR_EXTERNAL_PATH_WRITER")
            if file_limit is not None:
                if item["file_limit"] not in (None, file_limit):
                    self._reject("FILE_LIMIT_CHANGED")
                item["file_limit"] = file_limit
            self._free_check(self._file_metadata_bound + self._allocation_unit)
            raw = path.open(mode, buffering=0)
            try:
                item["extent"] = os.fstat(raw.fileno()).st_size
                item["present"], item["open"] = True, True
                return _R13PhysicalWriter(self, raw, item)
            except BaseException:
                try:
                    raw.close()
                except BaseException as secondary:
                    self.secondary(secondary)
                item["open"] = not raw.closed
                raise

    def open_text(self, path, category, mode="x", **kwargs):
        if mode not in ("x", "w", "a"):
            self._reject("EXPLICIT_TEXT_MODE_REQUIRED")
        raw = self.open(path, category, mode + "b", **kwargs)
        return _R13TextWriter(io.BufferedWriter(raw, buffer_size=CHUNK),
                              encoding="utf-8", errors="strict", newline="\n")

    def replace(self, source, target):
        with self._lock:
            source, target = self._path(source), self._path(target)
            if source == target or str(target.parent).casefold() not in self._dirs:
                self._reject("RENAME_SAME_PATH_OR_UNREGISTERED_PARENT")
            old = self._files.get(str(source).casefold())
            if old is None or old["open"] or not old["present"]:
                self._reject("CLOSED_REGISTERED_RENAME_SOURCE_REQUIRED")
            target_key = str(target).casefold()
            prior_target = self._files.get(target_key)
            if ((prior_target is not None and prior_target["open"])
                    or target_key in self._external):
                self._reject("RENAME_TARGET_WRITER_OPEN")
            if prior_target is not None:
                if (prior_target["category"] != old["category"]
                        or prior_target["kind"] != old["kind"]):
                    self._reject("RENAME_CATEGORY_CHANGE")
                del self._files[target_key]
            new = self._register_file(target, old["category"], old["kind"], 0,
                                      old["file_limit"])
            if prior_target is not None:
                new["extent"], new["present"] = prior_target["extent"], prior_target["present"]
            # Rename spends a target-name slot even if OS replacement fails.
            os.replace(source, target)
            new["extent"], new["present"] = old["extent"], True
            old["present"] = False

    def reserve_external_log(self, path, *, role, byte_cap, evidence,
                             max_physical_write):
        """Only finite, frozen parent stdout/stderr/RESULT/summary statements.

        This is escrow, not runtime interception. A promise alone is not the
        writer bound; evidence must identify exact frozen output statements.
        """
        with self._lock:
            path = self._path(path)
            self._validate_external(role, byte_cap, evidence, max_physical_write)
            key = str(path).casefold()
            if path.exists() or key in self._external or key in self._files:
                self._reject("FRESH_EXTERNAL_LOG_REQUIRED")
            self._register_file(path, "failure", "ordinary")
            self._charge("failure", byte_cap)
            self._free_check(byte_cap)
            self._external[key] = {"path": str(path), "role": role,
                                   "reserved": byte_cap, "actual": None,
                                   "evidence": evidence,
                                   "max_physical_write": max_physical_write}
            return key

    def _validate_external(self, role, byte_cap, evidence, max_physical_write):
        _count(byte_cap, "external_cap")
        if (role not in LOG_ROLES or not evidence
                or type(max_physical_write) is not int
                or not 0 < max_physical_write <= CHUNK):
            self._reject("FINITE_FROZEN_EXTERNAL_LOG_BOUND_REQUIRED")

    def settle_external_log(self, token):
        with self._lock:
            item = self._external[token]
            if item["actual"] is not None:
                self._reject("EXTERNAL_LOG_ALREADY_SETTLED")
            path = self._path(item["path"])
            size = path.stat().st_size
            item["actual"] = size
            self.actual_io["failure"] += size
            file_state = self._files[token]
            file_state["extent"], file_state["present"] = size, True
            if size > item["reserved"]:
                self._reject("FROZEN_EXTERNAL_LOG_BOUND_BROKEN")

    def secondary(self, error):
        if len(self._errors) < 32:
            self._errors.append(type(error).__name__ + ":" + str(error)[:512])

    def receipt(self):
        with self._lock:
            # Permit sealing evidence after the deadline; never resume IO.
            if os.getpid() != self._owner_pid:
                raise R13BudgetViolation("CROSS_PROCESS_RECEIPT_FORBIDDEN")
            return {"schema": "M3_R13_GLOBAL_PREWRITE_BUDGET_R03",
                    "status": "ACCOUNTING_ONLY_NOT_A_GO_DECISION",
                    "configured": self.configured, "full_window": self.full_window,
                    "unconfigured_unit_fallback": not self.configured,
                    "deadline_monotonic": self._deadline,
                    "limits": dict(LIMITS), "quota_reserved": dict(self.reserved),
                    "total_reserved_upper_bytes": sum(self.reserved.values()),
                    "actual_io_bytes_known": dict(self.actual_io),
                    "actual_io_bytes_unknown_upper": dict(self.unknown_actual_upper),
                    "baseline_bytes": self._baseline_bytes,
                    "baseline_files": self._baseline_files,
                    "baseline_observed_allocation_bytes": self._baseline_allocated if self.configured else None,
                    "baseline_extra_preallocation_bytes": self._baseline_allocation_excess,
                    "registered_file_slots": sum(self._counts[key] for key in
                                                 ("payload_part", "delivery_part", "ordinary")),
                    "registered_directory_slots": len(self._dirs),
                    "file_kind_slots": dict(self._counts),
                    "allocation_unit_bytes": self._allocation_unit,
                    "allocation_unit_from_frozen_profile": self.configured,
                    "allocation_unit_observation": getattr(self, "allocation_unit_observation", None),
                    "allocation_and_metadata_bound_bytes": self.fs_bound,
                    "bound_scope": "OWN_ARTIFACT_TAILS_OPTIONAL_FD_NOT_VOLUME_MFT",
                    "filesystem_bound_evidence": self.fs_evidence,
                    "external_logs": list(self._external.values()),
                    "writes": self._writes, "max_physical_write": self._max_write,
                    "reads": self._reads, "max_physical_read": self._max_read,
                    "short_writes": self._short_writes, "quota_rejections": self._rejections,
                    "initial_free_bytes": self.initial_free,
                    "minimum_free_observed": self.min_free_observed,
                    "continuous_free_space_proved_here": False,
                    "secondary_errors": list(self._errors),
                    "unclosed_writers": sum(item["open"] for item in self._files.values()),
                    "known_live_file_lengths": sum(item["extent"] for item in self._files.values()
                                                   if item["present"]),
                    "final_physical_census": "REQUIRED_NOT_REPLACED_BY_KNOWN_LENGTHS",
                    "all_writer_closure_and_external_proofs": "REQUIRED_FROM_ROOT",
                    "refund_bytes": 0, "execution_allowed": False}


class _R13PhysicalWriter(io.RawIOBase):
    def __init__(self, budget, raw, item):
        self.budget, self.raw, self.item = budget, raw, item
        self.name, self.mode = raw.name, raw.mode
        self._write_failure = None

    def writable(self):
        return True

    def seekable(self):
        return True

    def readable(self):
        return False

    def tell(self):
        return self.raw.tell()

    def fileno(self):
        # Frozen callers may use this ONLY for fsync/fstat. An os.write,
        # ftruncate, mmap or descriptor duplicate would bypass the budget.
        return self.raw.fileno()

    def seek(self, offset, whence=0):
        with self.budget._lock:
            _count(self.item["extent"], "extent")
            base = {0: 0, 1: self.raw.tell(), 2: self.item["extent"]}.get(whence)
            if type(offset) is not int or base is None:
                self.budget._reject("SEEK_ARGUMENT")
            target = base + offset
            if not 0 <= target <= self.item["extent"]:
                self.budget._reject("SPARSE_OR_OUTSIDE_EXTENT_SEEK_FORBIDDEN")
            return self.raw.seek(target, 0)

    def truncate(self, size=None):
        with self.budget._lock:
            self.budget.check()
            target = self.raw.tell() if size is None else size
            if type(target) is not int or not 0 <= target <= self.item["extent"]:
                self.budget._reject("TRUNCATE_CANNOT_EXTEND_OR_CREATE_HOLE")
            result = self.raw.truncate(target)
            self.item["extent"] = target
            if self.raw.tell() > target:
                self.raw.seek(target)
            return result  # no reserved byte/file slot is returned

    def write(self, data):
        if self._write_failure is not None:
            raise self._write_failure
        try:
            return self._write_once_per_block(data)
        except BaseException as error:
            self._write_failure = error
            raise

    def _write_once_per_block(self, data):
        view = memoryview(data).cast("B")
        offset = 0
        while offset < len(view):
            block = view[offset:offset + CHUNK]
            count = len(block)
            with self.budget._lock:
                self.budget._same_owner()
                if self.closed or self.raw.closed:
                    raise ValueError("write to closed file")
                position = (self.item["extent"] if "a" in self.mode else self.raw.tell())
                if not 0 <= position <= self.item["extent"]:
                    self.budget._reject("WRITE_WOULD_CREATE_HOLE")
                bound = self.item["file_limit"]
                if bound is not None and position + count > bound:
                    self.budget._reject("FILE_BOUND_BEFORE_PHYSICAL_WRITE")
                self.budget._free_check(count + self.budget._allocation_unit - 1)
                category = self.item["category"]
                # Charge every attempted byte including overwrites and failed
                # IO. No subsequent status or cleanup ever refunds this.
                self.budget._charge(category, count)
                self.budget._writes += 1
                self.budget._max_write = max(self.budget._max_write, count)
                try:
                    written = self.raw.write(block)
                except BaseException:
                    self.budget.unknown_actual_upper[category] += count
                    try:
                        self.item["extent"] = os.fstat(self.raw.fileno()).st_size
                    except BaseException as secondary:
                        self.budget.secondary(secondary)
                    raise  # exact original IO exception, no retry
                if type(written) is int and 0 <= written <= count:
                    self.budget.actual_io[category] += written
                    self.item["extent"] = max(self.item["extent"], position + written)
                else:
                    self.budget.unknown_actual_upper[category] += count
                if written != count:
                    self.budget._short_writes += 1
                    raise R13BudgetViolation("PHYSICAL_SHORT_WRITE_NO_RETRY")
            offset += count
        return len(view)

    def flush(self):
        if not self.raw.closed:
            self.raw.flush()

    def close(self):
        if self.closed:
            return
        active = sys.exc_info()[1]
        primary = None
        try:
            super().close()
        except BaseException as error:
            primary = error
        try:
            self.raw.close()
        except BaseException as secondary:
            if primary is None:
                primary = secondary
            else:
                self.budget.secondary(secondary)
        finally:
            self.item["open"] = not self.raw.closed
        if primary is not None:
            if active is None:
                raise primary.with_traceback(primary.__traceback__)
            self.budget.secondary(primary)

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self.close()
        else:
            try:
                self.close()
            except BaseException as secondary:
                self.budget.secondary(secondary)
        return False


class _R13TextWriter(io.TextIOWrapper):
    def __init__(self, buffer, **kwargs):
        self._budget = buffer.raw.budget
        super().__init__(buffer, **kwargs)

    def close(self):
        active = sys.exc_info()[1]
        try:
            super().close()
        except BaseException as error:
            if active is None:
                raise
            self._budget.secondary(error)

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self.close()
        else:
            try:
                self.close()
            except BaseException as secondary:
                self._budget.secondary(secondary)
        return False


_HERE = Path(__file__).resolve().parent
_OUTPUT = _HERE.parents[6] / "code/output/m3_backend_stream_r13_20261018"
_ACTIVE_BUDGET = None
_CONFIGURATION_STATE = "UNCONFIGURED"
_CONFIGURATION_LOCK = threading.RLock()
_CATEGORY_OVERRIDES = {}


def configure_accounting(profile, external_logs, deadline_monotonic):
    """Once, before get_budget/any worker IO; no deadline rebasing/refund.

    profile: schema, whole_output_root, allocation_unit_bytes (actual P0 value),
    enforce_start_free bool, initial_roles, category_overrides, filesystem evidence,
    file_metadata_bound_bytes=0 and directory_bound_bytes=0. F/D are optional
    additional bounds; artifact AllocationSize/free observations stay separate.
    external_logs: R03 path->finite escrow mapping frozen/funded by parent.
    """
    global _ACTIVE_BUDGET, _CONFIGURATION_STATE, _CATEGORY_OVERRIDES
    with _CONFIGURATION_LOCK:
        if _CONFIGURATION_STATE != "UNCONFIGURED" or _ACTIVE_BUDGET is not None:
            raise R13BudgetViolation("ACCOUNTING_CONFIGURE_ONCE_BEFORE_ANY_BORROW")
        _CONFIGURATION_STATE = "CONFIGURING"
        try:
            if (type(profile) is not dict or type(external_logs) is not dict
                    or type(deadline_monotonic) not in (float, int)
                    or not math.isfinite(deadline_monotonic)
                    or deadline_monotonic <= time.monotonic()):
                raise R13BudgetViolation("FROZEN_PROFILE_LOGS_ABSOLUTE_DEADLINE_REQUIRED")
            root = Path(profile.get("whole_output_root", profile.get("workspace_root", _OUTPUT))).absolute()
            full_window = profile.get("enforce_start_free", profile.get("full_window", False))
            if (profile.get("schema") != "M3_R13_ACCOUNTING_PROFILE_V1"
                    or root != _OUTPUT.absolute() or type(full_window) is not bool
                    or not profile.get("filesystem_bound_evidence")):
                raise R13BudgetViolation("EXACT_GLOBAL_WORKSPACE_AND_WINDOW_FLAG")
            if "limits" in profile and profile["limits"] != LIMITS:
                raise R13BudgetViolation("FROZEN_R13_BUCKETS_CANNOT_BE_CHANGED")
            observed_unit = allocation_unit(root)  # executes only inside admitted root slot
            supplied_unit = profile.get("allocation_unit_bytes")
            if supplied_unit is not None and type(supplied_unit) is not int:
                raise R13BudgetViolation("INTEGER_OR_P0_DISCOVERY_ALLOCATION_UNIT")
            if supplied_unit in (None, 0):
                if full_window:
                    raise R13BudgetViolation("W_REQUIRES_FROZEN_P0_ALLOCATION_UNIT")
            elif (type(supplied_unit) is not int or
                  supplied_unit != observed_unit["allocation_unit_bytes"]):
                raise R13BudgetViolation("CURRENT_ALLOCATION_UNIT_CHANGED_FROM_PROFILE")
            overrides = dict(profile.get("category_overrides", {}))
            for relative, category in overrides.items():
                path = Path(relative)
                if (path.is_absolute() or ".." in path.parts or category not in LIMITS
                        or category in {"fs_allowance", "baseline"}):
                    raise R13BudgetViolation("CATEGORY_OVERRIDE_PATH_OR_BUCKET")
            aliases = {"raw_plain": "plain_raw", "all_stores": "gzip_payload", "delivery": "delivery_copy"}
            initial_roles = {path: aliases.get(role, role)
                             for path, role in dict(profile.get("initial_roles", {})).items()}
            budget = R13GlobalBudget(
                root, allocation_unit_bytes=observed_unit["allocation_unit_bytes"],
                file_metadata_bound_bytes=profile.get("file_metadata_bound_bytes", 0),
                directory_bound_bytes=profile.get("directory_bound_bytes", 0),
                filesystem_bound_evidence=profile["filesystem_bound_evidence"],
                initial_roles=initial_roles,
                external_log_escrows=external_logs,
                deadline_monotonic=deadline_monotonic,
                full_window=full_window, configured=True)
            _CATEGORY_OVERRIDES = overrides
            budget.allocation_unit_observation = observed_unit
            _ACTIVE_BUDGET = budget
            _CONFIGURATION_STATE = "CONFIGURED"
            return budget
        except BaseException:
            _CONFIGURATION_STATE = "FAILED_NO_RECONFIGURATION"
            raise


def get_budget():
    """One process-wide object. Unconfigured fallback is only for small units."""
    global _ACTIVE_BUDGET
    with _CONFIGURATION_LOCK:
        if _CONFIGURATION_STATE == "FAILED_NO_RECONFIGURATION":
            raise R13BudgetViolation("ACCOUNTING_CONFIGURATION_FAILED")
        if _ACTIVE_BUDGET is None:
            _ACTIVE_BUDGET = R13GlobalBudget(
                _OUTPUT, allocation_unit_bytes=1,
                file_metadata_bound_bytes=0, directory_bound_bytes=0,
                filesystem_bound_evidence="UNCONFIGURED_UNIT_NOT_ALLOCATION_EVIDENCE",
                full_window=False, configured=False, scan_baseline=False)
        return _ACTIVE_BUDGET


def _category(path, requested=None):
    aliases = {"all_stores": "gzip_payload", "delivery": "delivery_copy",
               "raw_plain": "plain_raw"}
    requested = aliases.get(requested, requested)
    if requested not in (None, "all_other"):
        if requested not in LIMITS or requested in {"baseline", "fs_allowance"}:
            raise R13BudgetViolation("WRITE_CATEGORY")
        return requested
    path = Path(path).absolute()
    existing = None if _ACTIVE_BUDGET is None else _ACTIVE_BUDGET._files.get(str(path).casefold())
    if existing is not None:
        if existing["category"] == "baseline":
            raise R13BudgetViolation("EXISTING_BASELINE_IS_READ_ONLY_USE_OWN_COPY")
        return existing["category"]
    if path.is_relative_to(_OUTPUT):
        relative = path.relative_to(_OUTPUT).as_posix()
        if relative in _CATEGORY_OVERRIDES:
            return _CATEGORY_OVERRIDES[relative]
    parts = {part.casefold() for part in path.parts}
    name = path.name.casefold()
    if "failure" in name or name in {"stderr.bin", "stderr.txt"}:
        return "failure"
    if (parts & {"inputs", "source", "sources", "extract", "snapshots",
                 "private_archive_snapshots", "temp", "temporary"}
            or name.startswith(("source_", "source-"))):
        return "plain_aux"
    effective = path.with_suffix("") if path.suffix.casefold() == ".tmp" else path
    if effective.suffix.casefold() in {".json", ".md", ".txt", ".zip"}:
        return "control"
    return "plain_aux"


def accounting_mkdir(path, parents=False, exist_ok=False):
    return get_budget().mkdir(path, parents=parents, exist_ok=exist_ok)


def accounting_replace(source, target):
    return get_budget().replace(source, target)


class _R13PhysicalReader(io.RawIOBase):
    """Bound actual OS reads; normal close never drains an unread tail."""
    def __init__(self, path, budget):
        self.budget = budget
        self.current = Path(path).open("rb", buffering=0)
        self.name, self.mode = str(path), "rb"

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.current.tell()

    def seek(self, offset, whence=0):
        self.budget.check()
        return self.current.seek(offset, whence)

    def readinto(self, buffer):
        view = memoryview(buffer).cast("B")
        total = 0
        while total < len(view):
            self.budget.check()
            size = min(CHUNK, len(view) - total)
            self.budget._reads += 1
            self.budget._max_read = max(self.budget._max_read, size)
            count = self.current.readinto(view[total:total + size])
            if not count:
                break
            total += count
        return total

    def readall(self):
        # Needed by ZIP central-directory tail readers. Large business streams
        # must use bounded reads, not materialize their entire logical role.
        blocks, total, scratch = [], 0, bytearray(CHUNK)
        while True:
            count = self.readinto(scratch)
            if not count:
                return b"".join(blocks)
            total += count
            if total > 64 * CHUNK:
                raise R13BudgetViolation("UNBOUNDED_READ_ROLE_OVER_64MIB")
            blocks.append(bytes(memoryview(scratch)[:count]))

    def fileno(self):
        return self.current.fileno()

    def close(self):
        if self.closed:
            return
        active = sys.exc_info()[1]
        primary = None
        try:
            super().close()
        except BaseException as error:
            primary = error
        try:
            self.current.close()
        except BaseException as error:
            if primary is None:
                primary = error
            else:
                self.budget.secondary(error)
        if primary is not None:
            if active is None:
                raise primary.with_traceback(primary.__traceback__)
            self.budget.secondary(primary)

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self.close()
        else:
            try:
                self.close()
            except BaseException as error:
                self.budget.secondary(error)
        return False


def accounting_open(path, mode, category=None, encoding=None, errors=None, newline=None):
    budget = get_budget()
    budget.check()
    path = Path(os.path.abspath(path))
    if mode in {"rb", "r", "rt"}:
        for component in (path, *path.parents):
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise R13BudgetViolation("READ_REPARSE_OR_LINK")
        raw = _R13PhysicalReader(path, budget)
        stream = io.BufferedReader(raw, buffer_size=CHUNK)
        if "b" in mode:
            if encoding is not None or errors is not None or newline is not None:
                stream.close()
                raise ValueError("binary mode does not accept text options")
            return stream
        try:
            return _R13ReadText(stream, encoding=encoding or "utf-8",
                                errors=errors or "strict", newline=newline)
        except BaseException:
            try:
                stream.close()
            except BaseException as secondary:
                budget.secondary(secondary)
            raise
    path = budget._path(path)
    category = _category(path, category)
    kind = ("payload_part" if category == "gzip_payload" else
            "delivery_part" if category == "delivery_copy" else "ordinary")
    if mode in {"xb", "wb", "ab", "r+b", "rb+"}:
        if encoding is not None or errors is not None or newline is not None:
            raise ValueError("binary mode does not accept text options")
        return budget.open(path, category, "r+b" if mode == "rb+" else mode,
                           kind=kind,
                           file_limit=32 * MIB if category == "gzip_payload" else None)
    if mode not in {"x", "xt", "w", "wt", "a", "at"}:
        raise R13BudgetViolation("ACCOUNTING_OPEN_MODE")
    raw = budget.open(path, category, mode[0] + "b", kind=kind)
    stream = io.BufferedWriter(raw, buffer_size=CHUNK)
    try:
        return _R13TextWriter(stream, encoding=encoding or "utf-8",
                              errors=errors or "strict", newline=newline)
    except BaseException:
        try:
            stream.close()
        except BaseException as secondary:
            budget.secondary(secondary)
        raise


class _R13ReadText(io.TextIOWrapper):
    def __init__(self, buffer, **kwargs):
        self._budget = buffer.raw.budget
        super().__init__(buffer, **kwargs)

    def close(self):
        active = sys.exc_info()[1]
        try:
            super().close()
        except BaseException as error:
            if active is None:
                raise
            self._budget.secondary(error)

    def __exit__(self, kind, value, traceback):
        if kind is None:
            self.close()
        else:
            try:
                self.close()
            except BaseException as error:
                self._budget.secondary(error)
        return False


def accounting_save_bytes(path, body, category=None, exclusive=True):
    with accounting_open(path, "xb" if exclusive else "wb", category) as target:
        count = target.write(body)
    return _saved_descriptor(path, count, hashlib.sha256(body).hexdigest())


def accounting_copy_file(source, target, category=None, exclusive=True):
    count, digest = 0, hashlib.sha256()
    with accounting_open(source, "rb") as original:
        with accounting_open(target, "xb" if exclusive else "wb", category) as output:
            while True:
                get_budget().check()
                block = original.read(CHUNK)
                if not block:
                    break
                output.write(block)
                digest.update(block)
                count += len(block)
    return _saved_descriptor(target, count, digest.hexdigest())


def _saved_descriptor(path, count, sha256):
    path, root = Path(path).absolute(), _HERE.parents[6]
    return {"path": path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path),
            "bytes": count, "sha256": sha256}

