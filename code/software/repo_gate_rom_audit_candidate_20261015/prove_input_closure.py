"""Prove the precise include set retains all actual source/tool identities."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rom_gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--configs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    old, new = (rom_gate.read_json(path) for path in (args.before, args.after))
    same = all(old['files'].get(key) == value for key, value in new['files'].items())
    tools_same = old['tools'] == new['tools'] and old['tool_root'] == new['tool_root']
    records = []
    for config in args.configs:
        document = rom_gate.read_json(config)
        root, stage, tools = (Path(document[key]) for key in ('repo', 'output', 'tool_root'))
        commands_same = document['commands'] == rom_gate.commands(root, stage, tools, document['top'])
        env_same = document['environment'] == rom_gate.environment(tools, stage)
        records.append({'config': str(config.resolve()), 'sha256': rom_gate.sha(config),
                        'commands_unchanged': commands_same, 'environment_unchanged': env_same})
    passed = same and tools_same and all(row['commands_unchanged'] and row['environment_unchanged'] for row in records)
    result = {'passed': passed, 'before_sha256': rom_gate.sha(args.before),
              'after_sha256': rom_gate.sha(args.after),
              'old_inputs': len(old['files']), 'precise_inputs': len(new['files']),
              'all_retained_input_sha_equal': same, 'all_tool_sha_equal': tools_same,
              'removed_unused_historical_headers': sorted(set(old['files']) - set(new['files'])),
              'original_execution_commands': records, 'tool_calls': 0}
    output = args.output.resolve()
    root = Path(__file__).resolve().parents[3]
    if output.parent != root / 'code/output' or not output.name.startswith('repo_gate_rom_audit_'):
        parser.error('fresh task output required')
    output.mkdir(exist_ok=False)
    rom_gate.write_json(output / 'proof.json', result)
    print(json.dumps({'passed': passed, 'proof': str(output / 'proof.json')}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
