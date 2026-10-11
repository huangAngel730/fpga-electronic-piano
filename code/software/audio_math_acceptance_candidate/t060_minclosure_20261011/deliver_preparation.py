"""Seal/verify/finalize STATIC preparation, never launches RTL or EDA tools."""
import argparse
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from fsm_oracle import require  # noqa: E402
from prepare import MATH_SHA, ROOT, dump, metadata, sha  # noqa: E402
from strict_capture import object_pairs  # noqa: E402

DOC = ROOT / 'code/docs/hardware/audio_math_acceptance_v1/T060_MINCLOSURE_20261011'


def load(raw):
    return json.loads(raw, object_pairs_hook=object_pairs)


def fresh(path, base):
    path = path.resolve()
    require(path.is_relative_to(base) and path != base and not path.exists(), 'DELIVERY_OUTPUT_SCOPE_OR_EXISTS')
    path.mkdir(parents=True)
    return path


def validate_portable(members):
    prefix = 'run/portable/'
    manifest = load(members[prefix + 'manifest.json'])
    inputs = manifest['inputs']
    require({p[len(prefix):] for p in members if p.startswith(prefix)} == set(inputs) | {'manifest.json'},
            'PRECHECK_PORTABLE_MEMBERS')
    for name, identity in inputs.items():
        require(metadata(members[prefix + name]) == identity, 'PRECHECK_PORTABLE_MEMBER_SHA:' + name)
    math_root = prefix + 'code/software/audio_math_acceptance_candidate/'
    for name, expected in MATH_SHA.items():
        require(sha(members[math_root + name]) == expected, 'PRECHECK_MATH_SOURCE_CHANGED:' + name)
    require(manifest['sources_before'] == manifest['sources_after'] and manifest['originals'] == 56
            and manifest['RTL_runs'] == manifest['RTL_compilations'] == manifest['EDA_runs'] == 0
            and manifest['new_RTL_execution_authorized'] is False, 'PRECHECK_PORTABLE_BOUNDARY')


def seal(run, first_failure, notes, output):
    run = run.resolve()
    require(run.is_relative_to(ROOT / 'code/output'), 'DELIVERY_RUN_SCOPE')
    receipt = load((run / 'receipt.json').read_bytes())
    require(receipt['status'] == 'NEW_SOFTWARE_PREPARATION_PASS' and receipt['exit_code'] == 0,
            'DELIVERY_NOT_PASS')
    require(receipt['sources_before'] == receipt['sources_after'], 'DELIVERY_SOURCE_DRIFT')
    for name, identity in receipt['sources_after'].items():
        require(metadata((ROOT / name).read_bytes()) == identity, 'DELIVERY_EXECUTED_SOURCE_CHANGED:' + name)
    members = {'run/' + p.relative_to(run).as_posix(): p.read_bytes()
               for p in sorted(run.rglob('*')) if p.is_file()}
    first_failure = first_failure.resolve()
    require(first_failure.is_relative_to(ROOT / 'code/output'), 'DELIVERY_FAILURE_SCOPE')
    require(load((first_failure / 'receipt.json').read_bytes())['exit_code'] == 1, 'DELIVERY_FIRST_FAILURE')
    for p in sorted(first_failure.rglob('*')):
        if p.is_file():
            members['first_failure/' + p.relative_to(first_failure).as_posix()] = p.read_bytes()
    members['PRECHECK_PREPARATION.md'] = notes.read_bytes()
    validate_portable(members)
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    payload = raw.getvalue()
    output = fresh(output, DOC)
    (output / 'STATIC_PRECHECK.zip.b64').write_text(base64.encodebytes(payload).decode('ascii'),
                                                   encoding='ascii', newline='\n')
    seal_receipt = dict(status='STATIC_PRECHECK_SEALED_NOT_RTL_CAPTURE', exit_code=0,
                        zip=metadata(payload), members={n: metadata(d) for n, d in sorted(members.items())},
                        software_receipt=receipt['status'], tests=22,
                        RTL_compilations=0, RTL_runs=0, EDA_runs=0, t060_complete=False,
                        M2_notice='awaiting_user_forward_not_delivered')
    dump(output / 'seal.json', seal_receipt)
    return dict(status=seal_receipt['status'], members=len(members), zip=metadata(payload))


def verify(sealed, output):
    sealed = sealed.resolve()
    expected = load((sealed / 'seal.json').read_bytes())
    payload = base64.b64decode((sealed / 'STATIC_PRECHECK.zip.b64').read_bytes())
    require(metadata(payload) == expected['zip'], 'PRECHECK_ZIP_IDENTITY')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and set(names) == set(expected['members']), 'PRECHECK_ZIP_MEMBERS')
        require(archive.testzip() is None, 'PRECHECK_ZIP_CRC')
        members = {name: archive.read(name) for name in names}
    for name, data in members.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'PRECHECK_ZIP_PATH')
        require(metadata(data) == expected['members'][name], 'PRECHECK_ZIP_MEMBER_SHA:' + name)
    validate_portable(members)
    # New seal-only negative checks, no original capture/model replay.
    tamper = []
    dependency = 'run/portable/code/software/audio_math_acceptance_candidate/envelope_model.py'
    for label, mode, diagnostic in (
        ('missing_dependency', 'missing', 'PRECHECK_PORTABLE_MEMBERS'),
        ('changed_dependency', 'changed', 'PRECHECK_PORTABLE_MEMBER_SHA'),
        ('resigned_bad_dependency', 'resigned', 'PRECHECK_MATH_SOURCE_CHANGED')):
        bad = dict(members)
        if mode == 'missing':
            del bad[dependency]
        else:
            bad[dependency] += b'\n# deliberately changed dependency\n'
            if mode == 'resigned':
                manifest = load(bad['run/portable/manifest.json'])
                manifest['inputs'][dependency[len('run/portable/'):]] = metadata(bad[dependency])
                bad['run/portable/manifest.json'] = json.dumps(manifest).encode()
        try:
            validate_portable(bad)
        except ValueError as error:
            require(diagnostic in str(error), 'PRECHECK_WRONG_TAMPER_DIAGNOSTIC')
            tamper.append(dict(label=label, rejected=True, diagnostic=str(error)))
        else:
            raise ValueError('PRECHECK_TAMPER_ACCEPTED:' + label)
    output = fresh(output, ROOT / 'code/output')
    for name, data in members.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / 'STATIC_PRECHECK.zip').write_bytes(payload)
    result = dict(status='STATIC_PRECHECK_VERIFIED', exit_code=0, zip=metadata(payload),
                  members=len(members), tamper_checks=tamper, RTL_compilations=0,
                  RTL_runs=0, EDA_runs=0, t060_complete=False)
    dump(output / 'verification.json', result)
    return result


def finalize(sealed, gate, output):
    output = fresh(output, ROOT / 'code/output')
    steps = []
    def git(label, *args):
        argv = ['git', *args]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=60)
        (output / (label + '.stdout.txt')).write_bytes(result.stdout)
        (output / (label + '.stderr.txt')).write_bytes(result.stderr)
        steps.append(dict(label=label, argv=argv, exit_code=result.returncode,
                          stdout=metadata(result.stdout), stderr=metadata(result.stderr)))
        require(result.returncode == 0, 'PRECHECK_FINAL_GIT:' + label)
        return result.stdout.decode().strip()
    head, tree = git('head', 'rev-parse', 'HEAD'), git('tree', 'rev-parse', 'HEAD^{tree}')
    branch, dirty = git('branch', 'branch', '--show-current'), git('status', 'status', '--porcelain')
    remote = git('remote', '-c', 'http.version=HTTP/1.1', 'ls-remote', 'origin', 'refs/heads/develop').split()[0]
    gated = load((gate / 'receipt.json').read_bytes())
    require(head == remote and branch == 'develop' and not dirty
            and gated['status'] == 'EXACT_INDEX_NINE_GATES_PASS' and gated['tree'] == tree,
            'PRECHECK_FINAL_NOT_CLEAN_GATED_REMOTE')
    expected = load((sealed / 'seal.json').read_bytes())
    payload = base64.b64decode((sealed / 'STATIC_PRECHECK.zip.b64').read_bytes())
    require(metadata(payload) == expected['zip'], 'PRECHECK_FINAL_ZIP_IDENTITY')
    receipt = dict(status='T060_STATIC_PRECHECK_GATED_PUSH_VERIFIED', exit_code=0,
                   commit=head, tree=tree, remote_develop=remote, gate=str(gate),
                   sealed_package=expected['zip'], steps=steps,
                   RTL_compilations=0, RTL_runs=0, EDA_runs=0,
                   mandatory_repository_short_RTL_gates=True, t060_complete=False,
                   M2_notice='awaiting_user_forward_not_delivered')
    dump(output / 'git_delivery.json', receipt)
    forward = output / 'M3_T060_MINCLOSURE_PRECHECK_M2_20261012.zip'
    with zipfile.ZipFile(forward, 'x', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('STATIC_PRECHECK.zip', payload)
        archive.write(sealed / 'seal.json', 'seal.json')
        for p in sorted(gate.glob('*')):
            if p.is_file():
                archive.write(p, 'GATE/' + p.name)
        for p in sorted(output.glob('*')):
            if p.is_file() and p != forward:
                archive.write(p, 'PUBLICATION/' + p.name)
    dump(output / 'forward_manifest.json', dict(file=forward.name, **metadata(forward.read_bytes())))
    return dict(status=receipt['status'], commit=head, forward=str(forward), **metadata(forward.read_bytes()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('seal', 'verify', 'finalize'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--first-failure', type=Path)
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--sealed', type=Path)
    parser.add_argument('--gate', type=Path)
    args = parser.parse_args()
    if args.mode == 'seal':
        result = seal(args.run, args.first_failure, args.notes, args.output)
    elif args.mode == 'verify':
        result = verify(args.sealed, args.output)
    else:
        result = finalize(args.sealed, args.gate, args.output)
    print(json.dumps(result))
