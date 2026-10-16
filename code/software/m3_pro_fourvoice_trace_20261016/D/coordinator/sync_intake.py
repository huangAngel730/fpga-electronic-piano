"""Record a read-only dependency refresh without rerunning signed evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/SYNC_INTAKE'
FILES = ['code/docs/M3_完赛任务单_2026-10-15.md',
         'code/docs/138K四声部后续集成任务总览_2026-10-15.md',
         'code/docs/M2_双滑块同版接入边界与待定生产者_2026-10-16.md',
         'code/docs/test/m1_r05_pcm_oracle_20261016/REFERENCE_CONTRACT.json',
         'code/model/m1_r05_pcm_oracle_20261016/oracle.py',
         'code/model/m1_r05_pcm_oracle_20261016/DEPENDENCIES.json',
         'code/model/m1_r05_pcm_oracle_20261016/frozen/rom/piano_band_4x256_8191.mem',
         'code/model/m1_r05_pcm_oracle_20261016/frozen/rom/triangle_wavetable.hex',
         'code/model/m1_r05_pcm_oracle_20261016/frozen/rom/velocity_gain_rom.mem']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
    result = {'schema': 'M3_NIGHT_SYNC_INTAKE_V1', 'utc': datetime.now(timezone.utc).isoformat(),
              'head': head, 'old_t0_head': 'ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0',
              'source_status': 'PENDING_M2_PRO_SOURCE_OR_TRACE',
              'M1_status': 'R05_ORIGINALS_NOW_PRESENT_PRO_SAME_VERSION_MAPPING_PENDING',
              'new_test_rounds': 0, 'files': []}
    for rel in FILES:
        data = (ROOT / rel).read_bytes()
        sha = digest(data)
        snapshot = sha[:16] + '_' + Path(rel).name
        (OUT / snapshot).write_bytes(data)
        blob = subprocess.run(['git', 'show', head + ':' + rel], cwd=ROOT, capture_output=True, check=True).stdout
        result['files'].append({'path': rel, 'snapshot': snapshot, 'bytes': len(data), 'sha256': sha,
                                'source_commit': head, 'git_blob_bytes': len(blob),
                                'git_blob_sha256': digest(blob), 'worktree_equals_git_blob': blob == data})
    t0 = json.loads((OUT.parent / 'T0/T0_RECEIPT.json').read_text(encoding='utf-8'))
    old = OUT / 'T0_ORIGINALS'
    old.mkdir()
    recovered = []
    for item in t0['inputs']:
        if 'sha256' not in item:
            continue
        file = Path(item['path'])
        if file.exists() and digest(file.read_bytes()) == item['sha256']:
            data = file.read_bytes()
        elif file.is_relative_to(ROOT):
            rel = file.relative_to(ROOT).as_posix()
            p = subprocess.run(['git', 'show', result['old_t0_head'] + ':' + rel], cwd=ROOT, capture_output=True)
            data = p.stdout if p.returncode == 0 else b''
        else:
            data = b''
        if digest(data) != item['sha256']:
            recovered.append({'path': str(file), 'status': 'NOT_RECOVERED_RAW_SHA_MISMATCH'})
            continue
        name = item['sha256'][:16] + '_' + file.name
        (old / name).write_bytes(data)
        recovered.append({'path': str(file), 'snapshot': name, 'bytes': len(data), 'sha256': digest(data)})
    result['t0_recovery'] = recovered
    (OUT / 'SYNC_INTAKE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'RECORDED', 'head': head, 'new_inputs': len(result['files']),
                      't0_originals_recovered': sum('sha256' in r for r in recovered),
                      't0_missing': [r for r in recovered if 'status' in r]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
