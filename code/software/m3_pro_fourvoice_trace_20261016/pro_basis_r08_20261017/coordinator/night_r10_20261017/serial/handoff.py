"""R10 source-bound handoff preparation only; no import-time I/O or tools."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[7]
OWNER = ROOT / 'code/docs/test/m2_night_r10_20261017/DELIVERY_CONTRACT.json'
OWNER_SHA = 'bc375cadc16188a716e2b710fa337082e252b99193b8d36830e095397f6241bf'
SW = 'code/software/m3_pro_fourvoice_trace_20261016/'
FIXED = {
    'unique_FRAME_generator': (SW + 'pro_basis_r06_20261017/event_calendar/frame_plan_generator_candidate.py',
        '38592faebeeeb0a2022668785453760a5b58babd24af6ff18a96f15790597191'),
    'calendar_checker': (SW + 'pro_basis_r06_20261017/event_calendar/r07_fix/calendar_r07_fix_candidate.py',
        '9af7022b0a228e0f8e180fd6a3c58646757cb407dfb132726c8ae0ace28413a5'),
    'TX_serial_checker': (SW + 'pro_basis_r06_20261017/tx_clock_reset_checker/c9_completion_r01/serial.py',
        'c576a5c79169eb5e91d796775aec820260a5df0e47b5c4472acf8630f5dcc5b7'),
    'mechanical_math_wrapper': (SW + 'pro_basis_r07_20261017/oracle_bundle_bridge/c9_completion_r01/math_bundle.py',
        '83659169c25e5d77621e1649eeda25697b7f0eb4767d8321599144a19ceb3854'),
    'PinDecoder': ('code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py',
        'da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb'),
}


def need(value, reason):
    if not value:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def no_alias(file):
    file = Path(file)
    need(not str(file).startswith(('\\\\.\\', '\\\\?\\', '\\??\\')), 'DEVICE_PATH')
    need(not any(re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part)
                 for part in file.parts), 'DEVICE_NAME')
    for part in (file, *file.parents):
        need(not part.is_symlink() and not part.is_junction(), 'PATH_ALIAS')
    return file.resolve()


def identity(file):
    h, size = hashlib.sha256(), 0
    file = no_alias(file)
    need(file.is_file(), 'REGULAR_FILE_REQUIRED')
    with file.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
            size += len(block)
    return {'bytes': size, 'sha256': h.hexdigest()}


def artifact(file):
    file = no_alias(file)
    return {'path': file.relative_to(ROOT).as_posix() if file.is_relative_to(ROOT)
            else str(file), **identity(file)}


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'DUPLICATE_JSON_KEY:' + key)
        result[key] = value
    return result


def read(file):
    with no_alias(file).open('rb') as stream:
        raw = stream.read(16 * 1024**2 + 1)
    need(len(raw) <= 16 * 1024**2, 'JSON_METADATA_BOUND')
    def invalid(value):
        raise ValueError('NONFINITE_JSON:' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def save(file, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with Path(file).open('xb') as stream:
        stream.write(raw)


def assemble(request, out):
    need(isinstance(request, dict), 'HANDOFF_REQUEST_OBJECT')
    out = no_alias(out)
    allowed = ROOT / 'code/output/m3_c9_chain_night_r10_20261017'
    need(out != allowed and out.is_relative_to(allowed), 'HANDOFF_OUTPUT_SCOPE')
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'REQUEST.json', request)
    tracked = {}

    def checked(desc, external=False):
        need(isinstance(desc, dict) and {'path', 'bytes', 'sha256'} <= desc.keys(), 'DESCRIPTOR_FIELDS')
        name = desc['path']
        need(isinstance(name, str) and name and type(desc['bytes']) is int and desc['bytes'] >= 0
             and isinstance(desc['sha256'], str) and re.fullmatch('[0-9a-f]{64}', desc['sha256']),
             'DESCRIPTOR_TYPES')
        file = Path(name)
        if not file.is_absolute():
            need(PurePosixPath(name).as_posix() == name and '..' not in PurePosixPath(name).parts,
                 'DESCRIPTOR_RELATIVE_PATH')
            file = ROOT / file
        file = no_alias(file)
        need(external or file.is_relative_to(ROOT), 'DESCRIPTOR_SCOPE')
        actual = artifact(file)
        need({key: actual[key] for key in ('bytes', 'sha256')} ==
             {key: desc[key] for key in ('bytes', 'sha256')}, 'DESCRIPTOR_SHA:' + name)
        tracked[str(file)] = actual
        return file

    def fixed(role):
        name, sha = FIXED[role]
        desc = artifact(ROOT / name)
        need(desc['sha256'] == sha, 'FIXED_SOURCE_CHANGED:' + role)
        checked(desc)
        return desc

    def archive(desc):
        file = checked(desc)
        result, total = {}, 0
        with zipfile.ZipFile(file) as z:
            for entry in z.infolist():
                if entry.is_dir():
                    continue
                name = entry.filename
                p = PurePosixPath(name)
                need(not p.is_absolute() and '..' not in p.parts and '\\' not in name
                     and ':' not in name and p.as_posix() == name, 'ARCHIVE_PATH')
                need(name.casefold() not in {k.casefold() for k in result}, 'ARCHIVE_DUPLICATE')
                total += entry.file_size
                need(total <= 64 * 1024**2 and entry.file_size <= 16 * 1024**2, 'ARCHIVE_BOUND')
                h, size = hashlib.sha256(), 0
                with z.open(entry) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        size += len(block)
                        h.update(block)
                result[name] = {'member': name, 'bytes': size, 'sha256': h.hexdigest()}
        return result

    try:
        need(request.get('schema') == 'N10_M3_HANDOFF_REQUEST_V1', 'HANDOFF_SCHEMA')
        capture = request['capture_id']
        need(isinstance(capture, str) and re.fullmatch('[A-Za-z0-9_-]{1,80}', capture), 'CAPTURE_ID')
        owner = artifact(OWNER)
        need(owner['sha256'] == OWNER_SHA, 'OWNER_CONTRACT_CHANGED')
        checked(owner)
        contract = read(OWNER)
        refs = request['source_contract_refs']
        need(isinstance(refs, list), 'CONTRACT_REFS_LIST')
        refs_by_path = {}
        for desc in refs:
            file = checked(desc)
            name = file.relative_to(ROOT).as_posix()
            need(name not in refs_by_path, 'DUPLICATE_CONTRACT_REF')
            refs_by_path[name] = artifact(file)
        for name, expected in contract['references'].items():
            need(name in refs_by_path and {key: refs_by_path[name][key] for key in ('bytes', 'sha256')}
                 == expected, 'SOURCE_CONTRACT_MIX:' + name)
        refs = list(refs_by_path.values())
        def owner_ref(basename):
            names = [name for name in contract['references'] if name.endswith('/' + basename)]
            need(len(names) == 1, 'OWNER_ROLE_PATH:' + basename)
            return refs_by_path[names[0]]
        app_request_path = checked(request['application_request'])
        proposed = read(app_request_path)
        report = request['application_report']
        need(proposed.get('schema') == 'M3_C9_EXECUTION_APPLICATION_REQUEST_V1'
             and proposed.get('approved') is False, 'APPLICATION_REQUEST_AUTHORITY')
        need(report.get('schema') == 'M3_C9_APPLICATION_BUILD_RESULT_V1'
             and report.get('execution_allowed') is False and report.get('real_pass') is False
             and report.get('board_release_allowed') is False, 'APPLICATION_REPORT_AUTHORITY')
        arts = report['artifacts']
        artifact_paths = {name: checked(desc) for name, desc in arts.items()}
        need({'application', 'resolved_plan', 'dependency_graph', 'tools', 'source', 'guard',
              'reservation', 'claim'} <= artifact_paths.keys(), 'APPLICATION_ARTIFACT_SET')
        application = read(artifact_paths['application'])
        bound = read(artifact_paths['resolved_plan'])
        source, spec = proposed['source'], proposed['execution_spec']
        need(source['application']['sha256'] ==
             'b23c65d58e50da089bc78645cf9ec65b5a3be5149f242fbe59d9891c3e44d1a2',
             'EXISTING_75_UNIT_APPLICATION_REQUIRED')
        need(capture == spec['window_parameters']['CAPTURE_ID']
             == bound['execution']['window_parameters']['CAPTURE_ID'], 'CAPTURE_MISMATCH')
        need(application.get('execution_allowed') is False and application.get('approved') is False
             and application.get('authenticated') is False and application.get('board_release_allowed') is False,
             'APPLICATION_SELF_AUTHORITY')
        need(application['source'] == source == bound['source'] and application['bound_plan'] == bound,
             'APPLICATION_SOURCE_SPLICE')
        need(bound['execution'] == spec and bound['tools'] == proposed['tools']
             and bound['external_inputs'] == proposed['external_inputs']
             and bound['window_reference'] == proposed['window_reference'], 'APPLICATION_SPEC_SPLICE')
        need(bound['permission'] == 'NOT_GRANTED' and bound['process_route'] == 'ABSENT',
             'BOUND_PLAN_AUTHORITY')
        plan_sha = hashlib.sha256(canonical(bound).encode('utf-8')).hexdigest()
        need(plan_sha == report['plan_sha256'] == application['plan_sha256'], 'BOUND_PLAN_SHA')
        reservation = read(artifact_paths['reservation'])
        claim = read(artifact_paths['claim'])
        need(reservation == application['reservation'], 'RESERVATION_SPLICE')
        need(all(reservation['claim'][k] == arts['claim'][k] for k in ('bytes', 'sha256'))
             and claim['capture_id'] == capture and claim['plan_sha256'] == plan_sha
             and claim['nonce'] == spec['nonce'] and claim['output'] == reservation['output']
             == bound['resolved_output'] and claim['execution_allowed'] is False,
             'CLAIM_PLAN_CAPTURE_SPLICE')
        need(read(artifact_paths['guard']) == application['guard'], 'GUARD_SPLICE')
        need(bound['resolved_environment'] == spec['environment']
             and bound['requested_budget'] == spec['budget'], 'RESOLVED_SPEC_SPLICE')
        need(artifact(checked(source['base'])) == owner_ref('SOURCE_CLOSURE_R06C9.zip'),
             'C9_BASE_CONTRACT_MIX')
        base = archive(source['base'])
        full = archive(source['application'])
        need(source['application']['sha256'] == arts['source']['sha256']
             and application['source_application_verified']['sha256'] == source['application']['sha256'],
             'APPLICATION_ARCHIVE_SPLICE')
        for name, desc in base.items():
            need(name in full and full[name] == desc, 'SOURCE_ROM_INCLUDE_MIX:' + name)
        for role, basename in {'DRIVER': 'midi_public_port_driver.sv',
                               'OBSERVER': 'r7a_c9_public_observer.sv',
                               'TB': 'tb_r7a_c9_public_capture.sv'}.items():
            desc = artifact(checked(source['capture_sources'][role]))
            member = full.get('inputs/m3_c9/' + basename)
            need(member is not None and all(member[k] == desc[k] for k in ('bytes', 'sha256')),
                 'CAPTURE_SOURCE_MIX:' + role)
        need(set(source['stimulus_inputs']) == {'bytes.drv', 'reset.drv', 'ready.drv', 'plan.json'},
             'INDEPENDENT_INPUT_SET')
        for name, desc in source['stimulus_inputs'].items():
            checked(desc)
            need('inputs/' + name in full and all(full['inputs/' + name][k] == desc[k]
                 for k in ('bytes', 'sha256')), 'INPUT_PLAN_SPLICE:' + name)
        checked(source['decision'])
        need(source['decision']['sha256'] ==
             '2766cf25223072c244d03da36e656f1b0946363e2d3cfa8c983d74fe9c3cd8a2',
             'C9_DECISION_IDENTITY')
        roles = {'exports': 'OBSERVER_EXPORTS_R06C9.json', 'row_schema': 'NORMALIZED_ROW_SCHEMA_R06C9.json',
                 'capture': 'CAPTURE_CONTRACT_R06C9.json'}
        need(set(source['contracts']) == set(roles), 'CAPTURE_CONTRACT_ROLES')
        for role, basename in roles.items():
            desc = artifact(checked(source['contracts'][role]))
            expected = owner_ref(basename)
            need(desc == expected, 'CAPTURE_CONTRACT_SPLICE:' + role)
        external_path = checked(proposed['external_inputs'])
        external = {str(no_alias(d['path'])): d for d in read(external_path)['files']}
        for tool in proposed['tools'].values():
            for desc in [tool['tool']['file'], *[item['file'] for item in tool['dependencies']]]:
                name = str(no_alias(desc['path']))
                need(name in external and all(desc[k] == external[name][k] for k in ('bytes', 'sha256')),
                     'TOOL_EXTERNAL_SPLICE')
                checked(desc, external=True)
        graph = read(artifact_paths['dependency_graph'])
        with zipfile.ZipFile(checked(source['application'])) as z:
            text = z.read('inputs/compile_c9_capture.f').decode('utf-8')
        ordered_units = [line.strip() for line in text.splitlines()
                         if line.strip() and not line.strip().startswith('+')]
        need(graph['units'] == ordered_units and len(set(ordered_units)) == 75
             and all('inputs/' + unit in full for unit in ordered_units), 'COMPILE_UNIT_ARCHIVE_SPLICE')
        need(len(graph['units']) == 75 and report['source_units'] == 75
             and application['source_counts'] == {'base_units': 72, 'with_capture_units': 75,
                 'ROMs': 9, 'headers': 2, 'aliases': 2}, 'C9_SOURCE_COUNTS')
        checked(proposed['window_reference'])
        context = request['context']
        need(isinstance(context, dict), 'CONTEXT_OBJECT')
        receipts = context.get('receipts', {})
        need(isinstance(receipts, dict), 'CONTEXT_RECEIPTS_OBJECT')
        for role, items in receipts.items():
            need(isinstance(items, list), 'CONTEXT_RECEIPT_LIST:' + role)
            for desc in items:
                checked(desc)
        code_refs = {role: fixed(role) for role in FIXED}
        need(source['capture_sources']['TB']['sha256'] ==
             'a31ae010d835d62b83096ba7604f8517793401eac90e928bbefeb2f024c89a4d'
             and source['stimulus_inputs']['reset.drv']['sha256'] ==
             'c255e20fafbd47d3591a9166ef736e1766ff1a8b93378afd4ef895ad693c1a52'
             and source['capture_sources']['DRIVER']['sha256'] ==
             '99e40266a46f1606409fa6ef270dd0c6b056dcb511363ae90dfbaf67653df89a',
             'DRAFT_TIMING_SOURCE_UNBOUND')
        draft = {'schema': 'N10_FRAME_INPUT_DRAFT_NOT_GENERATOR_INPUT_V1', 'capture_id': capture,
                 'status': 'PENDING_FINISH_PHASE', 'M2_frozen': False,
                 'first_core_ps': 12500, 'period_ps': 25000,
                 'epochs': [{'epoch': 0, 'assert': 0, 'release': 802, 'stop': 1000479},
                            {'epoch': 1, 'assert': 1000480, 'release': 1002482, 'stop': None}],
                 'finish': None, 'generator_invoked': False,
                 'derivation': 'Source-derived draft only; old TB248-251 same-phase negedge D or D+1 unresolved',
                 'source_refs': {'TB': source['capture_sources']['TB'],
                                 'reset_driver': source['stimulus_inputs']['reset.drv'],
                                 'window': proposed['window_reference']}}
        save(out / 'FRAME_INPUT_DRAFT.json', draft)
        pending = [
            {'item': 'FINISH_PHASE_D_OR_D_PLUS_1', 'owner': 'M2', 'condition': 'Freeze actual finish/core sampling phase'},
            {'item': 'TRUSTED_EXECUTOR_AND_EXACT_C9_EXECUTION', 'owner': 'M2', 'condition': 'New exact execution admission'},
            {'item': 'ACTUAL_RAW_PINS_RESET_EDGES_EXIT_STREAMS', 'owner': 'M3 after M2 admission', 'condition': 'Same-capture actual originals'},
            {'item': 'INDEPENDENT_APPLY_PLAN_AND_PCM24_ID_CLIP_GOLDEN', 'owner': 'M1', 'condition': 'Supported arithmetic/profile independent results'},
            {'item': 'AUDIO_STABLE_POLICY', 'owner': 'M2', 'condition': 'Published implementation/definition'},
            {'item': 'DUT_BACKPRESSURE_NOT_DRIVEN', 'owner': 'M2/M3', 'condition': 'ready.drv output is not connected to actual DUT ready'},
        ]
        context_known = False
        try:
            start = datetime.fromisoformat(context['original_START'])
            stop = datetime.fromisoformat(context['deadline'])
            goal = context['goal']
            context_known = (start.tzinfo is not None and stop.tzinfo is not None
                and 0 < (stop - start).total_seconds() <= 5 * 3600
                and isinstance(goal, dict) and isinstance(goal.get('threadId'), str)
                and bool(goal['threadId'].strip()) and type(goal.get('createdAt')) is int
                and goal['createdAt'] > 0 and goal.get('status') == 'active')
        except (KeyError, TypeError, ValueError):
            pass
        if not context_known:
            pending.append({'item': 'CONTEXT_IDENTITY_UNKNOWN', 'owner': 'night1/M3', 'condition': 'Bind existing START/deadline/Goal, no timer reset'})
        if not receipts.get('old_software') or not receipts.get('consumption'):
            pending.append({'item': 'SOFTWARE_OR_CONSUMPTION_RECEIPTS_MISSING', 'owner': 'night1/M3', 'condition': 'Supply actual preserved originals; no counters inferred'})
        if not receipts.get('first_failure'):
            pending.append({'item': 'FIRST_FAILURE_HISTORY_NOT_PROVIDED', 'owner': 'night1/M3', 'condition': 'Bind actual earlier failure originals; absence is not a no-failure claim'})
        identities = {'source_base': source['base'], 'application_archive': source['application'],
                      'archive_members': full, 'capture_roles': source['capture_sources'],
                      'checkers_and_mechanical_wrapper': code_refs, 'tools': proposed['tools'],
                      'tool_identity_reports': arts['tools'], 'dependency_graph': arts['dependency_graph'],
                      'dynamic_tool_dependencies': 'PENDING_NOT_AUTHENTICATED'}
        package = {
            'schema_version': 'N10_M3_INTEGRATION_HANDOFF_V1', 'capture_id': capture,
            'source_contract_refs': refs,
            'source_ROM_include_TB_driver_observer_checker_tool_identities': identities,
            'independent_input_plan': {'status': 'SOURCE_BOUND_NOT_EXECUTED', 'files': source['stimulus_inputs'],
                'ready_drv_applied_to_DUT': False, 'independent_apply_mapping': 'PENDING'},
            'clock_reset_profile_and_raw_edges': {'first_core_ps': 12500, 'period_ps': 25000,
                'input_reset_schedule': source['stimulus_inputs']['reset.drv'],
                'raw_edges': None, 'raw_edges_status': 'NOT_RUN', 'window': proposed['window_reference'],
                'finish_phase': 'SOURCE_UNFROZEN_D_OR_D_PLUS_1'},
            'unique_FRAME_PLAN_ref': {'status': 'PENDING_FINISH_PHASE', 'ref': None,
                'generator': code_refs['unique_FRAME_generator'], 'generator_invoked': False,
                'draft': artifact(out / 'FRAME_INPUT_DRAFT.json')},
            'raw_public_trace_and_pins_or_explicit_NOT_RUN': {'status': 'NOT_RUN', 'raw_ref': None, 'pins_ref': None},
            'math_input_bundle_ref': {'status': 'NOT_RUN', 'ref': None,
                'wrapper': code_refs['mechanical_math_wrapper'],
                'NEXT_INPUT_CONTRACT': owner_ref('NEXT_INPUT_CONTRACT.md'),
                'math_result_owner': 'M1', 'observed_PCM_used_as_golden': False},
            'exact_argv_cwd_environment_output_budget_request': {'request_ref': request['application_request'],
                'bound_plan_ref': arts['resolved_plan'], 'plan_sha256': plan_sha,
                'execution_spec': spec, 'resolved_cwd': bound['resolved_cwd'],
                'resolved_output': bound['resolved_output'], 'resolved_environment': bound['resolved_environment'],
                'requested_budget': bound['requested_budget'], 'execution_allowed': False},
            'assertions_and_software_receipts': {'expected_assertions': spec['expected_assertions'],
                'application_report': report, 'old_software_receipts': receipts.get('old_software', []),
                'reuse_scope': 'REUSED_PREVIOUS_SOFTWARE_ONLY_NOT_CURRENT_CAPTURE_EXECUTION'},
            'actual_exit_streams_finish_receipts_or_explicit_PENDING': {'status': 'PENDING_EXECUTION',
                'execution_receipt': None, 'exit_code': None, 'stdout': None, 'stderr': None, 'finish': None},
            'consumption_and_first_failure_history': {'consumption_refs': receipts.get('consumption', []),
                'first_failure_refs': receipts.get('first_failure', []), 'other_receipts': receipts,
                'new_execution_consumed_by_assembler': False, 'old_consumption_restored': False,
                'context': context},
            'missing_inputs_and_next_owner': pending,
            'status': 'SOURCE_BOUND_PREPARATION', 'HDL_status': 'HDL_NOT_RUN',
            'execution_allowed': False, 'execution_verified': False, 'real_verified': False,
            'math_verified': False, 'board_release_allowed': False,
            'application_request_ref': request['application_request'], 'context_known': context_known,
            'owner_contract': owner, 'structural_identity_is_not_authenticity': True,
        }
        need(set(contract['package_fields']) <= package.keys(), 'OWNER_PACKAGE_FIELD_MISSING')
        for name, desc in tracked.items():
            need(artifact(name) == desc, 'READ_AFTER_INPUT_CHANGED:' + name)
        save(out / 'INPUT_IDENTITIES.json', {'files': list(tracked.values()), 'read_after_equal': True})
        save(out / 'INTEGRATION_HANDOFF.json', package)
        return {'schema': 'N10_M3_HANDOFF_RESULT_V1', 'status': package['status'], 'capture_id': capture,
                'artifacts': {'integration_handoff': artifact(out / 'INTEGRATION_HANDOFF.json'),
                              'frame_input_draft': artifact(out / 'FRAME_INPUT_DRAFT.json'),
                              'input_identities': artifact(out / 'INPUT_IDENTITIES.json')},
                'pending': pending, 'HDL_status': 'HDL_NOT_RUN', 'execution_allowed': False,
                'real_verified': False, 'math_verified': False, 'board_release_allowed': False}
    except Exception as error:
        save(out / 'FIRST_FAILURE.json', {'status': 'REJECT', 'reason': str(error),
                'checked_inputs': list(tracked.values()), 'originals_retained': True,
                'execution_allowed': False, 'real_verified': False, 'board_release_allowed': False})
        raise
