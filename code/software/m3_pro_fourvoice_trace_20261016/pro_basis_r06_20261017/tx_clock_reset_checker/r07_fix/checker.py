"""R07 candidate front-end. Old R6-6 and its twenty cases remain read-only."""
import argparse
import json
from pathlib import Path

import serial_core as core
from boundaries import provenance, validate_profile, validate_transactions, verify_plan
from crosspack import A_SCHEMA, CAL_SCHEMA, load_rows, adapt_calendar


def prepare(binding, calendar, plan, oracle, rows, input_bytes, rules_bytes):
    provenance(binding)
    internal_binding = dict(binding)
    if binding.get('trace_profile') == A_SCHEMA:
        internal_binding['trace_profile'] = 'R06C3_TX_FLAT_V1'
    profile = validate_profile(internal_binding, rows, oracle)
    frame_view = verify_plan(plan, input_bytes, rules_bytes, rows)
    calendar_adapter, pending = adapt_calendar(calendar, rows)
    calendar_view, ledger = validate_transactions(calendar_adapter, plan, rows)
    if calendar_adapter.get('canonical_plan_id') != plan['canonical_plan_id']:
        raise core.Reject('FA_CALENDAR_PLAN_ID')
    # Compatibility views only; neither the unique plan nor the raw rows change.
    # request_cycle remains A in the inherited serial backend. F/first_valid/A
    # and original source lines survive in the new boundary ledger/report.
    calendar_view['schema'] = 'M3_R06_TX_TRANSACTION_CALENDAR_V1'
    return profile, frame_view, calendar_view, ledger, pending


def run_files(paths, binding_sha, decoder, decoder_sha, output):
    identities = {}
    preservation = {}
    details = {}
    try:
        identities['binding'] = {'path': str(paths['binding']), 'sha256': core.sha256(paths['binding'])}
        if identities['binding']['sha256'] != binding_sha:
            raise core.Reject('BINDING_SHA')
        binding = core.load_json(paths['binding'])
        provenance(binding)
        if binding.get('trace_profile') not in ('LEGACY_R06_FLAT_V1', 'R06C3_TX_FLAT_V1', A_SCHEMA):
            raise core.Pending('PENDING_UNSUPPORTED_PROFILE')
        identities.update({name: {'path': str(path), 'sha256': core.sha256(path)} for name, path in paths.items() if name != 'binding'})
        core.verify_input_hashes(binding, {name: path for name, path in paths.items() if name != 'binding'})
        calendar, plan, oracle = [core.load_json(paths[role]) for role in ('calendar', 'frame_plan', 'oracle')]
        if calendar.get('schema') == CAL_SCHEMA:
            preservation['r65_calendar'] = calendar
        rows = load_rows(paths['trace'], binding.get('trace_profile'), preservation)
        profile, frame_view, calendar_view, ledger, pending = prepare(binding, calendar, plan, oracle, rows,
                                                             paths['frame_input'].read_bytes(), paths['frame_rules'].read_bytes())
        details = {'unique_plan_id': plan['canonical_plan_id'], 'trace_profile': binding['trace_profile'],
                   'backend_profile': profile, 'frame_first_valid_accept_ledger': ledger,
                   'pending_reasons': pending, 'compatibility_view': 'request_cycle_is_A_F_NOT_MOVED'}
        if pending:
            raise core.Pending('PENDING_TX_SELECTION_PLAN', 'Native R6-5 observed report retained; no independent selection oracle or producer admission invented')
        module = core.load_decoder(decoder, decoder_sha)
        internal_binding = {**binding, 'trace_profile': profile}
        report = core.analyze(internal_binding, calendar_view, frame_view, oracle, rows, module)
        report.update(schema='M3_R07_FA_TX_REPORT_V1', real_pro_tx_pass=False,
                      unique_plan_id=plan['canonical_plan_id'], trace_profile=profile,
                      frame_first_valid_accept_ledger=ledger,
                      compatibility_view='request_cycle_is_A_F_NOT_MOVED',
                      inherited_serial_verification='READ_RESULT_NOT_REPLACED_BY_BOUNDARY_PASS')
        code = 0
    except core.Pending as error:
        report, code = {'status': error.code, 'detail': error.detail, 'real_pro_tx_pass': False}, 3
    except (core.Reject, OSError, ValueError, TypeError, KeyError) as error:
        report, code = {'status': 'REJECT', 'error': getattr(error, 'code', str(error)),
                        'detail': getattr(error, 'detail', ''), 'real_pro_tx_pass': False}, 2
    report.update(details)
    report.update(schema='M3_R07_FA_TX_REPORT_V1', inputs=identities,
                  crosspack_preservation=preservation, board_release_allowed=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return code, report


def main():
    ap = argparse.ArgumentParser()
    for name in ('binding', 'calendar', 'frame-plan', 'oracle', 'trace', 'frame-input', 'frame-rules', 'decoder', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--binding-sha', required=True)
    ap.add_argument('--decoder-sha', required=True)
    args = ap.parse_args()
    paths = {name: getattr(args, name) for name in ('binding', 'calendar', 'frame_plan', 'oracle', 'trace', 'frame_input', 'frame_rules')}
    code, report = run_files(paths, args.binding_sha, args.decoder, args.decoder_sha, args.output)
    print(json.dumps({'status': report['status'], 'error': report.get('error'), 'exit_code': code}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
