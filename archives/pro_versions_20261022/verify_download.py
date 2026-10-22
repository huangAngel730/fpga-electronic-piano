"""Read-only verification of the archive and every original file inside it."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'ARCHIVE_CONTENTS.json').read_text(encoding='utf-8'))
path = root / manifest['archive']
assert path.stat().st_size == manifest['archive_bytes'], 'ZIP size mismatch'
assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest['archive_sha256'], 'ZIP SHA256 mismatch'
with zipfile.ZipFile(path) as archive:
    expected = {manifest['zip_prefix'] + r for r in manifest['entries']}
    assert len(archive.namelist()) == len(expected) and set(archive.namelist()) == expected, 'ZIP membership mismatch'
    for relative, item in manifest['entries'].items():
        data = archive.read(manifest['zip_prefix'] + relative)
        assert len(data) == item['bytes'], relative + ': size mismatch'
        assert hashlib.sha256(data).hexdigest() == item['sha256'], relative + ': SHA256 mismatch'
print('PASS', len(expected), 'archived files, including all three original FPGA bitstreams')
