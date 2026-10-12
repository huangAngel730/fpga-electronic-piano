"""Seal NEW C software evidence / export forward ZIP; no tests or RTL tools."""
import argparse
import base64
import io
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from controlled_runner import Budget, dump, finish, identity, load, require, step  # noqa: E402
from prepare import ROOT, TB_REL, dependencies, sha  # noqa: E402

DOC = ROOT / 'code/docs/hardware/audio_math_acceptance_v1/T060_MINCLOSURE_20261011'


def qualify_budget_tail(out, suite):
    """New identity/sealing qualification: three targeted tests, NOT old suites."""
    budget = Budget(300)
    require(not out.exists() and out.is_relative_to(ROOT / 'code/output'),
            'TAIL_OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True)
    paths, _ = dependencies()
    paths += [p for p in (ROOT / TB_REL).glob('*') if p.is_file()]
    before = {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}
    steps, failure, config_identity = [], None, None
    python = [sys.executable, '-I', '-S', '-B', '-X', 'utf8']
    try:
        changed = ['controlled_runner.py', 'test_followup.py',
                   'prepare_followup.py', 'deliver_followup.py']
        steps.append(step(out, 'authorized_source_diff', ['git', 'diff', '--binary', 'HEAD', '--',
            *[(HERE / name).relative_to(ROOT).as_posix() for name in changed]],
            ROOT, budget, 90))
        steps.append(step(out, 'new_tail_tests_only', python + [str(HERE / 'test_followup.py'),
            '--evidence-dir', str(out / 'synthetic_clock'), 'FinalizationBudgetTests', '-v'],
            out, budget, 90))
        steps.append(step(out, 'new_identity_package', python + [str(HERE / 'prepare_followup.py'),
            '--output', str(out / 'prepared'), '--suite', str(suite)], out, budget, 90))
        portable = out / 'prepared/portable'
        config = portable / 'CONTROLLED_CONFIG_NOT_AUTHORIZED.json'
        config_identity = identity(config)
        software = portable / HERE.relative_to(ROOT)
        steps.append(step(out, 'default_locked_local_preflight', python + [str(software / 'controlled_runner.py'),
            '--config', str(config), '--output', str(out / 'locked_preflight')], out, budget, 90))
        locked = load(out / 'locked_preflight/receipt.json')
        require(locked['status'] == 'PRECHECK_ONLY_EXECUTION_LOCKED'
                and locked['execution_authorized'] is False and locked['steps'] == [],
                'TAIL_DEFAULT_NOT_LOCKED')
        require(not (portable / 'ONE_SHOT_ATTEMPT.json').exists(), 'TAIL_ATTEMPT_CONSUMED')
        require(identity(config) == config_identity, 'TAIL_CONFIG_DRIFT')
        budget.limit(90)
    except Exception as error:
        failure = str(error)
    after = {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}
    if before != after:
        failure = (failure or '') + '; SOURCE_DRIFT'
    receipt = dict(status='NEW_C_BUDGET_TAIL_SOFTWARE_PASS' if not failure else 'FAIL_PARTIAL',
        exit_code=int(failure is not None), failure=failure, sources_before=before,
        sources_after=after, steps=steps, config=config_identity,
        evidence_origin='SYNTHETIC_CLOCK_NO_TOOLS_AND_DEFAULT_LOCKED_PREFLIGHT',
        total_limit_seconds=300, step_limit_seconds=90,
        old_13_tests='V0301 REUSED; NOT_RERUN', old_22_tests='V0295 REUSED; NOT_RERUN',
        A_long_software='NOT_RERUN', execution_authorized=False,
        RTL_compilations=0, RTL_runs=0, EDA_runs=0,
        physical_verified=False, t060_complete=False, t061_complete=False)
    result = finish(out, budget, receipt)
    print(json.dumps(dict(status=result['status'], exit_code=result['exit_code'],
                          config=result['config'], elapsed_seconds=result['elapsed_seconds'])))
    return result['exit_code']


def archive_payload(payload):
    manifest = {name: dict(bytes=len(raw), sha256=sha(raw)) for name, raw in payload.items()}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(name, raw)
        archive.writestr('FORWARD_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(io.BytesIO(stream.getvalue())) as archive:
        require(archive.testzip() is None, 'FOLLOWUP_ZIP_CRC')
        for name, item in manifest.items():
            require(sha(archive.read(name)) == item['sha256'], 'FOLLOWUP_ZIP_SHA')
    return stream.getvalue(), manifest


def seal(evidence, failures, target):
    require(not target.exists() and target.parent == DOC, 'FOLLOWUP_SEAL_SCOPE_OR_EXISTS')
    receipt = load(evidence / 'receipt.json')
    require(receipt['status'] in ('NEW_C_FOLLOWUP_SOFTWARE_PASS', 'NEW_C_BUDGET_TAIL_SOFTWARE_PASS')
            and receipt['sources_before'] == receipt['sources_after']
            and receipt['exit_code'] == 0 and receipt['elapsed_seconds'] < 300,
            'FOLLOWUP_NOT_PASS')
    for rel, expected in receipt['sources_after'].items():
        require(identity(ROOT / rel) == expected, 'FOLLOWUP_FINAL_SOURCE_DRIFT:' + rel)
    payload = {}
    for folder in [evidence, *failures]:
        require(folder.is_relative_to(ROOT / 'code/output'), 'FOLLOWUP_EVIDENCE_SCOPE')
        for path in folder.rglob('*'):
            if path.is_file():
                payload['evidence/' + folder.name + '/' + path.relative_to(folder).as_posix()] = path.read_bytes()
    raw, manifest = archive_payload(payload)
    target.mkdir()
    (target / 'evidence.zip.b64').write_bytes(base64.b64encode(raw) + b'\n')
    dump(target / 'seal.json', dict(status='NEW_C_SOFTWARE_SEALED', zip_sha256=sha(raw),
        zip_bytes=len(raw), members=len(manifest) + 1, member_identity=manifest,
        sources=receipt['sources_after'], source_receipt=receipt,
        original_V0295_static_zip_sha256='93c946eaff03d6fb86eeb3a28805e2a47029f50f143e96383a80cb6b6bf3b89b',
        execution_authorized=False, old_22='REUSED V0295; not rerun',
        private_message='待用户转发，尚未送达', physical_verified=False, t060_complete=False))
    print(json.dumps(dict(status='SEALED', bytes=len(raw), sha256=sha(raw))))


def forward(target, gate, out, commit, remote):
    require(not out.exists() and out.is_relative_to(ROOT / 'code/output'), 'FOLLOWUP_FORWARD_SCOPE_OR_EXISTS')
    sealed = load(target / 'seal.json')
    raw = base64.b64decode((target / 'evidence.zip.b64').read_bytes(), validate=False)
    require(sha(raw) == sealed['zip_sha256'], 'FOLLOWUP_SEAL_SHA')
    require(commit == remote and len(commit) == 40, 'FOLLOWUP_REMOTE_NOT_CONFIRMED')
    gated = load(gate / 'receipt.json')
    require(gated['status'] == 'EXACT_INDEX_NINE_GATES_PASS', 'FOLLOWUP_NINE_GATES')
    payload = {'NEW_C_SOFTWARE_EVIDENCE.zip': raw}
    for rel, expected in sealed['sources'].items():
        require(identity(ROOT / rel) == expected, 'FOLLOWUP_FORWARD_SOURCE_DRIFT:' + rel)
        payload[rel] = (ROOT / rel).read_bytes()
    for path in [DOC / 'C_FOLLOWUP_20261012.md', target / 'seal.json',
                 *(DOC / 'BUDGET_TAIL_20261012').glob('*'), *gate.glob('*')]:
        if path.is_file():
            payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    payload['GITHUB_DELIVERY.json'] = (json.dumps(dict(commit=commit, remote_develop=remote,
        gated_tree=gated['tree'], private_notice='待用户转发，尚未送达'), indent=2) + '\n').encode()
    raw, manifest = archive_payload(payload)
    out.mkdir(parents=True)
    name = ('M3_T060_C_BUDGET_TAIL_M2_20261012.zip'
            if sealed['source_receipt']['status'] == 'NEW_C_BUDGET_TAIL_SOFTWARE_PASS'
            else 'M3_T060_C_FOLLOWUP_M2_20261012.zip')
    archive_path = out / name
    archive_path.write_bytes(raw)
    dump(out / 'forward_receipt.json', dict(status='FORWARD_ZIP_VERIFIED', file=str(archive_path),
        **identity(archive_path), members=len(manifest) + 1, commit=commit, remote_develop=remote))
    print(json.dumps(load(out / 'forward_receipt.json')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['seal', 'forward', 'qualify-budget-tail'])
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--failures', type=Path, nargs='*', default=[])
    parser.add_argument('--target', type=Path)
    parser.add_argument('--suite', type=Path)
    parser.add_argument('--gate', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--remote')
    args = parser.parse_args()
    if args.mode == 'qualify-budget-tail':
        raise SystemExit(qualify_budget_tail(args.output.resolve(), args.suite.resolve()))
    elif args.mode == 'seal':
        seal(args.evidence.resolve(), [p.resolve() for p in args.failures], args.target.resolve())
    else:
        forward(args.target.resolve(), args.gate.resolve(), args.output.resolve(), args.commit, args.remote)
