"""Create an evidence-only ZIP, excluding all programming images and large databases."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
TARGET = HERE / 'M3_138K_C_optimization_L5_evidence_20261005.zip'
assert not TARGET.exists(), 'Never overwrite an already delivered archive'
receipt = json.loads((HERE / 'verification_receipt.json').read_text(encoding='utf-8'))
assert receipt['evidence_verification_passed'] and receipt['design_timing_passed']
members = {}
for source in HERE.rglob('*'):
    if not source.is_file():
        continue
    relative = source.relative_to(HERE)
    if any(part in ['tmp', '__pycache__'] for part in relative.parts):
        continue
    if source.suffix.lower() not in {'.py', '.md', '.json', '.log', '.txt', '.html', '.xml',
                                     '.tcl', '.gprj', '.sv', '.v', '.svh', '.hex', '.mem',
                                     '.cst', '.sdc', '.do', '.cfg', '.timing_paths', '.prj'}:
        continue
    assert source.suffix.lower() not in {'.fs', '.bin', '.binx', '.pr', '.vg', '.vvp'}
    members[relative.as_posix()] = {'SHA256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                   'size': source.stat().st_size}
with zipfile.ZipFile(TARGET, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name in sorted(members):
        archive.write(HERE / name, name)
    archive.writestr('ZIP_PAYLOAD_MANIFEST.json', json.dumps(members, indent=2) + '\n')
with zipfile.ZipFile(TARGET) as archive:
    assert archive.testzip() is None
    for name, expected in members.items():
        data = archive.read(name)
        assert len(data) == expected['size'] and hashlib.sha256(data).hexdigest() == expected['SHA256']
result = {'archive': str(TARGET), 'SHA256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
          'size': TARGET.stat().st_size, 'verified_payload_members': len(members),
          'programming_images_included': False, 'tool_runtime_included': False,
          'standalone_one_click_reproduction_claimed': False, 'CRC_and_member_SHA256_passed': True}
(HERE / 'archive_receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
