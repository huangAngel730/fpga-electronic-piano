"""Windows Job Object used to own exactly one launched process tree."""
import ctypes
from ctypes import wintypes


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("per_process_time", ctypes.c_int64),
        ("per_job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_process_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority_class", wintypes.DWORD),
        ("scheduling_class", wintypes.DWORD),
    ]


class _Counters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "read_operations",
            "write_operations",
            "other_operations",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimit),
        ("io", _Counters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


class WindowsJob:
    """Attach a suspended child before it can create descendants."""

    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.kernel.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = _ExtendedLimit()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = self.kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)
        )
        if not ok:
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def attach_and_resume(self, process):
        process_handle = wintypes.HANDLE(int(process._handle))
        if not self.kernel.AssignProcessToJobObject(self.handle, process_handle):
            error = ctypes.get_last_error()
            process.kill()
            process.wait(timeout=5)
            raise ctypes.WinError(error)
        resume = ctypes.WinDLL("ntdll").NtResumeProcess
        resume.argtypes = [wintypes.HANDLE]
        resume.restype = ctypes.c_long
        status = resume(process_handle)
        if status != 0:
            self.terminate()
            process.wait(timeout=5)
            raise OSError("OWNED_JOB_RESUME_FAILED:" + str(status))

    def terminate(self):
        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"mechanism": "TerminateJobObject", "owned_job": True}

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
