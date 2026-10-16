"""Bounded Windows Job execution, separate raw streams, descendant supervision."""
import os
from pathlib import Path
import threading
import time

from common import identity
from windows_job import JobProcess


def invoke(argv, cwd, output, name, deadline, step_budget=300, log_limit=64 * 1024 * 1024,
           environment=None, on_created=None):
    output = Path(output)
    out = output / f"{name}.stdout.log"
    err = output / f"{name}.stderr.log"
    if out.exists() or err.exists():
        raise FileExistsError("refuse overwritten original streams")
    started = time.monotonic()
    step_deadline = min(deadline, started + step_budget)
    if step_deadline <= started:
        raise TimeoutError("budget exhausted before process creation")
    counts, errors = [0, 0], []
    log_lock = threading.Lock()
    job = None
    threads = []
    timed_out = False
    log_exceeded = False
    exit_code = None
    detail = None
    process_created = False
    launch_stage = None
    winerror = None
    create_attempted = False
    create_returned = None
    created_pid = None
    try:
        def created(pid):
            nonlocal process_created, created_pid, create_attempted, create_returned
            process_created = True
            created_pid = pid
            create_attempted, create_returned = True, True
            if on_created:
                on_created(pid)

        job = JobProcess(list(map(str, argv)), str(cwd), env=environment, on_created=created)

        def drain(index, destination):
            try:
                with destination.open("xb") as stream:
                    while True:
                        block = job.streams[index].read(65536)
                        if not block:
                            break
                        # Retain originals up to the fixed combined cap, then
                        # supervisor terminates the whole Job. Never unlimited.
                        with log_lock:
                            allowed = max(0, log_limit - sum(counts))
                            kept = block[:allowed]
                            stream.write(kept)
                            counts[index] += len(kept)
                            if len(kept) < len(block):
                                errors.append("LOG_LIMIT")
                                break
            except Exception as exc:
                errors.append(repr(exc))

        for index, destination in enumerate((out, err)):
            thread = threading.Thread(target=drain, args=(index, destination), daemon=True)
            thread.start()
            threads.append(thread)
        while job.poll() is None or job.active() != 0:
            if time.monotonic() >= step_deadline:
                timed_out = True
                job.terminate()
                break
            if errors or sum(counts) >= log_limit:
                log_exceeded = True
                job.terminate()
                break
            time.sleep(0.02)
        exit_code = job.poll()
    except Exception as exc:
        detail = repr(exc)
        process_created = True if process_created else getattr(exc, "process_created", None)
        launch_stage = getattr(exc, "launch_stage", None)
        winerror = getattr(exc, "winerror", None)
        create_attempted = getattr(exc, "create_process_attempted", create_attempted)
        create_returned = getattr(exc, "create_process_returned", create_returned)
        created_pid = getattr(exc, "created_pid", created_pid)
    finally:
        if job:
            job.close()  # KILL_ON_JOB_CLOSE covers lingering children.
        for thread in threads:
            thread.join(timeout=3)
        if any(t.is_alive() for t in threads):
            detail = "STREAM_READER_NOT_CLOSED"
        elif job:
            for stream in job.streams:
                stream.close()
        for path in (out, err):
            if not path.exists():
                path.write_bytes(b"")
        log_exceeded = log_exceeded or "LOG_LIMIT" in errors or sum(counts) >= log_limit
    return {
        "argv": list(map(str, argv)), "cwd": str(Path(cwd).resolve()),
        "exit_code": exit_code, "timeout": timed_out, "log_limit_exceeded": log_exceeded,
        "elapsed_s": time.monotonic() - started,
        "step_budget_s": step_budget, "step_deadline_monotonic": step_deadline,
        "stdout": identity(out), "stderr": identity(err),
        "error": detail or (repr(errors) if errors else None),
        "process_created": process_created,
        "launch_stage_failed": launch_stage,
        "winerror": winerror,
        "create_process_attempted": create_attempted,
        "create_process_returned": create_returned,
        "created_pid": created_pid,
        "stdin_policy": "INHERIT_READ_ONLY_NUL_EOF",
        "process_tree_policy": "SUSPENDED_START_ASSIGNED_JOB_KILL_ON_CLOSE",
    }
