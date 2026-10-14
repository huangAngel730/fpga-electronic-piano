"""Progress-guarded simulation; no test-vector or DUT changes."""
import subprocess
import time
import ctypes
from ctypes import wintypes

from windows_job import WindowsJob
from runner import identity, write_json


def _cpu_ticks(process):
    created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    function = ctypes.WinDLL('kernel32', use_last_error=True).GetProcessTimes
    function.argtypes = [wintypes.HANDLE, *(ctypes.POINTER(wintypes.FILETIME),) * 4]
    function.restype = wintypes.BOOL
    if not function(wintypes.HANDLE(int(process._handle)),
                    ctypes.byref(created), ctypes.byref(exited),
                    ctypes.byref(kernel), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    def value(item):
        return (item.dwHighDateTime << 32) | item.dwLowDateTime
    return value(kernel) + value(user)


def run_simulation(output, label, argv, cwd, cap, budget):
    started = time.monotonic()
    timeout = budget.remaining(cap)
    out = output / (label + '.stdout.bin')
    err = output / (label + '.stderr.bin')
    last_progress = started
    last_size = 0
    process = None
    cleanup = None
    failure = None
    timed_out = False
    with out.open('xb') as stdout, err.open('xb') as stderr:
        job = WindowsJob()
        try:
            process = subprocess.Popen(list(map(str, argv)), cwd=str(cwd),
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x4)
            job.attach_and_resume(process)
            while process.poll() is None:
                now = time.monotonic()
                size = out.stat().st_size
                if size > last_size:
                    last_progress, last_size = now, size
                if now - last_progress >= 300 or now - started >= timeout:
                    timed_out = True
                    failure = ('SIMULATION_NO_OUTPUT_PROGRESS_300S'
                               if now - last_progress >= 300 else 'WALL_LIMIT')
                    cleanup = job.terminate()
                    break
                time.sleep(1)
            exit_code = process.wait(timeout=5)
        except Exception as error:
            failure = type(error).__name__ + ':' + str(error)
            if process is not None and process.poll() is None:
                cleanup = job.terminate()
                process.wait(timeout=5)
            exit_code = process.returncode if process else None
        finally:
            job.close()
    result = dict(label=label, argv=list(map(str, argv)), cwd=str(cwd),
        pid=process.pid if process else None, timeout_cap_seconds=cap,
        effective_timeout_seconds=timeout, elapsed_seconds=time.monotonic()-started,
        exit_code=exit_code, timed_out=timed_out, cleanup=cleanup,
        launch_error=failure, stdout=identity(out), stderr=identity(err),
        progress_policy='STOP_AFTER_300_SECONDS_WITHOUT_STDOUT_GROWTH',
        last_observed_stdout_bytes=last_size, automatic_retries=0)
    write_json(output / (label + '.receipt.json'), result)
    return result


def run_cpu_guarded(output, label, argv, cwd, cap, budget):
    """Stop a silent checker only after five minutes without CPU progress."""
    started = time.monotonic()
    timeout = budget.remaining(cap)
    out = output / (label + '.stdout.bin')
    err = output / (label + '.stderr.bin')
    last_progress = started
    last_ticks = 0
    process = None
    cleanup = None
    failure = None
    timed_out = False
    with out.open('xb') as stdout, err.open('xb') as stderr:
        job = WindowsJob()
        try:
            process = subprocess.Popen(list(map(str, argv)), cwd=str(cwd),
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x4)
            job.attach_and_resume(process)
            while process.poll() is None:
                now = time.monotonic()
                ticks = _cpu_ticks(process)
                if ticks > last_ticks:
                    last_progress, last_ticks = now, ticks
                if now - last_progress >= 300 or now - started >= timeout:
                    timed_out = True
                    failure = ('CHECKER_NO_CPU_PROGRESS_300S'
                               if now - last_progress >= 300 else 'WALL_LIMIT')
                    cleanup = job.terminate()
                    break
                time.sleep(1)
            exit_code = process.wait(timeout=5)
        except Exception as error:
            failure = type(error).__name__ + ':' + str(error)
            if process is not None and process.poll() is None:
                cleanup = job.terminate()
                process.wait(timeout=5)
            exit_code = process.returncode if process else None
        finally:
            job.close()
    result = dict(label=label, argv=list(map(str, argv)), cwd=str(cwd),
        pid=process.pid if process else None, timeout_cap_seconds=cap,
        effective_timeout_seconds=timeout, elapsed_seconds=time.monotonic()-started,
        exit_code=exit_code, timed_out=timed_out, cleanup=cleanup,
        launch_error=failure, stdout=identity(out), stderr=identity(err),
        progress_policy='STOP_AFTER_300_SECONDS_WITHOUT_CPU_TIME_GROWTH',
        last_observed_cpu_100ns=last_ticks, automatic_retries=0)
    write_json(output / (label + '.receipt.json'), result)
    return result
