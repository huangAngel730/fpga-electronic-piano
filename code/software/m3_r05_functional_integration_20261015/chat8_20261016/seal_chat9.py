"""Seal the software delta, immutable M1 input, sources and old trace references."""
import json
from pathlib import Path
import zipfile

from analyze_existing import ROOT, STAGE, PINS, identity
from chat9_replay import PACKAGE, PACKAGE_SHA, sha, require


def main():
    src = Path(__file__).parent
    docs = ROOT / 'code/docs/test/m3_r05_functional_integration_20261015/chat8_20261016'
    out = docs / 'SEAL_CHAT9R02'
    out.mkdir(exist_ok=False)
    payload = {}
    for p in sorted(src.glob('*.py')):
        payload['software/' + p.name] = p.read_bytes()
    for name in ('CHAT9R01', 'CHAT9R02'):
        for p in sorted((docs / name).rglob('*')):
            if p.is_file():
                payload['evidence/' + str(p.relative_to(docs)).replace('\\', '/')] = p.read_bytes()
    for name in ('CHAT9_RESULT_AND_HANDOFF.md',):
        payload[name] = (docs / name).read_bytes()
    data = PACKAGE.read_bytes()
    require(sha(data) == PACKAGE_SHA, 'M1_PACKAGE_CHANGED')
    payload['input/' + PACKAGE.name] = data
    binding = json.loads((docs / 'CHAT9R02/analysis/CLOSURE.json').read_text(encoding='utf-8'))
    for item in binding['executed_tree']:
        p = Path(item['path'])
        data = p.read_bytes()
        require(sha(data) == item['sha256'], 'SOURCE_CHANGED')
        payload['executed_sources/' + p.relative_to(STAGE).as_posix()] = data
    receipt = json.loads((docs / 'CHAT9R02/RECEIPT.json').read_text(encoding='utf-8'))
    for item in receipt['source_after']:
        require(identity(Path(item['path'])) == item, 'EXECUTED_SOFTWARE_CHANGED')
    refs = []
    for name in ('REAL_INPUTS.jsonl', 'REAL_CAPTURE.jsonl'):
        item = identity(STAGE / name)
        require(item['sha256'] == PINS[STAGE / name], 'ORIGINAL_TRACE_CHANGED')
        refs.append(item)
    payload['ORIGINAL_TRACE_REFERENCES.json'] = json.dumps(dict(
        included=False, reason='Already sealed/published original continuous traces; not duplicated',
        required_to_replay=refs), indent=2).encode('utf-8')
    manifest = dict(scope='SOFTWARE_DELTA_WITH_REUSED_REAL_CAPTURE_SCOPED_MATH',
                    RTL_calls=0, EDA_calls=0, Git_writes=0, board_release_allowed=False,
                    members=[dict(path=n, bytes=len(b), sha256=sha(b)) for n, b in sorted(payload.items())])
    payload['MANIFEST.json'] = json.dumps(manifest, indent=2).encode('utf-8')
    archive = out / 'M3_CHAT9_R05_PCM_REPLAY_20261016.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(payload.items()):
            z.writestr(name, data)
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None and set(z.namelist()) == set(payload), 'SEAL_CRC_OR_SET')
        for name, data in payload.items():
            require(z.read(name) == data, 'SEAL_BYTES')
    result = dict(archive=identity(archive), payload_members=len(payload) - 1,
                  CRC_and_bytes_verified=True, prior_evidence_untouched=True,
                  original_traces_included=False, Git_writes=0)
    (out / 'SEAL_RECEIPT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
