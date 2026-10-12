"""Software-only tests for the T052 static preparation and future parser."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from precheck import (ACTUAL_ORIGIN, DUT_SHA256, PLAN_SHA256, InsufficientEvidence,
                      read_jsonl, validate_capture, validate_plan, validate_static)
from publication import calendar, read_rows


ROOT = HERE.parents[3]
PLAN = ROOT / 'code/docs/test/t052_publication_acceptance_20261012/M2_CONTROL_PLAN_20261012/controls_proposed.jsonl'
MEM = ROOT / 'code/tb/audio/t052_publication_acceptance_candidate_20261012/controls_128.hex'
MANIFEST = ROOT / 'code/docs/test/t052_publication_acceptance_20261012/CONTROL_PREPARATION_20261012/source_manifest.json'


def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
                          encoding='utf-8', newline='\n')


def synthetic_tracks(directory):
    proposed = read_rows(PLAN)
    plan_rows = proposed[1:-1]
    prediction = calendar(proposed)
    meta = {'type': 'META', 'origin': ACTUAL_ORIGIN, 'sampling': 'PRE_NBA',
            'dut_sha256': DUT_SHA256, 'rom_sha256':
            '5e1dbd3797f353686f5e567831b56d6dcf9bee55c423097b471ade93203e84b2',
            'plan_sha256': PLAN_SHA256, 'tb_sha256': '0' * 64,
            'observer_sha256': '1' * 64, 'tool_sha256': '2' * 64}
    controls = [meta]
    observations = [{key: meta[key] for key in
                     ('type', 'origin', 'sampling', 'dut_sha256', 'plan_sha256')}]
    for row, pin in zip(plan_rows, prediction['pins']):
        controls.append({**row, 'time': row['cycle'] * 20 + 10})
        observations.append({'cycle': row['cycle'], 'time': row['cycle'] * 20 + 10,
                             'calc_ready': pin['calc_ready'],
                             'result_valid': pin['result_valid'],
                             'result_req_id': pin['result_id']})
    controls.append({'type': 'END', 'last_cycle': 127, 'rows': 128})
    observations.append({'type': 'END', 'last_cycle': 127, 'rows': 128})

    events = [{'type': 'META', 'origin': ACTUAL_ORIGIN,
               'qualification': 'PUBLIC_HANDSHAKE_ONLY',
               'dut_sha256': DUT_SHA256, 'plan_sha256': PLAN_SHA256}]
    by_cycle = {}
    for row in prediction['accepted']:
        key = row['key']
        by_cycle.setdefault(row['cycle'], []).append(
            {'event': 'ACCEPT', 'cycle': row['cycle'],
             'time': row['cycle'] * 20 + 10, 'epoch': key[0],
             'serial': key[1], 'req_id': key[2]})
    for row in prediction['cancelled']:
        key = row['key']
        by_cycle.setdefault(row['cycle'], []).append(
            {'event': 'CANCEL', 'cycle': row['cycle'],
             'time': row['cycle'] * 20 + 10, 'epoch': key[0],
             'serial': key[1], 'req_id': key[2], 'reason': row['reason']})
    for row in prediction['publications']:
        key = row['key']
        by_cycle.setdefault(row['cycle'], []).append(
            {'event': 'PUBLISH', 'cycle': row['cycle'],
             'time': row['cycle'] * 20 + 10, 'epoch': key[0],
             'serial': key[1], 'req_id': key[2], 'observed_req_id': key[2]})
    for cycle in range(128):
        events.extend(by_cycle.get(cycle, []))
    events.append({'type': 'END', 'accepted': 6, 'published': 3,
                   'cancelled': 3, 'open': 0})
    resets = [{'type': 'META', 'origin': 'RTL_SIM_RESET_SIGNAL_V1',
               'time_unit': '1ns', 'dut_sha256': DUT_SHA256,
               'plan_sha256': PLAN_SHA256}]
    for cycle, level in ((0, 0), (2, 1), (64, 0), (66, 1)):
        resets.append({'event': 'RESET_EDGE', 'time': cycle * 20,
                       'cycle_visible_next': cycle, 'rst_n': level})
    resets.append({'type': 'END', 'last_cycle': 127})
    paths = [Path(directory) / name for name in
             ('controls.jsonl', 'observations.jsonl', 'publications.jsonl', 'resets.jsonl')]
    for path, rows in zip(paths, (controls, observations, events, resets)):
        write_jsonl(path, rows)
    return paths


class PrecheckTests(unittest.TestCase):
    def test_static_preparation_and_driver_projection(self):
        self.assertEqual(len(validate_plan(PLAN, MEM)), 128)
        self.assertEqual(validate_static(MANIFEST)['RTL_runs'], 0)

    def test_future_capture_positive_is_explicitly_synthetic(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'code/output') as temporary:
            paths = synthetic_tracks(temporary)
            result = validate_capture(MANIFEST, PLAN, *paths)
            self.assertEqual(result['ledger']['published'], 3)

    def test_handwritten_source_cannot_claim_actual_capture(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'code/output') as temporary:
            paths = synthetic_tracks(temporary)
            rows = read_jsonl(paths[0])
            rows[0]['origin'] = 'HANDWRITTEN_SOFTWARE_FIXTURE'
            write_jsonl(paths[0], rows)
            with self.assertRaisesRegex(ValueError, 'ACTUAL_SOURCE_ORIGIN'):
                validate_capture(MANIFEST, PLAN, *paths)

    def test_frame_ready_cannot_be_added_as_publication(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'code/output') as temporary:
            paths = synthetic_tracks(temporary)
            rows = read_jsonl(paths[2])
            rows.insert(-1, {'event': 'PUBLISH', 'cycle': 43, 'time': 870,
                             'epoch': 1, 'serial': 4, 'req_id': 12,
                             'observed_req_id': 12})
            rows[-1]['published'] = 4
            write_jsonl(paths[2], rows)
            with self.assertRaisesRegex(ValueError, 'PUBLICATION_EVENT_MISMATCH'):
                validate_capture(MANIFEST, PLAN, *paths)

    def test_missing_edge_and_open_window_are_unknown(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'code/output') as temporary:
            paths = synthetic_tracks(temporary)
            rows = read_jsonl(paths[1])
            rows.pop(-2)
            write_jsonl(paths[1], rows)
            with self.assertRaises(InsufficientEvidence):
                validate_capture(MANIFEST, PLAN, *paths)

    def test_duplicate_json_key_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'code/output') as temporary:
            path = Path(temporary) / 'bad.jsonl'
            path.write_text('{"cycle":0,"cycle":1}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'DUPLICATE_JSON_KEY'):
                read_jsonl(path)


if __name__ == '__main__':
    unittest.main()
