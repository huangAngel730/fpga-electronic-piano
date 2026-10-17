"""New H24 material preflight fixtures; no permission or device operation."""
import importlib.util
import json
from pathlib import Path


def fixture(c, directory):
    directory.mkdir(parents=True, exist_ok=False)
    # Deliberately fictitious test identity; never a claim about the user's part.
    part, version = 'SYNTHETIC_TEST_ONLY_PG676', 'SYNTHETIC_VERSION_A'
    sources = directory / 'sources.json'; sources.write_bytes(b'{"synthetic_source_closure":true}\n')
    source_sha = c.identity(sources)['sha256']
    artifacts = {}
    for role in ('sources', 'rom', 'constraints', 'pll', 'fs', 'pnr', 'sta', 'cdc', 'recovery'):
        file = sources if role == 'sources' else directory / (role + ('.fs' if role == 'fs' else '.txt'))
        if role != 'sources': file.write_bytes(('SYNTHETIC_ONLY_' + role + '\n').encode('ascii'))
        identity = c.identity(file)
        artifacts[role] = {'path': file.name, 'bytes': identity['bytes'], 'sha256': identity['sha256'],
                           'part': part, 'version': version, 'source_sha256': source_sha}
    identity = {'part': part, 'package': 'SYNTHETIC_PG676', 'version': version, 'unit_id': 'SYNTHETIC_UNIT24',
                'verification': 'ORIGINAL_EVIDENCE_AVAILABLE'}
    permission = {'mode': 'SRAM_ONLY', 'single_use': True, 'flash_write_allowed': False,
                  'consumed_count': 0, 'requested_count': 1, 'session_id': 'SYNTH_H24_SESSION',
                  'fs_sha256': artifacts['fs']['sha256'], 'unit_id': identity['unit_id'], 'part': part, 'version': version}
    return {'schema': 'M3_R08_RECOVERY_PREFLIGHT_V1', 'origin': 'SYNTHETIC', 'input_root': str(directory),
            'session_id': 'SYNTH_H24_SESSION', 'physical_identity': identity,
            'build': {'part': part, 'version': version, 'source_sha256': source_sha}, 'artifacts': artifacts,
            'timing_coverage': {**dict.fromkeys(('setup', 'hold', 'recovery', 'removal', 'generated_clocks', 'io_timing', 'cdc'), 'PASS'),
                                'unconstrained_paths': 0}, 'permission': permission}


def run_case(case_id, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    p = Path(__file__).with_name('r08c24_recovery.py')
    s = importlib.util.spec_from_file_location('r08c24_test_engine', p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    c = m.shared(); data = fixture(c, Path(output_dir) / 'input_files')
    expected = {'H24_COMPLETE_STILL_PENDING': 'PENDING_TRUSTED_M2_ADMISSION', 'H24_OLD_PG484': 'OLD_PG484_TARGET',
                'H24_UNKNOWN_VERSION': 'PENDING_PHYSICAL_IDENTITY', 'H24_MISSING_FS': 'PENDING_BUILD_RECOVERY_MATERIAL',
                'H24_MISSING_RECOVERY_REMOVAL': 'PENDING_FULL_PHYSICAL_COVERAGE', 'H24_WRONG_FS_PERMISSION': 'PERMISSION_SCOPE_MISMATCH',
                'H24_FLASH_FORBIDDEN': 'FLASH_FORBIDDEN', 'H24_CONSUMED_SRAM': 'SRAM_REUSE_OR_REPEAT',
                'H24_PERMISSION_OTHER_VERSION': 'PERMISSION_SCOPE_MISMATCH'}[case_id]
    if case_id == 'H24_OLD_PG484': data['physical_identity']['part'] = 'SYNTHETIC_PG484'
    if case_id == 'H24_UNKNOWN_VERSION': data['physical_identity']['version'] = None
    if case_id == 'H24_MISSING_FS': del data['artifacts']['fs']
    if case_id == 'H24_MISSING_RECOVERY_REMOVAL':
        data['timing_coverage']['recovery'] = data['timing_coverage']['removal'] = 'UNKNOWN'
    if case_id == 'H24_WRONG_FS_PERMISSION': data['permission']['fs_sha256'] = '0' * 64
    if case_id == 'H24_FLASH_FORBIDDEN': data['permission'].update(mode='FLASH', flash_write_allowed=True)
    if case_id == 'H24_CONSUMED_SRAM': data['permission']['consumed_count'] = 1
    if case_id == 'H24_PERMISSION_OTHER_VERSION': data['permission']['version'] = 'SYNTHETIC_OTHER_VERSION'
    for role in ('sta', 'cdc'):
        record = data['artifacts'][role]
        body = {'schema': 'M3_R08_NORMALIZED_PHYSICAL_REPORT_V1', 'part': record['part'], 'version': record['version'],
                'source_sha256': record['source_sha256'], 'coverage': data['timing_coverage'], 'origin': 'SYNTHETIC'}
        target = Path(data['input_root']) / record['path']
        target.write_text(json.dumps(body) + '\n', encoding='utf-8', newline='\n')
        record['sha256'], record['bytes'] = c.identity(target)['sha256'], c.identity(target)['bytes']
    c.save(Path(output_dir) / 'INPUT_BEFORE_CALL.json', data)
    actual = c.call(m.analyze, data)
    c.save(Path(output_dir) / 'ACTUAL_BEFORE_ASSERT.json', actual)
    if case_id == 'H24_COMPLETE_STILL_PENDING':
        assert actual['mechanical_structure'] == 'COMPLETE' and actual['download_authorized'] is False
        assert actual['operations_performed'] == 0 and data['permission']['consumed_count'] == 0
    return c.check_case(output_dir, data, actual, expected)
