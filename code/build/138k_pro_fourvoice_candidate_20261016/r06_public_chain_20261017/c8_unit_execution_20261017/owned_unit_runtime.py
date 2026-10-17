"""Fresh owned-Job runtime for the two R09 units; not a CLI command executor."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

JOB_HELPER_SHA = '5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b'


def identity(path):
    raw = Path(path).read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def no_reparse(path):
    path = Path(path).absolute()
    for item in [path, *path.parents]:
        if item.exists() and (getattr(item.lstat(), 'st_file_attributes', 0) & 0x400):
            raise PermissionError('REPARSE_PATH_REJECTED:' + str(item))
    return path


class _Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (name, wintypes.DWORD) for name in ('page_faults', 'total', 'active', 'terminated')]


class FixtureAbort(BaseException):
    """Only used by the frozen software fixture before Job attachment."""


class OwnedJob:
    def __init__(self, helper):
        if os.name != 'nt' or identity(helper)['sha256'] != JOB_HELPER_SHA:
            raise PermissionError('PINNED_WINDOWS_JOB_HELPER_REQUIRED')
        spec = importlib.util.spec_from_file_location('m2_r09_pinned_job', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.job = module.WindowsJob()
        self.kernel = self.job.kernel
        self.kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryInformationJobObject.restype = wintypes.BOOL
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD

    def accounting(self):
        value = _Accounting()
        if not self.kernel.QueryInformationJobObject(self.job.handle, 1, ctypes.byref(value),
                                                     ctypes.sizeof(value), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'total_processes': int(value.total), 'active_processes': int(value.active),
                'terminated_processes': int(value.terminated)}

    def wait_empty(self, deadline):
        while True:
            value = self.accounting()
            if value['active_processes'] == 0:
                return value
            if time.monotonic() >= deadline:
                raise TimeoutError('OWNED_JOB_NOT_EMPTY')
            time.sleep(0.01)


class ExactRunner:
    """Capability is a map of fixed operations supplied by the pinned entry point.

    A caller cannot supply argv, cwd, tools or timeout to execute(); every field
    is rebuilt from the fixed operation table. No shell or arbitrary-command CLI.
    """

    def __init__(self, helper, root, operations, frozen_inputs, environment_base):
        self.helper = Path(helper)
        self.root = no_reparse(root).resolve()
        self.operations = operations
        self.inputs = {str(Path(path).resolve()): expected for path, expected in frozen_inputs.items()}
        self.environment_base = dict(environment_base)
        if not self.root.is_dir():
            raise PermissionError('FIXED_GROUP_ROOT_MISSING')

    def check_inputs(self):
        for path, expected in self.inputs.items():
            if identity(path) != expected:
                raise PermissionError('FROZEN_INPUT_CHANGED:' + path)

    def validate_request(self, name, proposed=None):
        if name not in self.operations:
            raise PermissionError('OPERATION_NOT_IN_FIXED_TABLE')
        operation = self.operations[name]
        if proposed is not None and proposed != operation:
            raise PermissionError('CALLER_CHANGED_FIXED_OPERATION')
        if not name.replace('_', '').isalnum() or not 0 < operation['seconds'] <= 15:
            raise PermissionError('INVALID_FIXED_OPERATION')
        return operation

    def execute(self, name, group_deadline, *, software_fault_before_attach=False,
                software_fault_tail_log=False, software_fault_receipt=False):
        operation = self.validate_request(name)
        if any((software_fault_before_attach, software_fault_tail_log, software_fault_receipt)) and not operation.get('software_fixture'):
            raise PermissionError('FAULT_INJECTION_ONLY_FOR_FIXED_SOFTWARE_FIXTURE')
        self.check_inputs()
        case = self.root / name
        no_reparse(case)
        case.mkdir(exist_ok=False)
        case = no_reparse(case).resolve()
        if case.parent != self.root:
            raise PermissionError('OUTPUT_SCOPE_ESCAPE')
        (case / 'tmp').mkdir()
        for source, filename in operation.get('stage_files', []):
            if Path(filename).name != filename:
                raise PermissionError('NON_BASENAME_STAGE_FILE')
            (case / filename).write_bytes(Path(source).read_bytes())
        # Output token replacement is internal, never accepted from a JSON argv.
        argv = [value.replace('{case}', str(case)) for value in operation['argv']]
        env = dict(self.environment_base)
        env.update({'TEMP': str(case / 'tmp'), 'TMP': str(case / 'tmp')})
        start = time.monotonic()
        if group_deadline - start < operation['seconds'] + 3:
            raise TimeoutError('INSUFFICIENT_GROUP_BUDGET')
        record = {'schema': 'M2_R09_OWNED_STEP_V1', 'operation': name, 'argv': argv, 'cwd': str(case),
                  'environment': env, 'started_utc': utc(), 'pid': None, 'job_attached': False,
                  'stop_reason': None, 'root_exit_code': None, 'cleanup': None, 'error': None,
                  'job_empty_before_close': False, 'root_handle_signaled': False,
                  'root_handle_closed': False,
                  'streams_closed_after_job_empty': False, 'software_fixture': operation.get('software_fixture', False),
                  'board_release_allowed': False, 'log_watermark': operation.get('log_watermark', 1048576),
                  'log_limit_is_observed_watermark_not_hard_cap': True}
        save(case / 'START.json', record)
        job = None
        process = None
        stdout = stderr = None
        primary = None
        finalization_errors = []

        def release_root(deadline):
            if process is None or record['root_handle_closed']:
                return
            record['root_exit_code'] = process.wait(timeout=max(0.01, deadline - time.monotonic()))
            signaled = job.kernel.WaitForSingleObject(wintypes.HANDLE(int(process._handle)), 0) == 0
            record['root_handle_signaled'] = signaled
            if not signaled:
                raise RuntimeError('ROOT_HANDLE_NOT_SIGNALED')
            process._handle.Close()
            record['root_handle_closed'] = True

        try:
            job = OwnedJob(self.helper)
            stdout = (case / 'stdout.raw').open('xb')
            stderr = (case / 'stderr.raw').open('xb')
            process = subprocess.Popen(argv, cwd=case, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, shell=False,
                                       creationflags=0x08000000 | subprocess.CREATE_NEW_PROCESS_GROUP | 4)
            record['pid'] = process.pid
            if software_fault_before_attach:
                raise FixtureAbort('FIXTURE_ABORT_BEFORE_JOB_ATTACH')
            # No fallible metadata write between suspended creation and ownership.
            job.job.attach_and_resume(process)
            record['job_attached'] = True
            save(case / 'LAUNCHED_ATTACHED.json', record)
            deadline = min(group_deadline - 3, start + operation['seconds'])
            root_ended_at = None
            while True:
                sizes = [(case / n).stat().st_size for n in ('stdout.raw', 'stderr.raw')]
                record['last_observed_stream_bytes'] = sizes
                if sum(sizes) > record['log_watermark']:
                    record['stop_reason'] = 'LOG_WATERMARK'
                    break
                code = record['root_exit_code'] if record['root_handle_closed'] else process.poll()
                if code is not None and not record['root_handle_closed']:
                    record['root_exit_code_before_cleanup'] = code
                    # ActiveProcesses may retain terminated processes while a
                    # process reference remains. Release our confirmed root
                    # reference before requiring the still-open Job to be empty.
                    release_root(deadline)
                accounting = job.accounting()
                if code is not None:
                    record['root_exit_code'] = code
                    if accounting['active_processes'] == 0:
                        record['stop_reason'] = 'ROOT_AND_JOB_EXITED'
                        break
                    if root_ended_at is None:
                        root_ended_at = time.monotonic()
                    elif time.monotonic() - root_ended_at > 0.2:
                        record['stop_reason'] = 'JOB_NONEMPTY_AFTER_ROOT_EXIT'
                        break
                if time.monotonic() >= deadline:
                    record['stop_reason'] = 'TIMEOUT'
                    break
                time.sleep(0.005)
            if software_fault_tail_log:
                # Deterministic software-only reproduction of a tail write
                # after the final poll; never enabled for a compiler/simulator.
                stdout.write(b'T' * (record['log_watermark'] + 1))
                stdout.flush()
        except BaseException as error:
            record['error'] = type(error).__name__ + ': ' + str(error)
            record['stop_reason'] = 'EXCEPTION'
            primary = (error, error.__traceback__)
        finally:
            cleanup_deadline = min(group_deadline, time.monotonic() + 2.5)
            try:
                if process is not None and not record['job_attached']:
                    if process.poll() is None:
                        process.kill()  # current Popen handle only, never old PID
                    release_root(cleanup_deadline)
                    record['cleanup'] = 'CURRENT_UNATTACHED_POPEN_HANDLE_KILL_AND_WAIT'
                if job is not None:
                    record['accounting_before_cleanup'] = job.accounting()
                    if record['accounting_before_cleanup']['active_processes']:
                        job.job.terminate()
                        record['cleanup'] = 'OWNED_JOB_TERMINATE_AND_WAIT_EMPTY'
                    if process is not None:
                        release_root(cleanup_deadline)
                    record['accounting_final'] = job.wait_empty(cleanup_deadline)
                    record['job_empty_before_close'] = True
                if process is None:
                    record['root_handle_signaled'] = True
                    record['root_handle_closed'] = True
            except BaseException as cleanup_error:
                record['cleanup_error'] = type(cleanup_error).__name__ + ': ' + str(cleanup_error)
            finally:
                if job is not None:
                    try:
                        job.job.close()  # fallback also kills this owned tree
                    except BaseException as close_error:
                        finalization_errors.append('job.close: ' + repr(close_error))
                if process is not None and not record['root_handle_closed']:
                    try:
                        if process.poll() is None:
                            process.kill()  # our live Popen handle, never a PID
                        release_root(cleanup_deadline)
                    except BaseException as root_error:
                        finalization_errors.append('root.final_cleanup: ' + repr(root_error))
                stream_close_ok = True
                for label, stream in [('stdout', stdout), ('stderr', stderr)]:
                    if stream is not None:
                        try:
                            stream.close()
                        except BaseException as close_error:
                            stream_close_ok = False
                            finalization_errors.append(label + '.close: ' + repr(close_error))
                record['streams_closed_after_job_empty'] = record['job_empty_before_close'] and stream_close_ok
                record['ended_utc'] = utc()
                record['elapsed_seconds'] = time.monotonic() - start
                record['group_deadline_kept'] = time.monotonic() <= group_deadline
                record['logs'] = {}
                for log_name in ('stdout.raw', 'stderr.raw'):
                    try:
                        record['logs'][log_name] = identity(case / log_name)
                    except BaseException as log_error:
                        finalization_errors.append(log_name + '.identity: ' + repr(log_error))
                record['log_limit_observed'] = (record['stop_reason'] == 'LOG_WATERMARK' or
                    sum(item['bytes'] for item in record['logs'].values()) > record['log_watermark'])
                if record['log_limit_observed'] and record['stop_reason'] == 'ROOT_AND_JOB_EXITED':
                    record['stop_reason'] = 'LOG_WATERMARK_FINAL'
                try:
                    self.check_inputs()
                    record['inputs_unchanged'] = True
                except BaseException as identity_error:
                    record['inputs_unchanged'] = False
                    record['identity_error'] = str(identity_error)
                record['clean_exit'] = (record['stop_reason'] == 'ROOT_AND_JOB_EXITED' and
                                        record['root_exit_code'] == 0 and record['job_empty_before_close'] and
                                        record['root_handle_signaled'] and record['root_handle_closed'] and record['inputs_unchanged'] and
                                        record['group_deadline_kept'] and 'cleanup_error' not in record and
                                        record['streams_closed_after_job_empty'] and not record['log_limit_observed'] and
                                        len(record['logs']) == 2 and not finalization_errors)
                record['finalization_errors'] = finalization_errors
                record['receipt_complete'] = True
                try:
                    if software_fault_receipt:
                        raise OSError('FIXTURE_RECEIPT_WRITE_FAILURE')
                    save(case / 'RECEIPT.json', record)
                except BaseException as receipt_error:
                    finalization_errors.append('receipt.save: ' + repr(receipt_error))
                    record['clean_exit'] = False
                    record['receipt_complete'] = False
                    try:
                        save(case / 'FINALIZATION_FAILURE.json', record)
                    except BaseException as fallback_error:
                        finalization_errors.append('fallback.save: ' + repr(fallback_error))
        if primary is not None:
            if finalization_errors:
                try:
                    print(json.dumps({'primary_error': record['error'], 'finalization_errors': finalization_errors}),
                          file=sys.stderr, flush=True)
                except BaseException:
                    pass
            raise primary[0].with_traceback(primary[1])
        if finalization_errors or 'cleanup_error' in record:
            raise RuntimeError('OWNED_STEP_FINALIZATION_FAILED:' + repr(record))
        return record
