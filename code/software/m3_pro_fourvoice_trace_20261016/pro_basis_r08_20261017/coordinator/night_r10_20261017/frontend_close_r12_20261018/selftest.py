"""Root-admitted R12 file-only workers; implementation is not test evidence.

Only root may execute --worker with its independently frozen admission SHA.
make_capture_fixture performs metadata/file construction only. C uses the
actual pinned processing chain. Only W installs a private D4 boundary stub.
"""
import argparse
import ast
import builtins
import copy
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import hashlib
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import types
import traceback
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
OUTPUT = ROOT / 'code/output/m3_frontend_close_r12_20261018'


class JobAccounting(ctypes.Structure):
    _fields_ = [('user', ctypes.c_int64), ('kernel', ctypes.c_int64),
                ('period_user', ctypes.c_int64), ('period_kernel', ctypes.c_int64),
                ('faults', wintypes.DWORD), ('total', wintypes.DWORD),
                ('active', wintypes.DWORD), ('terminated', wintypes.DWORD)]


def job_accounting(job):
    assert ctypes.sizeof(JobAccounting) == 48 and JobAccounting.active.offset == 40
    query = job.kernel.QueryInformationJobObject
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    query.restype = wintypes.BOOL
    info, length = JobAccounting(), wintypes.DWORD()
    if not query(job.handle, 1, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(length)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'active': info.active, 'total': info.total, 'terminated': info.terminated,
            'returned_bytes': length.value, 'monotonic': time.monotonic()}


def peak_working_set(process):
    class MemoryCounters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak_working_set', 'working_set',
             'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
    api = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    api.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    api.restype = wintypes.BOOL
    data = MemoryCounters()
    data.cb = ctypes.sizeof(data)
    if not api(wintypes.HANDLE(int(process._handle)), ctypes.byref(data), data.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'metric': 'Windows PROCESS_MEMORY_COUNTERS.PeakWorkingSetSize (PeakWorkingSet64)',
            'bytes': int(data.peak_working_set), 'pointer_bits': ctypes.sizeof(ctypes.c_void_p) * 8}


def owned_call(argv, cwd, output, cap_seconds, *, natural_wait=None):
    """Same frozen Job owner; release root reference before proving Job0."""
    output = Path(output).resolve()
    assert output != OUTPUT and output.is_relative_to(OUTPUT)
    output.mkdir(parents=True, exist_ok=False)
    owner_path = ROOT / 'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
    raw = owner_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b'
    owner = types.ModuleType('_r12_unchanged_job_owner')
    exec(compile(raw, str(owner_path), 'exec', dont_inherit=True), owner.__dict__)
    started, job = time.monotonic(), owner.WindowsJob()
    deadline = started + cap_seconds
    record = {'argv': list(argv), 'cwd': str(cwd), 'cap_seconds': cap_seconds,
              'started_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': None,
              'job_handle_closed': False, 'root_process_handle_closed': False,
              'job_zero_observed_before_job_close': False, 'samples': []}
    def hard_stop():
        try:
            if job.handle:
                job.terminate()
        finally:
            os._exit(124)
    timer = threading.Timer(max(0.1, cap_seconds - 0.5), hard_stop)
    timer.daemon = True
    timer.start()
    process = None
    try:
        with (output / 'stdout.bin').open('xb') as out, (output / 'stderr.bin').open('xb') as err:
            process = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err,
                stdin=subprocess.DEVNULL, creationflags=0x00000004 | 0x08000000)
            record['pid'] = process.pid
            job.attach_and_resume(process)
            try:
                wait = min(natural_wait if natural_wait is not None else cap_seconds - 4,
                           max(0.1, deadline - time.monotonic() - 3))
                code = process.wait(timeout=wait)
                record['exit_class'] = 'NATURAL'
            except subprocess.TimeoutExpired:
                job.terminate()
                code = process.wait(timeout=1)
                record['exit_class'] = 'OWNED_TERMINATED_TIMEOUT'
            record['process_exit_code'] = code
            record['peak_working_set'] = peak_working_set(process)
            record['before_root_handle_close'] = job_accounting(job)
            # Windows counts an exited process while references remain held.
            process._handle.Close()
            record['root_process_handle_closed'] = True
            drain_deadline = min(deadline - 0.5, time.monotonic() + 2)
            while True:
                sample = job_accounting(job)
                record['samples'].append(sample)
                if sample['active'] == 0:
                    record['job_zero_observed_before_job_close'] = True
                    break
                if time.monotonic() >= drain_deadline:
                    raise RuntimeError('OWNED_JOB_NOT_ZERO_BY_ABSOLUTE_DEADLINE')
                time.sleep(0.025)
            record['exit_code'] = code if record['exit_class'] == 'NATURAL' else 124
    except BaseException as error:
        record['error'] = type(error).__name__ + ':' + str(error)
        record['exit_code'] = 125
        if job.handle:
            job.terminate()
        if process is not None and process.returncode is None:
            process.wait(timeout=1)
        if process is not None and not record['root_process_handle_closed']:
            process._handle.Close()
            record['root_process_handle_closed'] = True
    finally:
        job.close()
        record['job_handle_closed'] = job.handle is None
        record['elapsed_seconds'] = time.monotonic() - started
        record['ended_utc'] = datetime.now(timezone.utc).isoformat()
        record['within_cap'] = record['elapsed_seconds'] <= cap_seconds
        (output / 'RESULT.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
        timer.cancel()
    return record


def private_module(path, name, pins, imports=None):
    # Test-only fresh namespaces; no shared production object is patched.
    expected = pins[path.relative_to(ROOT).as_posix()]
    assert expected['bytes'] <= 4 * 1024 * 1024, 'TEST_SOURCE_SIZE_BOUND'
    blocks, count = [], 0
    with path.open('rb') as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            assert count <= expected['bytes'], 'FROZEN_TEST_SOURCE_CHANGED'
            blocks.append(block)
    raw = b''.join(blocks)
    assert len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'], 'FROZEN_TEST_SOURCE_CHANGED'
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    if imports:
        def local_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and name in imports:
                return imports[name]
            return builtins.__import__(name, globals, locals, fromlist, level)
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': local_import}
    exec(compile(raw, str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


class JSONFixture:
    """Independent DAG of actual files, with no manufactured historical run."""
    def __init__(self, root, case, pins):
        self.root = root
        self.pins = pins
        self.directory = root / case
        self.directory.mkdir(parents=True, exist_ok=False)
        self.ji = private_module(HERE / 'json_identity.py', '_r12_test_json_' + case, pins)
        self.binding = private_module(HERE / 'delivery_binding.py', '_r12_test_binding_' + case, pins,
                                      imports={'json_identity': self.ji})
        self.binding.ji = self.ji
        self.transport = private_module(HERE / 'delivery_transport.py', '_r12_test_transport_' + case, pins)
        self.transport.support = lambda: self.binding
        self.engine = private_module(HERE.parent / 'night_drill_r01/intake/engine.py', '_r12_test_store_' + case, pins)
        self.engine.OUTPUT = root
        self.transport.OUTPUT = self.directory / 'network'
        self.transport.STORE_ROOT = self.directory / 'store'
        self.transport.engine = lambda: self.engine
        self.refs = {}
        self.spec = self.build(case)

    def ref(self, path):
        return {'path': path.relative_to(ROOT).as_posix(), **self.ji.identity(path)}

    def document(self, name, value=None, raw=None):
        path = self.directory / name
        if raw is None:
            raw = (json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        path.write_bytes(raw)
        return self.ref(path)

    def build(self, case):
        sample = self.document('Q.json', {'schema': 'R12_SYNTHETIC_SOFTWARE_TEST', 'value': 'A'})
        archive = self.directory / 'PAYLOAD.zip'
        with zipfile.ZipFile(archive, 'x') as z:
            body = (ROOT / sample['path']).read_bytes()
            # J12 carries a valid ZIP(B) and separately pinned original A.
            # The controlled reread substitution below cannot change A's
            # already validated buffer into B.
            z.writestr('Q.json', body.replace(b'"A"', b'"B"') if case == 'J12' else body)
        archive_ref = self.ref(archive)
        identity = {'handoff_id': 'R12_J_' + case, 'task_id': 'R12_SOFTWARE_FIXTURE',
                    'plan_version': 'R12', 'producer': 'M2', 'consumer': 'M3',
                    'base_commit': '1' * 40, 'result_commit': '2' * 40}
        handoff = self.document('HANDOFF.json', {'schema': 'NIGHT_HANDOFF_V1', **identity,
                                               'manifest': [archive_ref]})
        sources = [self.ref(HERE / 'delivery_binding.py')]
        contract = self.document('CONTRACT.json', {'inputs': [handoff], 'source_frozen': sources})
        result = self.document('RESULT.json', {'sample_commit': identity['result_commit'],
            'checks': [{'receipt': 'sample', 'commit': identity['result_commit'], **archive_ref}]})
        provenance = self.document('PROVENANCE.json', {'schema': 'M3_R11_RESULT_PROVENANCE_V1',
            'run_contract': contract, 'delivery_identity': {k: v for k, v in identity.items() if k != 'result_commit'},
            'frozen_inputs': [handoff], 'frozen_sources': sources, 'input_handoff': handoff,
            'result_refs': [result]})
        self.refs = dict(sample=sample, archive=archive_ref, handoff=handoff, contract=contract,
                         result=result, provenance=provenance)
        return {'schema': 'M3_R11_FROZEN_DELIVERY_SPEC_V1', 'direction': 'RECEIVE',
            'purpose': 'NEW_RECEIVED_DELIVERY', 'handoff': handoff, 'expected_identity': identity,
            'expected_manifest': [archive_ref], 'run_contract': contract,
            'frozen_inputs': [handoff], 'frozen_sources': sources,
            'result_relations': [{'file': result, 'equalities': [], 'manifest_check': {
                'pointer': '/checks', 'filter_key': 'receipt', 'filter_value': 'sample'}}],
            'commit_binding': {'file': result, 'pointer': '/sample_commit'},
            'execution_provenance': provenance,
            'archive_bindings': [{'file': sample, 'archive': archive_ref, 'member': 'Q.json'}]}

    def spec_ref(self):
        return self.document('SPEC.json', self.spec)

    def receive(self):
        return self.transport.receive_frozen(self.spec_ref())

    def admission(self, spec_ref, bound):
        now = datetime.now(timezone.utc)
        empty = self.document('empty.bin', raw=b'')
        base = {'cwd': str(ROOT), 'utc': now.isoformat(), 'stdout': empty, 'stderr': empty}
        fetch = self.document('FETCH.json', {**base, 'kind': 'fetch', 'exit_code': 0,
            'within_30_seconds': True, 'argv': self.transport.GIT_PREFIX + ['fetch', 'origin']})
        ancestry = self.document('ANCESTRY.json', {**base, 'exit_code': 1, 'fetch_result': fetch,
            'argv': [self.transport.GIT_PREFIX[0], 'merge-base', '--is-ancestor',
                     bound['handoff']['result_commit'], 'origin/develop']})
        tree = self.document('TREE.json', {'commit': bound['handoff']['result_commit'],
            'manifest': bound['handoff']['manifest'], 'entries': [{**base, 'exit_code': 0,
                'payload': item, 'stdout': item, 'argv': [self.transport.GIT_PREFIX[0], 'show',
                bound['handoff']['result_commit'] + ':' + item['path']]}
                for item in bound['handoff']['manifest']]})
        git = Path(self.transport.GIT_PREFIX[0])
        return {'schema': 'M3_R11_EXACT_TRANSPORT_RUN_CONTRACT_V1', 'delivery_spec': spec_ref,
            'executor_thread': '01a14050-cd98-7c41-8004-5d3e25765167',
            'network_source': self.ref(HERE.parent / 'night_drill_r01/network.py'),
            'engine_source': self.ref(HERE.parent / 'night_drill_r01/intake/engine.py'),
            'git_executable': {'path': str(git), **self.ji.identity(git)},
            'argv': self.transport.target_argv(bound['handoff']['result_commit']), 'cwd': str(ROOT),
            'network_seconds': 30, 'max_attempts': 2,
            'valid_from': (now - timedelta(seconds=10)).isoformat(),
            'deadline': (now + timedelta(seconds=120)).isoformat(),
            'fresh_fetch_result': fetch, 'fresh_ancestry_result': ancestry,
            'commit_tree_verification': tree}


def expect_rejection(action, expected):
    try:
        action()
    except ValueError as error:
        allowed = (expected,) if isinstance(expected, str) else tuple(expected)
        if not any(token in str(error) for token in allowed):
            raise AssertionError('WRONG_REJECTION:' + str(error)) from error
        return {'expected_rejection': str(error)}
    raise AssertionError('UNEXPECTED_ACCEPTANCE')


def j_case(f, case):
    """Draft case bodies; no case has been executed or wired into admission."""
    if case == 'J01':
        result = f.receive()
        receipt = result['receipt']['receipt']
        assert result['receipt']['status'] == 'RECEIVED'
        assert receipt['advance_count'] == 0 and receipt['accepted'] is False
        assert not result['advance_performed'] and not result['remote_verified']
        return {'receipt': receipt}
    if case == 'J02':
        spec_ref = f.spec_ref()
        original = (ROOT / spec_ref['path']).read_bytes()
        changed = original.replace(b'NEW_RECEIVED_DELIVERY', b'NEW_RECEIVED_DELIVERX', 1)
        assert changed != original and len(changed) == len(original)
        old_read, substituted = f.ji.chunk_read, []
        def alternating(stream, size=f.ji.CHUNK):
            raw = old_read(stream, size)
            if str(getattr(stream, 'name', '')).casefold() == str(ROOT / spec_ref['path']).casefold() and raw:
                substituted.append(True)
                assert raw == original
                return changed
            return raw
        f.ji.chunk_read = alternating
        try:
            observed = expect_rejection(lambda: f.transport.receive_frozen(spec_ref), 'JSON_IDENTITY_MISMATCH')
            assert substituted and (ROOT / spec_ref['path']).read_bytes() == original
            return observed
        finally:
            f.ji.chunk_read = old_read
    if case == 'J03':
        ref = f.spec_ref()
        ref['sha256'] = '0' * 64
        return expect_rejection(lambda: f.transport.receive_frozen(ref),
                                ('FILE_CHANGED', 'JSON_IDENTITY_MISMATCH'))
    if case == 'J04':
        # The self-consistent trusted spec points at actual duplicate-key raw.
        old = ROOT / f.refs['handoff']['path']
        body = json.loads(old.read_text('utf-8'))
        raw = ('{"schema":"DUPLICATE",' + json.dumps(body)[1:]).encode('utf-8')
        replacement = f.document('HANDOFF_DUPLICATE.json', raw=raw)
        f.spec['handoff'] = replacement
        return expect_rejection(f.receive, 'DUPLICATE_JSON_KEY')
    if case == 'J05':
        f.spec['run_contract'] = {**f.spec['run_contract'], 'bytes': f.spec['run_contract']['bytes'] + 1}
        return expect_rejection(f.receive, 'JSON_IDENTITY_MISMATCH')
    if case == 'J06':
        raw = (ROOT / f.refs['provenance']['path']).read_bytes().rstrip()
        replacement = f.document('NONFINITE.json', raw=raw[:-1] + b',"nonfinite":NaN}')
        f.spec['execution_provenance'] = replacement
        return expect_rejection(f.receive, 'NONFINITE_JSON')
    if case == 'J07':
        f.spec['result_relations'][0]['file'] = {**f.refs['result'], 'sha256': '0' * 64}
        return expect_rejection(f.receive, 'JSON_IDENTITY_MISMATCH')
    if case in ('J08', 'J09', 'J10', 'J11'):
        spec_ref = f.spec_ref()
        bound = f.binding.verify(spec_ref)
        if case == 'J08':
            ref = f.document('OVERSIZE.json', raw=b' ' * (f.ji.MAX_JSON + 1))
            expected = 'JSON_BOUND'
        else:
            admission = f.admission(spec_ref, bound)
            field = {'J09': 'fresh_fetch_result', 'J10': 'fresh_ancestry_result',
                     'J11': 'commit_tree_verification'}[case]
            admission[field] = {**admission[field], 'sha256': '0' * 64}
            ref = f.document('ADMISSION.json', admission)
            expected = 'JSON_IDENTITY_MISMATCH'
        return expect_rejection(lambda: f.transport.check_admission(f.binding, ref, spec_ref, bound), expected)
    if case == 'J12':
        original = ref_path(f.refs['sample']).read_bytes()
        read_verified, substituted = f.ji.read_verified, []
        def substitute(ref, *args, **kwargs):
            record = read_verified(ref, *args, **kwargs)
            if ref == f.refs['sample']:
                ref_path(ref).write_bytes(original.replace(b'"A"', b'"B"'))
                substituted.append(True)
            return record
        f.ji.read_verified = substitute
        try:
            result = expect_rejection(f.receive, 'ARCHIVE_RESULT_SPLICE')
            assert substituted and not (f.transport.STORE_ROOT / 'STATE.json').exists()
            return {**result, 'original_read_substitution': 'A validated, path B, ZIP B rejected against buffer A'}
        finally:
            ref_path(f.refs['sample']).write_bytes(original)
            f.ji.read_verified = read_verified
    raise ValueError('UNIMPLEMENTED_CASE:' + case)


def run_j_draft(output, *, source_pins):
    """Future admitted controller must freeze and own this whole single group."""
    root = Path(output).resolve()
    assert root != OUTPUT and root.is_relative_to(OUTPUT)
    root.mkdir(parents=True, exist_ok=False)
    results = CaseResults(root / 'case_results')
    for number in range(1, 13):
        case = 'J' + str(number).zfill(2)
        fixture = JSONFixture(root, case, source_pins)
        result = j_case(fixture, case)
        results.append({'case': case, 'result': result})
    return results


class GitFixture(JSONFixture):
    def __init__(self, root, case, pins):
        super().__init__(root, case, pins)
        self.calls = []
        self.outcome = (0, 'OK', b'')
        upstream = self.refs['handoff']
        identity = {**self.spec['expected_identity'], 'handoff_id': 'R12_G_' + case,
                    'producer': 'M3', 'consumer': 'M2'}
        sources = self.spec['frozen_sources']
        contract = self.document('SEND_CONTRACT.json', {'inputs': [upstream], 'source_frozen': sources})
        result = self.document('SEND_RESULT.json', {'status': 'SYNTHETIC_SOFTWARE_RESULT'})
        provenance = self.document('SEND_PROVENANCE.json', {
            'schema': 'M3_R11_RESULT_PROVENANCE_V1', 'run_contract': contract,
            'delivery_identity': {k: v for k, v in identity.items() if k != 'result_commit'},
            'frozen_inputs': [upstream], 'frozen_sources': sources,
            'input_handoff': upstream, 'result_refs': [result]})
        archived = [contract, result, provenance, upstream]
        bundle = self.directory / 'SEND_PAYLOAD.zip'
        with zipfile.ZipFile(bundle, 'x') as z:
            for number, item in enumerate(archived):
                z.writestr(str(number) + '.json', (ROOT / item['path']).read_bytes())
        bundle_ref = self.ref(bundle)
        handoff = self.document('SEND_HANDOFF.json', {'schema': 'NIGHT_HANDOFF_V1', **identity,
                                                     'manifest': [bundle_ref]})
        commit_proof = self.document('POST_PUBLICATION_PROOF.json', {'commit': identity['result_commit']})
        baseline = (ROOT / 'code/docs/test' / HERE.parent.relative_to(ROOT / 'code/software') /
                    'night_drill_r01/morning_r11_20261018/LEGACY_NETWORK_BASELINE.json')
        baseline_ref = self.ref(baseline)
        assert baseline_ref['sha256'] == self.transport.LEGACY_BASELINE_SHA
        self.transport.OUTPUT.joinpath('state').mkdir(parents=True, exist_ok=False)
        (self.transport.OUTPUT / 'state/network.json').write_bytes(baseline.read_bytes())
        self.spec = {'schema': 'M3_R11_FROZEN_DELIVERY_SPEC_V1', 'direction': 'SEND',
            'purpose': 'NEW_UNPUBLISHED_DELIVERY', 'handoff': handoff,
            'expected_identity': identity, 'expected_manifest': [bundle_ref],
            'run_contract': contract, 'frozen_inputs': [upstream], 'frozen_sources': sources,
            'result_relations': [{'file': result, 'equalities': [
                {'pointer': '/status', 'equals': 'SYNTHETIC_SOFTWARE_RESULT'}]}],
            'commit_binding': {'file': commit_proof, 'pointer': '/commit'},
            'execution_provenance': provenance, 'legacy_network_snapshot': baseline_ref,
            'archive_bindings': [{'archive': bundle_ref, 'file': ref, 'member': str(i) + '.json'}
                                 for i, ref in enumerate(archived)]}
        self.sref = self.spec_ref()
        self.bound = self.binding.verify(self.sref)
        self.adoc = self.admission(self.sref, self.bound)
        self.aref = self.document('RUN_ADMISSION.json', self.adoc)
        original_load = self.transport.load
        fixture = self
        class FixedSoftwareNetwork:
            COMMANDS = {'push': []}
            def run(self, kind, op, retry_basis=None):
                assert kind == 'push' and op == fixture.transport.operation_id(fixture.bound['key'])
                store = fixture.engine.Store(fixture.transport.STORE_ROOT, owner='night_task_1')
                item = store._read()['outbox'][fixture.bound['key']]
                assert item['status'] == 'IN_FLIGHT'
                fixture.calls.append({'op': op, 'attempt': item['attempts']})
                run = fixture.transport.OUTPUT / 'runs' / (op + '_' + str(item['attempts']).zfill(2))
                run.mkdir(parents=True, exist_ok=False)
                code, status, error = fixture.outcome
                (run / 'stdout.bin').write_bytes(b'')
                (run / 'stderr.bin').write_bytes(error)
                actual_argv = fixture.transport.GIT_PREFIX + self.COMMANDS['push']
                assert actual_argv == fixture.adoc['argv'], 'WRONG_ACTUAL_NETWORK_REFSPEC'
                record = {'argv': actual_argv, 'cwd': str(ROOT), 'kind': 'push',
                          'status': status, 'exit_code': code, 'elapsed_seconds': 0.001,
                          'synthetic_fixed_callback': True}
                (run / 'RESULT.json').write_text(json.dumps(record) + '\n', encoding='utf-8')
                state_path = fixture.transport.OUTPUT / 'state/network.json'
                state = json.loads(state_path.read_text('utf-8'))
                state.setdefault(op, []).append(record)
                state_path.write_text(json.dumps(state) + '\n', encoding='utf-8')
                return code
        def load(path, sha, name):
            if Path(path) == self.transport.LEGACY / 'network.py':
                assert sha == self.transport.NETWORK_SHA
                return FixedSoftwareNetwork()
            return original_load(path, sha, name)
        self.transport.load = load

    def send(self, retry=None):
        return self.transport.send_once(self.sref, self.aref, retry_basis=retry)

    def alter_precheck(self, field, change):
        ref = self.adoc[field]
        document = json.loads((ROOT / ref['path']).read_text('utf-8'))
        change(document)
        new_ref = self.document(Path(ref['path']).name, document)
        self.adoc[field] = new_ref
        if field == 'fresh_fetch_result':
            old = self.adoc['fresh_ancestry_result']
            ancestry = json.loads((ROOT / old['path']).read_text('utf-8'))
            ancestry['fetch_result'] = new_ref
            self.adoc['fresh_ancestry_result'] = self.document('ANCESTRY.json', ancestry)
        self.aref = self.document('RUN_ADMISSION.json', self.adoc)


def g_case(f, case):
    if case == 'G01':
        result = f.send()
        assert len(f.calls) == 1 and result['outbox']['status'] == 'AWAITING_REMOTE_VERIFICATION'
        assert not result['remote_verified'] and not result['receiver_accepted']
        return result
    if case in ('G02', 'G03', 'G04'):
        field = {'G02': 'fresh_fetch_result', 'G03': 'fresh_ancestry_result',
                 'G04': 'commit_tree_verification'}[case]
        def change(row):
            if case == 'G04':
                row['entries'][0]['cwd'] = str(f.directory)
            else:
                row['cwd'] = str(f.directory)
        f.alter_precheck(field, change)
        expected = {'G02': 'FETCH_CWD_IDENTITY', 'G03': 'ANCESTRY_CWD_IDENTITY', 'G04': 'SHOW_CWD_IDENTITY'}[case]
        result = expect_rejection(f.send, expected)
        assert f.calls == []
        assert f.engine.Store(f.transport.STORE_ROOT)._read()['outbox'][f.bound['key']]['attempts'] == 0
        return result
    if case in ('G05', 'G06', 'G07', 'G08'):
        role = 'stdout' if case in ('G05', 'G06') else 'stderr'
        missing = case in ('G05', 'G07')
        def change(row):
            row[role] = {**row[role], **({'path': f.directory.relative_to(ROOT).as_posix() + '/missing.bin'}
                                       if missing else {'sha256': '0' * 64})}
        f.alter_precheck('fresh_fetch_result', change)
        result = expect_rejection(f.send, 'DESCRIPTOR_SCOPE' if missing else 'FILE_CHANGED')
        assert f.calls == []
        return result
    if case == 'G09':
        first = f.send()
        store = f.engine.Store(f.transport.STORE_ROOT)
        persisted = store._read()['outbox'][f.bound['key']]
        # Recreate the real Store from its durable files, never reconstruct counts.
        reloaded = private_module(HERE.parent / 'night_drill_r01/intake/engine.py',
                                  '_r12_G09_reloaded_store', f.pins)
        reloaded.OUTPUT = f.root
        another = reloaded.Store(f.transport.STORE_ROOT)._read()['outbox'][f.bound['key']]
        assert persisted == another and persisted['attempts'] == 1
        assert first['outbox']['key'] == f.bound['key']
        assert f.calls == [{'op': f.transport.operation_id(f.bound['key']), 'attempt': 1}]
        return {'key': f.bound['key'], 'attempts': another['attempts']}
    if case in ('G10', 'G11'):
        f.outcome = (124, 'TIMEOUT', b'') if case == 'G10' else (1, 'FAILED', b'permission denied')
        first = f.send()
        expected_state = 'UNKNOWN' if case == 'G10' else 'STOPPED_DENIED'
        assert first['outbox']['status'] == expected_state
        basis = f.document('RETRY_BASIS.json', {'outbox_key': f.bound['key'], 'prior_attempt': 1,
                                              'run_contract': f.aref})
        result = expect_rejection(lambda: f.send(basis), 'UNKNOWN_REQUIRES_REMOTE_CHECK' if case == 'G10' else 'SEND_NOT_READY')
        assert len(f.calls) == 1
        if case == 'G11':
            scenarios = [result]
            for state, message in (('STOPPED_REJECTED', b'remote rejected'),
                                   ('STOPPED_NON_FAST_FORWARD', b'non-fast-forward')):
                short_name = {'STOPPED_REJECTED': 'G11R', 'STOPPED_NON_FAST_FORWARD': 'G11N'}[state]
                extra = GitFixture(f.root, short_name, f.pins)
                extra.outcome = (1, 'FAILED', message)
                observed = extra.send()
                assert observed['outbox']['status'] == state
                ref = extra.document('RETRY_BASIS.json', {'outbox_key': extra.bound['key'],
                    'prior_attempt': 1, 'run_contract': extra.aref})
                scenarios.append(expect_rejection(lambda: extra.send(ref), 'SEND_NOT_READY'))
                assert len(extra.calls) == 1
            return {'required_denied_categories': scenarios}
        return result
    raise ValueError('UNIMPLEMENTED_CASE:' + case)


def run_g_draft(output, *, source_pins):
    """Draft real-Store/fixed-software-callback group; not admitted or run."""
    root = Path(output).resolve()
    assert root != OUTPUT and root.is_relative_to(OUTPUT)
    root.mkdir(parents=True, exist_ok=False)
    results = CaseResults(root / 'case_results')
    for number in range(1, 12):
        case = 'G' + str(number).zfill(2)
        fixture = GitFixture(root, case, source_pins)
        results.append({'case': case, 'result': g_case(fixture, case)})
    fixture = JSONFixture(root, 'G12', source_pins)
    first, second = fixture.receive(), fixture.receive()
    assert first['receipt']['status'] == 'RECEIVED' and second['receipt']['status'] == 'DUPLICATE'
    assert second['receipt']['receipt']['advance_count'] == 0
    results.append({'case': 'G12', 'receipt': second['receipt']})
    return results


CHUNK = 1024 * 1024
LARGE_BYTES = 1_398_627_657
PART_BYTES = 64 * 1024 * 1024
GROUP_CAPS = {'P0': 60, 'J': 60, 'G': 60, 'C': 120, 'W': 240, 'R': 240}
FALSE_FLAGS = ('execution_allowed', 'real_verified', 'math_verified', 'board_release_allowed')
OLD_CASE = ROOT / 'code/output/m3_c9_complete_d4_20261017/R03/cases/009'


def strict_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def strict_parse(raw):
    def finite(number):
        import math
        value = float(number)
        if not math.isfinite(value):
            raise ValueError('NONFINITE_JSON')
        return value
    return json.loads(raw, object_pairs_hook=strict_pairs, parse_float=finite,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def read_small(path, limit=8 * CHUNK):
    with Path(path).open('rb') as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError('JSON_BOUND')
    return body


def stamp(path):
    path = Path(path).resolve()
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while block := stream.read(CHUNK):
            digest.update(block)
            count += len(block)
    return {'path': path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            'bytes': count, 'sha256': digest.hexdigest()}


def ref_path(ref):
    value = Path(ref['path'])
    return value if value.is_absolute() else ROOT / value


def verified_document(ref):
    raw = read_small(ref_path(ref))
    assert len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'], 'FROZEN_FIXTURE_CHANGED'
    return strict_parse(raw)


def save_json(path, value, *, exclusive=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
    with path.open('xb' if exclusive else 'wb') as stream:
        stream.write(raw)
    return stamp(path)


class CaseResults(list):
    """Completed cases survive the group's first failure without reruns."""
    def __init__(self, output):
        super().__init__()
        self.output = Path(output)

    def append(self, item):
        save_json(self.output / ('CASE_' + item['case'] + '.json'), item)
        super().append(item)


def copy_file(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Path(source).open('rb') as incoming, target.open('xb') as outgoing:
        while block := incoming.read(CHUNK):
            outgoing.write(block)
    return stamp(target)


def make_capture_fixture(output):
    """Construct only files: no candidate load, AST, subprocess or tool call.

    New ZIP identity is explicit. Frozen 75-source/9-ROM/base provenance bodies
    remain byte-identical; only the four stimulus members are replaced.
    EXPECTED is inherited from archived outputs before any new processing.
    """
    output = Path(output).resolve()
    assert output != OUTPUT and output.is_relative_to(OUTPUT), 'FIXTURE_OUTPUT_SCOPE'
    output.mkdir(parents=True, exist_ok=False)
    application = strict_parse(read_small(OLD_CASE / 'chain/a/INPUT.json'))
    old_request = strict_parse(read_small(OLD_CASE / 'INPUT_REQUEST.json'))
    original_window = strict_parse(read_small(OLD_CASE / 'WINDOW.json'))
    old_result = strict_parse(read_small(OLD_CASE / 'RESULT.json'))['report']
    files = []
    stimulus = output / 'stimulus'
    stimulus.mkdir()
    bodies = {'bytes.drv': b'', 'reset.drv': b'0 1\n', 'ready.drv': b'0 1\n'}
    plan = strict_parse(read_small(OLD_CASE / 'MIDI_PLAN.json'))
    plan['total_cycles'] = 5
    plan_ref = save_json(stimulus / 'plan.json', plan)
    bodies['plan.json'] = (stimulus / 'plan.json').read_bytes()
    refs = {'plan.json': plan_ref}
    for name in ('bytes.drv', 'reset.drv', 'ready.drv'):
        (stimulus / name).write_bytes(bodies[name])
        refs[name] = stamp(stimulus / name)
    files.extend(refs.values())
    source_zip = ref_path(application['source']['application'])
    assert stamp(source_zip)['sha256'] == application['source']['application']['sha256'], 'OLD_APPLICATION_CHANGED'
    new_zip = output / 'SOURCE_APPLICATION_SYNTHETIC_C01.zip'
    unchanged, changed = [], []
    rom_copies = []
    graph = strict_parse(read_small(OLD_CASE / 'chain/a/DEPENDENCY_GRAPH.json'))
    rom_names = {item['path']: item for item in graph['ROM_payloads']}
    with zipfile.ZipFile(source_zip) as original, zipfile.ZipFile(new_zip, 'x', compression=zipfile.ZIP_DEFLATED) as successor:
        for member in original.infolist():
            assert member.file_size <= 16 * CHUNK, 'FIXTURE_ARCHIVE_MEMBER_BOUND'
            body = original.read(member)
            name = member.filename
            if name in {'inputs/' + item for item in bodies}:
                body = bodies[name[7:]]
                changed.append(name)
            else:
                unchanged.append({'member': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
            successor.writestr(member, body)
            if name.startswith('inputs/') and name[7:] in rom_names:
                rel = name[7:]
                expected = rom_names[rel]
                assert len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256']
                target = output / 'rom_originals' / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
                rom_copies.append(stamp(target))
    assert set(changed) == {'inputs/' + item for item in bodies} and len(rom_copies) == 9
    zip_ref = stamp(new_zip)
    files.extend([zip_ref, *rom_copies])
    parameters = {'CAPTURE_ID': original_window['capture_id'], 'PLAN_STOP_ID': original_window['plan_stop_id'],
        'STOP_DRIVER_CYCLE': 5, 'EXPECTED_FINISH_CORE_CYCLE': 6,
        'MAX_CORE_SAMPLES': 16, 'MAX_SIM_TIME_PS': 1_000_000}
    window = {**original_window, 'input_plan_sha256': plan_ref['sha256'], 'window_parameters': parameters}
    window_ref = save_json(output / 'WINDOW.json', window)
    files.append(window_ref)
    application['source']['application'] = zip_ref
    application['source']['stimulus_inputs'] = refs
    application['window_reference'] = window_ref
    application['execution_spec']['window_parameters'] = parameters
    order = ('CAPTURE_ID', 'PLAN_STOP_ID', 'STOP_DRIVER_CYCLE', 'EXPECTED_FINISH_CORE_CYCLE', 'MAX_CORE_SAMPLES', 'MAX_SIM_TIME_PS')
    step = next(item for item in application['execution_spec']['steps'] if item['tool'] == 'vsim')
    step['argv'] = [step['argv'][0], '-c'] + ['-g' + key + '=' + str(parameters[key]) for key in order] + [
        'work.tb_r7a_c9_public_capture', '-do', 'run -all; quit -f']
    application['proposed_plan'] = {'schema': 'M3_C9_BOUND_APPLICATION_PLAN_V1',
        'source': copy.deepcopy(application['source']), 'tools': copy.deepcopy(application['tools']),
        'external_inputs': copy.deepcopy(application['external_inputs']), 'window_reference': window_ref,
        'execution': copy.deepcopy(application['execution_spec']), 'permission': 'NOT_GRANTED', 'process_route': 'ABSENT'}
    app_ref = save_json(output / 'APPLICATION_REQUEST.json', application)
    files.append(app_ref)
    inputs = {}
    for role, source in (('raw', OLD_CASE / 'RAW.jsonl'), ('resets', ref_path(old_request['inputs']['resets'])),
                         ('end', OLD_CASE / 'END.json'), ('stdout', OLD_CASE / 'CAPTURE_STDOUT.txt'),
                         ('frame_input', OLD_CASE / 'FRAME_INPUT.json')):
        inputs[role] = copy_file(source, output / ('ORIGINAL_' + role + source.suffix))
        files.append(inputs[role])
    empty = output / 'CAPTURE_STDERR_SYNTHETIC_EMPTY.bin'
    empty.write_bytes(b'')
    inputs.update(stderr=stamp(empty), application_request=app_ref,
                  frame_rules=old_request['inputs']['frame_rules'], window_plan=window_ref, midi_plan=plan_ref)
    files.append(inputs['stderr'])
    source = application['source']
    source_members = [source['base'], source['decision'], source['application'], *source['capture_sources'].values()]
    source_ref = save_json(output / 'SOURCE_CLOSURE.json', {'schema': 'M3_R7D_FILE_CLOSURE_V1', 'files': source_members})
    rom_ref = save_json(output / 'ROM_CLOSURE.json', {'schema': 'M3_R7D_FILE_CLOSURE_V1', 'files': [zip_ref, *rom_copies]})
    native = {}
    for tool in application['tools'].values():
        for item in [tool['tool'], *tool.get('dependencies', [])]:
            descriptor = item['file']
            key = str(ref_path(descriptor).resolve()).casefold()
            assert key not in native or native[key] == descriptor
            native[key] = descriptor
    tool_ref = save_json(output / 'TOOL_CLOSURE.json', {'schema': 'M3_R7D_FILE_CLOSURE_V1',
        'files': list(native.values()), 'argv': step['argv'], 'cwd': application['execution_spec']['cwd'],
        'version': 'SYNTHETIC_DECLARATION_ONLY_NOT_EXECUTED; application-frozen native identities'})
    inputs.update(source_manifest=source_ref, rom_manifest=rom_ref, tool_manifest=tool_ref)
    files.extend([source_ref, rom_ref, tool_ref])
    binding_file = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/intake_20261018/CAPTURE_MODULE_BINDINGS.json'
    request = {key: copy.deepcopy(value) for key, value in old_request.items() if key != 'synthetic_application_example'}
    request.update(inputs=inputs, module_bindings=stamp(binding_file), origin='SYNTHETIC_SCHEMA_FIXTURE')
    descriptors = declared_roles(request, application)
    instant = datetime.now(timezone.utc).isoformat()
    receipt = {'schema': 'M3_R7D_DECLARED_EXECUTION_V1', 'capture_id': request['capture_id'],
        'argv': step['argv'], 'cwd': application['execution_spec']['cwd'],
        'bindings': {key: value['sha256'] for key, value in descriptors.items()},
        'exit_code': 0, 'timeout': False, 'cleanup_complete': True,
        'consumption': {'pid': os.getpid(), 'group_id': 'R12_SYNTHETIC_FIXTURE_NOT_NATIVE',
                        'started_utc': instant, 'ended_utc': instant}}
    receipt_ref = save_json(output / 'DECLARED_SYNTHETIC_RECEIPT.json', receipt)
    request['math_inputs'] = {'execution_receipt': receipt_ref}
    request_ref = save_json(output / 'CAPTURE_REQUEST.json', request)
    envelope_ref = save_json(output / 'ENVELOPE.json', {'schema': 'N10_M3_UNIFIED_PIPELINE_REQUEST_V1',
                                                     'mode': 'PROCESS_CAPTURE', 'request': request_ref})
    files.extend([receipt_ref, request_ref, envelope_ref])
    origin_ref = save_json(output / 'FIXTURE_ORIGIN.json', {'schema': 'M3_R12_C01_SYNTHETIC_INHERITANCE_V1',
        'origin': 'SYNTHETIC_SCHEMA_FIXTURE', 'native_tool_calls': 0,
        'receipt_semantics': {'argv': 'PROPOSED_NOT_EXECUTED', 'pid_and_times': 'ACTUAL_FIXTURE_BUILDER_NOT_NATIVE',
                             'exit_fields': 'STRUCTURAL_FIXTURE_VALUES_NOT_VSIM_OBSERVATIONS'},
        'original_application': application['source']['base'], 'original_zip': stamp(source_zip),
        'new_application_zip': zip_ref, 'replaced_members': sorted(changed), 'unchanged_members': unchanged,
        'RAW_FRAME_END_preserved': True, 'actual_driver_reset_phase_or_DUT_behavior_verified': False,
        'real_verified': False, 'math_verified': False, 'board_release_allowed': False})
    files.append(origin_ref)
    old_frame = strict_parse(read_small(OLD_CASE / 'chain/frame_plan/UNIQUE_FRAME_PLAN.json'))
    expected_ref = save_json(output / 'EXPECTED.json', {'schema': 'M3_R12_C01_INDEPENDENT_EXPECTED_V1',
        'origin': 'ARCHIVED_FROZEN_SYNTHETIC_EXPECTATIONS_NOT_NEW_BACKEND_OUTPUT',
        'archived_result': stamp(OLD_CASE / 'RESULT.json'), 'fixture_origin': origin_ref,
        'public_rows_sha256': old_result['artifacts']['public_rows']['sha256'],
        'csv_sha256': old_result['artifacts']['public_csv']['sha256'],
        'row_count': 7, 'finish_cycle': 6, 'finish_time_ps': 175000,
        'frame_plan_sha256': stamp(OLD_CASE / 'chain/frame_plan/UNIQUE_FRAME_PLAN.json')['sha256'],
        'canonical_plan_id': old_frame['canonical_plan_id'], 'expected_frames': [],
        'source_units': 75, 'roms': 9, 'calendar': old_result['summary']['calendar'],
        'serial': old_result['summary']['serial'], 'provenance': old_result['summary']['provenance'],
        'new_structure_only': ['synthetic declared receipt and exact closures', 'new application/stimulus/window identities'],
        'native_verified': False, 'real_verified': False, 'math_verified': False, 'board_release_allowed': False})
    files.append(expected_ref)
    fixture = {'schema': 'M3_R12_CAPTURE_FIXTURE_FILES_V1', 'envelope_ref': envelope_ref,
        'expected_ref': expected_ref, 'origin_ref': origin_ref, 'file_refs': files,
        'synthetic': True, 'native_tool_calls': 0}
    fixture_ref = save_json(output / 'FIXTURE.json', fixture)
    return {**fixture, 'fixture_ref': fixture_ref}


def declared_roles(request, application):
    inputs = request['inputs']
    result = {key: inputs[key] for key in ('source_manifest', 'rom_manifest', 'tool_manifest')}
    for name, role in (('input_plan', 'midi_plan'), ('window_plan', 'window_plan'), ('raw_stdout', 'stdout'),
                       ('raw_stderr', 'stderr'), ('raw_trace', 'raw'), ('reset_edges', 'resets'), ('finish_receipt', 'end')):
        result[name] = inputs[role]
    result['driver'] = application['source']['capture_sources']['DRIVER']
    result['observer'] = application['source']['capture_sources']['OBSERVER']
    return result


class CaptureHarness:
    def __init__(self, pins, dependency_ref, *, backend=False, probe=False, consumer_error=False):
        self.pins, self.dependencies = pins, dependency_ref
        suffix = str(os.getpid()) + '_' + str(time.monotonic_ns())
        self.ji = private_module(HERE / 'json_identity.py', '_r12_C_json_' + suffix, pins)
        self.ci = private_module(HERE / 'capture_identity.py', '_r12_C_identity_' + suffix, pins,
                                 {'json_identity': self.ji})
        self.link = private_module(HERE / 'capture_link_successor.py', '_r12_C_link_' + suffix, pins,
                                   {'json_identity': self.ji, 'capture_identity': self.ci})
        self.entry = private_module(HERE / 'capture_entry.py', '_r12_C_entry_' + suffix, pins,
            {'json_identity': self.ji, 'capture_link_successor': self.link})
        self.contexts, self.backend_calls = [], []
        harness = self
        original_context = self.link.DependencyContext
        class ObservedContext(original_context):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.test_closed = False
                harness.contexts.append(self)
            def load(self, path, *args, **kwargs):
                module = super().load(path, *args, **kwargs)
                if backend and Path(path).resolve() == self.link_d4():
                    def fixed(request, out):
                        harness.backend_calls.append({'raw': request['inputs']['raw'], 'stderr': request['inputs']['stderr']})
                        Path(out).mkdir(parents=True, exist_ok=False)
                        return {'status': 'R12_FIXED_SOFTWARE_BACKEND_FRONTEND_ONLY',
                                'artifacts': {}, **{key: False for key in FALSE_FLAGS}}
                    module.process = fixed
                elif consumer_error and Path(path).name == 'c9_stream.py':
                    def fail(*args, **kwargs):
                        raise OSError('R12_INJECTED_CONSUMER_FAILURE')
                    module.convert_files = fail
                return module
            @staticmethod
            def link_d4():
                return (HERE.parent.parent / 'task_day4_completion_20261017/chain.py').resolve()
            def close(self):
                try:
                    super().close()
                finally:
                    self.test_closed = True
        self.entry.DependencyContext = ObservedContext
        self.probe = probe

    def process(self, envelope, output):
        before = dict(self.ji.READ_METRICS)
        try:
            return self.entry.process(envelope, output, dependency_ref=self.dependencies)
        finally:
            self.metrics = {key: self.ji.READ_METRICS[key] - before.get(key, 0)
                            for key in self.ji.READ_METRICS if key != 'max_request'}
            self.metrics['max_request'] = self.ji.READ_METRICS.get('max_request', 0)
            assert self.metrics['max_request'] <= CHUNK
            for context in self.contexts:
                assert context.test_closed, 'CONTEXT_NOT_CLOSED'
                assert not any(name in sys.modules for name in getattr(context, 'owned_names', [])), 'PRIVATE_MODULE_LEAK'
                assert not getattr(context, 'private_modules', {}), 'PRIVATE_REGISTRATION_LEAK'
                assert not context.modules and not context.facades, 'PRIVATE_CACHE_NOT_CLOSED'
                assert all(not Path(path).exists() for path in context.snapshots.values()), 'PRIVATE_ARCHIVE_LEAK'


def capture_variant(fixture, output, *, change=None, stale_role=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    envelope = verified_document(fixture['envelope_ref'])
    request = verified_document(envelope['request'])
    application = verified_document(request['inputs']['application_request'])
    receipt = verified_document(request['math_inputs']['execution_receipt'])
    if change:
        change(request)
    receipt['bindings'] = {key: item['sha256'] for key, item in declared_roles(request, application).items()}
    request['math_inputs']['execution_receipt'] = save_json(output / 'RECEIPT.json', receipt)
    envelope['request'] = save_json(output / 'REQUEST.json', request)
    return envelope


def assert_capture_expected(result, expected, harness):
    assert all(result[key] is False for key in FALSE_FLAGS)
    assert result['summary']['rows'] == expected['row_count']
    for role, value in (('calendar', expected['calendar']), ('serial', expected['serial']), ('provenance', expected['provenance'])):
        assert result['summary'][role] == value, ('UNEXPECTED_CAPTURE_SUMMARY', role, result['summary'][role])
    assert result['artifacts']['public_rows']['sha256'] == expected['public_rows_sha256'], 'ARCHIVED_PUBLIC_ROWS_DIFFER'
    assert result['artifacts']['public_csv']['sha256'] == expected['csv_sha256'], 'ARCHIVED_CSV_DIFFER'
    assert result['artifacts']['frame_plan']['sha256'] == expected['frame_plan_sha256'], 'ARCHIVED_FRAME_PLAN_DIFFER'
    graph = verified_document(result['artifacts']['application_dependency_graph'])
    assert len(graph['units']) == expected['source_units'] and len(graph['ROM_payloads']) == expected['roms']
    assert harness.backend_calls == [], 'C01_BACKEND_STUB_FORBIDDEN'
    assert result['tool_execution_authenticity'] == 'UNKNOWN'
    return {'rows': result['summary']['rows'], 'public_rows': result['artifacts']['public_rows'],
            'frame_plan': result['artifacts']['frame_plan'], 'summary': result['summary']}


def assert_io_policy(harness, role_ref):
    """Probe the actual invocation policy object, never pathlib/global helpers."""
    assert harness.contexts and hasattr(harness.contexts[0], 'io'), 'ARTIFACT_IO_NOT_CONNECTED'
    policy = harness.contexts[0].io
    path = policy.path(ref_path(role_ref))
    expect_rejection(lambda: path.read_bytes(), 'WHOLE_STREAM_READ_FORBIDDEN')
    with path.open('rb') as stream:
        expect_rejection(lambda: stream.read(), 'WHOLE_STREAM_READ_FORBIDDEN')
        bounded = stream.read(CHUNK + 1)
        assert len(bounded) <= CHUNK + 1 and policy.metrics['max_request'] <= CHUNK
        expect_rejection(lambda: stream.read(harness.ci.MAX_LOGICAL_READ + 1), 'READ_REQUEST_BOUND')
        expect_rejection(lambda: policy.pull(stream.source, CHUNK + 1), 'READ_REQUEST_BOUND')
    assert policy.metrics['max_request'] <= CHUNK
    assert policy.metrics['whole_read_rejected'] >= 2
    return {'policy_metrics': dict(policy.metrics), 'ji_metrics': harness.metrics,
            'forbidden_probe': 'actual per-invocation role policy, no global monkeypatch'}


def run_c(output, admission, pins):
    fixture = get_fixture(admission)
    expected = verified_document(fixture['expected_ref'])
    root = Path(output)
    results = CaseResults(root / 'case_results')
    def actual(case, envelope, *, probe=False, consumer_error=False):
        h = CaptureHarness(pins, admission['dependencies_ref'], probe=probe, consumer_error=consumer_error)
        value = h.process(envelope, root / (case + '_actual'))
        return value, h
    envelope = verified_document(fixture['envelope_ref'])
    result, original = actual('C01', envelope)
    results.append({'case': 'C01', 'result': assert_capture_expected(result, expected, original)})
    required = {'assembler.py', 'c9_stream.py', 'c9_codec.py', 'intake_adapter.py',
                'frame_plan_generator_candidate.py', 'provenance.py', 'math_bundle.py'}
    observed = {Path(item['source']['path']).name for context in original.contexts for item in context.trace if 'source' in item}
    assert required <= observed, ('INCOMPLETE_ACTUAL_CALL_CHAIN', sorted(required - observed))
    results.append({'case': 'C02', 'loaded_frozen_sources': sorted(observed), 'contexts_closed': True})
    req = verified_document(envelope['request'])
    for case in ('C03', 'C04'):
        positive, exercised = actual(case, envelope, probe=True)
        assert_capture_expected(positive, expected, exercised)
        observation = assert_io_policy(exercised, req['inputs']['raw'])
        results.append({'case': case, **observation})
    for case, role, operation in (('C05', 'raw', 'mutate'), ('C06', 'stdout', 'truncate'), ('C07', 'stderr', 'sha')):
        def change(document, role=role, operation=operation, case=case):
            old = document['inputs'][role]
            if operation == 'sha':
                document['inputs'][role] = {**old, 'sha256': '0' * 64}
                return
            target = root / (case + '_bad' + Path(old['path']).suffix)
            body = ref_path(old).read_bytes()
            if operation == 'truncate':
                body = body[:-1]
            else:
                body = body[:-2] + bytes([body[-2] ^ 1]) + body[-1:]
            target.write_bytes(body)
            document['inputs'][role] = {**old, 'path': target.relative_to(ROOT).as_posix()}
        variant = capture_variant(fixture, root / (case + '_input'), change=change)
        h = CaptureHarness(pins, admission['dependencies_ref'])
        rejected = expect_rejection(lambda: h.process(variant, root / (case + '_actual')),
                                    ('FILE_CHANGED', 'STREAM_IDENTITY_MISMATCH', 'STREAM_SIZE_CHANGED'))
        results.append({'case': case, **rejected, 'closed': True})
    def source_mismatch(document):
        document['module_bindings'] = {**document['module_bindings'], 'sha256': '0' * 64}
    variant = capture_variant(fixture, root / 'C08_input', change=source_mismatch)
    h = CaptureHarness(pins, admission['dependencies_ref'])
    results.append({'case': 'C08', **expect_rejection(lambda: h.process(variant, root / 'C08_actual'),
                    ('FILE_CHANGED', 'STREAM_IDENTITY_MISMATCH', 'CAPTURE_LINK_BINDING'))})
    def wrong_end(document):
        end = verified_document(document['inputs']['end'])
        end['row_count'] += 1
        document['inputs']['end'] = save_json(root / 'C09_END.json', end)
    variant = capture_variant(fixture, root / 'C09_input', change=wrong_end)
    h = CaptureHarness(pins, admission['dependencies_ref'])
    results.append({'case': 'C09', **expect_rejection(lambda: h.process(variant, root / 'C09_actual'), 'END')})
    # Private fragmentation forces each raw JSON line across physical chunks.
    # All algorithms remain real, and the full archived expectation is fixed.
    fragmented = CaptureHarness(pins, admission['dependencies_ref'])
    original_chunk_read = fragmented.ji.chunk_read
    fragmented.ji.chunk_read = lambda stream, size=CHUNK: original_chunk_read(stream, min(size, 257))
    fragmented_result = fragmented.process(envelope, root / 'C10_actual')
    assert_capture_expected(fragmented_result, expected, fragmented)
    rows = []
    with ref_path(fragmented_result['artifacts']['public_rows']).open('rb') as stream:
        for line in stream:
            rows.append(strict_parse(line))
    assert [row['source']['cycle'] for row in rows] == list(range(7))
    assert [row['source']['line'] for row in rows] == list(range(1, 8))
    assert sum(row['fields']['finish'] for row in rows) == 1
    assert fragmented.metrics['max_request'] <= 257
    results.append({'case': 'C10', 'whole_ordered_window_rows': len(rows),
                    'physical_chunk_probe': 257, 'frozen_full_row_SHA_matched': True})
    def duplicate_json(document):
        path = root / 'C11_DUPLICATE_WINDOW.json'
        raw = ref_path(document['inputs']['window_plan']).read_bytes()
        body = b'{"schema":"BAD",' + raw.lstrip()[1:]
        path.write_bytes(body)
        document['inputs']['window_plan'] = stamp(path)
    variant = capture_variant(fixture, root / 'C11_input', change=duplicate_json)
    h = CaptureHarness(pins, admission['dependencies_ref'])
    results.append({'case': 'C11', **expect_rejection(lambda: h.process(variant, root / 'C11_actual'), 'DUPLICATE_JSON_KEY')})
    h = CaptureHarness(pins, admission['dependencies_ref'], consumer_error=True)
    try:
        h.process(envelope, root / 'C12_actual')
    except OSError as error:
        assert 'R12_INJECTED_CONSUMER_FAILURE' in str(error)
        assert all(ctx.test_closed for ctx in h.contexts)
        results.append({'case': 'C12', 'injected_error_propagated': str(error), 'contexts_closed': True,
                        'owned_worker_job_cleanup': 'Parent must verify owned_call Job0 before acceptance'})
    else:
        raise AssertionError('C12_ERROR_NOT_PROPAGATED')
    return results


def get_fixture(admission):
    config = admission['fixture']
    if 'capture' in config:
        config = config['capture']
    if 'fixture_ref' in config:
        fixture = verified_document(config['fixture_ref'])
    elif set(config) == {'path', 'bytes', 'sha256'}:
        fixture = verified_document(config)
    else:
        fixture = config
    assert fixture['schema'] == 'M3_R12_CAPTURE_FIXTURE_FILES_V1' and fixture['synthetic'] is True
    return fixture


def write_large(path):
    digest, count, index = hashlib.sha256(), 0, 0
    seed = b'R12_SYNTHETIC_FRONTEND_ONLY_NOT_NATIVE\n'
    block = (seed * (CHUNK // len(seed) + 1))[:CHUNK]
    with Path(path).open('xb') as stream:
        while count < LARGE_BYTES:
            header = ('R12_BLOCK_%016x\n' % index).encode('ascii')
            body = (header + block[len(header):])[:min(CHUNK, LARGE_BYTES - count)]
            stream.write(body)
            digest.update(body)
            count += len(body)
            index += 1
        stream.flush()
        os.fsync(stream.fileno())
    assert count == LARGE_BYTES and Path(path).stat().st_size == count
    assert not (getattr(Path(path).stat(), 'st_file_attributes', 0) & 0x200), 'SPARSE_LARGE_FIXTURE_FORBIDDEN'
    return {'path': Path(path).relative_to(ROOT).as_posix(), 'bytes': count, 'sha256': digest.hexdigest()}


def disk_bytes(root):
    return sum(item.stat().st_size for item in Path(root).rglob('*') if item.is_file())


def portable_parts(path, output, expected):
    output.mkdir(parents=True, exist_ok=False)
    parts, offset, whole = [], 0, hashlib.sha256()
    with path.open('rb') as source:
        sequence = 0
        while offset < expected['bytes']:
            target = output / ('part_%04d.gz' % sequence)
            piece_hash, decoded = hashlib.sha256(), 0
            length = min(PART_BYTES, expected['bytes'] - offset)
            with target.open('xb') as compressed:
                with gzip.GzipFile(filename='', mode='wb', compresslevel=1, fileobj=compressed, mtime=0) as packed:
                    while decoded < length:
                        block = source.read(min(CHUNK, length - decoded))
                        assert block, 'LARGE_ORIGINAL_TRUNCATED_DURING_PACK'
                        packed.write(block)
                        piece_hash.update(block)
                        whole.update(block)
                        decoded += len(block)
            assert decoded == length
            check, size = hashlib.sha256(), 0
            with gzip.open(target, 'rb') as verify:
                while block := verify.read(CHUNK):
                    check.update(block)
                    size += len(block)
                    assert size <= PART_BYTES
            assert size == decoded and check.hexdigest() == piece_hash.hexdigest(), 'PORTABLE_PART_ROUNDTRIP'
            parts.append({'sequence': sequence, 'offset': offset, 'decoded_bytes': decoded,
                          'decoded_sha256': piece_hash.hexdigest(), 'compressed': stamp(target)})
            offset += decoded
            sequence += 1
        assert source.read(1) == b''
    assert offset == LARGE_BYTES and whole.hexdigest() == expected['sha256']
    assert len(parts) == 21 and parts[-1]['decoded_bytes'] == 56_450_377
    manifest = {'schema': 'M3_R12_LOSSLESS_LARGE_ORIGINAL_PARTS_V1', 'format': 'gzip',
                'original': expected, 'parts': parts, 'decoded_part_limit': PART_BYTES,
                'global_order_complete': True, 'all_parts_decoded_and_hashed': True,
                'origin': 'SYNTHETIC_FRONTEND_CAPACITY_NOT_REAL_PRO_CAPTURE'}
    return save_json(output / 'PARTS.json', manifest)


def own_peak():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    return peak_working_set(types.SimpleNamespace(_handle=kernel.GetCurrentProcess()))


def run_w(output, admission, pins):
    fixture = get_fixture(admission)
    root = Path(output)
    large = root / 'LARGE_SYNTHETIC_STDERR.bin'
    original = write_large(large)
    results = CaseResults(root / 'case_results')
    def envelope_for(case):
        def change(request):
            request['inputs']['stderr'] = original
        return capture_variant(fixture, root / (case + '_input'), change=change)
    def frontend(case, envelope):
        harness = CaptureHarness(pins, admission['dependencies_ref'], backend=True)
        result = harness.process(envelope, root / (case + '_actual'))
        assert len(harness.backend_calls) == 1 and all(result[k] is False for k in FALSE_FLAGS)
        assert harness.backend_calls[0]['stderr'] == original
        assert harness.metrics['bytes'] >= LARGE_BYTES and harness.metrics['max_request'] <= CHUNK
        return result, harness
    positive = envelope_for('W01')
    result, harness = frontend('W01', positive)
    results.append({'case': 'W01', 'original': original, 'backend_calls': 1,
                    'identity_metrics': harness.metrics, 'peak_working_set': own_peak()})
    with large.open('r+b') as stream:
        stream.seek(-1, 2)
        final_byte = stream.read(1)
        stream.seek(-1, 2)
        stream.write(bytes([final_byte[0] ^ 1]))
    try:
        envelope = envelope_for('W02')
        fault = CaptureHarness(pins, admission['dependencies_ref'], backend=True)
        rejected = expect_rejection(lambda: fault.process(envelope, root / 'W02_actual'),
                                    ('FILE_CHANGED', 'STREAM_IDENTITY_MISMATCH'))
        assert fault.backend_calls == []
        results.append({'case': 'W02', **rejected, 'backend_calls': 0,
                        'actual_io': [dict(c.io.metrics) for c in fault.contexts]})
    finally:
        with large.open('r+b') as stream:
            stream.seek(-1, 2)
            stream.write(final_byte)
    with large.open('r+b') as stream:
        stream.truncate(LARGE_BYTES - 1)
    try:
        envelope = envelope_for('W03')
        fault = CaptureHarness(pins, admission['dependencies_ref'], backend=True)
        rejected = expect_rejection(lambda: fault.process(envelope, root / 'W03_actual'),
                                    ('FILE_CHANGED', 'STREAM_IDENTITY_MISMATCH', 'STREAM_SIZE_CHANGED'))
        assert fault.backend_calls == []
        results.append({'case': 'W03', **rejected, 'backend_calls': 0,
                        'actual_io': [dict(c.io.metrics) for c in fault.contexts]})
    finally:
        with large.open('ab') as stream:
            stream.write(final_byte)
    envelope = envelope_for('W04')
    result, harness = frontend('W04', envelope)
    probe = assert_io_policy(harness, original)
    assert stamp(large) == original, 'FINAL_LARGE_ORIGINAL_NOT_RESTORED'
    parts = portable_parts(large, root / 'PORTABLE_ORIGINALS', original)
    used = disk_bytes(root)
    peak = own_peak()
    assert peak['bytes'] <= 512 * CHUNK, 'WINDOWS_PEAK_WORKING_SET_EXCEEDED'
    assert used <= 4 * 1024 * CHUNK, 'W_OWNED_TEMP_DISK_EXCEEDED'
    results.append({'case': 'W04', **probe, 'backend_calls': 1, 'portable_originals': parts,
                    'original': original, 'owned_disk_bytes': used, 'peak_working_set': peak,
                    'full_frontend_only_not_real_capture': True})
    return results


def normalize_pins(value):
    pins = {}
    iterable = ({'path': key, **ref} for key, ref in value.items()) if isinstance(value, dict) else value
    for ref in iterable:
        name = Path(ref['path'])
        path = name if name.is_absolute() else ROOT / name
        path = path.resolve()
        assert path.is_relative_to(ROOT) and (path.suffix == '.py' or
            (path.parent == HERE and path.name in ('DEPENDENCIES.json', 'CALL_CHAIN_BINDINGS.json'))), 'PIN_SCOPE'
        pins[path.relative_to(ROOT).as_posix()] = {**ref, 'path': path.relative_to(ROOT).as_posix()}
    return pins


def run_p0(output, admission, pins):
    inspected = []
    own_names = ('json_identity.py', 'delivery_binding.py', 'delivery_transport.py', 'capture_identity.py',
                 'capture_link_successor.py', 'capture_entry.py', 'selftest.py',
                 'DEPENDENCIES.json', 'CALL_CHAIN_BINDINGS.json')
    for name in own_names:
        path = HERE / name
        ref = pins[path.relative_to(ROOT).as_posix()]
        body = read_small(path, 4 * CHUNK)
        assert len(body) == ref['bytes'] and hashlib.sha256(body).hexdigest() == ref['sha256']
        if path.suffix == '.py':
            ast.parse(body, filename=str(path))
        else:
            strict_parse(body)
        inspected.append(ref)
    dependencies = verified_document(admission['dependencies_ref'])
    for ref in dependencies['old_source_files']:
        assert stamp(ref_path(ref)) == ref
    fixture = get_fixture(admission)
    for ref in fixture['file_refs']:
        assert stamp(ref_path(ref)) == ref, 'FROZEN_FIXTURE_CHANGED'
    expected = verified_document(fixture['expected_ref'])
    assert expected['row_count'] == 7 and expected['finish_cycle'] == 6
    owner = ROOT / 'code/software/t052_runner_acceptance_candidate_20261012/windows_job.py'
    assert stamp(owner)['sha256'] == '5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b'
    outbox = admission.get('existing_outbox',
        'code/output/m3_m2_night_drill_20261017/state/actual_intake/STATE.json')
    if isinstance(outbox, dict):
        state = verified_document(outbox)
        state_ref, binding = outbox, 'INDEPENDENT_ADMISSION_PIN'
    else:
        path = ROOT / outbox
        raw = read_small(path)
        state = strict_parse(raw)
        state_ref = {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw),
                     'sha256': hashlib.sha256(raw).hexdigest()}
        binding = 'OBSERVED_EXISTING_DURABLE_STATE_NOT_INDEPENDENTLY_PINNED'
    assert state['schema'] == 'M3_DRILL_INTAKE_STATE_V1' and type(state['outbox']) is dict, 'EXISTING_OUTBOX_STATE'
    return [{'case': 'P0', 'source_AST': inspected, 'dependency_files': len(dependencies['old_source_files']),
             'fixture_files': len(fixture['file_refs']), 'existing_job_identity': stamp(owner),
             'native_processes_started': 0, 'existing_outbox': {'state': state_ref,
             'binding': binding, 'items': len(state['outbox']), 'new_store_created': False}}]


def worker_main(args):
    """Admission requires frozen source_pins, dependencies_ref and fixture.
    Root may narrow deadline, allowed_groups and caps; approved=false rejects.
    Minimal root contract uses this successor's fixed deadline and group caps.
    Root persists/owns overall once-only budgets and child Job lifecycle.
    """
    assert args.worker and sys.dont_write_bytecode and not sys.flags.optimize, 'WORKER_REQUIRES_B_ASSERTIONS_ON'
    raw = read_small(args.admission)
    assert hashlib.sha256(raw).hexdigest() == args.admission_sha256, 'ADMISSION_RAW_SHA_MISMATCH'
    admission = strict_parse(raw)
    assert admission.get('writers_frozen') is True and admission.get('approved', True) is True, 'WRITERS_NOT_FROZEN'
    assert args.group in admission.get('allowed_groups', tuple(GROUP_CAPS)), 'GROUP_NOT_ADMITTED'
    deadline = datetime.fromisoformat(admission.get('deadline', '2026-10-18T20:09:21+08:00'))
    assert deadline.tzinfo is not None and datetime.now(timezone.utc) < deadline, 'ADMISSION_EXPIRED'
    cap = admission.get('group_caps_seconds', GROUP_CAPS)[args.group]
    assert type(cap) is int and 0 < cap <= GROUP_CAPS[args.group], 'UNAPPROVED_GROUP_CAP'
    pins = normalize_pins(admission['source_pins'])
    # Merge only independently frozen dependencies, never derive missing pins
    # from current source bytes during execution.
    dependencies = verified_document(admission['dependencies_ref'])
    for ref in dependencies['old_source_files']:
        name = Path(ref['path']).relative_to(ROOT).as_posix() if Path(ref['path']).is_absolute() else ref['path']
        assert name not in pins or pins[name] == ref, 'DEPENDENCY_PIN_CONFLICT'
        pins[name] = ref
    own = Path(__file__).resolve().relative_to(ROOT).as_posix()
    assert stamp(HERE / 'selftest.py') == pins[own], 'WORKER_SOURCE_NOT_FROZEN'
    target = Path(args.output).resolve()
    assert target != OUTPUT and target.is_relative_to(OUTPUT), 'WORKER_OUTPUT_SCOPE'
    target.mkdir(parents=True, exist_ok=False)
    (target / 'ADMISSION.raw').write_bytes(raw)
    started = time.monotonic()
    save_json(target / 'CONSUMPTION.json', {'schema': 'M3_R12_WORKER_ONCE_ONLY_SLOT_V1',
        'group': args.group, 'pid': os.getpid(), 'admission_sha256': args.admission_sha256,
        'status': 'CONSUMED_RUNNING', 'cap_seconds': cap, 'started_utc': datetime.now(timezone.utc).isoformat()})
    result = {'schema': 'M3_R12_WORKER_RESULT_V1', 'group': args.group, 'pid': os.getpid(),
              'admission_sha256': args.admission_sha256, 'status': 'FAIL', 'cases': [],
              'native_tool_calls': 0, **{key: False for key in FALSE_FLAGS}}
    exit_code = 1
    try:
        if args.group == 'P0':
            cases = run_p0(target, admission, pins)
        elif args.group == 'J':
            cases = run_j_draft(target / 'cases', source_pins=pins)
        elif args.group == 'G':
            cases = run_g_draft(target / 'cases', source_pins=pins)
        elif args.group == 'C':
            cases = run_c(target, admission, pins)
        elif args.group == 'W':
            cases = run_w(target, admission, pins)
        elif args.group == 'R':
            repair = admission.get('located_repair', {})
            assert repair.get('cause_id') == 'G11_WINDOWS_FIXTURE_PATH_206'
            assert repair.get('original_failed_group') == 'G' and repair.get('cases') == [
                'G' + str(n).zfill(2) for n in range(1, 13)]
            assert repair.get('original_group_not_reset') is True
            for path in HERE.glob('*.py'):
                body = read_small(path, 4 * CHUNK)
                ref = pins[path.relative_to(ROOT).as_posix()]
                assert len(body) == ref['bytes'] and hashlib.sha256(body).hexdigest() == ref['sha256']
                ast.parse(body, filename=str(path))
            cases = run_g_draft(target / 'cases', source_pins=pins)
        else:
            raise ValueError('R_REQUIRES_ROOT_LOCATED_REPAIR_DISPATCH_NOT_AUTOMATIC_GROUP_REPLAY')
        assert len(cases) == {'P0': 1, 'J': 12, 'G': 12, 'C': 12, 'W': 4, 'R': 12}[args.group]
        assert time.monotonic() - started <= cap, 'GROUP_CAP_EXCEEDED'
        assert datetime.now(timezone.utc) <= deadline, 'GROUP_PASSED_AFTER_DEADLINE'
        result.update(status='PASS', cases=cases)
        exit_code = 0
    except BaseException as error:
        result.update(error=type(error).__name__ + ':' + str(error), traceback=traceback.format_exc())
        result['cases'] = [strict_parse(read_small(path)) for path in sorted(target.rglob('CASE_*.json'))]
        print(result['traceback'], file=sys.stderr, flush=True)
    finally:
        result.update(exit_code=exit_code, elapsed_seconds=time.monotonic() - started,
                      ended_utc=datetime.now(timezone.utc).isoformat(),
                      owned_process_cleanup='Parent owned_call must prove natural exit, close root handle and Job0')
        save_json(target / 'RESULT.json', result)
        save_json(target / 'GROUP_RESULT.json', result)
    print(json.dumps({'group': args.group, 'status': result['status'], 'cases': len(result['cases']),
                      'exit_code': exit_code, 'result': str(target / 'RESULT.json')}), flush=True)
    return exit_code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true', required=True)
    parser.add_argument('--group', choices=tuple(GROUP_CAPS), required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--admission-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    return worker_main(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
