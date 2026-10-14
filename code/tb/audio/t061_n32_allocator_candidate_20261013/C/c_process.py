"""C-only owned-process execution with wall and no-progress guards."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def write_json(path, value, *, exclusive=True):
    with Path(path).open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def cpu_ticks(process):
    times = [wintypes.FILETIME() for _ in range(4)]
    function = ctypes.WinDLL("kernel32", use_last_error=True).GetProcessTimes
    function.argtypes = [wintypes.HANDLE, *(ctypes.POINTER(wintypes.FILETIME),) * 4]
    function.restype = wintypes.BOOL
    if not function(wintypes.HANDLE(int(process._handle)),
                    *(ctypes.byref(item) for item in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    return sum((item.dwHighDateTime << 32) | item.dwLowDateTime for item in times[2:])


class OperationProgress:
    """Only completed/new driver operations count; repeated HOLD rows do not."""
    def __init__(self):
        self.offset = 0
        self.partial = b""
        self.last = None

    def poll(self, path):
        advanced = False
        with Path(path).open("rb") as stream:
            stream.seek(self.offset)
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                self.offset += len(block)
                rows = (self.partial + block).split(b"\n")
                self.partial = rows.pop()
                for row in rows:
                    if row.startswith(b"OP "):
                        fields = row.decode("ascii").split()
                        if fields != self.last:
                            self.last = fields
                            advanced = True
        return advanced


def run_step(step, output, environment, helpers, remaining):
    """Own one process tree; simulation must advance its public trace."""
    sys.path.insert(0, str(helpers))
    from windows_job import WindowsJob

    started = time.monotonic()
    cap = min(float(step["timeout_seconds"]), remaining())
    if cap <= 0:
        raise ValueError("C_TOTAL_BUDGET_EXHAUSTED")
    out = output / (step["name"] + ".stdout.bin")
    err = output / (step["name"] + ".stderr.bin")
    result = {"name": step["name"], "argv": step["argv"], "cwd": step["cwd"],
              "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "effective_timeout_seconds": cap, "exit_code": None,
              "timeout": False, "failure": None, "automatic_retries": 0,
              "progress_policy": ("OP_TRANSITIONS;HOLD_SPAM_NOT_PROGRESS;STOP_AFTER_300S" if step["name"] == "simulate"
                                  else "CPU_OR_LOG_GROWTH;STOP_AFTER_300S_WITHOUT_EITHER")}
    job = None
    process = None
    previous = (0, 0, 0)
    last_progress = started
    operations = OperationProgress()
    try:
        job = WindowsJob()
        with out.open("xb") as stdout, err.open("xb") as stderr:
            process = subprocess.Popen(step["argv"], cwd=step["cwd"],
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                env={**os.environ, **environment},
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x4)
            result["pid"] = process.pid
            job.attach_and_resume(process)
            while process.poll() is None:
                now = time.monotonic()
                current = (cpu_ticks(process), out.stat().st_size, err.stat().st_size)
                # A zero-time HDL oscillation consumes CPU without advancing
                # simulation time. Require trace growth for that process.
                progress = (operations.poll(out) if step["name"] == "simulate"
                            else any(a > b for a, b in zip(current, previous)))
                if progress:
                    last_progress = now
                previous = current
                if now - last_progress >= 300 or now - started >= cap:
                    result["timeout"] = True
                    result["failure"] = ("C_NO_PROGRESS_300S" if now-last_progress >= 300
                                         else "C_WALL_LIMIT")
                    result["cleanup"] = job.terminate()
                    break
                time.sleep(1)
            result["exit_code"] = process.wait(timeout=5)
    except Exception as error:
        result["failure"] = type(error).__name__ + ":" + str(error)
        if process is not None and process.poll() is None:
            result["cleanup"] = job.terminate()
            process.wait(timeout=5)
    finally:
        if job is not None:
            job.close()
    def optional_identity(path):
        try:
            return identity(path)
        except OSError as error:
            return {"missing_or_unreadable": True, "error": str(error)}
    result.update(ended_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  elapsed_seconds=time.monotonic()-started,
                  last_progress_cpu_and_bytes=list(previous),
                  last_semantic_operation=operations.last,
                  stdout=optional_identity(out), stderr=optional_identity(err))
    write_json(output / (step["name"] + ".receipt.json"), result)
    return result
