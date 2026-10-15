"""New desktop cases only; literal MIDI/byte expectations, no old-suite replay."""
from __future__ import annotations
import hashlib
from fractions import Fraction
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time
import unittest
from unittest import mock
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from desktop_controller import Controller, DesktopError, run_owned_child, MAX_WORKSPACE_UNITS, validate_workspace_path
from preview_model import ARTIFACTS, ROOT, PreviewError, identity, load_preview, windows_path_units, validate_windows_path, checked_read

spec = importlib.util.spec_from_file_location('desktop_fixture_bytes', ROOT / 'code/software/score_midi_import_candidate_20261014/midi_fixtures.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
OUT = Path(os.environ.get('DESKTOP_TEST_OUTPUT', ROOT / 'code/output' / ('score_midi_desktop_tests_' + uuid.uuid4().hex))).resolve()
OUT.mkdir(parents=True, exist_ok=True)
REAL_DIR = ROOT / 'code/software/score_midi_real_input_acceptance_20261015'
REAL_SHA = 'c0a8cb9f1ba3496a00367786a2b4ee5e0580be7b4bfbf0891b75e3b7475f634c'
CHARGE_SHA = 'f486148322b89c6e027b63f1a69f0ff278cf6f92db852d8f430ef2983c5b6ad8'


def event(tick, kind, channel=0, note=60, velocity=0):
    return dict(tick=tick, type=kind, channel=channel, note=note, velocity=velocity)


def settle(controller, maximum=30):
    deadline = time.monotonic() + maximum
    while controller.state in ('loading', 'exporting') and time.monotonic() < deadline:
        controller.poll()
        time.sleep(0.005)
    controller.poll()
    if controller.state in ('loading', 'exporting'):
        controller.close()
        controller.wait_closed(5)
        raise AssertionError('TEST_WAIT_BOUND_EXCEEDED')


class DesktopTests(unittest.TestCase):
    def setUp(self):
        short_id='t'+hashlib.sha256(self.id().encode('utf-8')).hexdigest()[:8]+uuid.uuid4().hex[:4]
        self.directory = OUT / short_id
        self.directory.mkdir()
        with (OUT/'TEST_INDEX.jsonl').open('a',encoding='utf-8',newline='\n') as stream:
            stream.write(json.dumps(dict(test_id=self.id(),case_id=short_id,path=str(self.directory)))+'\n')
        self.controllers = []

    def tearDown(self):
        for controller in self.controllers:
            controller.close()
            self.assertTrue(controller.wait_closed(5))

    def make(self, raw=None, source=None, runner=None):
        if source is None:
            source = self.directory / ('i' + uuid.uuid4().hex[:4] + '.mid')
            source.write_bytes(fixtures.basic() if raw is None else raw)
        controller = Controller(self.directory / ('w' + uuid.uuid4().hex[:4]), runner=runner)
        self.controllers.append(controller)
        controller.select_file(source)
        return controller, source

    def converted(self, raw=None, source=None):
        controller, source = self.make(raw, source)
        is_real=source.resolve()==(REAL_DIR/'inputs/MIDI_sample_2018-03-21.mid').resolve()
        controller.preview(source_description=('GolhaMedia original: https://commons.wikimedia.org/wiki/File:MIDI_sample_2018-03-21.mid' if is_real else 'Synthetic MIDI development fixture, not user-input acceptance'),
                           license_note='CC0 1.0 original; see SOURCE_RIGHTS.txt' if is_real else 'Locally constructed development fixture')
        settle(controller)
        self.assertEqual(controller.state, 'ready', controller.error)
        self.assertEqual(controller.result['execution']['exit_code'], 0)
        self.assertFalse(controller.result['hardware_pass_claim'])
        return controller, source

    def assert_events(self, controller, expected):
        self.assertEqual(controller.result['score']['events'], expected)
        actual = [(r['sample_tick'], r['type'], r['channel'], r['note'], r['velocity']) for r in controller.result['rows']]
        self.assertEqual(actual, [(e['tick'], e['type'], e['channel'], e['note'], e['velocity']) for e in expected])
        literal = b''.join(struct.pack('<IBBBB', e['tick'], int(e['type'] == 'note_off'), e['channel'], e['note'], e['velocity']) for e in expected)
        self.assertEqual((controller.stage / 'records.bin').read_bytes(), literal)
        self.assertEqual(b''.join(bytes.fromhex(r['record_hex']) for r in controller.result['rows']), literal)
        (self.directory / 'LITERAL_EXPECTED_EVENTS.json').write_text(json.dumps(expected, indent=2) + '\n', encoding='utf-8')

    def rejected(self, raw, diagnostic):
        controller, _ = self.make(raw)
        controller.preview()
        settle(controller)
        self.assertEqual(controller.state, 'error')
        self.assertIn(diagnostic, controller.error)
        self.assertIsNone(controller.result)
        receipts = list(controller.workspace.glob('logs_*/process_receipt.json'))
        self.assertEqual(len(receipts), 1)
        self.assertNotEqual(json.loads(receipts[0].read_text(encoding='utf-8'))['exit_code'], 0)

    def test_real_cc0_literal_44_rows_384000_samples(self):
        source = REAL_DIR / 'inputs/MIDI_sample_2018-03-21.mid'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), REAL_SHA)
        controller, _ = self.converted(source=source)
        notes = [65,74,65,72,70,70,69,70,72,70,68,60,69,60,67,65,65,64,65,67,65,63]
        durations = ([960] * 5 + [480] * 6) * 2
        expected, sample = [], 0
        for note, duration in zip(notes, durations):
            expected.append(event(sample, 'note_on', 4, note, 96))
            sample += duration * 25
            expected.append(event(sample, 'note_off', 4, note, 96))
        self.assertEqual((len(expected), sample), (44, 384000))
        self.assert_events(controller, expected)
        self.assertEqual(controller.result['input']['sha256'], REAL_SHA)

    def test_real_charge_meta54_rejected_without_alteration(self):
        raw = (REAL_DIR / 'inputs/charge.mid').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), CHARGE_SHA)
        self.rejected(raw, 'UNSUPPORTED_META: 0x54')
        controller=self.controllers[-1]
        logs=list(controller.workspace.glob('logs_*'))
        self.assertEqual(len(logs),1)
        before=json.loads((logs[0]/'dependency_before.json').read_text(encoding='utf-8'))
        after=json.loads((logs[0]/'dependency_after.json').read_text(encoding='utf-8'))
        self.assertEqual(before['phase'],'before');self.assertEqual(after['phase'],'after')
        self.assertEqual(len(before['observed']),5)
        self.assertEqual(before['observed'],after['observed'])
        self.assertIs(after['matches_before'],True)
        self.assertIn('IMPORT_EXIT',after['primary_error']);self.assertIn('0x54',after['primary_error'])

    def test_final_file_symlink_rejected_if_creation_is_permitted(self):
        controller,source=self.make()
        link=self.directory/'linked.mid'
        try:
            link.symlink_to(source)
        except (OSError,NotImplementedError) as error:
            reason='Actual file symlink creation unavailable: '+type(error).__name__+': '+str(error)
            (self.directory/'SYMLINK_SKIP.json').write_text(json.dumps(dict(status='SKIPPED_NOT_PASSED',reason=reason),indent=2)+'\n',encoding='utf-8')
            self.skipTest(reason)
        evidence=dict(link=str(link),target=str(source),checks=[],status='FAIL',target_before=identity(source.read_bytes()))
        try:
            with self.assertRaisesRegex(PreviewError,'INPUT_FILE_SYMLINK'):
                checked_read(link)
            evidence['checks'].append('checked_read_rejected_final_file_symlink')
            old=(controller.source,dict(controller.input_identity),controller.state)
            with self.assertRaisesRegex(DesktopError,'INPUT_FILE_SYMLINK'):
                controller.select_file(link)
            self.assertEqual((controller.source,controller.input_identity,controller.state),old)
            evidence['checks'].append('select_rejected_without_state_change')
            controller.preview();settle(controller)
            self.assertEqual(controller.state,'ready',controller.error)
            with self.assertRaisesRegex(PreviewError,'INPUT_FILE_SYMLINK'):
                load_preview(controller.stage,link,controller.input_identity)
            evidence['checks'].append('load_preview_rejected_final_file_symlink')
            evidence['status']='PASS'
        finally:
            # Remove only this newly-created link, never its regular target.
            evidence['target_after']=identity(source.read_bytes())
            evidence['owned_link_removed']=False
            if link.is_symlink():
                link.unlink();evidence['owned_link_removed']=True
            (self.directory/'SYMLINK_TEST.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')

    def test_type0_literal_bytes(self):
        controller, _ = self.converted()
        self.assert_events(controller, [event(0, 'note_on', velocity=100), event(24000, 'note_off')])

    def test_type1_two_tempos_36000_not_midi_tick(self):
        raw = fixtures.smf(fixtures.tempo(0, 500000) + fixtures.tempo(480, 250000) + fixtures.end(480), fixtures.note_on() + fixtures.note_off(960) + fixtures.end())
        controller, _ = self.converted(raw)
        self.assert_events(controller, [event(0, 'note_on', velocity=100), event(36000, 'note_off')])
        self.assertEqual([x['us_per_quarter'] for x in controller.result['tempo_map']], [500000,250000])

    def test_multitrack_simultaneous_stable_order(self):
        raw = fixtures.smf(fixtures.tempo(0,500000) + fixtures.end(480), fixtures.note_on(note=60,channel=1) + fixtures.note_off(480,note=60,channel=1) + fixtures.end(), fixtures.note_on(note=64,channel=2,velocity=90) + fixtures.note_off(480,note=64,channel=2) + fixtures.end())
        controller, _ = self.converted(raw)
        self.assert_events(controller, [event(0,'note_on',1,60,100),event(0,'note_on',2,64,90),event(24000,'note_off',1,60),event(24000,'note_off',2,64)])
        self.assertEqual([r['track'] for r in controller.result['rows']], [1,2,1,2])

    def test_zero_velocity_on_normalizes_off(self):
        controller, _ = self.converted(fixtures.smf(fixtures.note_on() + fixtures.note_on(480,velocity=0) + fixtures.end()))
        self.assert_events(controller,[event(0,'note_on',velocity=100),event(24000,'note_off')])

    def test_half_sample_absolute_ties_up(self):
        raw = fixtures.smf(fixtures.tempo(0,100000) + fixtures.note_on() + fixtures.note_off(1) + fixtures.end(),division=9600)
        controller, _ = self.converted(raw)
        self.assert_events(controller,[event(0,'note_on',velocity=100),event(1,'note_off')])
        row = controller.result['rows'][1]
        self.assertEqual(Fraction(row['exact_sample_numerator'],row['exact_sample_denominator']),Fraction(1,2))

    def test_capacity_512_kept_without_truncation(self):
        controller, _ = self.converted(fixtures.capacity(512))
        expected = [event(((i+1)//2)*50,'note_on' if i%2 == 0 else 'note_off',velocity=100 if i%2 == 0 else 0) for i in range(512)]
        self.assert_events(controller,expected)
        self.assertEqual(controller.result['remaining'],0)

    def test_capacity_513_rejected(self):
        self.rejected(fixtures.capacity(513),'CAPACITY')

    def test_truncated_rejected(self):
        self.rejected(fixtures.basic()[:-1],'TRUNCATED')

    def test_unsupported_semantic_cc_rejected(self):
        self.rejected(fixtures.smf(fixtures.event(0,[0xb0,64,127]) + fixtures.note_on() + fixtures.note_off() + fixtures.end()),'UNSUPPORTED_CHANNEL_EVENT')

    def test_note_out_of_range_rejected(self):
        self.rejected(fixtures.smf(fixtures.note_on(note=128) + fixtures.end()),'DATA_BYTE')

    def test_unsupported_type2_rejected(self):
        self.rejected(fixtures.smf(fixtures.note_on()+fixtures.note_off()+fixtures.end(),midi_format=2),'FORMAT')

    def tamper(self, artifact, change, reseal=False):
        controller, source = self.converted()
        path = controller.stage / artifact
        raw = path.read_bytes()
        path.write_bytes(change(raw))
        if reseal:
            receipt_path = controller.stage / 'receipt.json'
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            receipt['artifacts'][artifact] = identity(path.read_bytes())
            receipt_path.write_text(json.dumps(receipt),encoding='utf-8')
        with self.assertRaises((PreviewError,ValueError)):
            load_preview(controller.stage,source,controller.input_identity)

    def test_preview_json_semantics_tamper_even_resealed(self):
        def change(raw):
            d=json.loads(raw);d['events'][0]['note']=61;return json.dumps(d).encode()
        self.tamper('score.json',change,True)

    def test_preview_records_tamper(self):
        self.tamper('records.bin',lambda r:r[:-1]+bytes([r[-1]^1]),True)

    def test_preview_upload_tamper(self):
        self.tamper('upload.bin',lambda r:r[:-1]+bytes([r[-1]^1]),True)

    def test_preview_provenance_tamper_even_resealed(self):
        def change(raw):
            d=json.loads(raw);d['event_origins'][1]['sample_tick']+=1;return json.dumps(d).encode()
        self.tamper('provenance.json',change,True)

    def test_preview_readback_tamper(self):
        self.tamper('readback.json',lambda r:b'{}',True)

    def test_cancel_file_chooser_preserves_selection(self):
        controller,source=self.make()
        self.assertFalse(controller.select_file(''))
        self.assertEqual(controller.source,source.resolve())
        self.assertEqual(controller.state,'selected')

    def test_overlong_workspace_is_explicitly_rejected_before_creation(self):
        workspace=self.directory/('p'*100)/('q'*100)
        with self.assertRaisesRegex(DesktopError,'WINDOWS_PATH_LIMIT'):
            Controller(workspace)
        self.assertFalse(workspace.exists())

    def test_workspace_exact_utf16_198_199_boundary(self):
        anchor=Path(ROOT.anchor)
        boundary=anchor/('x'*(MAX_WORKSPACE_UNITS-windows_path_units(anchor)))
        self.assertEqual(windows_path_units(boundary),198)
        self.assertEqual(validate_workspace_path(boundary),boundary.resolve())
        with self.assertRaisesRegex(DesktopError,'WINDOWS_PATH_LIMIT'):
            validate_workspace_path(Path(str(boundary)+'x'))

    def test_nonbmp_utf16_units_not_python_character_count(self):
        self.assertEqual(windows_path_units('😀'),2)
        anchor=Path(ROOT.anchor)
        path=anchor/('x'*(MAX_WORKSPACE_UNITS-windows_path_units(anchor)-1)+'😀')
        self.assertEqual(len(str(path)),198)
        self.assertEqual(windows_path_units(path),199)
        with self.assertRaisesRegex(DesktopError,'WINDOWS_PATH_LIMIT'):
            validate_workspace_path(path)

    def test_overlong_source_rejected_without_destroying_selection(self):
        controller,_=self.make()
        before=(controller.source,dict(controller.input_identity),controller.state,controller._token)
        source=self.directory/('p'*100)/('q'*100)/'input.mid'
        with self.assertRaisesRegex(DesktopError,'WINDOWS_PATH_LIMIT'):
            controller.select_file(source)
        self.assertEqual((controller.source,controller.input_identity,controller.state,controller._token),before)
        self.assertEqual(list(controller.workspace.glob('logs_*')),[])

    def test_overlong_export_rejected_before_worker_or_directory(self):
        controller,_=self.converted()
        destination=self.directory/('p'*100)/('q'*100)
        token,worker=controller._token,controller._thread
        with self.assertRaisesRegex(DesktopError,'WINDOWS_PATH_LIMIT'):
            controller.export(destination,confirmed=True)
        self.assertEqual(controller.state,'ready')
        self.assertEqual(controller._token,token);self.assertIs(controller._thread,worker)
        self.assertFalse(destination.exists())

    def test_direct_runner_long_logs_rejected_before_native_or_directory(self):
        logs=self.directory/('p'*100)/('q'*100)
        with mock.patch('desktop_controller.ctypes.WinDLL',side_effect=AssertionError('NATIVE_CALL_FORBIDDEN')):
            with self.assertRaisesRegex(DesktopError,'WINDOWS_PATH_LIMIT'):
                run_owned_child([sys.executable,'-c','pass'],ROOT,logs,threading.Event(),5)
        self.assertFalse(logs.exists())

    def test_direct_runner_long_executable_rejected_before_logs(self):
        executable=self.directory/('p'*100)/('q'*100)/'python.exe'
        logs=self.directory/'long_executable_logs'
        with mock.patch('desktop_controller.ctypes.WinDLL',side_effect=AssertionError('NATIVE_CALL_FORBIDDEN')):
            with self.assertRaisesRegex(DesktopError,'WINDOWS_PATH_LIMIT'):
                run_owned_child([str(executable),'-c','pass'],ROOT,logs,threading.Event(),5)
        self.assertFalse(logs.exists())

    def test_busy_duplicate_preview_and_cancel(self):
        begun=threading.Event()
        def runner(argv,cwd,logs,cancel,timeout):
            begun.set();cancel.wait(2)
            return dict(exit_code=1,cancelled=cancel.is_set(),timed_out=False,tool_calls=0)
        controller,_=self.make(runner=runner)
        controller.preview();self.assertTrue(begun.wait(2))
        with self.assertRaisesRegex(DesktopError,'BUSY'):controller.preview()
        controller.cancel();settle(controller)
        self.assertEqual(controller.state,'selected');self.assertIsNone(controller.result)

    def test_late_result_after_close_ignored(self):
        def runner(argv,cwd,logs,cancel,timeout):
            cancel.wait(2);return dict(exit_code=1,cancelled=True,tool_calls=0)
        controller,_=self.make(runner=runner)
        controller.preview();controller.close();self.assertTrue(controller.wait_closed(5));controller.poll()
        self.assertEqual(controller.state,'closed');self.assertIsNone(controller.result)

    def test_stale_token_result_ignored(self):
        controller,_=self.make()
        controller._token='new-token'
        controller._queue.put(dict(type='completed',operation='preview',token='old-token',result={'stage':'wrong'}))
        self.assertEqual(controller.poll(),[])
        self.assertEqual(controller.state,'selected');self.assertIsNone(controller.result)

    def test_import_timeout_no_export(self):
        controller,_=self.make(runner=lambda *a:dict(exit_code=1,timed_out=True,tool_calls=0))
        controller.preview();settle(controller)
        self.assertIn('IMPORT_TIMEOUT',controller.error)

    def test_import_nonzero_no_export(self):
        controller,_=self.make(runner=lambda *a:dict(exit_code=7,tool_calls=0))
        controller.preview();settle(controller)
        self.assertIn('IMPORT_EXIT: 7',controller.error)

    def test_input_changed_after_selection_rejected(self):
        controller,source=self.make();source.write_bytes(fixtures.basic(note=61))
        controller.preview();settle(controller)
        self.assertIn('INPUT_CHANGED',controller.error)

    def test_export_confirmation_and_existing_directory_rejected(self):
        controller,_=self.converted();destination=self.directory/'export'
        with self.assertRaisesRegex(DesktopError,'CONFIRMATION'):controller.export(destination)
        self.assertFalse(destination.exists())
        controller.export(destination,confirmed=True);settle(controller)
        self.assertEqual(controller.state,'ready',controller.error)
        receipt=json.loads((destination/'desktop_export_receipt.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['status'],'OFFLINE_EXPORT_PASS')
        for name in (*ARTIFACTS,'receipt.json'):
            self.assertEqual((destination/name).read_bytes(),(controller.stage/name).read_bytes())
        with self.assertRaisesRegex(DesktopError,'OUTPUT_EXISTS'):controller.export(destination,confirmed=True)

    def test_input_changed_before_export_rejected(self):
        controller,source=self.converted();source.write_bytes(fixtures.basic(note=61))
        destination=self.directory/'export'
        controller.export(destination,confirmed=True);settle(controller)
        self.assertEqual(controller.state,'error');self.assertFalse(destination.exists())

    def test_real_owned_child_cancel_is_bounded(self):
        cancel=threading.Event();timer=threading.Timer(0.2,cancel.set);timer.start()
        try:
            result=run_owned_child([sys.executable,'-I','-S','-B','-c','import time;time.sleep(20)'],ROOT,self.directory/'owned_cancel',cancel,5)
        finally:timer.cancel()
        self.assertTrue(result['cancelled'],result)
        self.assertTrue(result['owned_job_assigned']);self.assertEqual(result['tool_calls'],1)
        self.assertLess(result['seconds'],5)

    def test_real_owned_child_timeout_is_bounded(self):
        result=run_owned_child([sys.executable,'-I','-S','-B','-c','import time;time.sleep(20)'],ROOT,self.directory/'owned_timeout',threading.Event(),0.2)
        self.assertTrue(result['timed_out'],result)
        self.assertTrue(result['owned_job_assigned']);self.assertLess(result['seconds'],5)

    def test_controller_close_terminates_its_actual_private_child(self):
        ready=self.directory/'actual_child_ready.txt'
        records=[]
        def runner(argv,cwd,logs,cancel,timeout):
            command=[sys.executable,'-I','-S','-B','-c',
                     "from pathlib import Path;import sys,time;Path(sys.argv[1]).write_text('ready',encoding='utf-8');time.sleep(20)",str(ready)]
            result=run_owned_child(command,cwd,logs,cancel,5)
            records.append(result)
            return result
        controller,_=self.make(runner=runner)
        controller.preview()
        deadline=time.monotonic()+3
        while not ready.exists() and time.monotonic()<deadline:time.sleep(0.01)
        self.assertTrue(ready.exists(),'actual owned child did not reach ready marker')
        controller.close();self.assertTrue(controller.wait_closed(5));controller.poll()
        self.assertEqual(controller.state,'closed');self.assertIsNone(controller.result)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['tool_calls'],1)
        self.assertTrue(records[0]['owned_job_assigned']);self.assertTrue(records[0]['cancelled'])


if __name__=='__main__':
    unittest.main(verbosity=2)
