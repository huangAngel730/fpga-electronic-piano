"""Verify and seal existing D repair evidence; starts no external tool."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RTL = ROOT / 'code/rtl/input/m3_dual_slider_138k_candidate_20261015'
TB = ROOT / 'code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015'
DEST = HERE / 'delivery_repair_20261016'
OLD_ZIP = HERE / 'delivery_night_r02/DUAL_SLIDER_NIGHT_PARTIAL_20261016.zip'
OLD_SHA = '6cee5e409e0082f5590ca68f45f61933eab15c4700e272c4f1195316d81185bc'


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read_json(path):
    return json.loads(path.read_bytes())


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def verify_run(number, expected_checks):
    folder = HERE / ('repair_run_%02d' % number)
    before = read_json(folder / 'before.json')
    after = read_json(folder / 'after.json')
    result = read_json(folder / 'RESULT.json')
    require(before == after, 'RUN_INPUT_OR_TOOL_DRIFT')
    require(len(before['tools']) == 438, 'TOOL_CLOSURE_COUNT')
    require(result['status'] == 'PASS' and result['identity_unchanged'], 'RESULT_NOT_PASS')
    require(result['tool_starts'] == 8 and result['elapsed_seconds'] < 300, 'BUDGET_OR_CALL_COUNT')
    for item in read_json(folder / 'products.json'):
        require(identity(Path(item['path']).read_bytes()) ==
                {'bytes': item['bytes'], 'sha256': item['sha256']}, 'PRODUCT_DRIFT:' + item['path'])
    calls = {}
    for path in folder.glob('*.receipt.json'):
        label = path.name.removesuffix('.receipt.json')
        receipt = read_json(path)
        require(receipt['process_created'] and not receipt['timeout'], 'TOOL_NOT_COMPLETED')
        require(receipt['timeout_seconds'] <= 90, 'PER_TOOL_BUDGET')
        calls[label] = receipt
    require(len(calls) == 8, 'RECEIPT_COUNT')
    for label in ('iverilog_version', 'vvp_version', 'compile', 'positive'):
        require(calls[label]['exit_code'] == 0, 'POSITIVE_EXIT:' + label)
    positive = (folder / 'positive.stdout.txt').read_text(encoding='utf-8')
    stderr = (folder / 'positive.stderr.txt').read_text(encoding='utf-8')
    require(not re.search(r'FATAL|REJECT|ERROR|FAIL', positive + stderr, re.I), 'POSITIVE_ERROR')
    checks = re.findall(r'^CHECK ([A-Z0-9_]+)$', positive, re.M)
    require(len(checks) == expected_checks, 'EXPECTED_CHECK_COUNT')
    require(re.findall(r'^PASS DUAL_SLIDER_ISOLATED checks=([0-9]+)$', positive, re.M)
            == [str(expected_checks)], 'EXACT_PASS_COUNT')
    diagnostics = ('MODE_CDC_DELIVERY', 'MODE_CDC_DELIVERY',
                   'FALLING_FRAME_PROGRESS', 'AUDIO_UNDERRUN')
    for index, diagnostic in enumerate(diagnostics, 1):
        label = 'negative_%d' % index
        stream = (folder / (label + '.stdout.txt')).read_text(encoding='utf-8')
        stream += (folder / (label + '.stderr.txt')).read_text(encoding='utf-8')
        require(calls[label]['exit_code'] == 1, 'NEGATIVE_EXIT')
        require(re.findall(r'REJECT ([A-Z0-9_]+)', stream) == [diagnostic], 'NEGATIVE_DIAGNOSTIC')
        require('PASS DUAL_SLIDER' not in stream, 'NEGATIVE_PASS_MIXED')
    if number == 2:
        required = {'LIVE_RENDERER_REAL_PIXEL', 'LIVE_OUTSIDE_BAR_BACKGROUND',
                    'FALLING_RENDERER_REAL_PIXEL', 'FALLING_EXCLUSIVE_END_BACKGROUND',
                    'RESET_INFLIGHT_NO_GHOST_DELIVERY', 'NO_DISPLAY_DROP_OR_DESYNC'}
        require(required <= set(checks), 'ENHANCED_COVERAGE_MISSING')
        require(checks.count('AUDIO_PROGRESS_DURING_DISPLAY_FRAME') == 47, 'CONCURRENT_FRAME_COUNT')
        require(checks.count('FALLING_CONTINUOUS_INTEGER_ORACLE') == 12, 'FALLING_FRAME_COUNT')
        # Check original numerical capture independently of the CHECK labels.
        frames = re.findall(r'^FRAME (\d+) mode=(\d) .* falling=([0-9a-f]+) ft=([0-9a-f]+) fe=([0-9a-f]+) audio=(\d+)$', positive, re.M)
        require(len(frames) == 47, 'RAW_FRAME_COUNT')
        for frame in range(31, 43):
            row = next(r for r in frames if int(r[0]) == frame)
            top = max(0, min(64, (frame - 32) * 8))
            end = max(0, min(64, (frame - 28) * 8))
            require(int(row[1]) == 1 and int(row[2], 16) == 1
                    and int(row[3], 16) == top and int(row[4], 16) == end,
                    'RAW_FALLING_GEOMETRY')
        require(all(int(frames[i][5]) > int(frames[i-1][5]) for i in range(1, 45)),
                'RAW_AUDIO_PROGRESS')
    return {'directory': folder.name, 'checks': expected_checks,
            'result': result, 'calls': calls, 'before_identity': identity((folder / 'before.json').read_bytes()),
            'after_identity': identity((folder / 'after.json').read_bytes())}


def main():
    require(not DEST.exists(), 'DELIVERY_EXISTS_NO_OVERWRITE')
    require(identity(OLD_ZIP.read_bytes())['sha256'] == OLD_SHA, 'OLD_PACKAGE_DRIFT')
    runs = [verify_run(1, 46), verify_run(2, 99)]
    final = HERE / 'repair_run_02'
    require((RTL / 'dual_slider_candidate.sv').read_bytes() == (final / 'stage/s08.sv').read_bytes(), 'CURRENT_RTL_DRIFT')
    require((TB / 'tb_dual_slider.sv').read_bytes() == (final / 'stage/s09.sv').read_bytes(), 'CURRENT_TB_DRIFT')
    require((HERE / 'run_repair.py').read_bytes() == (final / 'runner_source.py').read_bytes(), 'CURRENT_RUNNER_DRIFT')
    files, paths = {}, {}

    def add(path, name=None):
        require(not path.is_symlink(), 'SYMLINK_REFUSED')
        name = name or path.relative_to(ROOT).as_posix()
        files[name] = path.read_bytes()
        paths[name] = path

    for directory in (RTL, TB):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                add(path)
    for path in sorted(HERE.iterdir()):
        if path.is_file():
            add(path)
    for number in (1, 2):
        for path in sorted((HERE / ('repair_run_%02d' % number)).rglob('*')):
            if path.is_file():
                add(path)
    add(OLD_ZIP)
    add(OLD_ZIP.parent / 'DELIVERY.json')
    for item in read_json(final / 'before.json')['inputs']:
        path = Path(item['path'])
        if (path.is_relative_to(ROOT) and not any(path.is_relative_to(d) for d in (HERE, RTL, TB))):
            require(identity(path.read_bytes()) == {'bytes': item['bytes'], 'sha256': item['sha256']},
                    'READONLY_DEPENDENCY_DRIFT')
            add(path, 'readonly_dependencies/' + path.relative_to(ROOT).as_posix())

    def diff(name, original, current):
        files['diffs/' + name] = ''.join(difflib.unified_diff(
            original.read_text(encoding='utf-8').splitlines(keepends=True),
            current.read_text(encoding='utf-8').splitlines(keepends=True),
            fromfile=original.relative_to(ROOT).as_posix(),
            tofile=current.relative_to(ROOT).as_posix())).encode('utf-8')

    diff('wrapper_parameter_fix.patch', HERE / 'run_night_03/stage/s08.sv', RTL / 'dual_slider_candidate.sv')
    diff('testbench_coverage.patch', HERE / 'repair_run_01/stage/s09.sv', TB / 'tb_dual_slider.sv')
    diff('runner_successor.patch', HERE / 'run_candidate.py', HERE / 'run_repair.py')
    files['REPAIR_VERIFICATION.json'] = encode({
        'status': 'L2_ISOLATED_CANDIDATE_FIXTURE_PASS',
        'observed_utc': datetime.now(timezone.utc).isoformat(),
        'new_repair_runs': runs, 'old_night_tool_starts': 6, 'new_tool_starts': 16,
        'historical_tool_starts_total': 22, 'old_allowance_restored': False,
        'final_positive_checks': 99, 'final_expected_negative_rejections': 4,
        'board_release_allowed': False, 'physical_tool_calls': 0, 'hardware_calls': 0,
        'git_writes_by_this_window': 0, 'forwarding_status': 'PENDING_USER_FORWARD_NOT_DELIVERED'})
    manifest = {name: identity(raw) for name, raw in sorted(files.items())}
    files['MANIFEST.json'] = encode(manifest)
    DEST.mkdir(exist_ok=False)
    archive = DEST / 'DUAL_SLIDER_REPAIR_PASS_20261016.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, raw in sorted(files.items()):
            package.writestr(name, raw)
    with zipfile.ZipFile(archive) as package:
        require(package.testzip() is None, 'ARCHIVE_CRC')
        require(len(package.namelist()) == len(files), 'ARCHIVE_MEMBER_COUNT')
        for name, raw in files.items():
            require(package.read(name) == raw, 'ARCHIVE_READBACK:' + name)
    for name, path in paths.items():
        require(identity(path.read_bytes()) == manifest[name], 'FILE_CHANGED_DURING_SEAL')
    receipt = {'archive': archive.name, **identity(archive.read_bytes()), 'members': len(files),
               'status': 'L2_ISOLATED_CANDIDATE_FIXTURE_PASS', 'positive_checks': 99,
               'expected_negative_rejections': 4, 'crc_and_all_member_sha_verified': True,
               'source_unchanged_during_seal': True, 'old_package_sha256': OLD_SHA,
               'new_tool_starts': 16, 'historical_tool_starts_total': 22,
               'published': False, 'publisher': '总控', 'board_release_allowed': False,
               'hardware_calls': 0, 'eda_calls': 0,
               'forwarding_status': 'PENDING_USER_FORWARD_NOT_DELIVERED'}
    with (DEST / 'DELIVERY.json').open('xb') as stream:
        stream.write(encode(receipt))
    with (DEST / 'REPAIR_VERIFICATION.json').open('xb') as stream:
        stream.write(files['REPAIR_VERIFICATION.json'])
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
