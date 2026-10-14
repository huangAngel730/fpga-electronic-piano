"""One fresh, bounded compile-only comparison in the approved host environment."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / 'code/output/m3_t052_observer_repair_prepare_20261014_10'
PLAN = ROOT / 'code/output/m3_t052_environment_recovery_diag_plan_20261014_01'
OUTPUT = ROOT / 'code/output/m3_t052_environment_recovery_diag_run_20261014_01'
PARENT = Path(str(OUTPUT) + '_parent')
CONFIG = PLAN / 'config.json'
LEGACY = HERE / 't052_compile_only_diagnostic_20261014.py'
HELPERS = [LEGACY, HERE / 'runner.py', HERE / 'runner_tail_20261013.py',
           HERE / 'windows_job.py', HERE / 'supervisor_20261013.py', Path(__file__)]
NAMES = {'dut': 'readonly/t052_polyphony_test_source.sv',
         'dds': 'readonly/dds_oscillator.sv', 'mixer': 'readonly/pcm_mixer_4voice.sv',
         'rom': 'readonly/sine_1024_8192.mem', 'observer': 't052_public_observer_v2.sv',
         'tb': 'tb_t052_control_128_v2.sv', 'driver_mem': 'controls_128.hex'}


def ident(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def identity(path):
    return ident(Path(path).read_bytes())


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
                      + '\n').encode('utf-8'))


def check(mapping):
    for path, expected in mapping.items():
        need(identity(path) == expected, 'IDENTITY_DRIFT:' + path)


def prepare():
    need(platform.node() == 'LAPTOP-KSS1MRR7', 'MACHINE')
    need(not PLAN.exists() and not OUTPUT.exists() and not PARENT.exists(), 'OCCUPIED')
    manifest = read(OLD / 'prepared/manifest.json')
    old_config = read(OLD / 'prepared/config.json')
    old_step = read(OLD / 'prepared/actual_once/compile.receipt.json')
    need(old_step['exit_code'] == 3221225477, 'OLD_FAILURE')
    need(len(manifest['tools']) == 1014, 'TOOL_COUNT')
    helpers = {str(p.resolve()): identity(p) for p in HELPERS}
    tools = {}
    for name, item in manifest['tools'].items():
        expected = {k: item[k] for k in ('bytes', 'sha256')}
        need(identity(item['path']) == expected, 'TOOL_DRIFT:' + name)
        tools[name] = {'path': str(Path(item['path']).resolve()), **expected}
    captured = {}
    for role, relative in NAMES.items():
        raw = (OLD / 'prepared/actual_once/work' / relative).read_bytes()
        item = manifest['sources'][role]
        need(ident(raw) == {k: item[k] for k in ('bytes', 'sha256')}, 'SOURCE:' + role)
        captured[relative] = raw
    for key in ('plan', 'calendar'):
        item = manifest[key]
        raw = (ROOT / item['path']).read_bytes()
        need(ident(raw) == {k: item[k] for k in ('bytes', 'sha256')}, key)
        captured['reference/' + key + '/' + Path(item['path']).name] = raw
    environment = dict(old_config['environment'])
    environment.update(TEMP=str((OUTPUT / 'work').resolve()), TMP=str((OUTPUT / 'work').resolve()))
    preserved = {str(p.resolve()): identity(p) for p in OLD.rglob('*') if p.is_file()}
    PLAN.mkdir(parents=True)
    sources = {}
    for name, raw in captured.items():
        p = PLAN / 'inputs' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as stream:
            stream.write(raw)
        sources[name] = {'path': str(p.resolve()), **ident(raw)}
    config = {
        'schema': 'T052_COMPILE_ONLY_DIAGNOSTIC_V1',
        'permission': 'USER_REQUEST_ENVIRONMENT_RECOVERY_COMPILE_ONLY; FORMAL_CAPTURE_REQUIRES_NEW_PERMIT',
        'machine': platform.node(), 'budgets_seconds': {'outer_total': 120, 'compile': 90},
        'calls': {'compile': 1, 'vvp': 0, 'checker': 0, 'gowin': 0, 'version_queries': 0},
        'automatic_retries': 0, 'output': str(OUTPUT.resolve()),
        'parent_output': str(PARENT.resolve()), 'marker': str((PLAN / 'consumed.json').resolve()),
        'compile_argv': old_step['argv'], 'environment': environment,
        'sources': sources, 'tools': tools, 'helpers': helpers,
        'preserved_old_evidence': preserved,
        'worker': {'path': str(Path(__file__).resolve()), **identity(__file__)},
        'T052_complete': False,
    }
    write(CONFIG, config)
    result = {'status': 'PREPARED_NOT_EXECUTED', 'config': identity(CONFIG),
              'path': str(CONFIG), 'tools': len(tools), 'source_roles': len(NAMES)}
    write(PLAN / 'prepare_receipt.json', result)
    print(json.dumps(result))


def load_checked(expected_sha):
    raw = CONFIG.read_bytes()
    need(ident(raw)['sha256'] == expected_sha, 'CONFIG_SHA')
    c = json.loads(raw)
    check(c['helpers'])
    check(c['preserved_old_evidence'])
    spec = importlib.util.spec_from_file_location('t052_recovery_legacy', LEGACY)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    legacy.__file__ = str(Path(__file__).resolve())
    original_load = legacy.load_config

    def checked(path, sha):
        value, identity_value = original_load(path, sha)
        check(value['helpers'])
        check(value['preserved_old_evidence'])
        return value, identity_value

    legacy.load_config = checked
    return c, legacy


def seal():
    c = read(CONFIG)
    record = read(OUTPUT / 'receipt.json')
    parent = read(PARENT / 'observation.json')
    check(c['helpers'])
    check(c['preserved_old_evidence'])
    need(record['sources_before'] == record['sources_after'], 'SOURCES_AFTER')
    need(record['tools_before'] == record['tools_after'], 'TOOLS_AFTER')
    need(record['work_inputs_before'] == record['work_inputs_after'], 'WORK_AFTER')
    need(len(record['steps']) == 1, 'STEP_COUNT')
    need(record['artifact_executed'] is False, 'ARTIFACT_EXECUTED')
    target = PLAN / 'RESULT.zip'
    files = {}
    for prefix, directory in [('plan', PLAN), ('run', OUTPUT), ('parent', PARENT)]:
        for p in directory.rglob('*'):
            if p.is_file():
                files[prefix + '/' + p.relative_to(directory).as_posix()] = p.read_bytes()
    for p in HELPERS:
        files['implementation/' + p.name] = p.read_bytes()
    files['MANIFEST.json'] = (json.dumps({k: ident(v) for k, v in files.items()},
                                       sort_keys=True, indent=2) + '\n').encode()
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in files.items():
            z.writestr(name, raw)
    with zipfile.ZipFile(target) as z:
        need(z.testzip() is None, 'ZIP_CRC')
        for name, raw in files.items():
            need(z.read(name) == raw, 'ZIP_MEMBER:' + name)
    result = {'status': record['status'], 'compile_exit': record['steps'][0]['exit_code'],
              'compile_seconds': record['steps'][0]['elapsed_seconds'],
              'parent_exit': parent['exit_code'], 'parent_seconds': parent['elapsed_seconds'],
              'config_sha': identity(CONFIG)['sha256'], 'artifact_executed': False,
              'tools_unchanged': len(record['tools_after']), 'package': str(target),
              'package_identity': identity(target), 'T052_complete': False}
    write(PLAN / 'RESULT.json', result)
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'verify', 'launch', 'worker', 'seal'])
    parser.add_argument('--config')
    parser.add_argument('--config-sha')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
        return 0
    if args.mode == 'seal':
        seal()
        return 0
    c, legacy = load_checked(args.config_sha)
    if args.mode == 'verify':
        legacy.load_config(CONFIG, args.config_sha)
        legacy.snapshot(c['sources'])
        legacy.snapshot(c['tools'])
        need(not OUTPUT.exists() and not PARENT.exists()
             and not Path(c['marker']).exists(), 'NOT_FRESH')
        print('VERIFIED_COMPILE_ONLY_ZERO_TOOL_CALLS')
        return 0
    if args.mode == 'worker':
        os.environ.clear()
        os.environ.update(c['environment'])
        result = legacy.execute_worker(CONFIG, args.config_sha)
    else:
        result = legacy.launch(CONFIG, args.config_sha)
    print(json.dumps({k: result.get(k) for k in ('status', 'exit_code', 'failure')}))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
