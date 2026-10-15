"""Tk-free state machine and bounded owned-process offline MIDI import."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

from preview_model import (
    ARTIFACTS, FROZEN, IMPORTER_DIR, ROOT, PreviewError, checked_read, frozen_snapshot, identity,
    load_preview, validate_windows_path, windows_path_units,
)

STAGE_FILES = (*ARTIFACTS, 'receipt.json')
LOG_FILES = ('command.json', 'stdout.bin', 'stderr.bin', 'process_receipt.json',
             'desktop_execution.json', 'preview.json',
             'dependency_before.json', 'dependency_after.json')
EXPORT_FILES = (*STAGE_FILES, 'desktop_export_receipt.json')
# Longest suffix is \\logs_<32 hex>\\desktop_execution.json: 61 UTF-16 units.
MAX_WORKSPACE_UNITS = 259 - max(windows_path_units('\\logs_' + '0' * 32 + '\\' + name)
                                for name in LOG_FILES)


class DesktopError(ValueError):
    """Rejected desktop operation, never a hardware acceptance result."""


def _portable(path, directory=False, label='path', reject_final_symlink=False):
    try:
        return validate_windows_path(path, directory=directory, label=label,
                                     reject_final_symlink=reject_final_symlink)
    except PreviewError as exc:
        raise DesktopError(str(exc)) from exc


def validate_workspace_path(workspace):
    """Validate every future fixed filename before creating any workspace."""
    workspace = _portable(workspace, directory=True, label='workspace')
    token = '0' * 32
    for directory, names in ((workspace / ('stage_' + token), STAGE_FILES),
                             (workspace / ('logs_' + token), LOG_FILES)):
        _portable(directory, directory=True, label='generated directory')
        for name in names:
            _portable(directory / name, label='generated file')
    for tail in ('_start.json', '_receipt.json'):
        _portable(workspace / ('operation_' + token + tail), label='operation receipt')
    return workspace


def _save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def _environment():
    # Deliberately exclude PYTHONPATH/PYTHONHOME, shell hooks and credentials.
    allowed = ('PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP',
               'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'LOCALAPPDATA', 'APPDATA',
               'PROGRAMFILES', 'PROGRAMFILES(X86)', 'PROGRAMDATA',
               'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS')
    current = {key.upper(): value for key, value in os.environ.items()}
    result = {key: current[key] for key in allowed if key in current}
    result['PYTHONDONTWRITEBYTECODE'] = '1'
    result['PYTHONNOUSERSITE'] = '1'
    result['PYTHONIOENCODING'] = 'utf-8'
    return result


class _BasicLimit(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('minimum', ctypes.c_size_t),
                ('maximum', ctypes.c_size_t), ('active', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD)]


class _Counters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [('basic', _BasicLimit), ('io', _Counters),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]


class _Startup(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('reserved', wintypes.LPWSTR),
                ('desktop', wintypes.LPWSTR), ('title', wintypes.LPWSTR),
                ('x', wintypes.DWORD), ('y', wintypes.DWORD), ('xsize', wintypes.DWORD),
                ('ysize', wintypes.DWORD), ('xchars', wintypes.DWORD), ('ychars', wintypes.DWORD),
                ('fill', wintypes.DWORD), ('flags', wintypes.DWORD), ('show', wintypes.WORD),
                ('reserved_size', wintypes.WORD), ('reserved_data', ctypes.POINTER(ctypes.c_byte)),
                ('stdin', wintypes.HANDLE), ('stdout', wintypes.HANDLE), ('stderr', wintypes.HANDLE)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [('process', wintypes.HANDLE), ('thread', wintypes.HANDLE),
                ('pid', wintypes.DWORD), ('tid', wintypes.DWORD)]


def run_owned_child(argv, cwd, logs, cancel, timeout):
    """Create suspended, bind a private kill-on-close Job, then resume exactly once.

    No taskkill/name matching, shell, hidden retry or unbounded wait. The Windows
    target is explicit; unsupported platforms fail closed rather than weaken it.
    """
    if os.name != 'nt':
        raise DesktopError('WINDOWS_JOB_REQUIRED: this desktop target is Windows')
    if not 0 < timeout <= 90:
        raise DesktopError('STEP_TIMEOUT_RANGE: maximum is 90 seconds')
    logs = _portable(logs, directory=True, label='runner logs')
    _portable(cwd, directory=True, label='child cwd')
    _portable(argv[0], label='child executable')
    for name in LOG_FILES:
        _portable(logs / name, label='runner log file')
    logs.mkdir(parents=True, exist_ok=True)
    environment = _environment()
    record = dict(argv=list(map(str, argv)), cwd=str(Path(cwd).resolve()),
                  environment=environment, timeout_seconds=timeout,
                  started_utc=datetime.now(timezone.utc).isoformat(),
                  mechanism='CreateProcessW suspended / private kill-on-close Job / ResumeThread',
                  shell=False, automatic_retries=0, tool_calls=0,
                  exit_code=None, timed_out=False, cancelled=False)
    _save(logs / 'command.json', record)
    start = time.monotonic()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                     ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                                     ctypes.c_void_p, wintypes.LPCWSTR,
                                     ctypes.POINTER(_Startup), ctypes.POINTER(_ProcessInfo)]
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    job, process, primary = None, None, None
    assigned, resumed = False, False
    try:
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimit()
        limits.basic.flags = 0x2000
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        with (logs / 'stdout.bin').open('xb') as stdout, (logs / 'stderr.bin').open('xb') as stderr, open(os.devnull, 'rb') as stdin:
            if cancel.is_set():
                record['cancelled'] = True
            else:
                import msvcrt
                handles = [msvcrt.get_osfhandle(stream.fileno()) for stream in (stdin, stdout, stderr)]
                for handle in handles:
                    os.set_handle_inheritable(handle, True)
                info, startup = _ProcessInfo(), _Startup()
                startup.cb = ctypes.sizeof(startup)
                startup.flags = 0x100  # STARTF_USESTDHANDLES
                startup.stdin, startup.stdout, startup.stderr = handles
                command = ctypes.create_unicode_buffer(subprocess.list2cmdline(record['argv']))
                block = ctypes.create_unicode_buffer('\0'.join(f'{key}={value}' for key, value in sorted(environment.items())) + '\0\0')
                try:
                    # Suspended + Unicode environment + no console window.
                    created = kernel.CreateProcessW(record['argv'][0], command, None, None, True,
                                                    0x4 | 0x400 | 0x8000000, block, record['cwd'],
                                                    ctypes.byref(startup), ctypes.byref(info))
                finally:
                    for handle in handles:
                        os.set_handle_inheritable(handle, False)
                if not created:
                    raise ctypes.WinError(ctypes.get_last_error())
                process, primary = info.process, info.thread
                record.update(tool_calls=1, pid=info.pid)
                if not kernel.AssignProcessToJobObject(job, process):
                    raise ctypes.WinError(ctypes.get_last_error())
                assigned = True
                if kernel.ResumeThread(primary) == 0xffffffff:
                    raise ctypes.WinError(ctypes.get_last_error())
                resumed = True
                kernel.CloseHandle(primary)
                primary = None
                while True:
                    waited = kernel.WaitForSingleObject(process, 50)
                    if waited == 0:
                        break
                    if waited != 258:
                        raise ctypes.WinError(ctypes.get_last_error())
                    record['cancelled'] = cancel.is_set()
                    record['timed_out'] = time.monotonic() - start >= timeout
                    if record['cancelled'] or record['timed_out']:
                        if not kernel.TerminateJobObject(job, 1):
                            raise ctypes.WinError(ctypes.get_last_error())
                        if kernel.WaitForSingleObject(process, 3000) != 0:
                            raise DesktopError('OWNED_PROCESS_CLEANUP_FAILED')
                        break
                code = wintypes.DWORD()
                if not kernel.GetExitCodeProcess(process, ctypes.byref(code)):
                    raise ctypes.WinError(ctypes.get_last_error())
                record['exit_code'] = code.value
    except Exception as exc:
        record['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        if process:
            if assigned:
                kernel.TerminateJobObject(job, 1)  # Also reap any still-live descendants.
            elif not resumed:
                kernel.TerminateProcess(process, 1)  # Child never executed outside our Job.
            kernel.WaitForSingleObject(process, 3000)
        for handle in (primary, process, job):
            if handle:
                kernel.CloseHandle(handle)
        record['seconds'] = time.monotonic() - start
        record['owned_job_assigned'] = assigned
        for name in ('stdout', 'stderr'):
            path = logs / (name + '.bin')
            if path.is_file():
                record[name] = identity(path.read_bytes())
        _save(logs / 'process_receipt.json', record)
    return record


class Controller:
    """Caller-thread state transitions; workers only enqueue immutable results."""

    def __init__(self, workspace, runner=None, step_timeout=90):
        if not 0 < step_timeout <= 90:
            raise DesktopError('STEP_TIMEOUT_RANGE')
        self.workspace = validate_workspace_path(workspace)
        if self.workspace.exists():
            raise DesktopError('WORKSPACE_EXISTS: use a new exclusive directory')
        self.workspace.mkdir(parents=True, exist_ok=False)
        self.runner = runner or run_owned_child
        self.step_timeout = step_timeout
        self.state, self.result, self.error, self.stage = 'idle', None, None, None
        self.source, self.input_identity = None, None
        self.history = []
        self._token, self._thread, self._cancel = None, None, threading.Event()
        self._queue, self._owner = queue.Queue(), threading.get_ident()

    def _caller(self):
        if threading.get_ident() != self._owner:
            raise DesktopError('CONTROLLER_CALLER_THREAD_REQUIRED')

    def _available(self):
        self._caller()
        if self.state == 'closed':
            raise DesktopError('CONTROLLER_CLOSED')
        if self.state in ('loading', 'exporting'):
            raise DesktopError('BUSY: wait, cancel, or close the current operation')

    def select_file(self, path):
        self._available()
        if path is None or str(path) == '':
            return False
        source = _portable(path, label='selected MIDI file', reject_final_symlink=True)
        if source.suffix.lower() not in ('.mid', '.midi'):
            raise DesktopError('INPUT_EXTENSION: choose an existing .mid or .midi')
        raw = checked_read(source)
        self.source, self.input_identity = source, identity(raw)
        self.state, self.result, self.error, self.stage = 'selected', None, None, None
        return True

    def _launch(self, operation, work):
        token = uuid.uuid4().hex
        self._token, self._cancel = token, threading.Event()
        cancel = self._cancel
        self.state, self.error = ('loading' if operation == 'preview' else 'exporting'), None
        selected_source = str(self.source) if self.source is not None else None
        selected_identity = dict(self.input_identity) if self.input_identity is not None else None

        def execute():
            paths = [Path(__file__).resolve(), Path(__file__).with_name('preview_model.py').resolve(),
                     Path(__file__).with_name('desktop_gui.py').resolve(), Path(sys.executable).resolve()]
            record = dict(schema=1, operation=operation, token=token, source=selected_source,
                          input=selected_identity, serial_calls=0, network_calls=0,
                          hardware_pass_claim=False, started_utc=datetime.now(timezone.utc).isoformat())
            begun = time.monotonic()
            try:
                record['implementation_before'] = {str(path): identity(checked_read(path, 64 * 1024 * 1024)) for path in paths}
                _save(self.workspace / ('operation_' + token + '_start.json'), record)
                value = work(cancel, token)
                after = {str(path): identity(checked_read(path, 64 * 1024 * 1024)) for path in paths}
                record['implementation_after'] = after
                if after != record['implementation_before']:
                    raise DesktopError('DESKTOP_IMPLEMENTATION_CHANGED_DURING_OPERATION')
                item = dict(type='cancelled' if cancel.is_set() else 'completed',
                            operation=operation, token=token, result=value)
            except Exception as exc:
                item = dict(type='cancelled' if cancel.is_set() else 'failed',
                            operation=operation, token=token,
                            error=f'{type(exc).__name__}: {exc}',
                            diagnostics=list(getattr(exc, '__notes__', ())))
            record.update(status=item['type'], error=item.get('error'),
                          diagnostics=item.get('diagnostics', []),
                          seconds=time.monotonic() - begun,
                          exit_code=0 if item['type'] == 'completed' else 1)
            try:
                if 'implementation_after' not in record:
                    record['implementation_after'] = {str(path): identity(checked_read(path, 64 * 1024 * 1024)) for path in paths}
                _save(self.workspace / ('operation_' + token + '_receipt.json'), record)
            except Exception as exc:
                item = dict(type='failed', operation=operation, token=token,
                            error=f'EVIDENCE_WRITE_FAILED: {exc}; original={item.get("error")}')
            self._queue.put(item)

        self._thread = threading.Thread(target=execute, name='midi_desktop_' + operation, daemon=True)
        self._thread.start()
        return token

    def preview(self, score_id=1, session=1, source_description='', license_note=''):
        self._available()
        if self.source is None:
            raise DesktopError('NO_SELECTION')
        if type(score_id) is not int or not 0 <= score_id <= 0xffffffff:
            raise DesktopError('SCORE_ID: require u32 integer')
        if type(session) is not int or not 1 <= session <= 65535:
            raise DesktopError('SESSION: require 1..65535')
        source, expected = self.source, dict(self.input_identity)
        self.result = None

        def work(cancel, token):
            executable = Path(sys.executable).resolve()
            stage, logs = self.workspace / ('stage_' + token), self.workspace / ('logs_' + token)
            if stage.exists() or logs.exists():
                raise DesktopError('STAGE_EXISTS: never reuse an old attempt')
            logs.mkdir()

            def dependency_inventory():
                observed = {}
                for path in (*FROZEN, executable):
                    try:
                        observed[str(path)] = identity(checked_read(path, 64 * 1024 * 1024))
                    except Exception as exc:
                        observed[str(path)] = {'error': f'{type(exc).__name__}: {exc}'}
                return observed

            dependency_before, primary_error = dependency_inventory(), None
            try:
                _save(logs / 'dependency_before.json', dict(schema=1, phase='before',
                      observed=dependency_before, frozen_expected={str(path): sha for path, sha in FROZEN.items()}))
                before = frozen_snapshot()
                interpreter = identity(checked_read(executable, 64 * 1024 * 1024))
                if identity(checked_read(source)) != expected:
                    raise DesktopError('INPUT_CHANGED: select the file again')
                argv = [str(executable), '-S', '-s', '-B', '-X', 'utf8', str(IMPORTER_DIR / 'midi_import.py'),
                        'import', '--input', str(source), '--score-id', str(score_id),
                        '--session', str(session), '--source-description', source_description,
                        '--license-note', license_note, '--output', str(stage)]
                execution = self.runner(argv, ROOT, logs, cancel, self.step_timeout)
                _save(logs / 'desktop_execution.json', execution)
                if cancel.is_set() or execution.get('cancelled'):
                    raise DesktopError('CANCELLED: evidence retained, nothing exported')
                if execution.get('timed_out'):
                    raise DesktopError('IMPORT_TIMEOUT: no automatic retry')
                if execution.get('error') or execution.get('exit_code') != 0:
                    detail = execution.get('error', '')
                    stderr, stdout = logs / 'stderr.bin', logs / 'stdout.bin'
                    for path in (stderr, stdout):
                        if path.is_file():
                            detail += checked_read(path, 4 * 1024 * 1024).decode('utf-8', errors='replace')[-4096:]
                    raise DesktopError('IMPORT_EXIT: ' + str(execution.get('exit_code')) + ' ' + detail)
                result = load_preview(stage, source, expected)
                if before != frozen_snapshot() or interpreter != identity(checked_read(executable, 64 * 1024 * 1024)):
                    raise DesktopError('DEPENDENCY_CHANGED_DURING_IMPORT')
                result.update(stage=str(stage), execution=execution, interpreter=interpreter)
                _save(logs / 'preview.json', result)
                return result
            except Exception as exc:
                primary_error = exc
                raise
            finally:
                after = dependency_inventory()
                try:
                    _save(logs / 'dependency_after.json', dict(schema=1, phase='after', observed=after,
                          matches_before=after == dependency_before,
                          primary_error=None if primary_error is None else f'{type(primary_error).__name__}: {primary_error}'))
                except Exception as evidence_error:
                    if primary_error is None:
                        raise DesktopError('DEPENDENCY_EVIDENCE_WRITE_FAILED: ' + str(evidence_error)) from evidence_error
                    primary_error.add_note('DEPENDENCY_EVIDENCE_WRITE_FAILED: ' + str(evidence_error))
                if primary_error is None and after != dependency_before:
                    raise DesktopError('DEPENDENCY_CHANGED_DURING_IMPORT')

        return self._launch('preview', work)

    def export(self, destination, confirmed=False):
        self._available()
        if self.state != 'ready' or self.result is None:
            raise DesktopError('PREVIEW_REQUIRED')
        if confirmed is not True:
            raise DesktopError('EXPORT_CONFIRMATION_REQUIRED')
        destination = _portable(destination, directory=True, label='export directory')
        for name in EXPORT_FILES:
            _portable(destination / name, label='export file')
        if destination.exists():
            raise DesktopError('OUTPUT_EXISTS: choose a new directory')
        selected = self.result
        source, expected, stage = self.source, dict(self.input_identity), self.stage

        def work(cancel, token):
            result = load_preview(stage, source, expected)
            if result['identities'] != selected['identities'] or result['rows'] != selected['rows']:
                raise DesktopError('PREVIEW_CHANGED: re-import before exporting')
            if cancel.is_set():
                raise DesktopError('CANCELLED')
            blobs = {name: checked_read(stage / name, 2 * 1024 * 1024) for name in (*ARTIFACTS, 'receipt.json')}
            if any(identity(raw) != selected['identities'][name] for name, raw in blobs.items()):
                raise DesktopError('ARTIFACT_CHANGED_BEFORE_EXPORT')
            destination.mkdir(parents=True, exist_ok=False)
            receipt = dict(schema=1, status='FAIL', operation='confirmed_offline_export', token=token,
                           stage=str(stage), source=str(source), input=expected,
                           user_confirmed=True, artifacts={}, serial_calls=0, network_calls=0,
                           hardware_pass_claim=False, exit_code=1)
            try:
                for name, raw in blobs.items():
                    if cancel.is_set():
                        raise DesktopError('CANCELLED: partial output retained')
                    with (destination / name).open('xb') as stream:
                        stream.write(raw)
                    receipt['artifacts'][name] = identity(checked_read(destination / name))
                    if receipt['artifacts'][name] != selected['identities'][name]:
                        raise DesktopError('EXPORT_BYTES_MISMATCH')
                copied = load_preview(destination, source, expected)
                if copied['identities'] != selected['identities'] or copied['rows'] != selected['rows']:
                    raise DesktopError('EXPORT_READBACK_MISMATCH')
                receipt.update(status='OFFLINE_EXPORT_PASS', exit_code=0,
                               frozen_dependencies=copied['frozen_dependencies'])
            except Exception as exc:
                receipt['error'] = f'{type(exc).__name__}: {exc}'
                raise
            finally:
                _save(destination / 'desktop_export_receipt.json', receipt)
            return dict(destination=str(destination), receipt=receipt, preview=copied)

        return self._launch('export', work)

    def poll(self):
        self._caller()
        received = []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            self.history.append(item)
            if self.state == 'closed' or item['token'] != self._token:
                continue
            if item['type'] == 'completed':
                if item['operation'] == 'preview':
                    self.result = item['result']
                    self.stage = Path(self.result['stage'])
                self.state = 'ready'
                self.error = None
            elif item['type'] == 'cancelled':
                self.state, self.result, self.error = 'selected', None, 'CANCELLED: evidence retained'
            else:
                self.state, self.result, self.error = 'error', None, item['error']
            received.append(item)
        return received

    def cancel(self):
        self._caller()
        if self.state in ('loading', 'exporting'):
            self._cancel.set()

    def close(self):
        self._caller()
        self._cancel.set()
        self._token = None
        self.state, self.result = 'closed', None

    def wait_closed(self, timeout=5):
        if not 0 <= timeout <= 5:
            raise DesktopError('CLOSE_TIMEOUT_RANGE: maximum 5 seconds')
        if self._thread is not None:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True
