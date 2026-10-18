"""New C9 input/provenance seam checks; no subprocess or production capture.

The shared fixture is manufactured by fixture_cases using the unchanged
Reference.  Each test reseals an isolated copy and changes exactly the seam it
names.  This module does not execute tests on import.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import c9_inputs
import run_math
from fixture_cases import describe, json_data, make_fixture, write_fixture


class InputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._shared = tempfile.TemporaryDirectory(prefix='m1_r10_inputs_base_')
        cls.addClassCleanup(cls._shared.cleanup)
        cls._fixture = make_fixture(Path(cls._shared.name) / 'baseline', samples=1)
        bindings = c9_inputs.read_json(c9_inputs.HERE / 'SOURCE_BINDINGS.json')
        cls._row_schema = c9_inputs.read_json(c9_inputs.REPO / bindings['c9_row_schema_path'])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='m1_r10_inputs_case_')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'case'
        self.fixture = copy.deepcopy(self._fixture)
        self.job_path = write_fixture(self.root, self.fixture)

    def job(self):
        return json.loads(self.job_path.read_bytes())

    def save_job(self, job):
        self.job_path.write_bytes(json_data(job))

    def role(self, role):
        descriptor = self.job()['artifacts'][role]
        return json.loads((self.root / descriptor['path']).read_bytes())

    def save_role(self, role, value, *, raw=False):
        job = self.job()
        target = self.root / job['artifacts'][role]['path']
        target.write_bytes(value if raw else json_data(value))
        job['artifacts'][role] = describe(target, self.root)
        self.save_job(job)

    def save_public(self, records, *, index=None):
        """Reseal bytes/hashes while leaving semantic source claims untouched."""
        if index is None:
            index = self.role('mechanical_index')
        lines = [json_data(record) for record in records]
        self.save_role('public_rows', b''.join(lines), raw=True)
        descriptor = self.job()['artifacts']['public_rows']
        index['trace_input'] = copy.deepcopy(descriptor)
        for row, line in zip(index['rows'], lines):
            row['source']['raw_line_sha256'] = hashlib.sha256(line).hexdigest()
        self.save_role('mechanical_index', index)

    def public(self):
        path = self.root / self.job()['artifacts']['public_rows']['path']
        return [json.loads(line) for line in path.read_bytes().splitlines()]

    def assert_load_issue(self, code, *, status='CONTRACT_REJECTED'):
        with self.assertRaises(c9_inputs.MathIssue) as caught:
            c9_inputs.load_job(self.job_path)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.status, status)

    def evaluate_without_math(self):
        with patch.object(run_math, 'ClockedMath') as constructor:
            result = run_math.evaluate(self.job_path)
            constructor.assert_not_called()
        self.assertFalse(result['real_verified'])
        self.assertFalse(result['board_release_allowed'])
        return result

    def make_r7a_rows(self):
        originals = self.public()
        index = self.role('mechanical_index')
        reset_sha = self.job()['artifacts']['reset_edges']['sha256']
        for original, indexed in zip(originals, index['rows']):
            source = original['source']
            original['schema'] = 'M3_R7A_C9_PUBLIC_ROW_V1'
            original['origin'] = 'SYNTHETIC_SCHEMA_FIXTURE'
            original['source'] = dict(
                raw_sha256=source['raw_capture_sha256'],
                reset_edges_sha256=reset_sha, line=source['line'],
                cycle=source['cycle'], epoch=source['epoch'],
                time_ps=source['cycle'] * 20834,
                sampling_phase=source['sampling_phase'])
            original.pop('plan_association')
            original.update(raw_ports={'synthetic_marker': 1}, missing_reasons={},
                            events=[], semantics={'fixture': 'not RTL'})
            indexed['upstream_evidence'] = {
                key: copy.deepcopy(original[key]) for key in
                ('schema', 'origin', 'source', 'raw_ports', 'missing_reasons',
                 'events', 'semantics')}
        self.save_public(originals, index=index)

    def test_valid_originals_load_without_projection(self):
        job, docs, rows, pending = c9_inputs.load_job(self.job_path)
        self.assertIsNone(pending)
        self.assertEqual(job['capture_id'], self.fixture['capture_id'])
        self.assertEqual([row['fields'] for row in rows], self.fixture['rows'])
        self.assertEqual(docs['independent_plan'], self.fixture['plan'])

    def test_wrong_artifact_sha_rejects(self):
        job = self.job()
        job['artifacts']['mechanical_index']['sha256'] = '0' * 64
        self.save_job(job)
        self.assert_load_issue('ARTIFACT_BYTES_MISMATCH')

    def test_wrong_artifact_byte_count_rejects(self):
        job = self.job()
        job['artifacts']['independent_plan']['bytes'] += 1
        self.save_job(job)
        self.assert_load_issue('ARTIFACT_BYTES_MISMATCH')

    def test_parent_path_escape_rejects(self):
        job = self.job()
        job['artifacts']['raw_capture']['path'] = '../outside.json'
        self.save_job(job)
        self.assert_load_issue('ARTIFACT_PATH_ESCAPE')

    def test_absolute_windows_path_rejects(self):
        job = self.job()
        job['artifacts']['raw_capture']['path'] = 'C:/outside.json'
        self.save_job(job)
        self.assert_load_issue('ARTIFACT_PATH_ESCAPE')

    def test_duplicate_json_key_gets_machine_result(self):
        self.job_path.write_bytes(b'{"schema":"first","schema":"second"}\n')
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'CONTRACT_REJECTED')
        self.assertEqual(result['error']['code'], 'DUPLICATE_JSON_KEY')

    def test_float_json_number_rejects(self):
        self.job_path.write_bytes(b'{"unexpected_number":1.25}\n')
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'CONTRACT_REJECTED')
        self.assertEqual(result['error']['code'], 'NONINTEGER_JSON_NUMBER')

    def test_index_row_array_gets_machine_result(self):
        index = self.role('mechanical_index')
        index['rows'][0] = []
        self.save_role('mechanical_index', index)
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'CONTRACT_REJECTED')
        self.assertEqual(result['error']['code'], 'INDEX_RECORD_OBJECT')

    def test_index_apply_array_rejects(self):
        index = self.role('mechanical_index')
        index['rows'][0]['apply'] = []
        self.save_role('mechanical_index', index)
        self.assert_load_issue('INDEX_APPLY_OBJECT')

    def test_public_row_array_gets_machine_result(self):
        originals = self.public()
        originals[0] = []
        self.save_public(originals)
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'CONTRACT_REJECTED')
        self.assertEqual(result['error']['code'], 'PUBLIC_ROW_OBJECT')

    def test_provenance_array_gets_machine_result(self):
        self.save_role('provenance', [])
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'CONTRACT_REJECTED')
        self.assertEqual(result['error']['code'], 'PROVENANCE_OBJECT')

    def test_config_event_array_gets_machine_result(self):
        plan = self.role('independent_plan')
        plan['config_events'] = [[]]
        self.save_role('independent_plan', plan)
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'CONTRACT_REJECTED')

    def test_all_missing_inputs_are_pending_before_math(self):
        job = self.job()
        job['artifacts'] = {role: None for role in c9_inputs.ROLES}
        self.save_job(job)
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'PENDING_INPUT')
        self.assertEqual(set(result['missing']), set(c9_inputs.ROLES))

    def test_missing_original_file_is_pending(self):
        job = self.job()
        job['artifacts']['raw_capture']['path'] = 'not_arrived.json'
        self.save_job(job)
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'PENDING_INPUT')
        self.assertIn('raw_capture:original file missing', result['missing'])

    def test_missing_input_does_not_hide_bad_row_count(self):
        index = self.role('mechanical_index')
        index['row_count'] += 1
        self.save_role('mechanical_index', index)
        job = self.job()
        job['artifacts']['raw_capture'] = None
        self.save_job(job)
        self.assert_load_issue('INDEX_ROW_COUNT')

    def test_missing_capture_does_not_hide_source_forgery(self):
        index = self.role('mechanical_index')
        index['rows'][0]['source']['raw_capture_sha256'] = '0' * 64
        self.save_role('mechanical_index', index)
        job = self.job()
        job['artifacts']['raw_capture'] = None
        self.save_job(job)
        self.assert_load_issue('INDEX_RAW_SOURCE_MISMATCH')

    def test_self_declared_real_origin_needs_exact_admission(self):
        bindings = c9_inputs.read_json(c9_inputs.HERE / 'SOURCE_BINDINGS.json')
        self.assertEqual(bindings['admitted_real_provenance_sha256'], [])
        originals = self.public()
        for original in originals:
            original['origin'] = 'HDL_PUBLIC_CAPTURE_UNVERIFIED'
        index = self.role('mechanical_index')
        index['origin'] = 'HDL_PUBLIC_CAPTURE_UNVERIFIED'
        self.save_public(originals, index=index)
        job = self.job()
        job['mode'] = 'REAL'
        self.save_job(job)
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'PENDING_REAL_ADMISSION')

    def test_index_cannot_self_assign_plan_sequence(self):
        index = self.role('mechanical_index')
        index['rows'][0]['apply']['independent_apply_event_seq'] = 201
        self.save_role('mechanical_index', index)
        self.assert_load_issue('UNVERIFIED_PLAN_SEQUENCE_IN_INDEX')

    def test_public_field_cannot_self_assign_plan_sequence(self):
        index = self.role('mechanical_index')
        index['rows'][0]['fields']['apply_event_seq'] = 201
        self.save_role('mechanical_index', index)
        self.assert_load_issue('UNVERIFIED_PLAN_SEQUENCE_IN_INDEX')

    def test_original_declaration_only_plan_association_rejects(self):
        originals = self.public()
        originals[0]['plan_association'] = {'event_seq': 201}
        self.save_public(originals)
        result = self.evaluate_without_math()
        self.assertEqual(result['status'], 'CONTRACT_REJECTED')

    def test_wrong_physical_line_digest_rejects(self):
        index = self.role('mechanical_index')
        index['rows'][0]['source']['raw_line_sha256'] = '0' * 64
        self.save_role('mechanical_index', index)
        self.assert_load_issue('PUBLIC_LINE_SHA')

    def test_wrong_index_source_capture_sha_rejects(self):
        index = self.role('mechanical_index')
        index['rows'][0]['source']['raw_capture_sha256'] = '0' * 64
        self.save_role('mechanical_index', index)
        self.assert_load_issue('INDEX_RAW_SOURCE_MISMATCH')

    def test_wrong_index_source_trace_path_rejects(self):
        index = self.role('mechanical_index')
        index['rows'][0]['source']['trace_path'] = 'other_public_rows.jsonl'
        self.save_role('mechanical_index', index)
        self.assert_load_issue('INDEX_RAW_SOURCE_MISMATCH')

    def test_wrong_public_capture_sha_rejects_even_when_index_agrees(self):
        originals = self.public()
        originals[0]['source']['raw_capture_sha256'] = '0' * 64
        index = self.role('mechanical_index')
        index['rows'][0]['source']['raw_capture_sha256'] = '0' * 64
        self.save_public(originals, index=index)
        self.assert_load_issue('RAW_CAPTURE_SHA')

    def test_wrong_index_trace_descriptor_rejects(self):
        index = self.role('mechanical_index')
        index['trace_input']['sha256'] = '0' * 64
        self.save_role('mechanical_index', index)
        self.assert_load_issue('INDEX_PUBLIC_TRACE_IDENTITY')

    def test_original_field_disagreement_rejects(self):
        originals = self.public()
        originals[0]['fields']['audio_stable'] = 0
        self.save_public(originals)
        self.assert_load_issue('INDEX_PUBLIC_FIELD_MISMATCH')

    def test_r7a_original_evidence_can_be_loaded(self):
        self.make_r7a_rows()
        _, _, _, pending = c9_inputs.load_job(self.job_path)
        self.assertIsNone(pending)

    def test_r7a_upstream_evidence_must_be_byte_semantically_preserved(self):
        self.make_r7a_rows()
        index = self.role('mechanical_index')
        index['rows'][0]['upstream_evidence']['raw_ports'] = {}
        self.save_role('mechanical_index', index)
        self.assert_load_issue('UPSTREAM_EVIDENCE_DRIFT')

    def test_r7a_reset_sha_is_bound(self):
        self.make_r7a_rows()
        originals = self.public()
        originals[0]['source']['reset_edges_sha256'] = '0' * 64
        index = self.role('mechanical_index')
        index['rows'][0]['upstream_evidence']['source']['reset_edges_sha256'] = '0' * 64
        self.save_public(originals, index=index)
        self.assert_load_issue('RESET_EDGE_SOURCE_SHA')

    def test_c9_anyof_retains_xz_cancel_reason(self):
        rules = self._row_schema['properties']['cancel_reason']
        for value in ('x', 'Z', 'xz', '1X', '00', '01', 0, 1, None):
            with self.subTest(value=value):
                self.assertTrue(c9_inputs.schema_match(value, rules))
        for value in ('10', '11', 2, True, 1.0, 'xxx'):
            with self.subTest(invalid=value):
                self.assertFalse(c9_inputs.schema_match(value, rules))

    def test_duplicate_reset_range_rejects(self):
        reset = self.role('reset_edges')
        reset['low_ranges'].append(copy.deepcopy(reset['low_ranges'][0]))
        for edge in copy.deepcopy(reset['raw_edges']):
            edge['time_ps'] += 100000
            reset['raw_edges'].append(edge)
        self.save_role('reset_edges', reset)
        self.assert_load_issue('RESET_RANGES_OVERLAP_OR_REORDER')

    def test_reset_edge_epoch_disagreement_rejects(self):
        reset = self.role('reset_edges')
        reset['raw_edges'][0]['epoch'] = 99
        self.save_role('reset_edges', reset)
        self.assert_load_issue('RESET_EDGE_EPOCH')

    def test_unknown_reset_profile_is_unsupported(self):
        reset = self.role('reset_edges')
        reset['profile'] = 'UNPROVEN_ASYNC_PROFILE'
        self.save_role('reset_edges', reset)
        self.assert_load_issue('RESET_PROFILE_UNSUPPORTED', status='UNSUPPORTED_PROFILE')

    def test_plan_epoch_absent_from_capture_rejects(self):
        plan = self.role('independent_plan')
        extra = copy.deepcopy(plan['events'][0])
        extra['epoch'] = 99
        plan['events'].append(extra)
        self.save_role('independent_plan', plan)
        self.assert_load_issue('PLAN_EPOCH_NOT_IN_CAPTURE')

    def test_config_epoch_absent_from_capture_rejects(self):
        plan = self.role('independent_plan')
        plan['config_events'].append(dict(epoch=99, payload=0,
            arrival_window=dict(min_cycle=0, max_cycle=0)))
        self.save_role('independent_plan', plan)
        self.assert_load_issue('PLAN_EPOCH_NOT_IN_CAPTURE')


if __name__ == '__main__':
    unittest.main()
