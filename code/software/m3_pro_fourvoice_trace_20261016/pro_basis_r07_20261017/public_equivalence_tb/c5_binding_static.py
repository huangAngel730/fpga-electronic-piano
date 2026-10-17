"""Static ZIP/source identity only; does not import or execute B tests/HDL."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[5]
M2 = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017'
OUT = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_equivalence_tb/c5_binding'


def ident(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def main():
    decision = json.loads((M2 / 'SOURCE_DECISION_R06C5.json').read_text(encoding='utf-8'))
    archive = M2 / 'SOURCE_CLOSURE_R06C5.zip'
    assert ident(archive)['sha256'] == decision['archive']['sha256']
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        entries = [{'member': n, 'bytes': len(zipped.read(n)), 'sha256': hashlib.sha256(zipped.read(n)).hexdigest()}
                   for n in zipped.namelist() if not n.endswith('/')]
        units = [s.strip() for s in zipped.read('inputs/compile.f').decode('utf-8').splitlines()
                 if s.strip() and not s.strip().startswith('#')]
        assert len(units) == 71
        assert all('inputs/' + n in zipped.namelist() for n in units)
        literal = {}
        for name in units:
            for module in re.findall(rb'(?m)^\s*module\s+([A-Za-z_][A-Za-z_0-9]*)', zipped.read('inputs/' + name)):
                literal.setdefault(module.decode(), []).append(name)
        assert len(literal) == 73 and all(len(v) == 1 for v in literal.values())
        leaf = zipped.read('inputs/selected/dds_oscillator_leaf.sv')
        original = zipped.read('provenance/ORIGINAL_dds_oscillator.sv')
        assert original[:1240] + b'\n' == leaf
        assert len(leaf) == 1241 and hashlib.sha256(leaf).hexdigest() == decision['DDS_derivation']['leaf']['sha256']
        assert hashlib.sha256(original).hexdigest() == decision['DDS_derivation']['original']['sha256']
        assert literal['sine_wavetable_1024'] == ['sources/m1td_dds_oscillator.sv']
        roms = [e for e in entries if e['member'].startswith('inputs/rom/')]
        assert len(roms) == 9
    save('STATIC_BINDING.json', {
        'schema': 'M3_R7B_C5_STATIC_BINDING_V1', 'status': 'L0_STATIC_ONLY_B_NOT_RERUN',
        'decision': ident(M2 / 'SOURCE_DECISION_R06C5.json'), 'archive': ident(archive),
        'selected_units': units, 'selected_unit_count': 71, 'roms': roms,
        'literal_module_count': 73, 'module_to_source_literal_only': literal,
        'DDS_derivation': decision['DDS_derivation'], 'list_base': 'unpacked inputs directory',
        'observer_top': decision['top'], 'payloads': entries,
        'checks': {'ZIP_CRC': True, 'all_selected_payloads_present': True,
                   'literal_module_duplicates': False, 'DDS_leaf_byte_derivation': True},
        'dual_equivalence_closure': 'NOT_REASSEMBLED_NOT_COMPILED_REQUIRES_M2_EXACT_BINDING',
        'HDL_EDA_hardware_calls': 0, 'B_functional_runs_added': 0, 'execution_admission': None,
        'board_release_allowed': False})
    save('FROZEN_B_REFERENCES.json', {'files': [ident(OUT.parent / name) for name in ('RESULT.md', 'RECEIPT.json', 'FILE_SHA.json')
                                            if (OUT.parent / name).is_file()],
         'unchanged_B_final_delta': '<=stop L0 NOT_RUN; R01/R02 tied to their own original snapshots'})
    print(json.dumps({'units': len(units), 'ROM': len(roms), 'modules': len(literal), 'archive': ident(archive)}))


if __name__ == '__main__':
    main()
