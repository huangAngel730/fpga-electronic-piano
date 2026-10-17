"""Reuse B comparison and explain the earliest public difference; no top added."""
import importlib.util
from pathlib import Path

B_SHA = 'a8dbe186a4e8afcf5d931a52ac57b14734a2cd53113a71444378ce3658dabb8d'
PINS = ('BCLK', 'LRCLK', 'DIN', 'PA_EN', 'UART_TX', 'TMDS_CLK_P', 'TMDS_CLK_N',
        'TMDS_DATA_P0', 'TMDS_DATA_P1', 'TMDS_DATA_P2', 'TMDS_DATA_N0', 'TMDS_DATA_N1', 'TMDS_DATA_N2')


def shared():
    p = Path(__file__).resolve().parents[1] / 'i2s_serial_compare/r08c_common.py'
    s = importlib.util.spec_from_file_location('r08c18_common', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def analyze(data):
    c = shared()
    c.need(data.get('schema') == 'M3_R08_PUBLIC_DIFF_INPUT_V1', 'PUBLIC_DIFF_SCHEMA')
    c.need(data.get('allowed_differences') == [], 'UNSUPPORTED_DIFFERENCE_WHITELIST')
    root = Path(__file__).resolve().parents[5]
    source = root / 'code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_equivalence_tb/equivalence.py'
    b = c.load_module(source, 'r08c18_frozen_b_comparator', B_SHA)
    base = data['input_root']
    paths = {role: c.bounded_file(base, data[role]) for role in ('csv', 'events', 'stdout')}
    for role, p in paths.items():
        c.need(c.identity(p)['sha256'] == data['inputs_sha256'][role], 'PUBLIC_DIFF_INPUT_SHA', role=role)
    start, stop = data['start_cycle'], data['stop_cycle']
    start_ps, stop_ps = 12500 + (start - 1) * 25000, 12500 + (stop - 1) * 25000
    errors, checked = [], {}
    for role in ('samples', 'events'):
        try:
            checked[role] = (b.compare(paths['csv'], paths['stdout'], start, stop) if role == 'samples'
                             else b.compare_events(paths['events'], paths['stdout'], start_ps, stop_ps))
        except b.Reject as error:
            detail = error.detail
            at = detail.get('time_ps', 12500 + (detail['cycle'] - 1) * 25000 if 'cycle' in detail else -1)
            names = []
            if 'original' in detail and 'observer' in detail:
                names = [PINS[i] for i, (a, v) in enumerate(zip(detail['original'][::-1], detail['observer'][::-1])) if a != v]
            errors.append({'code': error.code, 'time_ps': at, 'stream': role, 'detail': detail,
                           'public_pins': names, 'allowance': 'NONE_M2_ALLOWED_TABLE_EMPTY'})
    identities = {role: c.identity(p) for role, p in paths.items()}
    if errors:
        first = min(errors, key=lambda error: error['time_ps'])
        return c.report('REJECT', reason='PUBLIC_DIFFERENCE_OR_CONTRACT', first_difference=first,
                        all_differences=errors, input_identities=identities,
                        source_identities=data.get('source_identities'), original_observations='NOT_PUBLIC')
    status = checked['samples']['status']
    return c.report(status, comparison=checked, input_identities=identities,
                    source_identities=data.get('source_identities'), original_observations='NOT_PUBLIC',
                    comparator=c.identity(source), diagnostic_fields_never_whitelisted=True)


if __name__ == '__main__':
    raise SystemExit(shared().cli(analyze))
