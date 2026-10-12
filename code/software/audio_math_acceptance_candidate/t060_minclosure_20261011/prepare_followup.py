"""New C follow-up package and read-only tool identity; NO HDL commands."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from controlled_runner import Budget, dump, identity, step  # noqa: E402
from fixtures import cancel_plan, lifecycle_plan  # noqa: E402
from prepare import ROOT, SOURCES, TB_REL, load_roms, prepare, sha  # noqa: E402

SUFFIX = {'1510': {'rst_n': 0}, '1514': {'rst_n': 1},
          '1518': {'event': 149032478953177088}, '1540': {'frame': 1}}
OLD_B_SHA = '41dd5f908a04adce266b65c36b177175ce22ee8e50eb7db1299c212a715308b1'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def plan_proof():
    b = cancel_plan(load_roms())
    old = json.loads(json.dumps(b))
    for key, value in SUFFIX.items():
        if old['inputs'].pop(key) != value:
            raise ValueError('FOLLOWUP_NOT_EXACT_SUFFIX')
    if sha(encoded(old)) != OLD_B_SHA:
        raise ValueError('FOLLOWUP_OLD_B_IDENTITY')
    return dict(original_B_sha256=OLD_B_SHA, B_sha256=sha(encoded(b)),
                A_sha256=sha(encoded(lifecycle_plan())),
                appended_inputs=SUFFIX, end_cycle=b['end_cycle'],
                original_cases=b['cases'], original_B_recovered_by_removing_only_four_inputs=True,
                A_execution='NOT_RERUN; only plan generated',
                predicted_recovery_cycle=1571, predicted_recovery_id=1,
                origin='SYNTHETIC_SOFTWARE_TEST', RTL_run=False)


def build(out, suite, budget):
    out, suite = out.resolve(), suite.resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'code/output'):
        raise ValueError('FOLLOWUP_OUTPUT_SCOPE_OR_EXISTS')
    out.mkdir(parents=True)
    proof = plan_proof()
    dump(out / 'plan_delta.json', proof)
    # Copy original inputs and dependencies; this does NOT simulate A.
    portable = out / 'portable'
    prepared = prepare(portable)
    tools = {name: str(suite / ('bin/' + name + '.exe')) for name in ('yosys', 'iverilog', 'vvp')}
    tools['python'] = str(Path(sys.executable).resolve())
    # Conservative superset: tool executables + all DLLs in both runtime dirs,
    # all Icarus backends/modules and Yosys data/plugins (includes slang.so).
    paths = {Path(p) for p in tools.values()}
    for base in (suite / 'bin', suite / 'lib'):
        paths.update(base.glob('*.dll'))
    for base in (suite / 'lib/ivl', suite / 'share/yosys'):
        paths.update(p for p in base.rglob('*') if p.is_file())
    tool_files = {}
    for path in sorted(paths):
        budget.limit(90)
        tool_files[path.as_posix()] = identity(path)
    tools = {name: Path(path).as_posix() for name, path in tools.items()}
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join((str(suite / 'bin'), str(suite / 'lib'),
                                 str(Path(os.environ['SystemRoot']) / 'System32')))
    version_steps = []
    for name, argv in (
            ('yosys_version', [tools['yosys'], '-V']),
            ('iverilog_version', [tools['iverilog'], '-V']),
            ('vvp_version', [tools['vvp'], '-V']),
            ('read_slang_help', [tools['yosys'], '-Q', '-T', '-m',
                str(suite / 'share/yosys/plugins/slang.so'), '-p', 'help read_slang'])):
        version_steps.append(step(out, name, argv, out, budget, 90, env=env))
    help_text = (out / 'read_slang_help.stdout.txt').read_text(encoding='utf-8')
    if 'read_slang' not in help_text or 'No such command' in help_text:
        raise ValueError('FOLLOWUP_SLANG_HELP_UNAVAILABLE')
    for path, expected in tool_files.items():
        budget.limit(90)
        if identity(path) != expected:
            raise ValueError('FOLLOWUP_TOOL_IDENTITY_DRIFT')
    config = dict(schema=1, execution_authorized=False, groups=['A', 'B'],
        proposed_execution_machine=dict(role='M3_CURRENT_LOCAL_MACHINE',
            computer_name=os.environ.get('COMPUTERNAME', 'UNKNOWN'),
            tool_identity_scope='THIS_MACHINE_ONLY; NOT_M2_TOOL_SUBSTITUTION'),
        total_seconds=900, tools=tools, tool_files=tool_files,
        version_queries=version_steps, inputs=prepared['inputs'],
        software_relative=HERE.relative_to(ROOT).as_posix(), tb_relative=TB_REL.as_posix(),
        compile_sources=['sources/' + n + '.sv' for n in SOURCES if n != 'voice_allocator_4'],
        end_cycles={'A': 4095000, 'B': 1600},
        mutations={'A': [['retirement_reuse_wrong_generation', 'MINCLOSURE_RETIRE_IDENTITY'],
                         ['accepted_panic_missing_off', 'MINCLOSURE_PANIC_RELEASE']],
                   'B': [['frame_accepts_old_result', 'MINCLOSURE_CANCEL_OLD_ID'],
                         ['advance_rolled_back', 'MINCLOSURE_ADVANCE_NONROLLBACK_MATH']]},
        old_body_status='V0295 REUSED; no 22 checks/A trajectory replay',
        t060_complete=False, RTL_runs=0, EDA_runs=0)
    dump(portable / 'CONTROLLED_CONFIG_NOT_AUTHORIZED.json', config)
    return dict(portable=str(portable), config=identity(portable / 'CONTROLLED_CONFIG_NOT_AUTHORIZED.json'),
                plans=proof, tool_files=len(tool_files), version_steps=version_steps,
                read_only_tool_queries=4, HDL_commands=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--suite', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.suite, Budget(300))))
