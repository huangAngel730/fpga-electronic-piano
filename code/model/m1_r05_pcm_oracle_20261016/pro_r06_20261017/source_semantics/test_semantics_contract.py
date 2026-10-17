"""New R6-1 contract/port negatives only; never launches an HDL tool."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

import semantics_contract as sc


def fixture(directory):
    """Synthetic RTL text tests the static checker, not circuit behavior."""
    declarations = []
    assignments = []
    connections = []
    for key, (width, signed, _, _) in sc.RULES.items():
        port = sc.PORTS[key]
        declaration = 'output wire ' + ('signed ' if signed else '')
        declaration += ('[' + str(width - 1) + ':0] ') if width > 1 else ''
        declarations.append(declaration + port)
        assignments.append('    assign ' + port + ' = ' + sc.ALIASES[key] + ';')
        connections.append('.' + port + '(' + port + ')')
    header = ',\n    '.join(['input wire clk'] + declarations)
    provider = 'module provider(\n    ' + header + '\n);\n' + '\n'.join(assignments) + '\nendmodule\n'
    wrapper = ('module wrapper(\n    ' + header + '\n);\n    provider u_provider(\n        ' +
               ',\n        '.join(connections) + '\n    );\nendmodule\n')
    baseline = provider
    for name, value in [('provider.sv', provider), ('wrapper.sv', wrapper), ('baseline.sv', baseline)]:
        (directory / name).write_text(value, encoding='utf-8', newline='\n')
    sources = []
    for name, role in [('provider', 'CANDIDATE'), ('wrapper', 'DEPENDENCY'), ('baseline', 'BASELINE')]:
        path = directory / (name + '.sv')
        sources.append({'id': name, 'path': path.name, 'sha256': sc.digest(path.read_bytes()), 'role': role})
    rows = []
    for key, (width, signed, update, rules) in sc.RULES.items():
        expression = '    assign ' + sc.PORTS[key] + ' = ' + sc.ALIASES[key] + ';'
        rows.append({'semantic_id': key, 'public_name': sc.PORTS[key], 'width': width,
                     'signed': signed, 'sample': copy.deepcopy(sc.SAMPLE), 'update_rule': update,
                     'semantic_rules': list(rules), 'definition': 'Synthetic parser fixture only.',
                     'derivation': 'DIRECT_SOURCE_OBSERVATION',
                     'source': {'file_id': 'provider', 'sha256': sources[0]['sha256'],
                                'module': 'provider', 'signal': sc.PORTS[key],
                                'evidence': [{'line': provider.splitlines().index(expression) + 1, 'text': expression}]},
                     'export': {'status': 'PROVIDED', 'reason': None, 'route': [
                         {'file_id': 'provider', 'module': 'provider', 'port': sc.PORTS[key], 'instance': None},
                         {'file_id': 'wrapper', 'module': 'wrapper', 'port': sc.PORTS[key], 'instance': 'u_provider'}]}})
    return {'schema': 'M1_R06_SOURCE_SEMANTICS_V1',
            'basis': {'commit': '0' * 40, 'evidence_origin': 'SYNTHETIC_TEST_ONLY'},
            'observation_module': 'wrapper', 'sample': copy.deepcopy(sc.SAMPLE),
            'sources': sources, 'source_list': ['provider', 'wrapper'],
            'm2_external_observer_mapping': 'UNRESOLVED_PENDING_M2_BLOB_AND_INTEGRATION',
            'pro_admission': False,
            'replacements': [{'baseline': 'baseline', 'candidate': 'provider', 'module': 'provider'}],
            'fields': rows, 'limitations': ['NO_HDL_RUN', 'NO_GOLDEN_MATH_PROOF', 'NO_PRO_BOARD_PASS',
                'M2_PUBLIC_ROUTE_AND_SOURCE_ADMISSION_REQUIRED', 'RESET_EDGES_REMAIN_REQUIRED']}


class SemanticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m1_r06_semantics_')
        self.root = Path(self.temp.name)
        self.contract = fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def check(self):
        return sc.check_contract(self.contract, self.root)

    def row(self, key):
        return next(row for row in self.contract['fields'] if row['semantic_id'] == key)

    def reject(self, pattern):
        with self.assertRaisesRegex(sc.ContractError, pattern):
            self.check()

    def rebind(self, key):
        source = next(row for row in self.contract['sources'] if row['id'] == key)
        source['sha256'] = sc.digest((self.root / source['path']).read_bytes())
        for row in self.contract['fields']:
            if row['source']['file_id'] == key:
                row['source']['sha256'] = source['sha256']
        # Synthetic baseline follows synthetic mutation so this specific test
        # reaches the intended width/route/alias check. No production source is
        # edited; the dedicated marker test checks original-source preservation.
        if key == 'provider':
            (self.root / 'baseline.sv').write_bytes((self.root / 'provider.sv').read_bytes())
            baseline = next(row for row in self.contract['sources'] if row['id'] == 'baseline')
            baseline['sha256'] = source['sha256']

    def test_exact19_explicit_outputs_and_replacement_accept(self):
        result = self.check()
        self.assertEqual(result['status'], 'STATIC_SOURCE_SEMANTICS_READY')
        self.assertEqual(result['checked_fields'], 19)
        self.assertFalse(result['hdl_executed'])
        self.assertFalse(result['golden_math_verified'])
        self.assertFalse(result['board_release_allowed'])

    def test_marker_strip_suffixes_preserves_original_source(self):
        baseline = (self.root / 'provider.sv').read_text(encoding='utf-8')
        observed = ('// BEGIN M1_OBSERVER_R06_PORTS\n// added observation\n'
                    '// END M1_OBSERVER_R06_PORTS\n' + baseline)
        self.assertEqual(sc.strip_observation_markers(observed), baseline)
        (self.root / 'provider.sv').write_text(observed, encoding='utf-8', newline='\n')
        source = self.contract['sources'][0]
        source['sha256'] = sc.digest((self.root / source['path']).read_bytes())
        for row in self.contract['fields']:
            row['source']['sha256'] = source['sha256']
            for item in row['source']['evidence']:
                item['line'] += 3
        self.assertEqual(self.check()['status'], 'STATIC_SOURCE_SEMANTICS_READY')
        (self.root / 'provider.sv').write_text(observed.replace('input wire clk', 'input wire changed_clk'),
                                            encoding='utf-8', newline='\n')
        source['sha256'] = sc.digest((self.root / source['path']).read_bytes())
        self.reject('SOURCE_CHANGED_OUTSIDE_OBSERVER_MARKERS')
        with self.assertRaisesRegex(sc.ContractError, 'UNCLOSED_OBSERVER_MARKER'):
            sc.strip_observation_markers('// BEGIN M1_OBSERVER_R06\n')

    def test_unresolved_requires_reason_and_stays_pending(self):
        self.row('apply_data')['export'] = {'status': 'UNRESOLVED',
                                          'reason': 'M2 wrapper not yet routed.', 'route': []}
        self.assertEqual(self.check()['status'], 'PENDING_PUBLIC_EXPORTS')
        self.row('apply_data')['export']['reason'] = ''
        self.reject('NONEMPTY_TEXT_REQUIRED')

    def test_missing_duplicate_or_unknown_field_rejects(self):
        self.contract['fields'].pop()
        self.reject('EXACTLY_19')
        self.contract = fixture(self.root)
        self.contract['fields'][-1] = copy.deepcopy(self.contract['fields'][0])
        self.reject('UNKNOWN_OR_DUPLICATE')
        self.contract['fields'][-1]['semantic_id'] = 'invented'
        self.reject('UNKNOWN_OR_DUPLICATE')

    def test_missing_json_field_rejects(self):
        del self.row('slot_note')['source']['sha256']
        self.reject('FIELDS')

    def test_wrong_width_signed_bool_and_sampling_reject(self):
        original = copy.deepcopy(self.contract)
        for field, value, expected in [('width', 28, 'FIELD_WIDTH_OR_SIGNED'),
                                        ('width', True, 'INTEGER_RANGE'),
                                        ('signed', 1, 'FIELD_WIDTH_OR_SIGNED')]:
            with self.subTest(field=field, value=value):
                self.contract = copy.deepcopy(original)
                self.row('slot_note')[field] = value
                self.reject(expected)
        self.contract = original
        self.row('slot_note')['sample']['phase'] = 'post_NBA'
        self.reject('FIELD_SAMPLE_OR_UPDATE_RULE')

    def test_wrong_global_edge_and_missing_source_binding_reject(self):
        self.contract['sample']['edge'] = 'negedge'
        self.reject('WRONG_SAMPLE_EDGE')
        self.contract = fixture(self.root)
        self.row('slot_source')['source']['file_id'] = 'unbound'
        self.reject('FIELD_SOURCE_NOT_COMPILED_OR_BOUND')

    def test_wrong_sha_or_changed_source_bytes_reject(self):
        self.row('slot_source')['source']['sha256'] = '0' * 64
        self.reject('FIELD_SOURCE_SHA_MISMATCH')
        self.contract = fixture(self.root)
        with (self.root / 'provider.sv').open('a', encoding='utf-8') as stream:
            stream.write('// changed\n')
        self.reject('SOURCE_SHA_MISMATCH')

    def test_fake_evidence_and_comment_only_evidence_reject(self):
        self.row('slot_channel')['source']['evidence'][0]['text'] += 'wrong'
        self.reject('SOURCE_LINE_EVIDENCE')
        self.contract = fixture(self.root)
        source = self.root / 'provider.sv'
        with source.open('a', encoding='utf-8') as stream:
            stream.write('// fake source proof\n')
        self.rebind('provider')
        self.row('slot_channel')['source']['evidence'] = [
            {'line': len(source.read_text(encoding='utf-8').splitlines()), 'text': '// fake source proof'}]
        self.reject('SOURCE_LINE_EVIDENCE')

    def test_advance_non1111_or_algebraic_inference_reject(self):
        path = self.root / 'provider.sv'
        raw = path.read_text(encoding='utf-8')
        raw = raw.replace('= {4{lane_tick}};', "= 4'b0011;")
        path.write_text(raw, encoding='utf-8', newline='\n')
        self.rebind('provider')
        self.row('advance_mask')['source']['evidence'] = [
            {'line': next(i + 1 for i, line in enumerate(raw.splitlines()) if "= 4'b0011;" in line),
             'text': "    assign obs_advance_mask = 4'b0011;"}]
        self.reject('SOURCE_ALIAS_OR_COMMON_ADVANCE')
        self.contract = fixture(self.root)
        self.row('occupied_mask')['derivation'] = 'RECOMPUTE_FROM_NOTE_OFF'
        self.reject('ALGEBRAIC_OR_INFERRED')

    def test_noteoff_retire_conflation_and_bad_update_rule_reject(self):
        self.row('note_off_mask')['semantic_rules'] = ['NOTE_OFF_IS_RETIRE']
        self.reject('SEMANTIC_RULES_MISMATCH')
        self.contract = fixture(self.root)
        self.row('slot_generation')['update_rule'] = 'INCREMENT_EVERY_TICK'
        self.reject('FIELD_SAMPLE_OR_UPDATE_RULE')

    def test_private_hierarchy_or_missing_public_port_reject(self):
        self.row('slot_channel')['source']['signal'] = 'u_private.slot_channel'
        self.reject('PLAIN_IDENTIFIER_REQUIRED_NO_HIERARCHY')
        self.contract = fixture(self.root)
        self.row('slot_channel')['source']['signal'] = 'not_declared'
        self.reject('PUBLIC_OUTPUT_WIDTH_SIGNED_OR_EXISTENCE')

    def test_route_wrong_instance_or_private_expression_reject(self):
        self.row('slot_channel')['export']['route'][1]['instance'] = 'wrong_instance'
        self.reject('NAMED_INSTANCE_NOT_UNIQUE')
        self.contract = fixture(self.root)
        self.row('slot_channel')['export']['route'][1]['port'] = 'u_private.value'
        self.reject('PLAIN_IDENTIFIER_REQUIRED_NO_HIERARCHY')

    def test_route_wrong_connection_reject_even_after_sha_update(self):
        path = self.root / 'wrapper.sv'
        raw = path.read_text(encoding='utf-8').replace('.obs_slot_channels(obs_slot_channels)',
                                                     '.obs_slot_channels(obs_slot_sources)')
        path.write_text(raw, encoding='utf-8', newline='\n')
        self.rebind('wrapper')
        self.reject('PUBLIC_PORT_ROUTE_NOT_DIRECT')

    def test_compiling_baseline_and_candidate_duplicate_module_rejects(self):
        self.contract['source_list'].append('baseline')
        self.reject('DUPLICATE_COMPILED_MODULE')

    def test_missing_explicit_replacement_or_excluded_candidate_rejects(self):
        self.contract['replacements'] = []
        self.reject('CANDIDATE_WITHOUT_EXPLICIT_REPLACEMENT')
        self.contract = fixture(self.root)
        self.contract['source_list'].remove('provider')
        self.reject('REPLACEMENT_NOT_EXPLICIT')

    def test_width_in_actual_port_not_self_declared_contract_is_checked(self):
        path = self.root / 'provider.sv'
        raw = path.read_text(encoding='utf-8').replace('[127:0] obs_slot_generations', '[63:0] obs_slot_generations')
        path.write_text(raw, encoding='utf-8', newline='\n')
        self.rebind('provider')
        self.reject('PUBLIC_OUTPUT_WIDTH_SIGNED_OR_EXISTENCE')

    def test_comment_fake_port_does_not_count(self):
        path = self.root / 'wrapper.sv'
        raw = path.read_text(encoding='utf-8').replace('output wire [15:0] obs_slot_channels,',
                                                     '/* output wire [15:0] obs_slot_channels, */')
        path.write_text(raw, encoding='utf-8', newline='\n')
        self.rebind('wrapper')
        self.reject('PUBLIC_OUTPUT_WIDTH_SIGNED_OR_EXISTENCE')

    def test_duplicate_json_key_float_path_escape_and_cli_no_overwrite(self):
        path = self.root / 'contract.json'
        path.write_text('{"a":1,"a":2}', encoding='utf-8')
        with self.assertRaisesRegex(sc.ContractError, 'DUPLICATE_JSON_KEY'):
            sc.read_json(path)
        path.write_text('{"a":1.0}', encoding='utf-8')
        with self.assertRaisesRegex(sc.ContractError, 'NONINTEGER_JSON_NUMBER'):
            sc.read_json(path)
        self.contract['sources'][0]['path'] = '../provider.sv'
        self.reject('PATH_ESCAPE')
        self.contract = fixture(self.root)
        path.write_text(json.dumps(self.contract), encoding='utf-8')
        out = self.root / 'result.json'
        argv = ['--root', str(self.root), '--contract', str(path), '--out', str(out)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(sc.main(argv), 0)
            before = out.read_bytes()
            self.assertEqual(sc.main(argv), 2)
            self.assertEqual(out.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
