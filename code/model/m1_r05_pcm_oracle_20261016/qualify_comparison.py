"""Record one synthetic positive and four new arithmetic comparison negatives."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = args.vectors / 'EXPECTED_PCM.json'
    expected = json.loads(source.read_text(encoding='utf-8'))
    rows = [dict(epoch=r['epoch'], request_id=r['request_id'], left=r['left'], right=r['right'],
                 clipped=r['clipped'], lane_pcm=[l['voice_pcm24'] for l in r['lanes']],
                 generation=[l['generation'] for l in r['lanes']]) for r in expected if r['expected_publish']]
    expected_path = out / 'EXPECTED_NORMALIZED_MATH.json'
    write(expected_path, rows)
    index = next(i for i, row in enumerate(rows) if all(row['lane_pcm']))
    fixtures = []
    fixtures.append(('synthetic_equal_entrance_only', copy.deepcopy(rows), 0))
    bad = copy.deepcopy(rows)
    bad[index]['lane_pcm'][3] = 0
    fixtures.append(('missing_lane3', bad, 1))
    bad = copy.deepcopy(rows)
    bad[index]['left'] += 1
    fixtures.append(('pcm_one_lsb', bad, 1))
    bad = copy.deepcopy(rows)
    bad[index]['generation'][0] += 1
    fixtures.append(('wrong_generation', bad, 1))
    bad = copy.deepcopy(rows)
    bad[index]['clipped'][0] = not bad[index]['clipped'][0]
    fixtures.append(('wrong_clip', bad, 1))
    sources = [Path(__file__), HERE / 'compare_math.py', Path(sys.executable), source]
    before = {str(p): sha(p) for p in sources}
    receipt = dict(schema='M1_PCM_MATH_COMPARATOR_SYNTHETIC_QUALIFICATION_V1',
                   scope='SOFTWARE_COMPARATOR_ENTRANCE_NOT_INDEPENDENT_DUT_POSITIVE',
                   actual_dut_result='PENDING_REAL_CAPTURE', source_before_sha256=before,
                   automatic_retry=False, cases=[])
    for name, actual, wanted_exit in fixtures:
        folder = out / name
        folder.mkdir(exist_ok=False)
        actual_path = folder / 'SYNTHETIC_ACTUAL.json'
        write(actual_path, actual)
        command = [sys.executable, '-B', '-X', 'utf8', str(HERE / 'compare_math.py'),
                   '--expected', str(expected_path), '--actual', str(actual_path),
                   '--output', str(folder / 'COMPARISON.json')]
        stdout, stderr = folder / 'stdout.bin', folder / 'stderr.bin'
        started = time.monotonic()
        with stdout.open('xb') as so, stderr.open('xb') as se:
            result = subprocess.run(command, cwd=HERE, stdout=so, stderr=se, timeout=10)
        row = dict(name=name, command=command, cwd=str(HERE),
                   exit_code=result.returncode, expected_exit_code=wanted_exit,
                   expectation_matched=result.returncode == wanted_exit,
                   elapsed_seconds=round(time.monotonic() - started, 6),
                   stdout_sha256=sha(stdout), stderr_sha256=sha(stderr),
                   actual_sha256=sha(actual_path), comparison_sha256=sha(folder / 'COMPARISON.json'))
        receipt['cases'].append(row)
        if not row['expectation_matched']:
            break
    receipt['source_after_sha256'] = {str(p): sha(p) for p in sources}
    receipt['source_unchanged'] = before == receipt['source_after_sha256']
    receipt['all_expectations_matched'] = len(receipt['cases']) == 5 and all(r['expectation_matched'] for r in receipt['cases']) and receipt['source_unchanged']
    write(out / 'QUALIFICATION_RECEIPT.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('scope', 'actual_dut_result', 'all_expectations_matched', 'source_unchanged')}))
    return 0 if receipt['all_expectations_matched'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
