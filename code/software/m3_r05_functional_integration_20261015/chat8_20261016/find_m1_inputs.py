"""Bounded read-only original-package search; writes only its own report."""
import argparse
import hashlib
import json
import os
import time
import zipfile
from pathlib import Path

TARGETS = {
    'M1_batch11': (750224, '842fa8f75356090440a5e8237acafc209620d114f9e3c0ce2eab5ffdf30862da'),
    'M1_algorithm': (416469, '5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06'),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    start = time.monotonic()
    errors, found, archives = [], [], 0
    roots = ['E:/FPGA/GAOYUNFPGA', 'C:/Users/songdongkuan/Downloads']
    exhausted = True
    for root in roots:
        for directory, dirs, files in os.walk(root, onerror=lambda e: errors.append(str(e))):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules')]
            if time.monotonic() - start > 75:
                exhausted = False
                break
            for name in files:
                if not name.lower().endswith('.zip'):
                    continue
                path = Path(directory) / name
                try:
                    archives += 1
                    size = path.stat().st_size
                    for target, (length, expected) in TARGETS.items():
                        if size == length and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
                            found.append({'target': target, 'path': str(path), 'member': None,
                                          'bytes': size, 'sha256': expected})
                    # Inspect only direct members; do not unpack or execute anything.
                    with zipfile.ZipFile(path) as z:
                        for member in z.infolist():
                            for target, (length, expected) in TARGETS.items():
                                if member.file_size == length:
                                    actual = hashlib.sha256(z.read(member)).hexdigest()
                                    if actual == expected:
                                        found.append({'target': target, 'path': str(path),
                                                      'member': member.filename,
                                                      'bytes': length, 'sha256': actual})
                except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                    errors.append(str(path) + ': ' + str(exc))
        if not exhausted:
            break
    result = {'roots': roots, 'targets': TARGETS, 'matches': found,
              'zip_files_inspected': archives, 'directory_walk_finished': exhausted,
              'errors': errors, 'wall_s': time.monotonic() - start,
              'scope': 'accessible ZIP files and one direct member level; deeper nested ZIPs not recursively expanded',
              'rtl_calls': 0, 'tool_calls': 0}
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'matches': found, 'zip_files_inspected': archives,
                      'walk_finished': exhausted, 'error_count': len(errors)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
