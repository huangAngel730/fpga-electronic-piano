"""54 individually counted proposed calls. Importing does not execute a case.

This is a dispatch contract. Fixture freezing belongs to the approved group,
inside its original clock; absence of any case callable fails closed.
"""
import hashlib
import json
from pathlib import Path


def freeze_matrix(path, expected_sha256):
    with Path(path).open('rb') as file:
        raw = file.read((1 << 20) + 1)
    if len(raw) > 1 << 20 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('CASE_MATRIX_IDENTITY')
    matrix = json.loads(raw)
    cases = matrix['cases']
    ids = [case['id'] for case in cases]
    if len(ids) != 54 or len(set(ids)) != 54 or ids != [f'P{i:02}' for i in range(1,9)] + [f'N{i:02}' for i in range(1,47)]:
        raise ValueError('EXACT_54_CASES_REQUIRED')
    if any(case['actual_target_calls'] != 1 for case in cases):
        raise ValueError('HIDDEN_CASE_INVOCATIONS')
    return cases


def run_cases(cases, handlers, audit, tick):
    """One handler call per case; it must report actual nested target invocations."""
    invoked = 0
    for case in cases:
        tick()
        handler = handlers.get(case['id'])
        if handler is None:
            raise ValueError('PENDING_CASE_CALLABLE:' + case['id'])
        result = handler(case)
        invoked += 1
        audit.append('comparison', dict(case_id=case['id'], result=result,
                                         dispatched_calls=invoked))
        if result.get('target_invocations') != 1:
            raise ValueError('CASE_INVOCATION_COUNT:' + case['id'])
        if result.get('status') != case['expected_status'] or result.get('code') != case['expected_code']:
            raise ValueError('FIRST_UNEXPECTED_CASE_RESULT:' + case['id'])
        expected = case.get('first_difference_exact')
        if expected and any(result.get('first_difference', {}).get(k) != v for k,v in expected.items()):
            raise ValueError('FIRST_DIFFERENCE_IDENTITY:' + case['id'])
    if invoked != 54:
        raise ValueError('CASE_DISPATCH_INCOMPLETE')
    return dict(status='SOFTWARE_CASES_MATCHED', invocations=invoked,
                real_verified=False, math_verified=False)
