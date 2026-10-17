"""Read-only source/ROM freeze for the authorized Pro successor A0 package.

Does not import a golden model or run HDL, EDA, or historical tests. New
artifacts are created exclusively beside this script and never overwritten.
"""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
MODEL = 'code/model/m1_r05_pcm_oracle_20261016'
DOCS = 'code/docs/test/m1_r05_pcm_oracle_20261016'
VECTORS = DOCS + '/m2_13_solo_chord_R01/run_R02/vectors'
M3MODEL = 'code/software/m3_r05_functional_integration_20261015/real_trace_successor_20261016'
M3DOCS = 'code/docs/test/m3_r05_functional_integration_20261015/real_trace_successor_20261016'
ARCHIVE = 'code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R06_XSAFE_7ms_ModelSim输入_20261016.zip'
TASK = Path('D:/嵌赛/高云二/拓展/M2/17/M1_夜间五小时_Pro四声基础_2026-10-16.md')
PRO = 'code/rtl/138K_Pro'
CALLS = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=False)
    CALLS.append({'argv': ['git', *args], 'cwd': str(ROOT),
                  'exit_code': result.returncode,
                  'stdout_sha256': sha(result.stdout),
                  'stderr_sha256': sha(result.stderr),
                  'stdout': result.stdout.decode('utf-8', 'replace') if args[0] != 'cat-file' else None,
                  'stderr': result.stderr.decode('utf-8', 'replace')})
    return result


def file_record(rel, role, expected=None):
    path = ROOT / rel
    data = path.read_bytes()
    result = git('rev-parse', 'HEAD:' + rel)
    blob_id = result.stdout.decode().strip() if result.returncode == 0 else None
    blob = git('cat-file', 'blob', blob_id).stdout if blob_id else None
    return {'path': rel, 'role': role, 'bytes': len(data), 'sha256': sha(data),
            'head_git_blob_oid': blob_id,
            'head_git_blob_sha256': sha(blob) if blob is not None else None,
            'working_tree_equals_head_blob': data == blob if blob is not None else None,
            'expected_sha256': expected,
            'expected_sha256_match': sha(data) == expected if expected else None}


def write_json(name, value):
    path = HERE / name
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    if not (ROOT / '.git').exists():
        raise ValueError('REPOSITORY_ROOT_NOT_FOUND:' + str(ROOT))
    for name in ('SOURCE_FREEZE.json', 'SOURCE_FREEZE.md', 'A0_RECEIPT.json', 'ARTIFACT_SHA256.json'):
        if (HERE / name).exists():
            raise FileExistsError('PRESERVE_EXISTING_ARTIFACT:' + name)
    started = datetime.now(timezone.utc).isoformat()
    head = git('rev-parse', 'HEAD').stdout.decode().strip()
    tracking = git('rev-parse', 'origin/develop').stdout.decode().strip()
    pro_hint = git('rev-parse', 'd308db5').stdout.decode().strip()
    files = []

    for rel in ('AGENTS.md', 'code/AGENTS.md', 'code/docs/协作入口.md',
                'code/docs/M1_完赛任务单_2026-10-15.md',
                'code/docs/138K四声部后续集成任务总览_2026-10-15.md',
                'code/docs/夜间任务通用执行规范.md'):
        files.append(file_record(rel, 'authority_or_local_task_card'))
    for name in ('oracle.py', 'DEPENDENCIES.json', 'solo_chord_vectors.py',
                 'test_solo_chord_vectors.py', 'timbre_switch_pairs_R01.py',
                 'test_timbre_switch_pairs_R01.py', 'compare_math.py'):
        files.append(file_record(MODEL + '/' + name, 'existing_signed_software_reference'))
    files.append(file_record(DOCS + '/REFERENCE_CONTRACT.json', 'existing_signed_reference_contract'))
    dependencies = json.loads((ROOT / MODEL / 'DEPENDENCIES.json').read_text(encoding='utf-8'))
    for item in dependencies['files']:
        row = file_record(MODEL + '/' + item['path'], 'frozen_dependency_reference', item['sha256'])
        row['historical_source_label'] = item.get('source', item.get('source_zip'))
        row['historical_archive_member'] = item.get('member')
        files.append(row)
    original_paths = (
        ('code/software/audio_math_acceptance_candidate/dds_model.py', 'frozen/dds_model.py'),
        ('code/software/audio_math_acceptance_candidate/envelope_model.py', 'frozen/envelope_model.py'),
        ('code/tb/board/generate_t010_allocator_vectors.py', 'frozen/allocator_oracle.py'),
    )
    original_matches = []
    for rel, dep in original_paths:
        row = file_record(rel, 'historical_original_algorithm_source')
        files.append(row)
        original_matches.append({'path': rel, 'frozen_path': MODEL + '/' + dep,
                                 'same_bytes': (ROOT / rel).read_bytes() == (ROOT / MODEL / dep).read_bytes()})
    for rel in sorted((ROOT / VECTORS).rglob('*')):
        if rel.is_file():
            files.append(file_record(rel.relative_to(ROOT).as_posix(), 'signed_R02_SYNTHETIC_ONLY_vector'))
    for rel in (
        DOCS + '/m2_13_solo_chord_R01/run_R02/RUN_RECEIPT.json',
        DOCS + '/m2_13_solo_chord_R01/MIDI_SOURCE_ID_R02.json',
        DOCS + '/m2_13_solo_chord_R01/MIDI_MAPPING_SOURCE_R01.json',
        'code/docs/M2_M1夜间A_B软件准备_限定复核_2026-10-16.md',
        'code/docs/M2_M1第13批四独奏合奏R02限定复核_2026-10-16.md',
        'code/docs/M2_R06双音色PCM隔离对照_2026-10-16.md',
        'code/docs/M2_R06同版闭包与双滑块受控接入清单_2026-10-16.md',
        M3MODEL + '/contract.py', M3MODEL + '/README.md', M3DOCS + '/FIELD_MATRIX.md',
        M3DOCS + '/RUN04/SOURCE_BINDINGS.json', M3DOCS + '/RUN04/INPUT_IDENTITY.json',
        M3DOCS + '/RUN04/RECEIPT.json',
        PRO + '/tang_mega_138k-pro_pins.cst',
        PRO + '/TANG_MEGA-138K-Pro_4072_Schematics.pdf',
        PRO + '/TANG_MEGA-138K_Dock-4071f3__Schematics.pdf',
        PRO + '/Pro_引脚核对_CST_R02_20261016/pin_relationships.json',
        PRO + '/Pro_引脚核对_CST_R02_20261016/validation.json',
        PRO + '/Pro_引脚核对_CST_R02_20261016/manifest.json',
        PRO + '/Pro_引脚核对_CST_R02_20261016/M2_待用户转发_尚未送达.txt',
    ):
        files.append(file_record(rel, 'signoff_schema_or_Pro_static_evidence'))
    carrier = file_record(ARCHIVE, 'R06_archive_carrier', dependencies['r06_archive_sha256'])
    files.append(carrier)
    members = []
    with zipfile.ZipFile(ROOT / ARCHIVE) as archive:
        for name in archive.namelist():
            if name.startswith('inputs/rom/') or (name.startswith('inputs/sources/') and
                    (Path(name).name.startswith('m1td_') or Path(name).name in
                     ('m2_fourvoice_timbre_delay_board_top.sv', 'm2_fourvoice_timbre_delay_frame_core.sv'))):
                data = archive.read(name)
                members.append({'carrier': ARCHIVE, 'carrier_git_blob_oid': carrier['head_git_blob_oid'],
                                'member': name, 'bytes': len(data), 'sha256': sha(data),
                                'standalone_git_blob_oid': None,
                                'note': 'Exact member bytes bound through archive Git blob; no extraction or RTL execution.'})
        rom_equality = []
        for item in dependencies['files']:
            if 'member' in item:
                rom_equality.append({'frozen_path': MODEL + '/' + item['path'], 'member': item['member'],
                                     'same_bytes': archive.read(item['member']) == (ROOT / MODEL / item['path']).read_bytes()})
    pro_rtl = [p.relative_to(ROOT).as_posix() for p in (ROOT / PRO).rglob('*')
               if p.is_file() and p.suffix.lower() in ('.sv', '.v', '.gprj', '.sdc')]

    arithmetic = [
        {'layer': 'DDS/FCW', 'source': MODEL + '/frozen/dds_model.py',
         'rule': '32-bit modulo phase. note_fcw uses frozen 12-entry SEMITONES and octave shifts; f=FCW*48000/2^32. NoteOn does not clear phase. Piano uses phase[31:24]+2-bit table; Triangle uses pre-tick phase[31:22].',
         'rounding': 'Integer right-shift/floor only for octave-down note FCW; no new frequency rounding.'},
        {'layer': 'ADSR', 'source': MODEL + '/frozen/envelope_model.py',
         'rule': '32-bit unsigned Q16 level/start/peak/sustain; signed33 delta/step; signed59 product; quotient signed33(product>>32); elapsed13; velocity10 addresses 1024x16 ROM, effective envelope 0..32767. Per-clock pipeline retained.',
         'rounding': 'Arithmetic right shifts, no added rounding. Final env=level>>16. R06 settled snapshot is lane_tick+5 pre-NBA, including updates through +4.'},
        {'layer': 'voice_gain', 'source': 'R06:inputs/sources/m1td_voice_gain_q15_candidate.sv',
         'rule': 'signed16 wave times unsigned16 envelope zero-extended to signed17 gives signed33 product. Contract envelope<=32767. scaled=product>>>15; signed16 sample=scaled[15:0]; signed24 PCM={sample,8b0}.',
         'rounding': 'Floor toward negative infinity, not round-to-zero or nearest.'},
        {'layer': 'four_lane_mix_clip', 'source': 'R06:inputs/sources/m1td_pcm_mixer_4voice.sv',
         'rule': 'Four signed24 lane PCMs sum in signed32; no divide-by-four. Saturate to [-8388608,8388607]. clip only total>max or total<min; exact boundaries do not clip.',
         'rounding': 'No intermediate truncation of the sum.'},
        {'layer': 'delay_output_and_feedback', 'source': MODEL + '/frozen/delay_effect_fixed.py',
         'rule': 'PCM signed24; gains unsigned Q0.15 0..32767; product signed39; separately floor each product by15 into signed24 contributions; sum signed25 then signed24 saturation. Feedback saturates independently. Depth1024 in existing oracle. Delay0 follows the frozen read-before-write full-depth history semantics.',
         'rounding': 'Two products shift separately before sum; adding effected solo PCMs is not a chord oracle.'},
        {'layer': 'effect_acceptance_and_reset', 'source': MODEL + '/oracle.py',
         'rule': 'History advances for every accepted effect transaction including later publication cancellation. DSP-only work without FX acceptance does not advance history. enable0 is exact PCM bypass and does not write history. enable/length changes flush; gains-only changes preserve. Independent L/R histories; reset clears lanes/history and increments epoch.',
         'rounding': 'PCM/clip tolerance is exactly 0 LSB. Old default post=lane_tick+7 is a synthetic settled-input value, not a Pro latency measurement.'},
    ]
    states = [
        {'aspect': 'signed_algorithm_and_ROM_bytes', 'state': '已证实', 'level': 'L0_SOURCE_FREEZE',
         'evidence': ['frozen_dependency_expected_sha256_match', 'R06_ROM_byte_equality', 'R02_vector_sources'],
         'limit': 'Existing signed algorithm references retained. Not a new Pro RTL test.'},
        {'aspect': 'Pro_pin_reference', 'state': '已证实', 'level': 'L0_STATIC_ONLY',
         'evidence': [PRO + '/tang_mega_138k-pro_pins.cst', PRO + '/Pro_引脚核对_CST_R02_20261016/validation.json'],
         'limit': '202 CST IO_LOC/IO_PORT static references and schematic report only; physical identity and bank voltage still unverified.'},
        {'aspect': 'latest_Pro_execution_card', 'state': '冲突', 'level': 'UNKNOWN_CURRENT_REMOTE',
         'evidence': ['external M2/17 night task requires Pro FPG676', 'local HEAD M1 card and overview still describe R06/PG484'],
         'limit': 'Parent fetch failed before A0 (local proxy to GitHub443); cached origin/develop is not a fresh remote verification. Do not guess newer Pro port/reset contract.'},
        {'aspect': 'Pro_top_ports_and_source_ROM_manifest', 'state': '缺失', 'level': 'PENDING_PRO_SOURCE_BINDING',
         'evidence': ['No .sv/.v/.gprj/.sdc inside current code/rtl/138K_Pro'],
         'limit': 'Pin names in CST are not proof that a Pro top uses them. Need selected FPG676 part/top/all source+ROM SHA, PLL/core-clock and exact public control taps.'},
        {'aspect': 'Pro_reset_and_epoch', 'state': '缺失', 'level': 'PENDING_REAL_CAPTURE',
         'evidence': [M3DOCS + '/FIELD_MATRIX.md'],
         'limit': 'Need actual Pro reset polarity/synchronizer/PLL hold and continuous sampled reset plus asynchronous RESET_EDGES(time_ps,rst_n,epoch). Do not inherit old PG484 reset or synthesize missing edges.'},
        {'aspect': 'Pro_real_trace', 'state': '缺失', 'level': 'PENDING_REAL_CAPTURE',
         'evidence': [M3MODEL + '/contract.py'],
         'limit': 'Current R06 schema accepts only SYNTHETIC_CONTRACT_SELFTEST and explicitly rejects REAL. Old R06 303-row replay does not prove Pro capture.'},
        {'aspect': 'independent_event_slot_epoch_cancel_fx_calendar', 'state': '缺失', 'level': 'PENDING_REAL_CAPTURE',
         'evidence': [M3DOCS + '/FIELD_MATRIX.md', M3DOCS + '/RUN04/SOURCE_BINDINGS.json'],
         'limit': 'Existing field mapping is proposed static wiring. Need independent scene/source/channel/note/generation and event application, every lane_tick including unpublished work, math acceptance, FX acceptance/config/cancel and reset records from the same run.'},
        {'aspect': 'old_PG484_NEO_evidence_versus_Pro', 'state': '冲突', 'level': 'NONTRANSFERABLE_BOARD_BINDING',
         'evidence': [PRO + '/Pro_引脚核对_CST_R02_20261016/M2_待用户转发_尚未送达.txt'],
         'limit': 'Pro pin/PA-enable/reset/PLL/device differ. Old PG484 bitstream/STA cannot sign FPG676 Pro. Historical L2/L5 results remain valid only in their original signed scopes.'},
    ]
    verification = {
        'frozen_dependencies_checked': len(dependencies['files']),
        'frozen_dependencies_all_expected_sha256_match': all(x['expected_sha256_match'] for x in files if x['role'] == 'frozen_dependency_reference'),
        'R06_archive_expected_sha256_match': carrier['expected_sha256_match'],
        'frozen_ROM_equals_R06_archive': rom_equality,
        'historical_original_equals_frozen': original_matches,
        'missing_original_delay_source': 'code/model/m1_timbre_delay_chain_candidate_20261014/delay_effect_fixed.py',
        'missing_original_delay_source_is_not_loss_of_frozen_bytes': True,
        'pro_implementation_candidates_in_Pro_directory': pro_rtl,
        'all_recorded_working_tree_files_equal_head_blobs': all(x['working_tree_equals_head_blob'] for x in files),
        'signed_old_tests_reexecuted': False, 'golden_models_imported': False,
        'HDL_EDA_or_hardware_executed': False,
    }
    source = {
        'schema': 'M1_PRO_SUCCESSOR_A0_SOURCE_FREEZE_V1', 'created_utc': started,
        'scope': 'A0 read-only freeze, no algorithm duplication or historical-test replay',
        'actual_level': 'L0_SOURCE_AND_CONTRACT_ONLY', 'real_result': 'PENDING_REAL_CAPTURE',
        'board_release_allowed': False, 'submitted': False, 'pushed': False,
        'repo_root': str(ROOT), 'head': head,
        'cached_origin_develop': tracking, 'cached_remote_is_freshly_verified': False,
        'Pro_history_hint_commit': pro_hint,
        'external_task': {'path': str(TASK), 'bytes': TASK.stat().st_size, 'sha256': sha(TASK.read_bytes())},
        'files': files, 'R06_member_references': members, 'arithmetic_contract_reference': arithmetic,
        'verification': verification, 'Pro_status': states,
        'existing_signed_levels': [
            {'scope': 'M1 A oracle/R02 four solos+chord', 'level': 'L0 software synthetic reference', 'reference': 'code/docs/M2_M1第13批四独奏合奏R02限定复核_2026-10-16.md'},
            {'scope': 'R06 original isolated timbre PCM RTL', 'level': 'L2 isolated RTL simulation only', 'reference': 'code/docs/M2_R06双音色PCM隔离对照_2026-10-16.md'},
            {'scope': 'Old PG484 _06 designated physical endpoints', 'level': 'L5 specified endpoints only, not Pro', 'reference': 'code/docs/M2_R06同版闭包与双滑块受控接入清单_2026-10-16.md'},
            {'scope': 'Pro schematic/CST report', 'level': 'L0_STATIC_ONLY', 'reference': PRO + '/Pro_引脚核对_CST_R02_20261016/validation.json'},
        ],
        'same_version_requirements': [
            'Bind exact Pro target part/top/PLL/reset/source+ROM SHA and original driver/capture bytes from one run, plus tool/argv/cwd/stdout/stderr/exit status.',
            'Before arithmetic, validate scene/source/channel/note/generation, epoch/request and accepted event/application provenance. Source0 is signed only for old R06 MIDI mapping.',
            'M3 calendar must be independent of DUT wave/env/phase/table and PCM; observed FCW/intermediate PCM may be comparison targets only.',
            'Include every lane tick and effect/config acceptance including unpublished or cancelled work. Never infer missing timing from commits, ready alone, max_cycles or a fixed offset.',
            'No default missing flags, timestamps, empty cancellations or unknown reset edges. Keep unknown tail/first_valid as UNKNOWN.',
            'Reconstruct four lanes, mix, then accepted FX history and compare signed PCM24 L/R plus exact clip, all at zero LSB. Never sum four effected solo final PCMs.',
            'A1/B0 synthetic fixture PASS stays software-only. Missing Pro source/ROM SHA or independent real input remains PENDING_REAL_CAPTURE.',
        ],
    }
    write_json('SOURCE_FREEZE.json', source)
    md = '''# A0：Pro 后继来源冻结（2026-10-16）

实际等级 **L0 来源／合同核对**；`real_result=PENDING_REAL_CAPTURE`，`board_release_allowed=false`。未提交、未推送。已签算法、ROM、向量仅按路径和字节引用，没有复制重写或重跑旧套件。

本机 HEAD `{head}`，缓存 `origin/develop={tracking}`。本轮开工 fetch 已受网络阻断，缓存不能证明最新远端。M2/17 新单明确 Pro FPG676；本机任务卡仍是旧 R06/PG484，记冲突，不猜新 Pro 卡内容。

直接复用 `{model}/oracle.py`（SHA `{oracle_sha}`）及 `DEPENDENCIES.json` 所列四模型、三 ROM。七件预期 SHA 全核同；三 ROM 与原 R06 ZIP 成员逐字节相等。原 delay 候选目录当前缺失，但已签冻结副本字节齐全，其签收不因原路径缺失或历史变动失效。每件工作树 SHA、HEAD Git blob OID、blob SHA、版本相等性和归档内成员身份详见 `SOURCE_FREEZE.json`。

三 ROM 精确绑定：Piano `c117230f43c7efce36be445f851140d3155aa2a35e71ea8a41f529ea2b5d32a1`；Triangle `a6ee3195ad3a3310de5102531aac9d7773eebc6c31633d72c01b72a7d2461e3c`；velocity `1bc0fd4430884604224a20620368afa50805b4efbf57d9703cae7a09132ffe64`。载体原 R06 ZIP SHA `4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483`。这些是现有黄金的已证来源，尚未获 Pro 源树同版证明。

算术直接引用：32 位环绕 phase/FCW；Piano tick 后相位、Triangle tick 前相位；ADSR 逐时钟整数流水、Q16 level、signed33 delta/step、signed59 product；`voice24 = signed16((wave16*env_q15)>>15)<<8`，负数右移向负无穷取整；四路 signed32 求和后饱和到 signed24，严格超界才 clip；效果的两个 signed39 乘积各自右移15位，再 signed25 相加/饱和。效果历史按接受事务推进，接受后取消发布不回滚；enable/length 变更清历史。详见 JSON 的原件路径和规则引用，不新增算术定义。

已签 R02 四独奏＋合奏向量仍是五场各256行的 `SYNTHETIC_ONLY`（`{vectors}`）；source0/channel0、四个 note/FCW/velocity/timbre 仅绑定原合成/R06条件。四份经过效果的独奏 PCM 不能相加当合奏黄金。原 M1 A/R02 等级 L0 软件准备，R06 指定音频仿真 L2、旧 PG484 物理指定端点 L5，均保留原范围；Pro CST/原理图仅 L0。

| Pro 对象 | 状态 | 最小缺件／限制 |
| --- | --- | --- |
| 引脚/CST参考 | 已证实（L0） | `138K_Pro` 有PDF、202项CST与静态核对；不等实物Bank、器件或新top通过 |
| 最新任务卡 | 冲突 | 新单要求FPG676，本机卡仍R06/PG484；fetch失败，等待可核新卡 |
| Pro top端口／源ROM树 | 缺失 | 当前Pro目录没有SV/V/GPRJ/SDC；需完整part/top/PLL/reset及源ROM SHA |
| Pro复位／epoch | 缺失 | 需真实极性/同步释放/PLL保持和异步`RESET_EDGES(time_ps,rst_n,epoch)` |
| Pro真实trace | 缺失 | 当前仅旧R06合成schema；旧303重放不证Pro |
| 独立事件/slot/取消/效果日历 | 缺失 | M3已有字段提议及来源绑定，尚无同版真实应用沿、每lane_tick、FX/config接受取消完整输入 |
| 旧NEO/PG484迁移 | 冲突 | PA极性、引脚、PLL/复位/器件不同，旧码流与STA不能签Pro |

M3 现有 `{m3model}/contract.py` 的 schema 是 `R06_DERIVED_PRE_NBA_CALENDAR_PROPOSAL_V1`，只接受 `SYNTHETIC_CONTRACT_SELFTEST`，REAL一律拒收；已有 math、四lane、applications、cancellations、FX/config/result 字段，但其自身明确异步复位边沿仍缺。B0 应先验原始 scene/source/channel/note/generation，再按全部独立接受日历计算；不能从 DUT wave/env/phase 或 commit 汇总反推。真实 Pro 源/ROM SHA 和日历未齐，一律 `PENDING_REAL_CAPTURE`。

本包仅执行 Python 文件/ZIP SHA和只读 Git blob 核对，无模型导入、HDL/EDA、旧测试、联网或消息发送。可复现命令与双流／退出码见 `A0_RECEIPT.json`。需重新冻结时使用新目录，保留当前原件。
'''.format(head=head, tracking=tracking, model=MODEL, vectors=VECTORS, m3model=M3MODEL,
           oracle_sha=next(x['sha256'] for x in files if x['path'] == MODEL + '/oracle.py'))
    with (HERE / 'SOURCE_FREEZE.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(md)
    valid = (verification['frozen_dependencies_all_expected_sha256_match'] and
             verification['R06_archive_expected_sha256_match'] and
             all(x['same_bytes'] for x in rom_equality) and
             verification['all_recorded_working_tree_files_equal_head_blobs'])
    receipt = {'schema': 'M1_PRO_A0_READONLY_EXECUTION_RECEIPT_V1', 'started_utc': started,
               'finished_utc': datetime.now(timezone.utc).isoformat(),
               'argv': [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).resolve())],
               'cwd': str(Path.cwd()), 'python_version': platform.python_version(),
               'python_executable': str(Path(sys.executable).resolve()),
               'python_executable_sha256': sha(Path(sys.executable).read_bytes()),
               'script_sha256': sha(Path(__file__).read_bytes()),
               'files_checked': len(files), 'archive_members_referenced': len(members),
               'read_only_git_commands': CALLS, 'verification': verification,
               'result': 'SOURCE_FREEZE_PASS_WITH_PRO_GAPS' if valid else 'SOURCE_FREEZE_FAILED',
               'exit_code': 0 if valid else 1, 'real_result': 'PENDING_REAL_CAPTURE',
               'actual_level': 'L0_SOURCE_AND_CONTRACT_ONLY', 'submitted': False, 'pushed': False}
    write_json('A0_RECEIPT.json', receipt)
    artifacts = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                  'sha256': sha(p.read_bytes())}
                 for p in sorted(HERE.iterdir()) if p.is_file() and p.name != 'ARTIFACT_SHA256.json']
    write_json('ARTIFACT_SHA256.json', {'schema': 'M1_PRO_A0_ARTIFACT_SHA256_V1', 'files': artifacts})
    print(json.dumps({'status': receipt['result'], 'files': len(files), 'members': len(members),
                      'real_result': 'PENDING_REAL_CAPTURE',
                      'source_freeze_sha256': sha((HERE / 'SOURCE_FREEZE.json').read_bytes())}))
    return receipt['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
