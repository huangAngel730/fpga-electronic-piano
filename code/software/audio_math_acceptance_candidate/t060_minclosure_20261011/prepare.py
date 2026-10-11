"""Generate a portable static-precheck package; NEVER starts RTL/EDA tools."""
import argparse
import ast
import difflib
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from fixtures import cancel_plan, lifecycle_plan, schedule_text  # noqa: E402
from fsm_oracle import require  # noqa: E402

ARCHIVE = 'code/rtl/138K_try/clock_trials_20261005/M3_138K_clock40_evidence_20261005.zip'
ARCHIVE_SHA = 'cdc196fef2635c8fc5b245d88a157e742a492c7bed89cb3ca1ce50517476e994'
INPUT_MANIFEST_SHA = '6705f3c6a184d07aaa21477a83b7653a076cd9043c1417f89186f2619de232c9'
PREFIX = 'H_pll_core40_route2/'
OLD_ROOT = 'E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/H_pll_core40_route2'
MATH_SHA = {
    'router_model.py': '1c2d4af9282b271fd68b16553ba2036d4cb01420669deafe0818bb2d1082957b',
    'envelope_model.py': '5826bb00da5d8ecc5c2eb3ffe43d159514781bc2f3bb1033965dcf312d12f933',
    'dds_model.py': 'c127f5af83e52cbcd7484e96fbb26f149862cdb225023f72041c61f220c0950d',
    'strict_capture.py': 'bac18df92a3e58bf4e976c3711a5fbb2f7d537637015bbd09e1890d99a5a6164',
}
SOURCES = ('audio_defs_pkg sustain_control_contract_pkg note_pitch sustain_controller '
           'voice_allocator_4 polyphonic_event_router performance_control_snapshot '
           'pitch_mod_fcw_pipeline pitch_mod_snapshot_pipeline dds_oscillator '
           'piano_dds_oscillator adsr_piano_envelope polyphonic_envelope_bank '
           'voice_gain_q15_candidate pcm_mixer_4voice pcm_result_hold pcm_frame_buffer '
           'pcm_clip_counter polyphonic_pcm_commit').split()
ROMS = ('velocity_gain_rom.mem', 'piano_band_4x256_8191.mem', 'oct_ratio_q16.mem',
        'sub_ratio_q16.mem', 'lfo_sine_q15.mem')
TB_REL = Path('code/tb/board/m3_midi_pcm_acceptance/t060_minclosure_20261011')
ANCHORS = {
    'polyphonic_envelope_bank.sv': ('delay_count<=6;phase<=SETTLE;',
        'phase<=SNAPSHOT;end', 'phase<=HOLD;', 'wire lane_tick=',
        'phase<=DRAIN;result_valid<=0;resume_requested<=0;',
        'resume_requested || sample_req', 'states[3*i+:3]==0'),
    'performance_control_snapshot.sv': ('if(read_slot==3)',),
    'pitch_mod_snapshot_pipeline.sv': ('if(age==6)', 'if(busy)cancelled<=1;',),
    'pitch_mod_fcw_pipeline.sv': ('else if(sample_enable)lfo_phase<=phase_now+LFO_INC;',),
    'adsr_piano_envelope.sv': ('localparam int RELEASE_SAMPLES = 4800;',),
    'pcm_result_hold.sv': ('!pcm_valid && result_req_id == current_req_id;',),
    'pcm_frame_buffer.sv': ('held_left      <= pending_left;',),
    'polyphonic_event_router.sv': ('RETIRE:if(cmd_ready)begin',),
    'sustain_controller.sv': ('SUSTAIN_CMD_PANIC: begin',),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def metadata(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def frozen():
    if not (ROOT / ARCHIVE).exists():
        raw = (ROOT / 'original_H/input_manifest.json').read_bytes()
        require(sha(raw) == INPUT_MANIFEST_SHA, 'PRECHECK_PORTABLE_MANIFEST_IDENTITY')
        result = {}
        for entry in json.loads(raw)['inputs']:
            name = entry['path'].replace('\\', '/')
            data = (ROOT / 'original_H' / name).read_bytes()
            require(sha(data) == entry['candidate_SHA256'], 'PRECHECK_H_MEMBER_IDENTITY:' + name)
            result[name] = data
        return result
    raw = (ROOT / ARCHIVE).read_bytes()
    require(sha(raw) == ARCHIVE_SHA, 'PRECHECK_H_ARCHIVE_IDENTITY')
    with zipfile.ZipFile(ROOT / ARCHIVE) as archive:
        raw = archive.read(PREFIX + 'input_manifest.json')
        require(sha(raw) == INPUT_MANIFEST_SHA, 'PRECHECK_INPUT_MANIFEST_IDENTITY')
        manifest = json.loads(raw)
        result = {}
        for entry in manifest['inputs']:
            name = entry['path'].replace('\\', '/')
            data = archive.read(PREFIX + name)
            require(sha(data) == entry['candidate_SHA256'], 'PRECHECK_H_MEMBER_IDENTITY:' + name)
            result[name] = data
    return result


def load_roms():
    original = frozen()
    return {name: [int(w, 16) for w in original['rom/' + name].split()] for name in ROMS}


def dependencies():
    result = {HERE.parent / n for n in MATH_SHA}
    for p in result:
        require(sha(p.read_bytes()) == MATH_SHA[p.name], 'PRECHECK_MATH_SOURCE_CHANGED:' + p.name)
    result.update(p for p in HERE.glob('*.py') if p.name not in ('scope.py', 'test_scope.py'))
    # Check the complete static local import graph; fail closed for unresolved
    # non-stdlib dependencies rather than silently using a host worktree.
    by_stem = {p.stem: p for p in result}
    edges = {}
    for p in result:
        imported = set()
        for node in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                imported.update(n.name.split('.')[0] for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
        unknown = imported - set(by_stem) - sys.stdlib_module_names
        require(not unknown, 'PRECHECK_UNRESOLVED_IMPORT:' + str(unknown))
        edges[p.relative_to(ROOT).as_posix()] = sorted(imported & set(by_stem))
    return sorted(result), edges


def check_import_origins():
    paths, _ = dependencies()
    for path in paths:
        module = sys.modules.get(path.stem)
        if module is not None:
            require(Path(module.__file__).resolve() == path.resolve(),
                    'PRECHECK_OUTSIDE_IMPORT:' + path.stem)


def prepare(out):
    out = out.resolve()
    require(out.is_relative_to(ROOT / 'code/output') and out != ROOT / 'code/output', 'PRECHECK_OUTPUT_SCOPE')
    require(not out.exists(), 'PRECHECK_REFUSE_OVERWRITE')
    check_import_origins()
    original = frozen()
    deps, graph = dependencies()
    paths = deps + [ROOT / TB_REL / n for n in ('tb_minclosure.sv', 'observer.svh')]
    paths += [ROOT / 'code/scripts/run_platform_audio_capture.py',
              ROOT / 'code/tb/board/m3_midi_pcm_acceptance/tb_midi_pcm.sv',
              ROOT / 'code/tb/board/platform_audio_acceptance_20261005/observer.sv.in',
              ROOT / 'code/docs/M2_T060字段排除与最小补采规格_给M3_2026-10-11.md']
    before = {p.relative_to(ROOT).as_posix(): metadata(p.read_bytes()) for p in paths}
    out.mkdir(parents=True)
    inputs = {}
    def write(rel, raw):
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
        inputs[str(rel).replace('\\', '/')] = metadata(raw)
    for p in paths:
        write(p.relative_to(ROOT), p.read_bytes())
    origins = {}
    for old_rel, new_rel, label in (
        (Path('code/tb/board/m3_midi_pcm_acceptance/tb_midi_pcm.sv'),
         TB_REL / 'tb_minclosure.sv', 'thin_tb'),
        (Path('code/tb/board/platform_audio_acceptance_20261005/observer.sv.in'),
         TB_REL / 'observer.svh', 'observer')):
        old_raw, new_raw = (ROOT / old_rel).read_bytes(), (ROOT / new_rel).read_bytes()
        origins[label] = dict(original=dict(path=old_rel.as_posix(), **metadata(old_raw)),
                              prepared=dict(path=new_rel.as_posix(), **metadata(new_raw)))
        generated = difflib.unified_diff(old_raw.decode().splitlines(True), new_raw.decode().splitlines(True),
                                        fromfile=old_rel.as_posix(), tofile=new_rel.as_posix())
        write(label + '_vs_generation_origin.diff', ''.join(generated).encode())
    dump(out / 'generation_origins.json', dict(origins=origins,
        generator='code/scripts/run_platform_audio_capture.py (copied read-only; NOT executed)',
        change='new thin event-level bank/gain/commit wrapper; no DIN/UART claim; test-only consumer handshake gate'))
    if (ROOT / ARCHIVE).exists():
        with zipfile.ZipFile(ROOT / ARCHIVE) as archive:
            write('original_H/input_manifest.json', archive.read(PREFIX + 'input_manifest.json'))
    else:
        write('original_H/input_manifest.json', (ROOT / 'original_H/input_manifest.json').read_bytes())
    diff = []
    for name, raw in original.items():
        # Preserve ALL 56 original inputs, including files not compiled here.
        write('original_H/' + name, raw)
        if name.startswith(('rom/', 'include/')) or name in ('sources/' + n + '.sv' for n in SOURCES):
            adapted = raw
            if name.startswith('sources/'):
                adapted = raw.replace(OLD_ROOT.encode(), b'.')
                for header in ('sine_table.svh', 'sustain_controller_ports.svh'):
                    adapted = adapted.replace(('./include/' + header).encode(), header.encode())
            write('simulation/' + name, adapted)
            diff.extend(difflib.unified_diff(raw.decode().splitlines(True), adapted.decode().splitlines(True),
                                           fromfile='original_H/' + name, tofile='simulation/' + name))
    write('generated_path_only.diff', ''.join(diff).encode())
    anchors = []
    for name, snippets in ANCHORS.items():
        raw = original['sources/' + name]
        lines = raw.decode().splitlines()
        for snippet in snippets:
            matches = [(i, line) for i, line in enumerate(lines, 1) if snippet in line]
            require(len(matches) == 1, 'PRECHECK_CALENDAR_ANCHOR:' + name + ':' + snippet)
            anchors.append(dict(file='original_H/sources/' + name, line=matches[0][0],
                                text=matches[0][1], source_sha256=sha(raw)))
    dump(out / 'source_calendar.json', dict(region='pre_NBA', anchors=anchors,
         chain='CAPTURE -> 4 serialized control reads -> math launch -> 7 ages -> consume -> ADVANCE -> 4 settle -> SNAPSHOT -> first HOLD -> bank handshake -> PCM register -> commit',
         lane_tick='ADVANCE && live_identity && !frame; frame never rolls back prior lane/LFO advancement'))
    roms = load_roms()
    plans = {1: lifecycle_plan(), 2: cancel_plan(roms)}
    # One lowering step and one compile per future group. Commands are DATA,
    # not executable authorization; this script never calls subprocess/tooling.
    commands = []
    for group, plan in plans.items():
        name = 'A' if group == 1 else 'B'
        # Future runs have separate CWDs: the TB's fixed capture filename cannot
        # overwrite another group's capture. Neither directory is executed here.
        sim = out / ('future_group_' + name)
        for source in (out / 'simulation').rglob('*'):
            if source.is_file():
                write(sim.relative_to(out) / source.relative_to(out / 'simulation'), source.read_bytes())
        dump(out / ('plan_' + name + '.json'), plan)
        write(sim.relative_to(out) / ('stimulus_' + name + '.txt'), schedule_text(plan).encode())
        ys = ('read_slang --top voice_allocator_4 sources/voice_allocator_4.sv\n'
              'proc\nopt\ntechmap\nopt\nwrite_verilog -noattr allocator.v\n')
        write(sim.relative_to(out) / 'lower_allocator.ys', ys.encode())
        files = ['sources/' + n + '.sv' for n in SOURCES if n != 'voice_allocator_4']
        commands.append(dict(group=name, authorized=False, cwd=str(sim),
            lowering=dict(timeout_seconds=90, argv=['yosys', '-Q', '-T', '-s', 'lower_allocator.ys']),
            compile=dict(timeout_seconds=90, argv=['iverilog', '-g2012', '-I', 'include',
                '-I', str(out / TB_REL), '-s', 'tb_minclosure', '-o', name + '.vvp',
                *files, 'allocator.v', str(out / TB_REL / 'tb_minclosure.sv')]),
            capture=dict(timeout_seconds=300, argv=['vvp', name + '.vvp',
                '+STIMULUS=stimulus_' + name + '.txt', '+END_CYCLE=' + str(plan['end_cycle']),
                '+GROUP=' + str(group), '+VELOCITY_ROM_PATH=rom/velocity_gain_rom.mem']),
            required_post_capture='Refuse if capture or vvp already exists; preserve this group directory. Exact plan-bound check and four complete corruptions remain required. No automatic retries.'))
    dump(out / 'future_commands_NOT_AUTHORIZED.json', dict(authorized=False,
         total_seconds=900, software_step_seconds=90, commands=commands,
         tools='M2 must confirm exact executable paths/versions/SHA and enable only these two groups'))
    after = {p.relative_to(ROOT).as_posix(): metadata(p.read_bytes()) for p in paths}
    require(before == after, 'PRECHECK_PROTECTED_SOURCE_DRIFT')
    inputs = {p.relative_to(out).as_posix(): metadata(p.read_bytes())
              for p in sorted(out.rglob('*')) if p.is_file()}
    manifest = dict(status='STATIC_PRECHECK_PREPARATION_ONLY', exit_code=0,
        archive=dict(path=ARCHIVE, sha256=ARCHIVE_SHA), originals=56,
        inputs=inputs, sources_before=before, sources_after=after, import_graph=graph,
        new_RTL_execution_authorized=False, RTL_compilations=0, RTL_runs=0, EDA_runs=0,
        t060_complete=False, t061_complete=False, physical_verified=False,
        old_entry='PARTIAL/exit3 unchanged; no old capture2 or 56 bad-case replay',
        boundary='H only; independent public-event injection, not DIN/UART evidence; consumer gate is TB-only')
    require(len(original) == manifest['originals'], 'PRECHECK_ORIGINAL_INPUT_COUNT')
    dump(out / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps(dict(status=result['status'], exit_code=0, inputs=len(result['inputs']),
                         RTL_runs=0, EDA_runs=0)))


if __name__ == '__main__':
    main()
