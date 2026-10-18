"""Four NEW metadata handoff seams. Coordinator-only; no old tests run."""
import copy
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[7]
DOC = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/serial'
SOURCE_SHA = '1ccc1c20a756c649fc6f5325eec20408c73d879f61a15e3e207815a7990f388f'
FIXTURE_SHA = 'd174b719d57ee1bdfb7b5defb713c7decd1b50dc4c6e079a4343b2fc9b51a1c0'


def run_case(case_id, out):
    expected = {
        'N10_HANDOFF_COMPLETE_PACKAGE': 'SOURCE_BOUND_PREPARATION',
        'N10_HANDOFF_CAPTURE_SOURCE_SPLICE': 'CAPTURE_MISMATCH+APPLICATION_SOURCE_SPLICE',
        'N10_HANDOFF_RESERVATION_CLAIM_SPLICE': 'RESERVATION_SPLICE+CLAIM_PLAN_CAPTURE_SPLICE',
        'N10_HANDOFF_UNKNOWN_NO_REAL_AUTHORITY': 'SOURCE_BOUND_PREPARATION',
    }[case_id]
    body = Path(__file__).with_name('handoff.py').read_bytes()
    assert hashlib.sha256(body).hexdigest() == SOURCE_SHA
    module = ModuleType('_n10_handoff_new_seam')
    module.__file__ = str(Path(__file__).with_name('handoff.py'))
    exec(compile(body, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    fixture = DOC / 'FIXTURE_REQUEST.json'
    assert module.identity(fixture)['sha256'] == FIXTURE_SHA
    request = module.read(fixture)
    module.save(out / 'INPUT_BEFORE_CALL.json', request)
    negatives = []

    def rejected(value, name, reason):
        try:
            result = module.assemble(value, out / name)
        except ValueError as error:
            actual = str(error)
        else:
            actual = result['status']
        module.save(out / (name + '_ACTUAL.json'), {'expected': reason, 'actual': actual})
        assert actual == reason, (reason, actual)
        assert (out / name / 'FIRST_FAILURE.json').is_file()
        negatives.append(actual)

    if case_id == 'N10_HANDOFF_CAPTURE_SOURCE_SPLICE':
        changed = copy.deepcopy(request)
        changed['capture_id'] += '_DIFFERENT'
        rejected(changed, 'capture', 'CAPTURE_MISMATCH')
        changed = copy.deepcopy(request)
        original = module.read(ROOT / changed['application_report']['artifacts']['application']['path'])
        original['source']['base']['sha256'] = '0' * 64
        module.save(out / 'MIXED_APPLICATION.json', original)
        changed['application_report']['artifacts']['application'] = module.artifact(out / 'MIXED_APPLICATION.json')
        rejected(changed, 'source', 'APPLICATION_SOURCE_SPLICE')
        actual = '+'.join(negatives)
    elif case_id == 'N10_HANDOFF_RESERVATION_CLAIM_SPLICE':
        changed = copy.deepcopy(request)
        reserve = module.read(ROOT / changed['application_report']['artifacts']['reservation']['path'])
        reserve['output'] += '_OTHER_CAPTURE'
        module.save(out / 'MIXED_RESERVATION.json', reserve)
        changed['application_report']['artifacts']['reservation'] = module.artifact(out / 'MIXED_RESERVATION.json')
        rejected(changed, 'reservation', 'RESERVATION_SPLICE')
        changed = copy.deepcopy(request)
        claim = module.read(ROOT / changed['application_report']['artifacts']['claim']['path'])
        claim['nonce'] = '0' * 64
        module.save(out / 'MIXED_CLAIM.json', claim)
        changed['application_report']['artifacts']['claim'] = module.artifact(out / 'MIXED_CLAIM.json')
        rejected(changed, 'claim', 'CLAIM_PLAN_CAPTURE_SPLICE')
        actual = '+'.join(negatives)
    else:
        if case_id == 'N10_HANDOFF_UNKNOWN_NO_REAL_AUTHORITY':
            request['context'] = {'original_START': '', 'deadline': 'UNKNOWN', 'goal': {}, 'receipts': {}}
        else:
            # Unrelated same-basename refs must not override fixed owner paths.
            extras = []
            for filename in ('NORMALIZED_ROW_SCHEMA_R06C9.json', 'NEXT_INPUT_CONTRACT.md'):
                module.save(out / filename, {'untrusted_extra': 'NOT_THE_OWNER_ROLE'})
                extras.append(module.artifact(out / filename))
            request['source_contract_refs'] = extras + request['source_contract_refs']
        result = module.assemble(request, out / 'handoff')
        actual = result['status']
        module.save(out / 'ACTUAL_BEFORE_ASSERT.json', result)
        package = module.read(out / 'handoff/INTEGRATION_HANDOFF.json')
        contract = module.read(module.OWNER)
        assert set(contract['package_fields']) <= package.keys()
        assert package['capture_id'] == request['capture_id']
        assert package['status'] == 'SOURCE_BOUND_PREPARATION' and package['HDL_status'] == 'HDL_NOT_RUN'
        for field in ('execution_allowed', 'execution_verified', 'real_verified',
                      'math_verified', 'board_release_allowed'):
            assert package[field] is False
        assert package['unique_FRAME_PLAN_ref']['status'] == 'PENDING_FINISH_PHASE'
        assert package['unique_FRAME_PLAN_ref']['ref'] is None
        assert package['unique_FRAME_PLAN_ref']['generator_invoked'] is False
        assert package['math_input_bundle_ref']['ref'] is None
        assert package['math_input_bundle_ref']['status'] == 'NOT_RUN'
        receipt = package['actual_exit_streams_finish_receipts_or_explicit_PENDING']
        assert all(receipt[k] is None for k in ('execution_receipt', 'exit_code', 'stdout', 'stderr', 'finish'))
        assert package['independent_input_plan']['ready_drv_applied_to_DUT'] is False
        assert {p.name for p in (out / 'handoff').iterdir()} == {
            'REQUEST.json', 'FRAME_INPUT_DRAFT.json', 'INPUT_IDENTITIES.json', 'INTEGRATION_HANDOFF.json'}
        if case_id == 'N10_HANDOFF_UNKNOWN_NO_REAL_AUTHORITY':
            assert package['context_known'] is False
            assert any(p['item'] == 'CONTEXT_IDENTITY_UNKNOWN' for p in result['pending'])
            assert any(p['item'] == 'SOFTWARE_OR_CONSUMPTION_RECEIPTS_MISSING' for p in result['pending'])
        else:
            assert package['context_known'] is True
            assert package['math_input_bundle_ref']['NEXT_INPUT_CONTRACT']['path'] == (
                'code/docs/test/m1_r05_pcm_oracle_20261016/pro_r06_20261017/oracle_adapter/NEXT_INPUT_CONTRACT.md')
    module.save(out / 'EXPECTATION.json', {'case_id': case_id, 'expected': expected, 'actual': actual})
    assert actual == expected, (expected, actual)
    return {'status': 'CASE_EXPECTATION_MATCHED', 'case_id': case_id, 'expected': expected,
            'actual': actual, 'real_verified': False, 'math_verified': False,
            'execution_allowed': False, 'board_release_allowed': False}
