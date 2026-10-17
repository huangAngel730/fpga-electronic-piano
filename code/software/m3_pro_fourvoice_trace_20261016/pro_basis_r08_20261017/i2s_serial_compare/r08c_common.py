"""Role C shared file/report helpers. Import performs no file I/O."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


class EvidenceError(ValueError):
    def __init__(self, code, **detail):
        self.code, self.detail = code, detail
        super().__init__(code)


def need(ok, code, **detail):
    if not ok:
        raise EvidenceError(code, **detail)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_module(file, name, expected_sha=None):
    file = Path(file)
    if expected_sha is not None:
        need(sha(file.read_bytes()) == expected_sha, 'DEPENDENCY_SHA', path=str(file))
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(status, **values):
    return {'status': status, 'real_pass': False, 'board_release_allowed': False, **values}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def identity(path):
    path = Path(path)
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': sha(raw)}


def bounded_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    need(path.is_relative_to(root) and path != root, 'PATH_ESCAPE', path=str(path))
    need(path.is_file(), 'MISSING_FILE', path=str(path))
    return path


def public_view(row):
    """Mechanical R7-A view; original object is always kept by the caller."""
    if row.get('schema') != 'M3_R7A_PUBLIC_ROW_V1':
        return row
    fields, source, ext = row['fields'], row['source'], row['extensions']
    need(ext.get('schema') == 'M3_R7A_TX_EXTENSION_V1', 'PUBLIC_EXTENSION_SCHEMA')
    need(fields['cycle'] == source['cycle'] and fields['epoch'] == source['epoch'], 'PUBLIC_COORDINATE')
    return {**fields, 'time_ps': source['time_ps'], 'source_line': source['line'],
            'tx_metadata_valid': ext.get('obs_tx_metadata_valid'), 'tx_req_id_valid': ext.get('obs_tx_req_id_valid'),
            'tx_clip_mask': ext.get('obs_tx_clip_mask'), 'metadata_error': ext.get('obs_metadata_error'),
            'frame_id_overflow': ext.get('obs_frame_id_overflow')}


def call(function, data):
    try:
        return function(data)
    except ValueError as error:
        if not hasattr(error, 'code') or not hasattr(error, 'detail'):
            raise
        return report('REJECT', reason=error.code, detail=error.detail)


def cli(function):
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8'))
    result = call(function, data)
    result['input'] = identity(args.input)
    save(args.output, result)
    print(json.dumps({'status': result['status'], 'reason': result.get('reason')}))
    return 2 if result['status'] == 'REJECT' else (3 if result['status'].startswith(('PENDING', 'UNKNOWN', 'UNRESOLVED')) else 0)


def check_case(output_dir, data, actual, expected):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save(output_dir / 'INPUT.json', data)
    save(output_dir / 'ACTUAL.json', actual)
    observed = actual.get('reason') if actual['status'] == 'REJECT' else actual['status']
    save(output_dir / 'EXPECTATION.json', {'expected': expected, 'actual': observed})
    assert observed == expected, (expected, observed)
    return {'status': 'CASE_EXPECTATION_MATCHED', 'expected': expected, 'actual': observed,
            'actual_status': actual['status'], 'is_pending': actual['status'].startswith(('PENDING', 'UNKNOWN', 'UNRESOLVED')),
            'result': actual, 'real_pass': False, 'board_release_allowed': False}
