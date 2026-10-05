"""Reuse the frozen seven-group runner, redirecting all new output here."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / 'preparation_20261005'
source = OLD / 'run_frozen_regression.py'
assert not (HERE / 'regression').exists(), 'Preserve previous regression evidence'
original_result = json.loads((OLD / 'frozen_regression_results.json').read_text(encoding='utf-8'))
for relative, expected_hash in original_result['bench_source_SHA256'].items():
    bench = OLD / 'regression/bench_original' / Path(relative).name
    assert hashlib.sha256(bench.read_bytes()).hexdigest() == expected_hash
text = source.read_text(encoding='utf-8')
replacements = {
    "Path('E:/FPGA/GAOYUNFPGA/138K_try/preparation_20261005')":
        "Path('E:/FPGA/GAOYUNFPGA/138K_try/optimization_20261005')",
    "DUT = HERE / 'relocated_bundle/sources'": "DUT = HERE / 'C_reset_location/sources'",
    'source = REPO / relative':
        "source = HERE.parent / 'preparation_20261005/regression/bench_original' / Path(relative).name",
}
for before, after in replacements.items():
    assert text.count(before) == 1
    text = text.replace(before, after)
provenance = {'runner_source': str(source), 'runner_source_SHA256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'in_memory_path_only_replacements': replacements,
              'scope': 'Frozen seven test groups against actual optimization DUT; not full system simulation'}
(HERE / 'regression_runner_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
exec(compile(text, str(source), 'exec'), {'__file__': str(HERE / 'replay_regression.py'), '__name__': '__main__'})
