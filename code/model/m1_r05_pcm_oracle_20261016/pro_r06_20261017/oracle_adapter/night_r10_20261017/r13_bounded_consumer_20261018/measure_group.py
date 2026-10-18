"""Unrun R13 fixed supervisor candidate. One counted clock includes all tails."""
import time
ENTRY_MONOTONIC_NS = time.monotonic_ns()
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import sys
import threading


class Memory(C.Structure):
    _fields_ = [('cb', W.DWORD), ('faults', W.DWORD)] + [
        (name, C.c_size_t) for name in ('peak_ws', 'ws', 'peak_pool_paged', 'pool_paged',
            'peak_pool_nonpaged', 'pool_nonpaged', 'pagefile', 'peak_pagefile', 'private')]


def native_counters(handle):
    api = C.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    api.argtypes, api.restype = [W.HANDLE, C.POINTER(Memory), W.DWORD], W.BOOL
    result = Memory()
    result.cb = C.sizeof(Memory)
    if not api(handle, C.byref(result), result.cb):
        raise C.WinError(C.get_last_error())
    return dict(working_set=result.ws, peak_working_set=result.peak_ws,
                private_usage=result.private, peak_commit=result.peak_pagefile)


def validate_recorded_samples(samples):
    """Bookkeeping-only unit seam; never substitutes for live OS measurements."""
    previous = None
    for sample in samples:
        now = sample['time_ns']
        if (type(now) is not int or sample.get('peak_working_set') is None
                or previous is not None and not 0 < now - previous <= 100000000):
            raise ValueError('RSS_MEASUREMENT_INCOMPLETE')
        previous = now
    if previous is None:
        raise ValueError('RSS_MEASUREMENT_INCOMPLETE')
    return True


def main():
    if os.name != 'nt':
        raise ValueError('WINDOWS_OWNED_JOB_REQUIRED')
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--package-sha256', required=True)
    parser.add_argument('--group', required=True, choices=('SW01', 'CAP01', 'FIX01'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--outer-start-ns', required=True, type=int)
    args = parser.parse_args()
    # This value is captured before launch by the approved parent; the worker
    # receives the identical value. No phase, import or cleanup resets it.
    start = args.outer_start_ns
    if not 0 < start <= ENTRY_MONOTONIC_NS:
        raise ValueError('OUTER_CLOCK_REQUIRED')
    with args.package.open('rb') as file:
        raw = file.read((1 << 20) + 1)
    if len(raw) > 1 << 20 or hashlib.sha256(raw).hexdigest() != args.package_sha256:
        raise ValueError('PACKAGE_IDENTITY')
    package = json.loads(raw)
    import importlib.util
    root = args.root.resolve()
    descriptor = package['worker_source']
    path = root / descriptor['path']
    source = path.read_bytes()
    if len(source) != descriptor['bytes'] or hashlib.sha256(source).hexdigest() != descriptor['sha256']:
        raise ValueError('WORKER_SOURCE_IDENTITY')
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('_r13_worker_bootstrap', None))
    module.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), module.__dict__)
    module.admit(package, args.group)
    bindings = json.loads(module.verified_buffer(root, package['source_bindings']))
    source_rows = {Path(row['path']).stem: row for row in bindings['files']}
    guard = module.import_buffer(root, source_rows['identity_guard'], '_r13_bootstrap_guard')
    source_locks = []
    try:
        for row in bindings['files'] + bindings['dependencies'] + [package['source_bindings']]:
            lock = guard.LockedInput(root, row, 'launch-source')
            source_locks.append(lock)
            lock.verify()
    except BaseException:
        for lock in source_locks:
            lock.close()
        raise
    if args.output.exists():
        raise ValueError('GROUP_OUTPUT_ALREADY_CONSUMED')
    args.output.mkdir(parents=True)
    marker = dict(group=args.group, start_ns=start, package_sha256=args.package_sha256,
                  permission_id=package['authorization']['permission_id'])
    with (args.output / 'CONSUMED.json').open('x', encoding='utf-8') as file:
        json.dump(marker, file)
    ledger = root / 'code/output/m1_c9_oracle_night_r10_20261017/R13_BOUNDED_PREP/CONSUMPTION'
    ledger.mkdir(exist_ok=True)
    grant_key = hashlib.sha256((package['authorization']['permission_id'] + ':' + args.group).encode()).hexdigest()
    with (ledger / (grant_key + '.json')).open('x', encoding='utf-8') as file:
        json.dump(marker, file)
    job_desc = package['windows_job_source']
    job_source = module.verified_buffer(root, job_desc)
    jobmod = importlib.util.module_from_spec(importlib.util.spec_from_loader('_r13_fixed_windows_job', None))
    jobmod.__file__ = str(root / job_desc['path'])
    exec(compile(job_source, jobmod.__file__, 'exec'), jobmod.__dict__)
    job = jobmod.JobProcess.__new__(jobmod.JobProcess)

    def before_resume(pid):
        limits = jobmod.ExtendedLimit()
        limits.basic.flags, limits.basic.active = 0x2000 | 0x8 | 0x200, 1
        limits.job_memory = 768 << 20
        job.ok(job.k.SetInformationJobObject(job.job, 9, C.byref(limits), C.sizeof(limits)))
    argv = [sys.executable, '-B', '-X', 'utf8', str(path), '--package', str(args.package),
            '--package-sha256', args.package_sha256, '--root', str(root), '--group', args.group,
            '--output', str(args.output), '--start-ns', str(start)]
    errors, threads, counts = [], [], [0, 0]

    def drain(stream, index):
        try:
            with (args.output / ('stdout.raw' if index == 0 else 'stderr.raw')).open('xb') as sink:
                while True:
                    block = stream.read(65536)
                    if not block:
                        break
                    counts[index] += len(block)
                    if counts[index] > 4 << 20:
                        raise ValueError('STD_STREAM_BUDGET_EXCEEDED')
                    sink.write(block)
                sink.flush()
                os.fsync(sink.fileno())
        except BaseException as error:
            errors.append(str(error))
    phase = package['time']['fences_seconds'][args.group]
    peak, gap_ns, prior, terminated, rc = 0, 0, start, False, None
    samples = (args.output / 'RSS_SAMPLES.jsonl').open('xb')
    last_self = last_worker = None
    try:
        job.__init__(argv, root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), on_created=before_resume)
        for index, stream in enumerate(job.streams):
            thread = threading.Thread(target=drain, args=(stream, index), daemon=True)
            thread.start()
            threads.append(thread)
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = W.HANDLE
        self_handle = kernel.GetCurrentProcess()
        while True:
            now = time.monotonic_ns()
            gap_ns = max(gap_ns, now - prior)
            prior = now
            last_self, last_worker = native_counters(self_handle), native_counters(job.process)
            peak = max(peak, last_self['peak_working_set'] + last_worker['peak_working_set'])
            sample = dict(elapsed_ns=now-start, supervisor=last_self, worker=last_worker)
            encoded = (json.dumps(sample, separators=(',', ':')) + '\n').encode()
            if samples.tell() + len(encoded) > 16 << 20:
                errors.append('RSS_LOG_BUDGET')
            else:
                samples.write(encoded)
            elapsed = (now - start) / 1e9
            if peak > 512 << 20 or last_self['private_usage'] > 128 << 20 or gap_ns > 100000000:
                errors.append('RSS_MEASUREMENT_INCOMPLETE_OR_LIMIT')
            if elapsed >= phase['cooperative_stop'] or errors:
                (args.output / 'STOP').touch(exist_ok=True)
            if (elapsed >= phase['kill'] or errors) and job.active():
                job.terminate()
                terminated = True
            rc = job.poll()
            if rc is not None and job.active() == 0 and all(not t.is_alive() for t in threads):
                break
            if elapsed >= phase['roots_closed']:
                raise ValueError('OWNED_JOB_OR_STREAM_TAIL_OVERDUE')
            time.sleep(0.02)
        # Keep final OS-latched peak counters obtained through held process handles.
        samples.flush()
        os.fsync(samples.fileno())
        samples.close()
        for stream in job.streams:
            stream.close()
        if job.active() != 0:
            raise ValueError('OWNED_JOB_NOT_ZERO')
        job.close()
        if (time.monotonic_ns()-start)/1e9 >= phase['evidence_flushed']:
            raise ValueError('EVIDENCE_TAIL_OVERDUE')
        receipt = dict(group=args.group, package_sha256=args.package_sha256, start_ns=start,
            peak_RSS_conservative_sum=peak, max_gap_ns=gap_ns, worker_exit=rc,
            job_active=0, root_and_stream_handles_closed=True, terminated=terminated,
            errors=errors, rss_definition='sum of OS-latched per-process PeakWorkingSetSize',
            private_usage_is_RSS=False, real_verified=False, math_verified=False)
        (args.output / 'GROUP_RECEIPT.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        if (time.monotonic_ns()-start)/1e9 >= phase['supervisor_exit']:
            raise ValueError('GROUP_WALL_LIMIT')
        return 0 if rc == 0 and not errors and not terminated else 1
    finally:
        if not samples.closed:
            samples.close()
        if getattr(job, 'job', None):
            if job.active():
                job.terminate()
            job.close()
        for stream in getattr(job, 'streams', []):
            stream.close()
        for lock in source_locks:
            lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
