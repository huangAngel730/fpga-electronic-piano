"""Materialize the exact frozen simulation pair; no compiler invocation."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from equivalence import need

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TAG = 'pro_basis_r07_20261017'
TB = ROOT / 'code/tb/board/m3_pro_fourvoice_trace_20261016' / TAG / 'public_equivalence_tb'
M2 = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017'
ARCHIVE = ROOT / 'code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/same_version_binding_20261017/M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip'
ARCHIVE_SHA = '931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2'
R6 = ROOT / 'code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/RUN_02/products'
DRIVER = ROOT / 'code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/midi_public_port_driver.sv'


def identity(path):
    p = Path(path)
    raw = p.read_bytes()
    return {'path': str(p), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def assemble(out, expected_archive_sha=ARCHIVE_SHA):
    out = Path(out)
    out.mkdir(exist_ok=False, parents=True)
    need(identity(ARCHIVE)['sha256'] == expected_archive_sha, 'ARCHIVE_SHA')
    replacement = json.loads((M2 / 'SOURCE_REPLACEMENTS_R06C3.json').read_text(encoding='utf-8'))
    exports = json.loads((M2 / 'OBSERVER_EXPORTS_R06C3.json').read_text(encoding='utf-8'))
    need(replacement['baseline_archive_sha256'] == ARCHIVE_SHA, 'REPLACEMENT_ARCHIVE')
    expected_excludes = ['sources/m2_fourvoice_timbre_delay_board_top.sv',
                         'sources/m2_fourvoice_timbre_delay_frame_core.sv', 'tb_m2_m1td_real_chain.sv']
    need(replacement['exclude_from_observer_list'] == expected_excludes, 'REPLACEMENT_EXCLUDES')
    origins, texts = [], {}

    def put(relative, data, source):
        rel = PurePosixPath(relative)
        need(not rel.is_absolute() and '..' not in rel.parts, 'ASSEMBLY_PATH')
        p = out / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        need(not p.exists(), 'ASSEMBLY_DUPLICATE', path=str(p))
        p.write_bytes(data)
        origins.append({'source': source, **identity(p)})
        return p

    with zipfile.ZipFile(ARCHIVE) as z:
        base = 'source_closure/inputs/'
        original = z.read(base + 'compile.f').decode('utf-8').splitlines()
        need(len(original) == 69 and len(set(original)) == 69, 'ORIGINAL_LIST')
        for name in original:
            if name == 'tb_m2_m1td_real_chain.sv':
                continue
            p = put(name, z.read(base + name), 'archive:' + base + name)
            texts[str(p)] = p.read_text(encoding='utf-8')
        wrapper = 'source_closure/candidate/m2_138k_pro_fourvoice_candidate_top.sv'
        old_wrapper = put('original_wrapper.sv', z.read(wrapper), 'archive:' + wrapper)
        texts[str(old_wrapper)] = old_wrapper.read_text(encoding='utf-8')
        clock = z.read(base + 'sources/clock_plan_sim.v')
        need(b'always #12.5' in clock and b'#1000;lock=1' in clock, 'CLOCK_STUB_CHANGED')
        roms = {PurePosixPath(n).name: (n, z.read(n)) for n in z.namelist()
                if n.startswith(base + 'rom/') and n.endswith(('.mem', '.hex'))}
        need(len(roms) == 9, 'ROM_COUNT')
        for basename, (member, data) in roms.items():
            put('rom/' + basename, data, 'archive:' + member)
        # Preserve literal default ROM paths in frozen sources without edits.
        aliases = set(re.findall(r'"([^"\n]+\.(?:mem|hex))"', '\n'.join(texts.values())))
        for alias in sorted(aliases):
            name = PurePosixPath(alias).name
            if name in roms and not (out / alias).exists():
                member, data = roms[name]
                put(alias, data, 'archive:' + member)
        unlisted_dds = {'member': base + 'sources/dds_oscillator.sv',
                        'sha256': hashlib.sha256(z.read(base + 'sources/dds_oscillator.sv')).hexdigest(),
                        'in_original_compile_list': False, 'automatically_added': False}
    new = []
    for name in replacement['add_R06_files']:
        source = ROOT / name
        need(identity(source)['sha256'] == exports['source_sha256'][source.name], 'R06_SOURCE_SHA')
        p = put('r06/' + source.name, source.read_bytes(), name)
        texts[str(p)] = p.read_text(encoding='utf-8')
        new.append(p)
    driver = put('midi_public_port_driver.sv', DRIVER.read_bytes(), str(DRIVER))
    tb_source = TB / 'tb_public_equivalence.sv'
    testbench = put(tb_source.name, tb_source.read_bytes(), str(tb_source))
    for name in ('bytes.drv', 'reset.drv', 'ready.drv', 'plan.json'):
        put(name, (R6 / name).read_bytes(), str(R6 / name))
    shared = [out / name for name in original if name not in expected_excludes]
    original_only = [out / name for name in original if name != 'tb_m2_m1td_real_chain.sv']
    lists = {'original.f': original_only + [old_wrapper, driver, testbench],
             'observer.f': shared + new + [driver, testbench],
             'dual.f': original_only + [old_wrapper] + new + [driver, testbench]}
    # The equivalence TB references BOTH roots; only dual.f is the planned build.
    for name, paths in lists.items():
        (out / name).write_text(''.join('"' + str(p).replace('\\', '/') + '"\n' for p in paths), encoding='utf-8')
    definitions = set()
    for text in texts.values():
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        for module in re.findall(r'\bmodule\s+(\w+)', text):
            need(module not in definitions, 'DUPLICATE_MODULE', module=module)
            definitions.add(module)
    need('dds_oscillator' not in definitions, 'UNDECLARED_BASELINE_LIST_CHANGE')
    result = {'status': 'PENDING_M2_DDS_LIST_DECISION', 'HDL_compile_allowed': False,
              'reason': 'MISSING_MODULE_LEXICAL_NOT_ELABORATION_PROOF', 'unlisted_dds': unlisted_dds,
              'compile_list_units': {name: len(paths) for name, paths in lists.items()},
              'dual_top': 'tb_public_equivalence', 'cwd': str(out), 'origins': origins,
              'observer_not_public_on_original': list(exports['expected_observation_ports']),
              'clock_stub': identity(out / 'sources/clock_plan_sim.v'),
              'comparison': {'first_core_posedge_ps': 12500, 'period_ps': 25000,
                             'start': 1200, 'stop': 12000000, 'allowed_pin_differences': []},
              'physical_PLL_verified': False, 'board_release_allowed': False}
    (out / 'ASSEMBLY.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
