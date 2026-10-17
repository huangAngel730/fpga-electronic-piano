"""Coordinator-only, <=60s owned-worker drill. Import has no side effects.

No Git, network, shells, devices or external task processes are started.
Only two direct executions of the sibling pure-Python worker are permitted.
"""
from __future__ import annotations

import argparse  # Include the worker CLI's initial stdlib imports in the snapshot.
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def identity(file):
    h, count = hashlib.sha256(), 0
    with Path(file).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
            count += len(block)
    return {'bytes': count, 'sha256': h.hexdigest()}


def save(file, value):
    with Path(file).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def read(file):
    with Path(file).open('rb') as stream:
        raw = stream.read(1024 * 1024 + 1)
    require(len(raw) <= 1024 * 1024, 'RECOVERY_METADATA_BOUND')
    return json.loads(raw)


def run(out: Path, context: dict) -> dict:
    """Context: original_START/deadline/goal/consumption plus optional handoff.

    Caller must persist consumption BEFORE invoking, then supply that complete
    consumption snapshot. This helper neither allocates nor resets a budget.
    It operates only in a fresh LOCAL_SYNTHETIC subdirectory of drill output.
    """
    began = time.monotonic()
    end = began + 55.0  # Reserve five seconds of the enclosing 60s group.
    root = Path(__file__).resolve().parents[8]
    allowed = root / 'code/output/m3_m2_night_drill_20261017'
    out = Path(out)
    for part in (out, *out.parents):
        require(not part.is_symlink() and not part.is_junction(), 'OUTPUT_ALIAS')
    out = out.resolve()
    require(out != allowed and out.is_relative_to(allowed), 'RECOVERY_OUTPUT_SCOPE')
    context_bytes = json.dumps(context, allow_nan=False).encode('utf-8')
    require(len(context_bytes) <= 256 * 1024, 'CONTEXT_SIZE_BOUND')
    context = json.loads(context_bytes)
    for key in ('original_START', 'deadline', 'goal', 'consumption'):
        require(key in context and context[key] is not None, 'CONTEXT_REQUIRED:' + key)
    require(isinstance(context['consumption'], dict) and context['consumption'],
            'PERSISTED_CONSUMPTION_SNAPSHOT_REQUIRED')
    require(isinstance(context['goal'], dict) and context['goal'].get('threadId')
            and type(context['goal'].get('createdAt')) is int
            and context['goal'].get('status') == 'active', 'ACTIVE_GOAL_IDENTITY_REQUIRED')
    start = datetime.fromisoformat(context['original_START'])
    deadline = datetime.fromisoformat(context['deadline'])
    require(start.tzinfo is not None and deadline.tzinfo is not None, 'START_TIMEZONE')
    require(0 < (deadline - start).total_seconds() <= 5 * 3600, 'ORIGINAL_TIMEBOX')
    require((deadline - datetime.now(timezone.utc)).total_seconds() >= 60,
            'INSUFFICIENT_ORIGINAL_TIME_REMAINING')
    handoff = context.get('handoff', {})
    handoff_id = handoff.get('handoff_id', 'NIGHT-RULES-GOAL-20261017-01')
    commit = handoff.get('result_commit', '30a8cd5474e6ff485ce0bf8fd5f3c1d51643123a')
    require(isinstance(handoff_id, str) and handoff_id and
            isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit), 'HANDOFF_IDENTITY')
    worker = Path(__file__).with_name('owned_worker.py').resolve()
    frozen = {str(worker): identity(worker), str(Path(__file__).resolve()): identity(__file__),
              str(Path(sys.executable).resolve()): identity(sys.executable)}
    stdlib_roots = [Path(sys.base_prefix) / 'Lib', Path(sys.base_prefix) / 'DLLs']
    stdlib_roots.append(Path(os.__file__).resolve().parent)
    stdlib_files = set()
    for module in tuple(sys.modules.values()):
        for name in (getattr(module, '__file__', None), getattr(module, '__cached__', None)):
            if not name:
                continue
            file = Path(name).resolve()
            if (file.is_file() and any(file.is_relative_to(base) for base in stdlib_roots)
                    and 'site-packages' not in file.parts):
                stdlib_files.add(file)
    for file in sorted(stdlib_files):
        frozen[str(file)] = identity(file)
    token = uuid.uuid4().hex
    out.mkdir(parents=True, exist_ok=False)
    seed = {'schema': 'M3_LOCAL_RECOVERY_SEED_V1', 'origin': 'LOCAL_SYNTHETIC',
            'token': token, 'handoff_id': handoff_id, 'result_commit': commit,
            'dedup_key': [handoff_id, commit, 'M3'],
            'identity': {key: context[key] for key in ('original_START', 'deadline', 'goal')},
            'consumption': context['consumption']}
    save(out / 'CONTEXT.json', context)
    save(out / 'SEED.json', seed)
    seed_sha = identity(out / 'SEED.json')['sha256']
    checkpoint = out / 'state/CHECKPOINT.json'
    processes, handles = [], []
    records = []

    def remaining(cap=5.0):
        value = min(cap, end - time.monotonic())
        require(value > 0, 'RECOVERY_GROUP_DEADLINE')
        return value

    def launch(mode):
        require(end - time.monotonic() >= 5, 'NO_TIME_FOR_OWNED_WORKER_START')
        for name, expected in frozen.items():
            require(identity(name) == expected, 'FROZEN_SOURCE_CHANGED:' + name)
        argv = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(worker), mode,
                '--directory', str(out), '--token', token, '--seed-sha', seed_sha]
        environment = {name: os.environ[name] for name in
                       ('SystemRoot', 'WINDIR', 'SYSTEMDRIVE', 'TEMP', 'TMP')
                       if name in os.environ}
        contract = {'origin': 'LOCAL_SYNTHETIC', 'argv': argv, 'cwd': str(out),
                    'sources_and_interpreter': frozen,
                    'environment': dict(sorted(environment.items())),
                    'seed': identity(out / 'SEED.json'), 'group_limit_seconds': 60,
                    'runner_internal_limit_seconds': 55, 'shell': False,
                    'dependency_coverage': 'Parent already-loaded stdlib file/cache snapshot; '
                                           'worker lazy imports and dynamic system DLL closure PENDING',
                    'dependencies': 'CPython stdlib only; interpreter SHA is not dynamic DLL authentication'}
        # Minimal actual environment: no inherited tokens or credentials.
        save(out / (mode + '_BEFORE_START.json'), contract)
        stdout = (out / (mode + '_stdout.raw')).open('xb')
        stderr = (out / (mode + '_stderr.raw')).open('xb')
        handles.extend([stdout, stderr])
        require(end - time.monotonic() >= 5, 'NO_TIME_FOR_OWNED_WORKER_START')
        proc = subprocess.Popen(argv, cwd=out, env=environment, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, shell=False,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        processes.append(proc)  # Only these exact handles may be terminated.
        record = {'mode': mode, 'pid': proc.pid, 'argv': argv,
                  'started_monotonic': time.monotonic(), 'exit_code': None}
        records.append(record)
        save(out / (mode + '_PID.json'), record)
        return proc, record

    try:
        first, first_record = launch('prepare')
        ready_deadline = min(end - 8, time.monotonic() + 15)
        while not checkpoint.exists():
            require(first.poll() is None, 'PREPARE_EXIT_BEFORE_CHECKPOINT')
            require(time.monotonic() < ready_deadline, 'PREPARE_CHECKPOINT_TIMEOUT')
            time.sleep(min(0.02, remaining()))
        cp = read(checkpoint)
        require(cp['owner_pid'] == first.pid and cp['token'] == token, 'OWNED_PID_CHECKPOINT')
        before = {str(p.relative_to(out)): identity(p) for p in (out / 'state').rglob('*') if p.is_file()}
        save(out / 'BEFORE_INTERRUPTION.json', {'state_files': before, 'checkpoint': cp,
                                               'owned_pid': first.pid, 'token': token})
        require(first.poll() is None, 'PREPARE_EXITED_BEFORE_INJECTION')
        first.terminate()
        first.wait(timeout=remaining())
        first_record.update(exit_code=first.returncode, interrupted_by_owner=True)
        save(out / 'prepare_EXIT.json', first_record)
        second, second_record = launch('resume')
        second.wait(timeout=remaining(15))
        second_record['exit_code'] = second.returncode
        save(out / 'resume_EXIT.json', second_record)
        require(second.returncode == 0, 'RESUME_NONZERO_EXIT')
        report = read(out / 'RESUME_REPORT.json')
        after = {str(p.relative_to(out)): identity(p) for p in (out / 'state').rglob('*') if p.is_file()}
        require(before == after, 'PERSISTED_STATE_CHANGED_OR_REPLAYED')
        require(report['identity'] == seed['identity'] and report['consumption'] == seed['consumption'],
                'RECOVERY_IDENTITY_OR_CONSUMPTION_RESET')
        require(report['pid'] == second.pid and report['interrupted_pid'] == first.pid,
                'RESUME_PID_BINDING')
        for name, expected in frozen.items():
            require(identity(name) == expected, 'SOURCE_CHANGED_AFTER_RUN:' + name)
        remaining(1)
        save(out / 'AFTER_RECOVERY.json', {'state_files': after, 'report': report})
        result = {'schema': 'M3_RECOVERY_DRILL_RESULT_V1', 'status': 'PASS_LOCAL_SYNTHETIC',
                  'origin': 'LOCAL_SYNTHETIC', 'original_START': context['original_START'],
                  'goal': context['goal'], 'consumption_not_reset': True,
                  'dedup_receipts': 1, 'task_advances': 1, 'outbox_attempts': 1,
                  'same_state_bytes_before_after': True, 'processes': records,
                  'group_elapsed_s': time.monotonic() - began,
                  'real_Git_network_calls': 0, 'foreign_process_termination': 0,
                  'App_restart_verified': False, 'machine_restart_verified': False,
                  'remote_recheck': 'REQUIRED: coordinator network.py immediately after return',
                  'real_two_machine_recovery': 'PENDING', 'board_release_allowed': False}
        remaining(1)
        save(out / 'RESULT.json', result)
        return result
    except BaseException as error:
        save(out / 'FIRST_FAILURE.json', {'status': 'FAIL_LOCAL_SYNTHETIC', 'reason': repr(error),
                                          'processes': records, 'elapsed_s': time.monotonic() - began,
                                          'originals_retained': True})
        raise
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.kill()  # Direct owned Popen handle only; no PID lookup/tree kill.
                try:
                    proc.wait(timeout=max(0.1, min(2, end - time.monotonic())))
                except subprocess.TimeoutExpired:
                    save(out / ('CLEANUP_PENDING_' + str(proc.pid) + '.json'),
                         {'pid': proc.pid, 'owned_handle': True, 'status': 'CLEANUP_NOT_CONFIRMED'})
        for stream in handles:
            stream.close()
        final_processes = []
        for proc, record in zip(processes, records):
            final_processes.append({**record, 'actual_final_exit_code': proc.poll(),
                                    'termination_confirmed': proc.poll() is not None,
                                    'stdout': identity(out / (record['mode'] + '_stdout.raw')),
                                    'stderr': identity(out / (record['mode'] + '_stderr.raw'))})
        save(out / 'FINAL_PROCESS_RECEIPTS.json',
             {'processes': final_processes, 'elapsed_s_including_cleanup': time.monotonic() - began,
              'origin': 'LOCAL_SYNTHETIC', 'owned_handles_only': True})
