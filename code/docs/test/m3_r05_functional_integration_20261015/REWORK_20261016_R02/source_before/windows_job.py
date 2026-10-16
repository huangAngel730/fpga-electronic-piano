"""Windows suspended-start Job Object, no PID-only tree termination.

Used only by the proposed runner and Python fake-process tests. No HDL here.
Children are assigned BEFORE their first instruction. Closing the job kills
all descendants, including those surviving their immediate parent's exit.
"""
import ctypes as C
from ctypes import wintypes as W
import msvcrt
import os
import subprocess


class Security(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p),
                ("inherit", W.BOOL)]


class Startup(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR),
                ("desktop", W.LPWSTR), ("title", W.LPWSTR),
                ("x", W.DWORD), ("y", W.DWORD), ("xsize", W.DWORD),
                ("ysize", W.DWORD), ("xchars", W.DWORD),
                ("ychars", W.DWORD), ("fill", W.DWORD),
                ("flags", W.DWORD), ("show", W.WORD),
                ("reserved_size", W.WORD), ("reserved_ptr", C.c_void_p),
                ("stdin", W.HANDLE), ("stdout", W.HANDLE),
                ("stderr", W.HANDLE)]


class ProcessInfo(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE),
                ("pid", W.DWORD), ("tid", W.DWORD)]


class BasicLimit(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64),
                ("flags", W.DWORD), ("minimum", C.c_size_t),
                ("maximum", C.c_size_t), ("active", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD),
                ("scheduling", W.DWORD)]


class Io(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in
                ("reads", "writes", "other", "read_bytes", "write_bytes",
                 "other_bytes")]


class ExtendedLimit(C.Structure):
    _fields_ = [("basic", BasicLimit), ("io", Io),
                ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
                ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [(name, C.c_int64) for name in
                ("user", "kernel", "period_user", "period_kernel")] + [
                    (name, W.DWORD) for name in
                    ("faults", "total", "active", "terminated")]


class JobProcess:
    def __init__(self, argv, cwd, env=None, on_created=None):
        if os.name != "nt":
            raise OSError("WINDOWS_JOB_REQUIRED")
        self.k = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": (W.HANDLE, [C.c_void_p, W.LPCWSTR]),
            "SetInformationJobObject": (W.BOOL, [W.HANDLE, C.c_int,
                                                 C.c_void_p, W.DWORD]),
            "QueryInformationJobObject": (W.BOOL, [W.HANDLE, C.c_int,
                                                   C.c_void_p, W.DWORD,
                                                   C.c_void_p]),
            "AssignProcessToJobObject": (W.BOOL, [W.HANDLE, W.HANDLE]),
            "CreatePipe": (W.BOOL, [C.POINTER(W.HANDLE), C.POINTER(W.HANDLE),
                                     C.POINTER(Security), W.DWORD]),
            "SetHandleInformation": (W.BOOL, [W.HANDLE, W.DWORD, W.DWORD]),
            "CreateProcessW": (W.BOOL, [W.LPCWSTR, W.LPWSTR, C.c_void_p,
                                         C.c_void_p, W.BOOL, W.DWORD,
                                         C.c_void_p, W.LPCWSTR,
                                         C.POINTER(Startup),
                                         C.POINTER(ProcessInfo)]),
            "ResumeThread": (W.DWORD, [W.HANDLE]),
            "TerminateJobObject": (W.BOOL, [W.HANDLE, W.UINT]),
            "TerminateProcess": (W.BOOL, [W.HANDLE, W.UINT]),
            "WaitForSingleObject": (W.DWORD, [W.HANDLE, W.DWORD]),
            "GetExitCodeProcess": (W.BOOL, [W.HANDLE, C.POINTER(W.DWORD)]),
            "CloseHandle": (W.BOOL, [W.HANDLE]),
        }
        for name, (restype, argtypes) in signatures.items():
            fn = getattr(self.k, name)
            fn.restype, fn.argtypes = restype, argtypes
        self.job = self.k.CreateJobObjectW(None, None)
        self.process = None
        self.streams = []
        handles = []
        info = ProcessInfo()
        launch_stage = "CREATE_JOB"
        try:
            self.ok(self.job)
            limits = ExtendedLimit()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            self.ok(self.k.SetInformationJobObject(
                self.job, 9, C.byref(limits), C.sizeof(limits)))
            security = Security(C.sizeof(Security), None, True)
            write_handles = []
            for _ in range(2):
                read, write = W.HANDLE(), W.HANDLE()
                self.ok(self.k.CreatePipe(C.byref(read), C.byref(write),
                                          C.byref(security), 0))
                handles.extend([read.value, write.value])
                self.ok(self.k.SetHandleInformation(read, 1, 0))
                fd = msvcrt.open_osfhandle(read.value, os.O_RDONLY | os.O_BINARY)
                handles.remove(read.value)  # Python now owns read handle
                self.streams.append(os.fdopen(fd, "rb", buffering=0))
                write_handles.append(write.value)
            start = Startup()
            start.cb, start.flags = C.sizeof(Startup), 0x100
            start.stdout, start.stderr = write_handles
            # Invalid stdin is intentional: interactive input is prohibited.
            start.stdin = None
            command = C.create_unicode_buffer(subprocess.list2cmdline(argv))
            environment = None
            flags = 0x4 | 0x08000000
            if env is not None:
                block = "\0".join(f"{key}={value}" for key, value in
                                    sorted(env.items(), key=lambda item: item[0].upper()))
                environment = C.create_unicode_buffer(block + "\0\0")
                flags |= 0x400  # CREATE_UNICODE_ENVIRONMENT, child-local only
            launch_stage = "CREATE_PROCESS_SUSPENDED"
            self.ok(self.k.CreateProcessW(argv[0], command, None, None, True,
                                          flags, environment, str(cwd),
                                          C.byref(start), C.byref(info)))
            self.process, self.pid = info.process, info.pid
            if on_created:
                on_created(self.pid)
            # Fail closed if parent job restrictions prevent assignment.
            launch_stage = "ASSIGN_TO_JOB"
            self.ok(self.k.AssignProcessToJobObject(self.job, self.process))
            launch_stage = "RESUME_THREAD"
            if self.k.ResumeThread(info.thread) == 0xFFFFFFFF:
                raise C.WinError(C.get_last_error())
        except BaseException as exc:
            exc.process_created = bool(info.process)
            exc.launch_stage = launch_stage
            if info.process:
                self.k.TerminateProcess(info.process, 99)
            self.close()
            raise
        finally:
            if info.thread:
                self.k.CloseHandle(info.thread)
            for handle in handles:
                self.k.CloseHandle(handle)

    @staticmethod
    def ok(value):
        if not value:
            raise C.WinError(C.get_last_error())

    def poll(self):
        if self.k.WaitForSingleObject(self.process, 0) == 0x102:
            return None
        value = W.DWORD()
        self.ok(self.k.GetExitCodeProcess(self.process, C.byref(value)))
        return value.value

    def active(self):
        result = Accounting()
        self.ok(self.k.QueryInformationJobObject(
            self.job, 1, C.byref(result), C.sizeof(result), None))
        return result.active

    def terminate(self):
        self.ok(self.k.TerminateJobObject(self.job, 99))

    def close(self):
        if self.job:
            self.k.CloseHandle(self.job)
            self.job = None
        if self.process:
            self.k.CloseHandle(self.process)
            self.process = None
