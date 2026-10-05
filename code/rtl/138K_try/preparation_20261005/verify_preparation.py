"""Verify retained preparation evidence without rerunning EDA or touching the repo."""
from datetime import datetime
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re

HERE = Path(__file__).resolve().parent
ROOT = Path('E:/FPGA/GAOYUNFPGA/138K_try').resolve()
if HERE != ROOT / 'preparation_20261005':
    raise ValueError('Unexpected evidence directory')


def safe(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError('Evidence path outside isolated directory: ' + str(path))
    return resolved


def sha(path):
    return hashlib.sha256(safe(path).read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


literal = re.compile(r'"([^"\r\n]+\.(?:mem|hex|svh))"')


def canonical(data):
    return literal.sub(lambda m: '"<data:' + PureWindowsPath(m[1]).name + '>"',
                       data.decode('utf-8'))


proof = json.loads((ROOT / 'm3_continuation_20261005/proven_bundle_manifest.json')
                   .read_text(encoding='utf-8'))
proof_by_name = {r['name']: r for r in proof['records']}
relocation = load('relocation_manifest.json')
assert len(proof_by_name) == len(relocation['records']) == 55
assert relocation['frozen_project_entries_available'] == 46
assert relocation['frozen_project_entries_expected'] == 47
assert relocation['PnR_of_V0171_executed'] is False
replacements = 0
for record in relocation['records']:
    old, new = safe(record['original']), safe(record['relocated'])
    proven = proof_by_name[record['name']]
    assert old == safe(proven['copy'])
    assert sha(old) == proven['sha256'] == record['old_sha256']
    assert sha(new) == record['new_sha256']
    if old.suffix in ('.v', '.sv'):
        assert canonical(old.read_bytes()) == canonical(new.read_bytes())
        for match in literal.finditer(new.read_text(encoding='utf-8')):
            assert safe(match[1]).is_relative_to(HERE / 'relocated_bundle')
            assert safe(match[1]).is_file()
    else:
        assert old.read_bytes() == new.read_bytes()
    replacements += len(record['changes'])
assert replacements == relocation['replaced_path_occurrences'] == 20

toolchain = load('toolchain_results.json')
assert len(toolchain['results']) == 3
assert {r['label'] for r in toolchain['results']} == {'60K', '138K_B', '138K_C'}
assert toolchain['frozen_V0171_PnR_executed'] is False
tool_artifacts = 0
for record in toolchain['results']:
    assert record['errors'] == [] and record['observed_cli_exit_code'] == 0
    assert record['programmed'] is False
    assert record['metadata']['Tool Version'] == 'V1.9.11.03 Education'
    for path, digest in record['artifact_SHA256'].items():
        assert sha(path) == digest, path
        tool_artifacts += 1

regression = load('frozen_regression_results.json')
assert regression['passed'] is True and len(regression['results']) == 7
assert regression['DUT_modified'] is False and regression['bench_modified'] is False
assert regression['programmed'] is False
for path, digest in regression['bench_source_SHA256'].items():
    assert sha(HERE / 'regression/bench_original' / PureWindowsPath(path).name) == digest
for record in regression['results']:
    assert record['passed'] is True
    assert record['compile_exit'] == record['run_exit'] == 0
    for name, digest in record['DUT_SHA256'].items():
        assert sha(HERE / 'relocated_bundle/sources' / name) == digest
    for name, digest in record['log_SHA256'].items():
        assert sha(HERE / 'regression' / record['case'] / name) == digest
    log = (HERE / 'regression' / record['case'] / 'run.log').read_text(encoding='utf-8')
    assert record['pass_lines'] and all(line in log for line in record['pass_lines'])
    assert not re.search(r'FATAL:|\bFAIL\b|\bERROR:|RUNNER_TIMEOUT', log)

selftest = (HERE / 'collector_selftest.log').read_text(encoding='utf-8')
assert 'Ran 20 tests' in selftest and selftest.rstrip().endswith('OK')
assert 'PASS' in (HERE / 'tool_probe_sim.log').read_text(encoding='utf-8')
evidence_names = [
    'README.md', 'M2_准备阶段交接.md', '138K_compatibility_review.md',
    'toolchain_results.json', 'relocation_manifest.json', 'frozen_regression_results.json',
    'collector_selftest.log', 'tool_probe_sim.log', 'collect_sta_results.py',
    'test_collect_sta_results.py', 'relocate_frozen_inputs.py',
    'run_frozen_regression.py', 'verify_preparation.py',
]
receipt = {
    'time': datetime.now().astimezone().isoformat(), 'passed': True,
    'scope': 'Retained evidence integrity only; no new EDA run or repo mutation',
    'proven_original_files_rehashed': 55, 'relocated_files_rehashed': 55,
    'path_only_replacements_verified': replacements,
    'tool_probe_PnR_passes': 3, 'tool_artifact_hashes_verified': tool_artifacts,
    'functional_regression_passes': 7, 'collector_selftest_passes': 20,
    'V0171_whole_design_PnR_executed': False, 'programmed': False,
    'original_repo_written': False,
    'evidence_SHA256': {name: sha(HERE / name) for name in evidence_names},
}
(HERE / 'verification_receipt.json').write_text(
    json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('PASS evidence integrity: 55 original + 55 relocated files; 20 path-only replacements')
print(f'PASS retained results: 3 tool probes / {tool_artifacts} artifact hashes; 7 regressions; 20 collector tests')
print('NOT executed: V0171 whole-design PnR, hardware programming, original-repo writes')
