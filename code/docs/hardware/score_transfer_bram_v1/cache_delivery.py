"""T062 scoped evidence/gates. No Git index, network, or hardware operations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
DOC = Path(__file__).resolve().parent
OWN = ('code/rtl/input/score_transfer_bram_candidate',
       'code/tb/input/score_transfer_bram_candidate',
       'code/software/score_transfer_bram_test_candidate',
       'code/docs/hardware/score_transfer_bram_v1')
RUNNER = 'code/scripts/run_m3_score_transfer_bram_acceptance.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def inventory():
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached',
                                   '--others', '--exclude-standard'], cwd=ROOT, timeout=30)
    return {name: sha(ROOT/name) for name in sorted(set(raw.decode('utf-8').split('\0')))
            if name and (ROOT/name).is_file()}


def execute(out, label, command, timeout, environment=None):
    start = time.monotonic()
    with (out/(label+'.stdout.bin')).open('xb') as stdout, \
            (out/(label+'.stderr.bin')).open('xb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                   env=environment)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            killed = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                    capture_output=True, timeout=20)
            if killed.returncode and process.poll() is None:
                process.kill()
            process.wait(timeout=20)
    return dict(command=command, cwd=str(ROOT), elapsed=time.monotonic()-start,
                timeout=timeout, timed_out=timed_out, exit_code=process.returncode,
                stdout_sha256=sha(out/(label+'.stdout.bin')),
                stderr_sha256=sha(out/(label+'.stderr.bin')))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=('gate', 'seal', 'verify', 'probe', 'audit'))
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--build', type=Path)
    cli.add_argument('--simulation', type=Path)
    cli.add_argument('--gate', type=Path)
    args = cli.parse_args()
    out = args.output.resolve()
    out.relative_to(ROOT/'code/output')
    if args.mode == 'verify':
        manifest = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
        archive_path = out/'T062_M2_HANDOFF.zip'
        if sha(archive_path) != manifest['zip_sha256']:
            raise ValueError('ZIP identity')
        with zipfile.ZipFile(archive_path) as archive:
            if set(archive.namelist()) != set(manifest['members']) or archive.testzip():
                raise ValueError('member inventory/CRC')
            for name, digest in manifest['members'].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    raise ValueError('member identity: '+name)
                if name.lower().endswith('.fs'):
                    raise ValueError('unreleased bitstream in handoff')
        print('PASS_T062_PACKAGE', len(manifest['members']), manifest['zip_sha256'])
        return 0
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), out/'delivery_runner.py')
    if args.mode=='probe':
        tool = ROOT.parent.parent/'138K/tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe'
        tcl = DOC/'probe_sta_coverage.tcl'
        step = execute(out, 'probe', [str(tool), str(tcl)], 30)
        shutil.copyfile(tcl, out/tcl.name)
        dump(out/'receipt.json', dict(read_only=True, no_build=True, step=step,
             tool_sha256=sha(tool), script_sha256=sha(tcl)))
        print('PROBE_COMPLETE', step['exit_code'])
        return step['exit_code']
    if args.mode=='audit':
        build = args.build.resolve()
        build.relative_to(ROOT/'code/output')
        reviewer = DOC/'sta_review.py'
        step = execute(out, 'audit', [sys.executable, '-B', '-X', 'utf8',
                                     str(reviewer), str(build)], 30)
        dump(out/'receipt.json', dict(step=step, reviewer_sha256=sha(reviewer),
             audit_sha256=sha(build/'sta_review.json'), do_not_program=True))
        print(json.loads((build/'sta_review.json').read_text(encoding='utf-8'))['status'])
        return step['exit_code']
    if args.mode == 'gate':
        before = inventory()
        python = str(Path(sys.executable))
        steps = {}
        for label, name in (('sta_tests', 'test_sta_review.py'),
                            ('execution_tests', 'test_timing_build.py')):
            steps[label] = execute(out, label, [python, '-B', '-X', 'utf8', str(DOC/name)], 30)
        shell = shutil.which('powershell.exe')
        environment = os.environ.copy()
        environment['PATH'] = str(Path(python).parent)+os.pathsep+environment.get('PATH','')
        environment['PYTHONUTF8']='1'
        environment['PYTHONDONTWRITEBYTECODE']='1'
        steps['repo_gates'] = execute(out, 'repo_gates', [shell, '-NoProfile',
            '-ExecutionPolicy', 'Bypass', '-File', str(ROOT/'code/scripts/check_repo.ps1')], 900,
            environment)
        after = inventory()
        changed = [name for name in sorted(set(before)|set(after))
                   if before.get(name) != after.get(name)]
        log = (out/'repo_gates.stdout.bin').read_text(encoding='utf-8', errors='replace')
        gates_passed = (log.count('[PASS]') == 9 and '[FAIL]' not in log and
                        all(step['exit_code']==0 and not step['timed_out'] for step in steps.values()))
        dump(out/'receipt.json', dict(status='NINE_GATES_PASS_WORKTREE_ONLY'
             if gates_passed else 'FAIL_GATES', steps=steps,
             inputs_before=before, inputs_after=after, changed_during_gate=changed,
             process_environment_overrides=dict(PATH_prepend=str(Path(python).parent),
                 PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', system_environment_modified=False),
             exact_tree_frozen=not changed, committed=False, pushed=False,
             index_modified=False, do_not_program=True,
             tool_sha256={python:sha(Path(python)), shell:sha(Path(shell))}))
        print('NINE_GATES_PASS_WORKTREE_ONLY' if gates_passed else 'FAIL_GATES',
              'concurrent_input_changes', len(changed))
        return int(not gates_passed)

    build, simulation, gate = [path.resolve() for path in
                               (args.build, args.simulation, args.gate)]
    for path in (build, simulation, gate):
        path.relative_to(ROOT/'code/output')
    sim = json.loads((simulation/'receipt.json').read_text(encoding='utf-8'))
    native = json.loads((build/'receipt.json').read_text(encoding='utf-8'))
    audit = json.loads((build/'sta_review.json').read_text(encoding='utf-8'))
    gate_receipt = json.loads((gate/'receipt.json').read_text(encoding='utf-8'))
    if sim['status']!='PASS_MODULE_SIMULATION_ONLY':
        raise ValueError('simulation prerequisite')
    if gate_receipt['status']!='NINE_GATES_PASS_WORKTREE_ONLY':
        raise ValueError('nine gate prerequisite')
    if audit['build_receipt_sha256'] != sha(build/'receipt.json'):
        raise ValueError('audit identity')
    for rel, digest in sim['input_sha256'].items():
        if sha(ROOT/rel) != digest:
            raise ValueError('functional input changed: '+rel)
    for directory, receipt in ((simulation, sim), (build, native)):
        for rel, digest in receipt['output_sha256'].items():
            if sha(directory/rel) != digest:
                raise ValueError('executed artifact changed: '+str(directory/rel))
    selected = {}
    for rel in sim['input_sha256']:
        selected[rel] = ROOT/rel
    for rel in OWN:
        for path in (ROOT/rel).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and not any(
                    item.startswith(('EVIDENCE_', 'TIMING_EVIDENCE_')) for item in path.parts):
                selected[path.relative_to(ROOT).as_posix()] = path
    selected[RUNNER] = ROOT/RUNNER
    excluded = {}
    for folder in (simulation, build, gate,
                   ROOT/'code/output/m4_t062_cache_sim_20261010_01',
                   ROOT/'code/output/m4_t062_cache_build_20261010_01',
                   ROOT/'code/output/m4_t062_cache_build_20261010_02',
                   ROOT/'code/output/m4_t062_cache_audit_20261010_03',
                   ROOT/'code/output/m4_t062_gate_20261010_01',
                   ROOT/'code/output/m4_t062_sta_probe_20261010_01'):
        for path in folder.rglob('*'):
            if not path.is_file() or 'work' in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if path.suffix.lower() in ('.fs', '.wlf', '.db', '.p', '.ga', '.rdb', '.posp', '.bin', '.binx') and not path.name.endswith(('.stdout.bin', '.stderr.bin')):
                excluded[rel] = dict(bytes=path.stat().st_size, sha256=sha(path))
                continue
            selected[rel] = path
    old = ROOT/'code/output/m3_score_bram_timing_build_20261010_05'
    for name in ('receipt.json', 'pnr_started.json', 'pnr_process.json', 'pnr.stdout.bin',
                 'pnr.stderr.bin', 'module.sdc', 'synth.tcl', 'pnr.tcl',
                 'synthesis_runner.py', 'pnr_runner.py',
                 'project/score_ram/impl/gwsynthesis/score_ram_syn_rsc.xml',
                 'project/score_ram/impl/gwsynthesis/score_ram_syn.rpt.html',
                 'project/score_ram/impl/pnr/cmd.do'):
        path = old/name
        selected[path.relative_to(ROOT).as_posix()] = path
    completion = ROOT/'code/output/m3_score_bram_timing_build_20261010_05_launch/job/completion.json'
    selected[completion.relative_to(ROOT).as_posix()] = completion
    members = {name:sha(path) for name,path in sorted(selected.items())}
    internal = out/'PACKAGED_INPUTS.json'
    dump(internal, dict(status=audit['status'], members=members,
         excluded_quarantined=excluded, complete_system=False, do_not_program=True,
         committed=False, pushed=False, contains_only_T062_sources=True))
    selected['PACKAGED_INPUTS.json']=internal
    members['PACKAGED_INPUTS.json']=sha(internal)
    archive_path = out/'T062_M2_HANDOFF.zip'
    with zipfile.ZipFile(archive_path, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name,path in sorted(selected.items()):
            archive.write(path, name)
    dump(out/'manifest.json', dict(status=audit['status'], members=members,
         zip_sha256=sha(archive_path), zip_bytes=archive_path.stat().st_size,
         final_build=str(build), final_simulation=str(simulation), excluded=excluded,
         complete_system=False, board_timing_verified=False, do_not_program=True,
         committed=False, pushed=False, release_coordination='主对话2协调，未操作索引',
         gate_source_changed=gate_receipt['changed_during_gate']))
    print('SEALED_T062', len(members), archive_path.stat().st_size, sha(archive_path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
