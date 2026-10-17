"""Static dual source materialization only. No B builders, tests or HDL calls."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_equivalence_tb/c5_dual_assembly'
C5 = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/SOURCE_CLOSURE_R06C5.zip'
BASE = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/same_version_binding_20261017/M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)}


def save(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def main():
    DOC.mkdir(exist_ok=False)
    out = DOC / 'inputs'
    out.mkdir()
    assert identity(C5)['sha256'] == '2fc5518a35600f67d025aa2efe55e6b436daa5a04b592053f7326385b42134fb'
    assert identity(BASE)['sha256'] == '931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2'
    entries = []

    def put(name, raw, source):
        rel = PurePosixPath(name)
        assert not rel.is_absolute() and '..' not in rel.parts
        path = out / name
        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open('xb') as stream:
            stream.write(raw)
        entries.append({'relative_path': name, 'source': source, **identity(path)})

    with zipfile.ZipFile(C5) as selected, zipfile.ZipFile(BASE) as baseline:
        assert selected.testzip() is None and baseline.testzip() is None
        units = selected.read('inputs/compile.f').decode('utf-8').splitlines()
        assert len(units) == len(set(units)) == 71
        for name in selected.namelist():
            if name.startswith('inputs/') and not name.endswith('/'):
                relative = name[len('inputs/'):]
                if relative == 'compile.f':
                    relative = 'C5_observer_original.f'
                put(relative, selected.read(name), 'C5:' + name)
        original_list = baseline.read('source_closure/inputs/compile.f')
        assert len(original_list.decode('utf-8').splitlines()) == 69
        put('BASE_original_compile.f', original_list, 'BASE:source_closure/inputs/compile.f')
        added = []
        for name in ('m2_fourvoice_timbre_delay_frame_core.sv', 'm2_fourvoice_timbre_delay_board_top.sv'):
            member = 'source_closure/inputs/sources/' + name
            relative = 'original/' + name
            put(relative, baseline.read(member), 'BASE:' + member)
            added.append(relative)
        member = 'source_closure/candidate/m2_138k_pro_fourvoice_candidate_top.sv'
        wrapper = 'original/m2_138k_pro_fourvoice_candidate_top.sv'
        put(wrapper, baseline.read(member), 'BASE:' + member)
        added.append(wrapper)
        # C5 source ZIP omits these textual includes. Reuse exact original
        # approved baseline bytes; preserve both original locations/identities.
        for name in ('sine_table.svh', 'sustain_controller_ports.svh'):
            a = 'source_closure/inputs/include/' + name
            b = 'source_closure/inputs/sources/' + name
            assert baseline.read(a) == baseline.read(b)
            put('include/' + name, baseline.read(a), 'BASE:' + a + ' == ' + b)
    tb = ROOT / 'code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_equivalence_tb/tb_public_equivalence.sv'
    driver = ROOT / 'code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/midi_public_port_driver.sv'
    assert identity(tb)['sha256'] == '6768bf11f4d18e930f7d989707fe509ad263ec85c9a864729af98307b0a35bf8'
    assert identity(driver)['sha256'] == '99e40266a46f1606409fa6ef270dd0c6b056dcb511363ae90dfbaf67653df89a'
    for relative, path in (('tb/midi_public_port_driver.sv', driver), ('tb/tb_public_equivalence.sv', tb)):
        put(relative, path.read_bytes(), str(path))
        added.append(relative)
    stimulus = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/RUN_02/products'
    for name in ('bytes.drv', 'reset.drv', 'ready.drv', 'plan.json'):
        put(name, (stimulus / name).read_bytes(), str(stimulus / name))
    dual = units + added
    assert len(dual) == len(set(dual)) == 76
    definitions, includes, aliases = {}, set(), set()
    for name in dual:
        text = (out / name).read_text(encoding='utf-8')
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        for module in re.findall(r'\bmodule\s+(\w+)', text):
            definitions.setdefault(module, []).append(name)
        includes.update(re.findall(r'`include\s+"([^"\n]+)"', text))
        aliases.update(re.findall(r'"([^"\n]+\.(?:mem|hex))"', text))
    assert len(definitions) == 78 and all(len(v) == 1 for v in definitions.values())
    assert definitions['sine_wavetable_1024'] == ['sources/m1td_dds_oscillator.sv']
    assert definitions['dds_oscillator'] == ['selected/dds_oscillator_leaf.sv']
    assert {'m2_138k_pro_fourvoice_candidate_top', 'm2_138k_pro_fourvoice_observer_top_r06', 'tb_public_equivalence'} <= set(definitions)
    assert all((out / 'include' / name).is_file() for name in includes)
    for alias in sorted(aliases):
        path = out / alias
        if path.exists():
            continue
        source = out / 'rom' / PurePosixPath(alias).name
        assert source.is_file(), 'UNKNOWN_ROM_LITERAL:' + alias
        put(alias, source.read_bytes(), 'BYTE_IDENTICAL_ROM_ALIAS:' + source.relative_to(out).as_posix())
    put('dual_compile.f', ('+incdir+include\n' + '\n'.join(dual) + '\n').encode('utf-8'), 'C5_71_PLUS_BASE_2_WRAPPER_DRIVER_FINAL_TB')
    report = {'schema': 'M3_R7B_C5_DUAL_STATIC_ASSEMBLY_V1', 'status': 'STATIC_MATERIALIZED_NOT_COMPILED_NOT_ADMITTED',
              'created_from': [identity(C5), identity(BASE)], 'compile_list': 'inputs/dual_compile.f',
              'cwd': 'unpacked inputs directory', 'top': 'tb_public_equivalence',
              'observer_C5_source_units': 71, 'added_source_units': added, 'dual_source_units': 76,
              'literal_module_count': 78, 'module_to_source_literal_only': definitions,
              'includes': sorted(includes), 'ROM_literals': sorted(aliases), 'unique_original_ROM_payloads': 9,
              'source_and_input_origins': entries, 'B_original_TB_and_source_bytes_unchanged': True,
              'original_38_obs': 'NOT_PUBLIC', 'clock_DVI_PLL_models': 'SIMULATION_ONLY_PHYSICAL_UNVERIFIED',
              'B_last_comparator_delta': '<=stop L0_NOT_RUN_FINAL_GROUP_NOT_REEXECUTED',
              'build_sources_selftest_HDL_EDA_hardware_calls': 0, 'B_software_groups_added': 0,
              'compile_elaboration': 'NOT_RUN', 'execution_admission': None, 'board_release_allowed': False}
    save(DOC / 'ASSEMBLY.json', report)
    archive = DOC / 'M3_R7B_C5_DUAL_SOURCE_20261017.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(out.rglob('*')):
            if path.is_file():
                zipped.write(path, path.relative_to(DOC).as_posix())
        zipped.write(DOC / 'ASSEMBLY.json', 'ASSEMBLY.json')
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        for item in entries:
            data = zipped.read('inputs/' + item['relative_path'])
            assert sha(data) == item['sha256'] and len(data) == item['bytes']
    save(DOC / 'RECEIPT.json', {'assembly': identity(DOC / 'ASSEMBLY.json'), 'archive': identity(archive),
                             'CRC_member_bytes_SHA256': 'PASS', 'compile_elaboration': 'NOT_RUN',
                             'B_groups_added': 0, 'M2_execution_admission': 'PENDING', 'board_release_allowed': False})
    print(json.dumps({'units': len(dual), 'modules': len(definitions), 'includes': sorted(includes), 'archive': identity(archive)}))


if __name__ == '__main__':
    main()
