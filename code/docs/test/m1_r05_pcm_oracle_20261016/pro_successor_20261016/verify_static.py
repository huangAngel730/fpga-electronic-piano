"""Read-only source, scope, and artifact verification; no model test replay."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MODEL = REPO / 'code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016'
ALLOWED = [MODEL.relative_to(REPO).as_posix() + '/',
           HERE.relative_to(REPO).as_posix() + '/']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('DUPLICATE_KEY:' + key)
        obj[key] = value
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    freeze = json.loads((HERE / 'A0/SOURCE_FREEZE.json').read_text(encoding='utf-8'))
    checked = []
    for row in freeze['files']:
        path = REPO / row['path']
        data = path.read_bytes()
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise ValueError('FROZEN_SOURCE_CHANGED:' + row['path'])
        checked.append(row['path'])
    members = []
    for row in freeze['R06_member_references']:
        with zipfile.ZipFile(REPO / row['carrier']) as archive:
            data = archive.read(row['member'])
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise ValueError('ARCHIVE_MEMBER_CHANGED:' + row['member'])
        members.append(row['member'])
    command = ['git', '-c', 'core.longpaths=true', 'status',
               '--porcelain=v1', '-z', '--untracked-files=all']
    status = subprocess.run(command, cwd=REPO, capture_output=True, check=True)
    entries = [x.decode('utf-8') for x in status.stdout.split(b'\0') if x]
    for entry in entries:
        if not entry.startswith('?? ') or not any(entry[3:].startswith(p) for p in ALLOWED):
            raise ValueError('OUTSIDE_AUTHORIZED_NEW_FILES:' + entry)
    index = subprocess.run(['git', '-c', 'core.longpaths=true', 'diff', '--cached', '--name-only'],
                           cwd=REPO, capture_output=True, check=True)
    if index.stdout:
        raise ValueError('INDEX_NOT_EMPTY')
    newfiles = []
    for folder in (MODEL, HERE):
        for path in sorted(folder.rglob('*')):
            if not path.is_file():
                continue
            data = path.read_bytes()
            relative = path.relative_to(REPO).as_posix()
            if '__pycache__' in path.parts or path.suffix == '.pyc':
                raise ValueError('UNEXPECTED_BYTECODE:' + relative)
            if path.suffix == '.py':
                if b'\r' in data:
                    raise ValueError('PYTHON_REQUIRES_LF:' + relative)
                ast.parse(data.decode('utf-8'), filename=relative)
            if path.suffix == '.json':
                json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                           parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            newfiles.append({'path': relative, 'bytes': len(data), 'sha256': sha(data)})
    result = {
        'schema': 'M1_PRO_STATIC_DELIVERY_CHECK_V1', 'status': 'PASS',
        'scope': 'SOURCE_AND_NEW_ARTIFACTS_ONLY_NOT_RTL_OR_MATH_REPLAY',
        'frozen_files_checked_unchanged': len(checked),
        'R06_archive_members_checked_unchanged': len(members),
        'new_files': newfiles, 'git_status_argv': command,
        'git_status_stdout_sha256': sha(status.stdout),
        'git_status_stderr_sha256': sha(status.stderr),
        'all_new_files_within_two_authorized_directories': True,
        'index_empty': True, 'new_content_committed': False,
        'new_content_pushed': False, 'final_exact_tree_repo_gate_run': False,
        'REAL_RESULT': 'PENDING_REAL_CAPTURE', 'board_release_allowed': False,
        'A0_original_outer_stdout_stderr':
            'Initial freeze output existed in tool transcript only; this independent hash verification has raw streams in its own command receipt. Initial A0 receipt is retained unchanged.',
    }
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in (
        'status', 'frozen_files_checked_unchanged', 'R06_archive_members_checked_unchanged',
        'all_new_files_within_two_authorized_directories', 'index_empty')}))


if __name__ == '__main__':
    main()
