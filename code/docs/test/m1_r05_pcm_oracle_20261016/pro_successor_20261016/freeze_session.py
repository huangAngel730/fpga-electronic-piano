"""Freeze local Git facts and one bounded process-only direct fetch attempt."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name, argv, env, timeout=45):
    folder = HERE / 'SESSION' / name
    folder.mkdir(parents=True, exist_ok=False)
    started = time.time()
    timed_out = False
    with (folder / 'stdout.bin').open('xb') as out, (folder / 'stderr.bin').open('xb') as err:
        process = subprocess.Popen(argv, cwd=REPO, env=env, stdout=out, stderr=err)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            code = process.wait()
    result = {'argv': argv, 'cwd': str(REPO), 'exit_code': code,
              'timeout': timed_out, 'outer_bound_seconds': timeout,
              'started_epoch': started, 'elapsed_seconds': time.time() - started,
              'streams': {name: {'bytes': (folder / name).stat().st_size,
                                   'sha256': sha(folder / name)}
                          for name in ('stdout.bin', 'stderr.bin')}}
    (folder / 'RECEIPT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    env = os.environ.copy()
    git = ['git', '-c', 'core.longpaths=true']
    facts = {}
    for label, args in (
            ('head', ['rev-parse', 'HEAD']),
            ('origin_develop_before', ['rev-parse', 'origin/develop']),
            ('working_tree', ['status', '--short', '--branch']),
            ('index', ['diff', '--cached', '--name-only']),
            ('git_version', ['--version'])):
        facts[label] = run(label, git + args, env)
    # Preserve the existing process/global configuration. The attempt uses only
    # the configured origin URL, without a proxy, and never changes Git config.
    removed = []
    for key in list(env):
        if key.upper() in {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'}:
            removed.append(key)
            del env[key]
    facts['direct_fetch'] = run('direct_fetch', git + [
        '-c', 'http.proxy=', '-c', 'http.lowSpeedLimit=1',
        '-c', 'http.lowSpeedTime=20', 'fetch', 'origin', 'develop'], env)
    facts['direct_fetch']['proxy_environment_names_removed_in_child_only'] = removed
    facts['origin_develop_after'] = run('origin_develop_after', git + ['rev-parse', 'origin/develop'], env)
    receipt = {'schema': 'M1_PRO_SESSION_LOCAL_FACTS_V1',
               'python': {'path': sys.executable, 'version': sys.version,
                          'sha256': sha(Path(sys.executable))},
               'machine': platform.node(), 'git_commands': facts,
               'task_received_sha256': sha(HERE / 'TASK_RECEIVED.md'),
               'initial_clean_tree_observed_before_any_new_writes': True,
               'initial_clean_tree_basis': 'Root exec output c362e3 before delegated writes; this tool transcript is not fabricated raw output',
               'earlier_fetch_failure': 'Default configured connection failed via127.0.0.1 after2053ms, root tool output c362e3; not a raw stream file',
               'new_model_or_hdl_or_eda_tests_in_this_snapshot': False,
               'global_network_or_git_configuration_changed': False}
    (HERE / 'SESSION' / 'OPENING_RECEIPT.json').write_text(
        json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'head': (HERE / 'SESSION/head/stdout.bin').read_text().strip(),
                      'direct_fetch': facts['direct_fetch'],
                      'task_received_sha256': receipt['task_received_sha256']}, indent=2))


if __name__ == '__main__':
    main()
