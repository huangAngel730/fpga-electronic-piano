"""Assemble the exact simulation-only C3 closure; never invoke an HDL tool."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
DOC = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017'
RTL = ROOT / 'code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017'
BASE = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/same_version_binding_20261017/M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip'


def ident(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    archive = DOC / 'SOURCE_CLOSURE_R06C5.zip'
    if archive.exists():
        raise SystemExit('EXCLUSIVE_SOURCE_ARCHIVE_EXISTS_DO_NOT_OVERWRITE')
    assert ident(BASE.read_bytes())['sha256'] == '931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2'
    binding = json.loads((DOC.parent / 'r06_observer_20261017/OBSERVER_EXPORTS_R06C3.json').read_text(encoding='utf-8'))
    payloads = {}
    with zipfile.ZipFile(BASE) as z:
        prefix = 'source_closure/inputs/'
        original_list = z.read(prefix + 'compile.f')
        original = original_list.decode('utf-8').splitlines()
        assert len(original) == 69 and all(p and not p.startswith('-') for p in original)
        excluded = {'sources/m2_fourvoice_timbre_delay_board_top.sv',
                    'sources/m2_fourvoice_timbre_delay_frame_core.sv', 'tb_m2_m1td_real_chain.sv'}
        selected = [p for p in original if p not in excluded]
        assert len(selected) == 66
        for name in selected:
            payloads['inputs/' + name] = z.read(prefix + name)
        original_dds = z.read(prefix + 'sources/dds_oscillator.sv')
        m1_dds = z.read(prefix + 'sources/m1td_dds_oscillator.sv')
        assert ident(original_dds)['sha256'] == '9588637c20348c7df8eda5ab5bca780de4468aec607fc9d4b918df63f746c556'
        marker = b'module sine_wavetable_1024'
        shared = original_dds[original_dds.index(marker):]
        assert shared == m1_dds[m1_dds.index(marker):]
        assert ident(shared)['sha256'] == '4b1d526758efd05c2780d24b8116bc3660620aa98f639b3a2813e633c17d216f'
        assert original_dds[:1240].rstrip().endswith(b'endmodule')
        leaf = original_dds[:1240] + b'\n'
        assert ident(leaf)['sha256'] == '303e3a9927e743d4149ceae4bb8754ebb8abdfb14638d407254b8e555dfcd3bd'
        roms = [n for n in z.namelist() if n.startswith(prefix + 'rom/') and not n.endswith('/')]
        assert len(roms) == 9
        for name in roms:
            payloads['inputs/' + name[len(prefix):]] = z.read(name)
    for name, expected_sha in binding['source_sha256'].items():
        raw = (RTL / name).read_bytes()
        assert ident(raw)['sha256'] == expected_sha, 'SELECT_PUBLISHED_C3_ONLY:' + name
        selected.append('selected/' + name)
        payloads['inputs/selected/' + name] = raw
    selected.append('selected/dds_oscillator_leaf.sv')
    payloads['inputs/selected/dds_oscillator_leaf.sv'] = leaf
    assert len(selected) == 71
    # This counts literal module declarations only; it is not elaboration.
    modules = {}
    for name in selected:
        text = payloads['inputs/' + name].decode('utf-8')
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        for module in re.findall(r'\bmodule\s+(\w+)', text):
            assert module not in modules, 'DUPLICATE_LITERAL_MODULE:' + module
            modules[module] = name
    assert modules['dds_oscillator'] == 'selected/dds_oscillator_leaf.sv'
    assert modules['sine_wavetable_1024'] == 'sources/m1td_dds_oscillator.sv'
    source_list = ('\n'.join(selected) + '\n').encode('utf-8')
    payloads['inputs/compile.f'] = source_list
    payloads['provenance/ORIGINAL_COMPILE.f'] = original_list
    payloads['provenance/ORIGINAL_dds_oscillator.sv'] = original_dds
    decision = {
        'schema': 'M2_R06C5_SELECTED_SIMULATION_SOURCE_V1',
        'status': 'SELECTED_STATIC_NOT_COMPILED_NOT_ADMITTED',
        'selected_basis': 'published C3; excludes unpublished local C4 and future M1 observer sources',
        'original_units': 69, 'excluded_units': sorted(excluded), 'selected_units': 71,
        'rom_count': 9, 'literal_module_count': len(modules),
        'list_base': 'unpacked inputs directory; compile.f paths are relative to that directory',
        'top': 'm2_138k_pro_fourvoice_observer_top_r06',
        'DDS_derivation': {'original': ident(original_dds), 'shared_ROM_tail': ident(shared),
            'operation': 'original_dds[0:1240] + one LF; omit duplicate shared ROM tail',
            'leaf': ident(leaf), 'ROM_definition_owner': modules['sine_wavetable_1024'],
            'algorithm_or_port_edits': False},
        'module_to_source_literal_only': modules,
        'source_archive': str(BASE.relative_to(ROOT)).replace('\\', '/'),
        'source_archive_sha256': ident(BASE.read_bytes())['sha256'],
        'payloads': {name: ident(raw) for name, raw in sorted(payloads.items())},
        'HDL_executed': False, 'execution_admission': None, 'physical_mode_allowed': False,
        'simulation_stubs_and_old_PLL_header_retained_as_simulation_only': True,
        'full_chain_TB_not_included_pending_M3_R7_A': True,
        'M1_real_semantics_and_G0_G3': 'PENDING', 'board_release_allowed': False}
    DOC.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in sorted(payloads.items()):
            z.writestr(name, raw)
        z.writestr('MANIFEST.json', (json.dumps(decision, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(ident(z.read(name)) == expected for name, expected in decision['payloads'].items())
    decision['archive'] = {'path': str(archive.relative_to(ROOT)).replace('\\', '/'), **ident(archive.read_bytes())}
    (DOC / 'SOURCE_DECISION_R06C5.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (HERE / 'SOURCE_LIST_R06C5.f').write_bytes(source_list)
    print(json.dumps({k: decision[k] for k in ('status', 'selected_units', 'rom_count', 'literal_module_count', 'archive')}))


if __name__ == '__main__':
    main()
