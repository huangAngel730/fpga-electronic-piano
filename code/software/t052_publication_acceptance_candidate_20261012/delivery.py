"""Software-only qualification and self-contained publication-checker handoff."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publication import DUT_SHA, identity, need

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOC = ROOT / 'code/docs/test/t052_publication_acceptance_20261012'
REFERENCE = ROOT / 'code/docs/evidence/m2_new_deliveries_review_20261012'
RAW_SHA = '86704ddd20ee755d3d77ebe7a1379f3a8f2992e9a867a251fc1e3574ff4817a0'
PREFIX = 'received_M1_v5/'
REQ = PREFIX + 'logs/tb_t052_requests.log'
CAP = PREFIX + 'logs/tb_t052_polyphony.capture'
BAD = ['M1_v5_checker_incremental/missing_one_result_complete.capture',
       'M1_v5_checker_incremental/truncated_to_4096_complete.capture']
DUT = PREFIX + 'code/rtl/audio/t052_polyphony_test_source.sv'
SELECTED = [REQ, CAP, *BAD, DUT,
            PREFIX + 'code/tb/audio/t052_polyphony/tb_t052_polyphony.sv',
            PREFIX + 'code/tb/audio/t052_polyphony/check_t052_rtl.py',
            'received_identity.json', 'M1_v5_checker_incremental/receipt.json',
            'M1_v5_checker_incremental/missing_one_result.stdout.bin',
            'M1_v5_checker_incremental/truncate_4096.stdout.bin']


def dump(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sources():
    return {p.name: identity(p) for p in HERE.glob('*.py')}


def fresh(path):
    path = path.resolve()
    need(path.is_relative_to(ROOT / 'code/output') and not path.exists(), 'OUTPUT_SCOPE_OR_EXISTS')
    path.mkdir(parents=True)
    return path


def qualify(out):
    out = fresh(out)
    start, steps, failure = time.monotonic(), [], None
    before = sources()
    archive_identity = identity(REFERENCE / 'RAW_EVIDENCE.zip')
    command = [sys.executable, '-I', '-S', '-B', '-X', 'utf8']

    def step(label, args, expected=0, diagnostic=None):
        remaining = 300 - (time.monotonic() - start)
        need(remaining > 0, 'QUALIFICATION_TOTAL_BUDGET')
        begin = time.monotonic()
        value = subprocess.run(command + list(map(str, args)), cwd=out,
                               capture_output=True, timeout=min(90, remaining))
        (out / (label + '.stdout.txt')).write_bytes(value.stdout)
        (out / (label + '.stderr.txt')).write_bytes(value.stderr)
        steps.append(dict(label=label, command=command + list(map(str, args)),
                          exit_code=value.returncode, expected_exit=expected,
                          diagnostic=diagnostic, seconds=time.monotonic() - begin,
                          stdout=identity(out / (label + '.stdout.txt')),
                          stderr=identity(out / (label + '.stderr.txt'))))
        dump(out / (label + '.receipt.json'), steps[-1])
        print(label + ': exit ' + str(value.returncode), flush=True)
        need(value.returncode == expected and
             (not diagnostic or diagnostic.encode() in value.stdout + value.stderr),
             'SOFTWARE_CHECK_FAILED:' + label)
        need(time.monotonic() - start < 300, 'QUALIFICATION_TOTAL_BUDGET')

    try:
        need(archive_identity['sha256'] == RAW_SHA, 'M2_ARCHIVE_SHA')
        manifest = load(REFERENCE / 'MANIFEST.json')['members']
        readonly = out / 'readonly'
        readonly.mkdir()
        with zipfile.ZipFile(REFERENCE / 'RAW_EVIDENCE.zip') as archive:
            for name in SELECTED:
                raw = archive.read(name)
                need(dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) == manifest[name],
                     'M2_MEMBER_SHA:' + name)
                target = readonly / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        need(identity(readonly / DUT)['sha256'] == DUT_SHA, 'DUT_BASELINE_SHA')
        received = load(readonly / 'received_identity.json')
        need(received['M1']['sha256'] ==
             'c7981d106d162a45ee3580188a401f9dad81da64bd00e085c2dbf2fb49558e2c',
             'M2_RECORDED_OUTER_IDENTITY')
        dump(out / 'baseline_provenance.json', dict(M2_archive=archive_identity,
             selected_members={name: identity(readonly / name) for name in SELECTED},
             original_v5_zip_identity=received['M1'],
             original_outer_zip_locally_available=False,
             provenance='M2_PINNED_ARCHIVE_AND_MEMBER_MANIFEST', DUT_sha256=DUT_SHA))
        snapshot = out / 'snapshot'
        snapshot.mkdir()
        for name, expected in before.items():
            raw = (HERE / name).read_bytes()
            (snapshot / name).write_bytes(raw)
            need(identity(snapshot / name) == expected, 'SNAPSHOT_SHA')
        step('new_unit_tests', [snapshot / 'test_publication.py', '-v'])
        step('handwritten_corpus', [snapshot / 'vectors.py', '--output', out / 'corpus'])
        corpus_manifest = load(out / 'corpus/manifest.json')
        for name, entry in corpus_manifest.items():
            case = out / 'corpus' / name
            step(name, [snapshot / 'publication.py', 'controlled',
                        '--controls', case / 'controls.jsonl',
                        '--observations', case / 'observations.jsonl',
                        '--publications', case / 'publications.jsonl'],
                 entry['expected_exit'], entry['diagnostic'])
        legacy_results = {}
        for label, name in [('v5_original', CAP), ('v5_missing_one', BAD[0]),
                            ('v5_truncated_4096', BAD[1])]:
            step(label, [snapshot / 'publication.py', 'legacy', '--requests', readonly / REQ,
                         '--capture', readonly / name], 3, 'CONTROL_EVIDENCE_INSUFFICIENT')
            legacy_results[label] = load(out / (label + '.stdout.txt'))
        dump(out / 'input_sufficiency.json', dict(status='UNKNOWN',
             legacy_results=legacy_results, expected_from_capture=False,
             normal_cancellation_not_proven_by_legacy_bytes=True,
             original_math='REUSED V0300; NOT_RERUN',
             old_checker_false_acceptance='REUSED M2 original logs; NOT_RERUN',
             original_RTL='NOT_RERUN', new_RTL='NOT_AUTHORIZED_NOT_RUN'))
    except Exception as error:
        failure = str(error)
    after = sources()
    if after != before or identity(REFERENCE / 'RAW_EVIDENCE.zip') != archive_identity:
        failure = (failure or '') + '; SOURCE_OR_BASELINE_DRIFT'
    elapsed = time.monotonic() - start
    if elapsed >= 300:
        failure = (failure or '') + '; QUALIFICATION_TOTAL_BUDGET'
    receipt = dict(status='SOFTWARE_ONLY_QUALIFICATION_PASS' if failure is None else 'FAIL_PARTIAL',
                   exit_code=int(failure is not None), failure=failure,
                   sources_before=before, sources_after=after, steps=steps,
                   python=dict(path=sys.executable, version=sys.version, **identity(Path(sys.executable))),
                   elapsed_seconds=elapsed, total_limit_seconds=300, step_limit_seconds=90,
                   runtime_scope='STANDARD_LIBRARY_SOFTWARE_ONLY', RTL_runs=0, EDA_runs=0,
                   legacy_publication_complete=False, T052_complete=False,
                   notice='待用户转发，尚未送达')
    dump(out / 'receipt.json', receipt)
    print(json.dumps(dict(status=receipt['status'], exit_code=receipt['exit_code'],
                          elapsed_seconds=elapsed)))
    return receipt['exit_code']


def zip_payload(payload):
    manifest = {key: dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                for key, raw in payload.items()}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(name, raw)
        archive.writestr('MEMBERS.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        need(archive.testzip() is None, 'ZIP_CRC')
        for name, entry in manifest.items():
            need(hashlib.sha256(archive.read(name)).hexdigest() == entry['sha256'], 'ZIP_MEMBER_SHA')
    return buffer.getvalue(), manifest


def seal(evidence, target):
    evidence, target = evidence.resolve(), target.resolve()
    need(evidence.is_relative_to(ROOT / 'code/output') and target.parent == DOC
         and not target.exists(), 'SEAL_SCOPE_OR_EXISTS')
    receipt = load(evidence / 'receipt.json')
    need(receipt['status'] == 'SOFTWARE_ONLY_QUALIFICATION_PASS' and
         sources() == receipt['sources_before'] == receipt['sources_after'], 'NOT_QUALIFIED')
    payload = {'evidence/' + path.relative_to(evidence).as_posix(): path.read_bytes()
               for path in evidence.rglob('*') if path.is_file()}
    for path in DOC.glob('*.md'):
        payload['docs/' + path.name] = path.read_bytes()
    raw, manifest = zip_payload(payload)
    target.mkdir()
    (target / 'evidence.zip.b64').write_bytes(base64.b64encode(raw) + b'\n')
    dump(target / 'seal.json', dict(status='SEALED_SOFTWARE_ONLY',
         zip_bytes=len(raw), zip_sha256=hashlib.sha256(raw).hexdigest(),
         members=len(manifest) + 1, sources=sources(),
         evidence_receipt=receipt, notice='待用户转发，尚未送达'))
    print(json.dumps(dict(status='SEALED_SOFTWARE_ONLY', bytes=len(raw),
                         sha256=hashlib.sha256(raw).hexdigest())))


def forward(target, gate, output, commit, remote):
    need(commit == remote and len(commit) == 40, 'REMOTE_UNCONFIRMED')
    need(load(gate / 'receipt.json')['status'] == 'EXACT_INDEX_NINE_GATES_PASS', 'GATE_NOT_PASS')
    sealed = load(target / 'seal.json')
    need(sources() == sealed['sources'], 'SEALED_SOURCE_DRIFT')
    raw = base64.b64decode((target / 'evidence.zip.b64').read_bytes())
    need(hashlib.sha256(raw).hexdigest() == sealed['zip_sha256'], 'SEALED_ZIP_SHA')
    payload = {'SOFTWARE_EVIDENCE.zip': raw}
    for path in [*HERE.glob('*.py'), *DOC.glob('*.md'), *gate.glob('*'), target / 'seal.json']:
        if path.is_file():
            payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    payload['GITHUB_DELIVERY.json'] = json.dumps(dict(commit=commit, remote=remote,
         tree=load(gate / 'receipt.json')['tree'], notice='待用户转发，尚未送达')).encode()
    raw, manifest = zip_payload(payload)
    output = fresh(output)
    archive = output / 'M3_T052_PUBLICATION_M1_M2_20261012.zip'
    archive.write_bytes(raw)
    result = dict(status='FORWARD_ZIP_VERIFIED', file=str(archive), **identity(archive),
                  members=len(manifest) + 1, commit=commit, remote=remote)
    dump(output / 'forward_receipt.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['qualify', 'seal', 'forward'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--target', type=Path)
    parser.add_argument('--gate', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--remote')
    args = parser.parse_args()
    if args.mode == 'qualify':
        raise SystemExit(qualify(args.output))
    elif args.mode == 'seal':
        seal(args.evidence, args.target)
    else:
        forward(args.target, args.gate, args.output, args.commit, args.remote)
