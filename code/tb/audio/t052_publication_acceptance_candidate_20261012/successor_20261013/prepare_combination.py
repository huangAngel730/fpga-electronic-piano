"""Freeze the P0-1/P0-2 proposed input contract; no tools are executed."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import schedule_check as schedule

ROOT = schedule.ROOT
DOCS = ROOT / ('code/docs/test/t052_publication_acceptance_20261012/'
               'CONTROL_PREPARATION_20261012')


def spec(path):
    path = Path(path)
    return {'path': path.relative_to(ROOT).as_posix()
            if path.is_relative_to(ROOT) else path.as_posix(), **schedule.identity(path)}


def prepare():
    old = json.loads((DOCS / 'source_manifest.json').read_text(encoding='utf-8'))
    schedule.check()
    sources = {}
    for role, archive, member in (
            ('dut', 'raw_archive', 'received_M1_v5/code/rtl/audio/t052_polyphony_test_source.sv'),
            ('dds', 'readonly_archive', 'dds_oscillator.sv'),
            ('mixer', 'readonly_archive', 'pcm_mixer_4voice.sv'),
            ('rom', 'readonly_archive', 'sine_1024_8192.mem')):
        record = old[archive]
        schedule.need(schedule.identity(ROOT / record['path']) ==
                      {k: record[k] for k in ('bytes', 'sha256')}, 'ARCHIVE_IDENTITY')
        sources[role] = {'path': record['path'], 'member': member,
                         **record['members'][member]}
    sources.update(tb=spec(schedule.TB), observer=spec(schedule.OBSERVER),
                   driver_mem=spec(schedule.MEM))
    tools = {}
    for role, key in (('compile', 'iverilog'), ('runtime', 'vvp')):
        original = old['tools_proposed'][key]
        actual = spec(Path(original['path']))
        schedule.need({k: actual[k] for k in ('bytes', 'sha256')} ==
                      {k: original[k] for k in ('bytes', 'sha256')},
                      'PROPOSED_TOOL_DRIFT:' + role)
        tools[role] = actual
    compile_argv = [tools['compile']['path'], '-g2012', '-s', 'tb_t052_control_128_v2',
                    '-o', 't052_control_v2.vvp', 'readonly/t052_polyphony_test_source.sv',
                    'readonly/dds_oscillator.sv', 'readonly/pcm_mixer_4voice.sv',
                    't052_public_observer_v2.sv', 'tb_t052_control_128_v2.sv']
    run_argv = [tools['runtime']['path'], 't052_control_v2.vvp']
    for key, role in (('DUT', 'dut'), ('ROM', 'rom'), ('PLAN', None),
                      ('TB', 'tb'), ('OBSERVER', 'observer')):
        sha = schedule.PLAN_SHA if role is None else sources[role]['sha256']
        run_argv.append('+' + key + '_SHA=' + sha)
    run_argv.append('+TOOL_SHA=' + tools['runtime']['sha256'])
    return {'schema': 'T052_P0_STATIC_COMBINATION_V2', 'execution_authorized': False,
            'plan': spec(schedule.PLAN),
            'calendar': spec(ROOT / 'code/software/t052_publication_acceptance_candidate_20261012/publication.py'),
            'sources': sources, 'tools': tools, 'compile_argv': compile_argv,
            'run_argv': run_argv}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    schedule.need(not args.output.exists(), 'OUTPUT_EXISTS')
    manifest = prepare()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'manifest': spec(args.output), 'execution_authorized': False,
                      'tool_calls': 0}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
