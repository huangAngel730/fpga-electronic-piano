"""Bounded offline real-download acceptance; original importer/encoder read-only."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IMPORTER = HERE.parent / 'score_midi_import_candidate_20261014'
FROZEN = [IMPORTER / name for name in ('midi_import.py', 'offline_readback.py', 'midi_fixtures.py')]
FROZEN += [ROOT / 'code/software/score_transfer_v1/score_transfer.py',
           ROOT / 'code/docs/hardware/score_transfer_v1/PROTOCOL.md']
EXPECTED = {
    'MIDI_sample_2018-03-21.mid': 'c0a8cb9f1ba3496a00367786a2b4ee5e0580be7b4bfbf0891b75e3b7475f634c',
    'charge.mid': 'f486148322b89c6e027b63f1a69f0ff278cf6f92db852d8f430ef2983c5b6ad8',
}


def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def put(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def snapshot(paths):
    return {str(path): identity(path.read_bytes()) for path in paths}


def runtime_files():
    prefix = Path(sys.base_prefix)
    files = [Path(sys.executable).resolve(), *prefix.glob('*.dll'), *prefix.glob('*.zip'),
             *prefix.glob('DLLs/*.dll'), *prefix.glob('DLLs/*.pyd')]
    files.extend(p for p in (prefix / 'Lib').rglob('*.py') if 'site-packages' not in p.parts)
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-evidence', type=Path,
                        help='optional existing download provenance directory; never executed')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    sources = sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    sources += FROZEN
    runtimes = runtime_files()
    receipt = dict(schema=1, scope='REAL_DOWNLOADED_MIDI_OFFLINE_ONLY', status='FAIL',
                   started_utc=datetime.now(timezone.utc).isoformat(), machine=platform.node(),
                   python_version=sys.version, step_limit_seconds=90, total_limit_seconds=300,
                   steps=[], rtl_calls=0, serial_calls=0, eda_calls=0, network_calls=0,
                   git_writes=0, M2_final_acceptance='PENDING', hardware_pass_claim=False,
                   real_multitrack_success='NOT_COVERED_REAL_EIGHT_TRACK_INPUT_REJECTED',
                   real_explicit_tempo_change='NOT_COVERED_SYNTHETIC_FIXTURE_ONLY',
                   GUI_interaction='NOT_RUN_SEPARATE_DESKTOP_WINDOW',
                   hardware_measurements=dict(bank3='PENDING', bank4='PENDING', bank5='PENDING',
                       midi_fpga_side_level_and_ground='PENDING', hdmi_direction_and_power_if_enabled='PENDING'))
    receipt['sources_before'] = snapshot(sources)
    receipt['runtime_before'] = snapshot(runtimes)
    save(out / 'plan.json', dict(max_step_seconds=90, max_total_seconds=300, automatic_retries=0,
        real_positive='inputs/MIDI_sample_2018-03-21.mid', real_negative='inputs/charge.mid',
        synthetic_cases='tempo/multitrack/rounding/capacity/mutations are fixtures, not user acceptance',
        before=receipt['sources_before']))

    def step(label, command, expected=0, diagnostic=None):
        remaining = 300 - (time.monotonic() - start)
        if remaining <= 0:
            raise TimeoutError('total budget exhausted before ' + label)
        item = dict(label=label, argv=command, cwd=str(ROOT), expected_exit=expected,
                    timeout_seconds=min(90, remaining), timed_out=False,
                    started_utc=datetime.now(timezone.utc).isoformat())
        begun = time.monotonic()
        with (out / (label + '.stdout.bin')).open('xb') as stdout, (out / (label + '.stderr.bin')).open('xb') as stderr:
            try:
                completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                           timeout=item['timeout_seconds'])
                item['exit_code'] = completed.returncode
            except subprocess.TimeoutExpired:
                item.update(exit_code=None, timed_out=True)
        item['seconds'] = time.monotonic() - begun
        for name in ('stdout', 'stderr'):
            item[name] = identity((out / (label + '.' + name + '.bin')).read_bytes())
        receipt['steps'].append(item)
        save(out / (label + '.receipt.json'), item)
        if item['timed_out'] or item['exit_code'] != expected:
            raise RuntimeError(label + ': unexpected exit or timeout')
        if diagnostic:
            text = (out / (label + '.stdout.bin')).read_bytes().decode('utf-8', errors='replace')
            if diagnostic not in text:
                raise ValueError(label + ': designated rejection not observed')
        return item

    try:
        for path in sources:
            if path.suffix == '.py':
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for name, sha in EXPECTED.items():
            if identity((HERE / 'inputs' / name).read_bytes())['sha256'] != sha:
                raise ValueError('REAL_INPUT_IDENTITY: ' + name)
        if hashlib.sha1((HERE / 'inputs/MIDI_sample_2018-03-21.mid').read_bytes()).hexdigest() != '7714fefe9218a18e9060b8eccd59a0247f0af3e0':
            raise ValueError('PUBLISHER_SHA1_MISMATCH')
        py = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-X', 'utf8']
        bootstrap = ('import sys,runpy;sys.path.insert(0,sys.argv[1]);'
                     'p=sys.argv[1]+"/midi_import.py";sys.argv=[p,*sys.argv[2:]];'
                     'runpy.run_path(p,run_name="__main__")')
        cli = py + ['-c', bootstrap, str(IMPORTER)]
        tests = ('import sys,unittest,json;sys.path.insert(0,sys.argv[1]);'
                 's=unittest.defaultTestLoader.discover(sys.argv[1],pattern="test_oracle.py");'
                 'r=unittest.TextTestRunner(verbosity=2).run(s);'
                 'print(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))));'
                 'raise SystemExit(not r.wasSuccessful())')
        step('01_oracle_unit_tests', py + ['-c', tests, str(HERE)])
        receipt['unit_test_summary'] = json.loads((out / '01_oracle_unit_tests.stdout.bin').read_bytes().splitlines()[-1])
        real = HERE / 'inputs/MIDI_sample_2018-03-21.mid'
        step('02_real_import', cli + ['import', '--input', str(real), '--score-id', '20180321',
            '--session', '1510', '--source-description', 'Downloaded GolhaMedia Wikimedia Commons CC0 melody; see SOURCE_RIGHTS.txt',
            '--license-note', 'CC0 1.0 explicit author declaration, Commons revision 1224484831',
            '--output', str(out / 'real_import')])

        def verify(label, directory, records=None, upload=None, expected=0, diagnostic=None):
            return step(label, cli + ['verify', '--score', str(directory / 'score.json'),
                '--records', str(records or directory / 'records.bin'),
                '--upload', str(upload or directory / 'upload.bin'), '--output', str(out / label)], expected, diagnostic)

        imported = out / 'real_import'
        verify('03_real_offline_verify', imported)
        oracle = py + [str(HERE / 'independent_oracle.py')]

        def oracle_check(label, midi, directory, expected=0, diagnostic=None):
            step(label, oracle + ['--midi', str(midi), '--score', str(directory / 'score.json'),
                '--records', str(directory / 'records.bin'), '--upload', str(directory / 'upload.bin'),
                '--output', str(out / (label + '.json'))], expected, diagnostic)

        oracle_check('04_real_independent_rows', real, imported)
        receipt['real_user_input'] = {k: v for k, v in json.loads((out / '04_real_independent_rows.json').read_text(encoding='utf-8')).items() if k != 'rows'}
        sys.path.insert(0, str(IMPORTER))
        import midi_fixtures as f
        fixture = f.smf(f.tempo(0, 500000) + f.tempo(480, 1000000) + f.end(480),
                        f.note_on() + f.note_off(960) + f.end(),
                        f.note_on(480, note=67, velocity=90) + f.note_off(480, note=67, velocity=64) + f.end())
        fixture_path = out / 'SYNTHETIC_type1_tempo_three_tracks.mid'
        put(fixture_path, fixture)
        save(out / 'SYNTHETIC_fixture_scope.json', dict(kind='SYNTHETIC_DEVELOPMENT_NOT_REAL_USER_INPUT',
            expected_sample_ticks=[0, 24000, 72000, 72000], expected_notes=[60, 67, 60, 67],
            expected_tempos_us=[500000, 1000000], same_tick_order='track1 off precedes track2 off'))
        step('05_synthetic_multitrack_import', cli + ['import', '--input', str(fixture_path),
            '--output', str(out / 'synthetic_import'), '--source-description', 'SYNTHETIC development fixture, not downloaded input',
            '--license-note', 'Local test fixture only'])
        oracle_check('06_synthetic_independent_rows', fixture_path, out / 'synthetic_import')
        converted = json.loads((out / 'synthetic_import/score.json').read_text(encoding='utf-8'))['events']
        if [e['tick'] for e in converted] != [0, 24000, 72000, 72000] or [e['note'] for e in converted] != [60, 67, 60, 67]:
            raise ValueError('LITERAL_SYNTHETIC_EXPECTATION')
        step('07_real_type1_rejection', cli + ['import', '--input', str(HERE / 'inputs/charge.mid'),
            '--output', str(out / 'real_type1_rejected')], 1, 'UNSUPPORTED_META: 0x54')
        from independent_oracle import smf_inventory
        save(out / 'real_type1_inventory.json', smf_inventory((HERE / 'inputs/charge.mid').read_bytes()))
        for label, raw, code in [
            ('08_truncated_real_fixture', real.read_bytes()[:-1], 'TRUNCATED'),
            ('09_unsupported_cc_fixture', f.smf(f.note_on() + f.event(0, [0xB0, 64, 127]) + f.note_off() + f.end()), 'UNSUPPORTED_CHANNEL_EVENT'),
            ('10_capacity_fixture', f.capacity(514), 'CAPACITY')]:
            path = out / (label + '.mid')
            put(path, raw)
            step(label, cli + ['import', '--input', str(path), '--output', str(out / label),
                 '--source-description', 'SYNTHETIC_OR_MUTATED_NEGATIVE_FIXTURE_NOT_USER_INPUT'], 1, code)
        bad_records = bytearray((imported / 'records.bin').read_bytes())
        bad_records[6] ^= 1
        put(out / 'MUTATED_records.bin', bad_records)
        verify('11_readback_record_rejection', imported, records=out / 'MUTATED_records.bin',
               expected=1, diagnostic='READBACK_RECORD_MISMATCH')
        bad_upload = bytearray((imported / 'upload.bin').read_bytes())
        bad_upload[-1] ^= 1
        put(out / 'MUTATED_upload.bin', bad_upload)
        verify('12_upload_crc_rejection', imported, upload=out / 'MUTATED_upload.bin',
               expected=1, diagnostic='FRAME_CRC')
        # Coherently corrupt all three derived outputs: a self-roundtrip can pass;
        # the independent source-MIDI oracle must still reject the changed notes.
        coherent = out / 'MUTATED_coherent_outputs'
        coherent.mkdir()
        doc = json.loads((imported / 'score.json').read_text(encoding='utf-8'))
        doc['events'][0]['note'] += 1
        doc['events'][1]['note'] += 1
        save(coherent / 'score.json', doc)
        import midi_import
        codec = midi_import.load_encoder()
        sid, records = codec.encode_score(doc)
        put(coherent / 'records.bin', records)
        put(coherent / 'upload.bin', b''.join(codec.upload_frames(sid, records, 1510)))
        verify('13_coherent_self_roundtrip_control', coherent)
        oracle_check('14_coherent_source_mismatch_rejection', real, coherent, 1, 'ORACLE_MIDI_JSON_MISMATCH')
        save(out / 'failure_history.json', dict(current_attempt_unexpected_software_failures=[],
             historical_failure_note='Source snapshot FAILURE_HISTORY.txt and history/REAL_MIDI_R02_FAILURE.zip',
             expected_rejections=[s['label'] for s in receipt['steps'] if s['expected_exit'] == 1],
             original_importer_changed=False,
             initial_attempts='Initial Commons import exit0 and real charge rejection exit1 retained separately, not overwritten'))
        receipt['status'] = 'REAL_DOWNLOADED_TYPE0_OFFLINE_ACCEPTANCE_PASS'
    except Exception as error:
        receipt['failure'] = f'{type(error).__name__}: {error}'
    receipt['sources_after'] = snapshot(sources)
    receipt['runtime_after'] = snapshot(runtimes)
    if receipt['sources_before'] != receipt['sources_after'] or receipt['runtime_before'] != receipt['runtime_after']:
        receipt['status'], receipt['failure'] = 'FAIL', 'SOURCE_OR_RUNTIME_DRIFT'
    receipt['seconds_before_seal'] = time.monotonic() - start
    if receipt['seconds_before_seal'] >= 300:
        receipt['status'], receipt['failure'] = 'FAIL', 'TOTAL_BUDGET'
    save(out / 'receipt.json', receipt)
    source_dir = out / 'source_snapshot'
    source_dir.mkdir()
    for path in sources:
        dest = source_dir / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        if identity(raw) != receipt['sources_after'][str(path)]:
            raise ValueError('source changed before seal')
        put(dest, raw)
    if args.source_evidence:
        proof = out / 'download_provenance'
        proof.mkdir()
        # Raw public response headers stay local: do not redistribute cookies/IP.
        for name in ('commons_source_license.html', 'beatscribe_README_original.txt'):
            raw = (args.source_evidence / name).read_bytes()
            put(proof / name, raw)
        selected = {}
        for name in ('midi_download_headers.txt', 'charge_download_headers.txt', 'license_page_headers.txt'):
            lines = (args.source_evidence / name).read_text(encoding='utf-8').splitlines()
            selected[name] = [line for line in lines if line.startswith('HTTP/') or
                line.lower().split(':', 1)[0] in ('content-type', 'content-length', 'etag', 'last-modified', 'date')]
        save(proof / 'SAFE_HTTP_HEADERS.json', selected)
        save(proof / 'DOWNLOAD_RECEIPT.json', dict(kind='RECORDED_MANUAL_DOWNLOADS_BEFORE_OFFLINE_RUN',
            tool='curl.exe', proxy='http://127.0.0.1:7892', flags=['--fail', '--location', '--max-time', '60'],
            commands=[dict(url='https://upload.wikimedia.org/wikipedia/commons/0/05/MIDI_sample_2018-03-21.mid', exit_code=0,
                           artifact=EXPECTED['MIDI_sample_2018-03-21.mid']),
                      dict(url='https://raw.githubusercontent.com/Beatscribe/homebrew_vgm/master/GBA_MIDI/charge.mid', exit_code=0,
                           artifact=EXPECTED['charge.mid'])],
            note='Download progress was returned in tool transcript, not retained as raw curl stderr file; raw headers remain local. Offline step raw streams complete.'))
    members = {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob('*')) if p.is_file()}
    manifest = {name: identity(raw) for name, raw in members.items()}
    save(out / 'manifest.json', manifest)
    members['manifest.json'] = (out / 'manifest.json').read_bytes()
    packet = out / 'REAL_MIDI_OFFLINE_EVIDENCE.zip'
    with zipfile.ZipFile(packet, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    with zipfile.ZipFile(packet) as archive:
        if archive.testzip() is not None:
            raise ValueError('SEAL_CRC')
        for name, value in manifest.items():
            if identity(archive.read(name)) != value:
                raise ValueError('SEAL_SHA')
    elapsed = time.monotonic() - start
    status = receipt['status'] if elapsed < 300 else 'FAIL_TOTAL_BUDGET_AT_SEAL'
    save(out / 'delivery.json', dict(status=status, packet=identity(packet.read_bytes()),
        data_members=len(manifest), seconds_including_seal=elapsed, git_published=False,
        source_and_runtime_unchanged=receipt['sources_before'] == receipt['sources_after'] and receipt['runtime_before'] == receipt['runtime_after']))
    print(json.dumps(dict(status=status, output=str(out), steps=len(receipt['steps']),
                         seconds=elapsed, packet_sha256=identity(packet.read_bytes())['sha256'])))
    return int(status.startswith('FAIL'))


if __name__ == '__main__':
    raise SystemExit(main())
