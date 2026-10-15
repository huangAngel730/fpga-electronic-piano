"""Python-only adversarial children. Never invokes an HDL or EDA tool."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def process_creation(pid):
    """Windows kernel creation FILETIME, for PID-reuse-safe observations."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
        ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                         ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error in (87, 1168):  # exited/nonexistent PID, not access denied
            return None
        raise ctypes.WinError(error)
    try:
        fields = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(x) for x in fields]):
            raise ctypes.WinError(ctypes.get_last_error())
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"pid": pid, "creation_filetime":
                (fields[0].dwHighDateTime << 32) | fields[0].dwLowDateTime,
                "alive": exit_code.value == 259}
    finally:
        kernel.CloseHandle(handle)


def child(role):
    identity = process_creation(os.getpid())
    Path(role + ".identity.json").write_text(json.dumps(identity), encoding="utf-8")
    if role == "child":
        subprocess.Popen([sys.executable, "-B", __file__, "grandchild"])
    with Path(role + ".heartbeat").open("ab", buffering=0) as stream:
        for _ in range(3000):
            stream.write(b".")
            time.sleep(0.01)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode")
    args = parser.parse_args()
    mode = args.mode
    print("PYTHON_FAKE_PROCESS_ONLY:" + mode, flush=True)
    print("FAKE_STDERR_BEGIN", file=sys.stderr, flush=True)
    if mode in ("child", "grandchild"):
        child(mode)
    elif mode in ("tree_timeout", "orphan"):
        subprocess.Popen([sys.executable, "-B", __file__, "child"])
        until = time.monotonic() + 2
        while not Path("grandchild.identity.json").exists() and time.monotonic() < until:
            time.sleep(0.01)
        if not Path("grandchild.identity.json").exists():
            return 81
        if mode == "tree_timeout":
            time.sleep(30)
    elif mode in ("stdout_limit", "stderr_limit"):
        stream = sys.stdout.buffer if mode == "stdout_limit" else sys.stderr.buffer
        stream.write(b"X" * 32768)
        stream.flush()
        time.sleep(0.2)
    elif mode in ("capture_limit", "output_limit"):
        filename = "observations.hex" if mode == "capture_limit" else "unrelated.tmp"
        size = 96 * 1024 if mode == "capture_limit" else 192 * 1024
        Path(filename).write_bytes(b"Z" * size)
        time.sleep(0.2)
    elif mode == "nonzero":
        return 7
    elif mode in ("error", "fatal", "failure"):
        print(mode.upper() + ": intentionally injected diagnostic", flush=True)
    elif mode == "sleep":
        time.sleep(30)
    elif mode == "empty_capture":
        Path("observations.hex").touch()
    elif mode != "normal":
        return 82
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
