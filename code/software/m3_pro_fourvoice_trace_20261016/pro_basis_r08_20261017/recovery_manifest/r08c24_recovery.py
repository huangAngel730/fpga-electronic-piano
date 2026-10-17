"""Read-only physical/build/recovery/one-SRAM binding; cannot authorize a write."""
import importlib.util
import json
from pathlib import Path

ARTIFACTS = ('sources', 'rom', 'constraints', 'pll', 'fs', 'pnr', 'sta', 'cdc', 'recovery')
COVERAGE = ('setup', 'hold', 'recovery', 'removal', 'generated_clocks', 'io_timing', 'cdc')


def shared():
    p = Path(__file__).resolve().parents[1] / 'i2s_serial_compare/r08c_common.py'
    s = importlib.util.spec_from_file_location('r08c24_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def analyze(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_RECOVERY_PREFLIGHT_V1', 'RECOVERY_MANIFEST_SCHEMA')
    permission = data.get('permission', {})
    c.need(permission.get('mode') != 'FLASH' and permission.get('flash_write_allowed') is not True, 'FLASH_FORBIDDEN')
    c.need(permission.get('consumed_count', 0) == 0 and permission.get('requested_count', 1) == 1, 'SRAM_REUSE_OR_REPEAT')
    expected = data.get('physical_identity', {})
    if not expected.get('part') or not expected.get('version') or not expected.get('unit_id'):
        return c.report('PENDING_PHYSICAL_IDENTITY', missing=['part/version/unit_id'])
    c.need('PG484' not in expected['part'].upper() and 'PG484' not in expected.get('package', '').upper(), 'OLD_PG484_TARGET')
    if expected.get('verification') != 'ORIGINAL_EVIDENCE_AVAILABLE':
        return c.report('PENDING_PHYSICAL_IDENTITY', physical_identity=expected)
    build = data.get('build', {})
    c.need(build.get('part') == expected['part'] and build.get('version') == expected['version'], 'TARGET_VERSION_MISMATCH')
    artifacts = data.get('artifacts', {})
    missing = [role for role in ARTIFACTS if role not in artifacts]
    if missing:
        return c.report('PENDING_BUILD_RECOVERY_MATERIAL', missing=missing)
    identified = {}
    for role in ARTIFACTS:
        item = artifacts[role]
        file = c.bounded_file(data['input_root'], item['path'])
        identity = c.identity(file)
        c.need(identity['sha256'] == item.get('sha256') and identity['bytes'] == item.get('bytes'), 'RECOVERY_ARTIFACT_SHA', role=role)
        c.need(item.get('part') == expected['part'] and item.get('version') == expected['version'], 'ARTIFACT_TARGET', role=role)
        c.need(item.get('source_sha256') == build.get('source_sha256'), 'ARTIFACT_SOURCE_VERSION', role=role)
        identified[role] = identity
    c.need(identified['sources']['sha256'] == build.get('source_sha256'), 'SOURCE_CLOSURE_SHA')
    c.need(Path(identified['fs']['path']).suffix.lower() == '.fs', 'NEW_FS_REQUIRED')
    c.need(identified['fs']['sha256'] != data.get('forbidden_old_fs_sha256'), 'OLD_FS_REUSED')
    raw_reports = {}
    for role in ('sta', 'cdc'):
        try:
            raw_reports[role] = json.loads(Path(identified[role]['path']).read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            return c.report('PENDING_REPORT_FORMAT_UNSUPPORTED', role=role, artifacts=identified)
        report = raw_reports[role]
        if not isinstance(report, dict) or report.get('schema') != 'M3_R08_NORMALIZED_PHYSICAL_REPORT_V1':
            return c.report('PENDING_REPORT_FORMAT_UNSUPPORTED', role=role, artifacts=identified)
        c.need(report.get('part') == expected['part'] and report.get('version') == expected['version']
               and report.get('source_sha256') == build['source_sha256'], 'PHYSICAL_REPORT_VERSION', role=role)
    coverage = data.get('timing_coverage', {})
    c.need(coverage == raw_reports['sta'].get('coverage') and coverage.get('cdc') == raw_reports['cdc'].get('coverage', {}).get('cdc'),
           'COVERAGE_DECLARATION_DIFFERENCE')
    missing = [key for key in COVERAGE if coverage.get(key) != 'PASS']
    if missing or coverage.get('unconstrained_paths') != 0:
        return c.report('PENDING_FULL_PHYSICAL_COVERAGE', missing=missing, coverage=coverage, artifacts=identified)
    c.need(permission.get('mode') == 'SRAM_ONLY' and permission.get('single_use') is True, 'EXACT_SRAM_PERMISSION_REQUIRED')
    for key, value in {'fs_sha256': identified['fs']['sha256'], 'unit_id': expected['unit_id'],
                       'session_id': data.get('session_id'), 'part': expected['part'], 'version': expected['version']}.items():
        c.need(permission.get(key) == value and value is not None, 'PERMISSION_SCOPE_MISMATCH', field=key)
    # Even complete self-supplied files and approved:true do not create a trusted
    # M2 permission/physical identity verifier. No consumed flag is mutated.
    return c.report('PENDING_TRUSTED_M2_ADMISSION', mechanical_structure='COMPLETE',
                    artifacts=identified, permission_unmodified=permission,
                    timing_coverage=coverage, physical_identity=expected,
                    download_authorized=False, operations_performed=0)


if __name__ == '__main__':
    raise SystemExit(shared().cli(analyze))
