"""Pinned B2 hybrid source ledger; NOT elaboration, synthesis or new RTL proof.

The restricted declaration scanner is audited against named NBA targets in ten
exact source blobs. It counts declared payload before dead-state elimination,
not mapped FFs. Historical captures are referenced via their original seals;
this stage neither replays sound nor promotes those conclusions to physical STA.
"""
import argparse
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

from b2_clock import backend_calendar
from inventory import FROZEN, ROOT, capacities, identity, rom_inventory, slot_width

PIN = "52ad3dc5e27f499bc79bad5c1a6b8d4bbf8a4387"
DOC = ROOT / "code/docs/hardware/polyphony_scaling_v1"
RTL = ROOT / "code/rtl/common/polyphony_scaling_candidate"
STATUS = "B2I_PINNED_HYBRID_BUDGET_PASS_T061_PARTIAL"
# All clocked payload targets, including unused/debug output registers. Integer
# loop variables, wires, combinational temporaries, ROMs and initial-only scratch
# are deliberately NOT sequential state. Arrays retain their full dimensions.
FIELDS = {
    "b2d_event_audio": "state delay_count cfg_slot owned_id age held_notes held_release gathered written held_base held_gen held_velocity held_sources held_channels held_occupied held_bend held_mod held_range pedal_shadow tags descriptors result_valid result_id left right late frame_velocity frame_base frame_gen frame_bend frame_mod frame_range frame_sources frame_channels frame_occupied",
    "b2d_control_snapshot": "control_mem initialized busy read_slot snapshot_valid snapshot_id snapshot_occupied snapshot_sources snapshot_channels snapshot_generations snapshot_pitch_bend snapshot_modulation snapshot_pitch_range control_applied invalid_range",
    "b2c_event_router": "state held_event slot_sources slot_channels slot_generation retire_pending retire_generation target_slot release_index slot_note_on slot_note_off slot_occupied slot_releasing slot_velocity slot_fcw slot_notes",
    "b2c_voice_allocator": "slots allocated_slot slot_valid release_slot release_target_valid",
    "b2c_sustain_controller": "pedal_down occupied key_down deferred releasing pending_mask pending_generations source_mem channel_mem note_mem generation_mem",
    "b1_scheduler": "state slot request_id issued completed issued_tags drain_cycles frame_cycles req_tag req_context req_flags req_control req_pedal deadline_missed",
    "b1_statebank": "context_a context_b identities flags controls controls_valid pedals configured live_bank rd_valid rd_identity rd_flags rd_context rd_control rd_pedal",
    "b2_audio_backend": "state cursor wait_count pitch_inflight rom_inflight age held_occupied held_base fcw_values held_envelopes phase_acc attack_left active_table pending_table table_pending wave_q accumulator result_valid result_id result_sources result_channels result_generations pcm_left pcm_right clipped deadline_missed completed_mask lane_valid lane_slot lane_wave lane_envelope lane_pcm lane_phase lane_fcw lane_table",
    "adsr_piano_envelope": "state level_q16 start_q16 peak_q16 sustain_q16 step_q16 elapsed pending_tick release_start_q16 rom_addr rom_dout step_delta_q reciprocal_q step_product_q sustain_product_q",
    "pitch_mod_fcw_pipeline": "lfo_phase sine_s0 depth_s0 semi_s0 semi_s1 sine_product_s1 total_s2 oct_s3 sub_s3 ratio_s4 fcw_product_s5 base_s0 base_s1 base_s2 base_s3 base_s4 valid_pipe fcw_out fcw_valid",
}
LIFECYCLE = {
    "b2d_event_audio": "sample snapshots/tag/descriptors; cancel invalidates token/result, not persistent router/DSP; reset clears",
    "b2d_control_snapshot": "256 source4/channel4 controls; initialized guards reset RAM; serialize N reads; event/request same edge sees new control",
    "b2c_event_router": "event/allocation/release/retirement; full generation and source/channel/note; generation modulo2^32",
    "b2c_voice_allocator": "event-selected slot/LRU rank; release survives off until real retirement; reset initializes ranks",
    "b2c_sustain_controller": "256 pedals plus N generation-bound releases; pending payload held until ACK; panic/reset clears pedal",
    "b1_scheduler": "all N issue/write masks; exact full tags; cancel drains, timeout locks until whole-domain reset",
    "b1_statebank": "two discardable 74-bit context banks; atomic publish; separate 256 identity controls and valid/pedal masks",
    "b2_audio_backend": "DDS/table state persistent; cancel never rolls back advance; token snapshots/results invalidated; counted drain counters",
    "adsr_piano_envelope": "continuous private ADSR pipeline; note events/preparation/sample tick; no rollback on token cancel",
    "pitch_mod_fcw_pipeline": "continuous seven-stage lane pipeline; note resets LFO, sample_enable advances; enclosing token guards stale output",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_path(module):
    return (FROZEN / "sources" if module in ("adsr_piano_envelope", "pitch_mod_fcw_pipeline", "note_pitch") else RTL) / (module + ".sv")


def pinned(path):
    """Fail closed against an already pushed commit, not a self-written SHA list."""
    item = identity(path)
    result = subprocess.run(["git", "show", PIN + ":" + item["path"]], cwd=ROOT,
                            capture_output=True, timeout=30, check=False)
    if result.returncode or sha(result.stdout.replace(b"\r\n", b"\n")) != item["lf_sha256"]:
        raise ValueError("PINNED_SOURCE_CHANGED:" + item["path"])
    return dict(item, pin_commit=PIN)


def integer(expression, env):
    """Only the arithmetic used by these pinned declarations, never eval()."""
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name) and node.id in env:
            return env[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            a, b = visit(node.left), visit(node.right)
            return a+b if isinstance(node.op, ast.Add) else a-b if isinstance(node.op, ast.Sub) else a*b
        raise ValueError("DECLARATION_EXPRESSION")
    return visit(ast.parse(expression.strip(), mode="eval").body)


def range_size(text, env):
    if text is None:
        return 1
    parts = text.strip("[]").split(":")
    if len(parts) != 2:
        raise ValueError("DECLARATION_RANGE")
    return abs(integer(parts[0], env)-integer(parts[1], env))+1


def clean_source(text):
    # Preserve line numbers; exclude non-synthesizable diagnostic code only.
    text = re.sub(r"// synthesis translate_off.*?// synthesis translate_on",
                  lambda m: "\n"*m[0].count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*|/\*.*?\*/", lambda m: "\n"*m[0].count("\n"), text, flags=re.S)


def storage(module, text, n):
    env = dict(N=n, SW=slot_width(n), TW=72+slot_width(n), CW=74)
    code = clean_source(text)
    depths, depth = [], 0
    for char in code:
        depths.append(depth)
        depth += (char == "(") - (char == ")")
    # <= in an if/for predicate is relational, not an NBA assignment.
    nba = {m[1] for m in re.finditer(r"\b(\w+)\s*(?:\[[^\]\n]+\]\s*)*<=", code)
           if depths[m.start()] == 0}
    declarations = {}
    pattern = r"\b(?:logic|reg)\s*(?:signed\s*)?(\[[^\]\n]+\])?\s*((?:\w+\s*(?:\[[^\]\n]+\])?\s*)(?:,\s*\w+\s*(?:\[[^\]\n]+\])?\s*)*)"
    for match in re.finditer(pattern, code):
        if re.search(r"\binput\s*$", code[max(0, match.start()-12):match.start()]):
            continue
        for part in match[2].split(","):
            name = re.fullmatch(r"\s*(\w+)\s*(\[[^\]]+\])?\s*", part)
            if name and name[1] in nba:
                if name[1] in declarations:
                    raise ValueError("DUPLICATE_STORAGE:"+module+":"+name[1])
                declarations[name[1]] = (match[1], name[2], code[:match.start()].count("\n")+1)
    # The only sequential packed struct is the standard 64-bit event word.
    if module == "b2c_event_router":
        anchor = "performance_event_t held_event;"
        if code.count(anchor) != 1:
            raise ValueError("EVENT_STRUCT_ANCHOR")
        declarations["held_event"] = ("[63:0]", None, code[:code.index(anchor)].count("\n")+1)
    expected = set(FIELDS[module].split())
    if set(declarations) != expected:
        raise ValueError("STORAGE_COVERAGE:"+module+":missing="+str(sorted(expected-set(declarations)))+
                         ":extra="+str(sorted(set(declarations)-expected)))
    copies = n if module in ("adsr_piano_envelope", "pitch_mod_fcw_pipeline") else 1
    rows = []
    for name, (packed, unpacked, line) in sorted(declarations.items()):
        width, entries = range_size(packed, env), range_size(unpacked, env)
        rows.append(dict(module=module, field=name, line=line, packed_range=packed,
                         unpacked_range=unpacked, width=width, entries=entries,
                         module_copies=copies, declared_bits=width*entries*copies,
                         read_write="clocked NBA target; RAM read qualification/port contract per module",
                         lifecycle=LIFECYCLE[module]))
    return rows


def calendar(n, response, router_wait=0):
    slot_width(n)
    if type(response) is not int or not 1 <= response <= 64 or type(router_wait) is not int or router_wait < 0:
        raise ValueError("CALENDAR_PARAMETERS")
    # E=sample admission J. WAIT_ROUTER E+1, SETTLE six countdowns plus
    # transition, CONTROL E+9; N serialized reads, 2N control/config loads,
    # START, then READ/CAPTURE/OFFER 3N. Extra wait applies BEFORE CONTROL.
    control = 9+router_wait
    launch = control+n+1+2*n+1+3*n+1
    be = backend_calendar(launch, n, response)
    return dict(N=n, response=response, router_wait=router_wait,
                control_accept_offset=control, backend_accept_offset=launch,
                advance_offset=be.advance, first_lane_offset=be.lanes[0],
                last_lane_offset=be.lanes[-1], lane_initiation_interval=response+3,
                backend_first_valid_offset=be.backend_first,
                wrapper_first_valid_offset=be.wrapper_first,
                age_excludes_admission_edge=be.wrapper_first-1,
                fixture_833_deadline_met=be.wrapper_first-1 < 833,
                output_handshake_offset=None, return_to_idle_offset=None,
                whole_engine_worst_case_bound=None,
                assumptions="quiescent router, no cancellation/reset/injection, ready paths unstalled; output backpressure unbounded")


def roms(n):
    uses = {"piano_band_4x256_8191.mem": ("b2_audio_backend", "wave_rom", 1),
            "velocity_gain_rom.mem": ("adsr_piano_envelope", "gain_rom", n),
            "oct_ratio_q16.mem": ("pitch_mod_fcw_pipeline", "oct_lut", n),
            "sub_ratio_q16.mem": ("pitch_mod_fcw_pipeline", "sub_lut", n),
            "lfo_sine_q15.mem": ("pitch_mod_fcw_pipeline", "lfo_lut", n)}
    rows = []
    for rom in rom_inventory():
        if rom["name"] not in uses:
            continue
        module, field, copies = uses[rom["name"]]
        text = clean_source(source_path(module).read_text(encoding="utf-8"))
        anchor = re.search(r"\b"+field+r"\s*\[0:(\d+)\]", text)
        if not anchor or int(anchor[1])+1 != rom["depth"]:
            raise ValueError("ROM_DECLARATION_ANCHOR:"+field)
        rows.append(dict(rom, module=module, field=field, source_copies=copies,
                         logical_runtime_bits=rom["bits_per_copy"]*copies,
                         declaration_line=text[:anchor.start()].count("\n")+1,
                         mapped_blocks=None, mapped_replication=None,
                         inference="one runtime read per source copy; vendor packing/sharing unknown"))
    if len(rows) != 5:
        raise ValueError("ROM_SET")
    return rows


def sealed_reports(package):
    manifest_path = DOC / package / "manifest.json"
    carrier_path = manifest_path.with_name("evidence.zip.b64")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    carrier = carrier_path.read_bytes()
    raw = base64.b64decode(carrier, validate=True)
    if sha(raw) != manifest["zip_sha256"] or sha(carrier) != manifest["carrier_sha256"]:
        raise ValueError("PRIOR_SEAL_SHA:"+package)
    archive = zipfile.ZipFile(io.BytesIO(raw))
    members = manifest["members"]

    def member(name):
        data = archive.read(name)
        if sha(data) != members[name]["sha256"] or len(data) != members[name]["bytes"]:
            raise ValueError("PRIOR_MEMBER_SHA:"+name)
        return data

    receipt_raw = member(manifest["qualified_receipt"])
    receipt = json.loads(receipt_raw)
    if (type(receipt["exit_code"]) is not int or receipt["exit_code"] != 0 or not receipt["status"].endswith("PASS_T061_PARTIAL")
            or receipt["candidate_sources_before"] != receipt["candidate_sources_after"]
            or receipt["frozen_inputs_before"] != receipt["frozen_inputs_after"]):
        raise ValueError("PRIOR_RECEIPT_NOT_QUALIFIED")
    prior_sources = {item["path"]: item for item in receipt["candidate_sources_before"]+receipt["frozen_inputs_before"]}
    for module in FIELDS:
        current = identity(source_path(module))
        if current["path"] not in prior_sources or prior_sources[current["path"]]["lf_sha256"] != current["lf_sha256"]:
            raise ValueError("PRIOR_FUNCTIONAL_SOURCE_DIFFERS:"+module)
    bound_outputs = {item["path"]: item for item in receipt["outputs"]}
    payloads = {manifest["qualified_receipt"]: receipt_raw}
    reports = []
    for name in sorted(members):
        if not re.search(r"/B2[DEFH]_N\d+_R\d+_long[01]\.json$", name):
            continue
        data = member(name)
        if name not in bound_outputs or bound_outputs[name]["sha256"] != sha(data):
            raise ValueError("REPORT_NOT_RECEIPT_BOUND")
        report = json.loads(data)
        if type(report["N"]) is not int or type(report["response"]) is not int:
            raise ValueError("PRIOR_REPORT_TYPES")
        predicted = calendar(report["N"], report["response"])
        if report["min_request_to_result_cycles"] != predicted["age_excludes_admission_edge"]:
            raise ValueError("SOURCE_CALENDAR_DISAGREES_WITH_SEALED_REPORT")
        if (report["max_request_to_result_cycles"] < report["min_request_to_result_cycles"] or
                bool(report["deadline_misses"]) != (report["max_request_to_result_cycles"] >= 833)):
            raise ValueError("PRIOR_DEADLINE_CLASSIFICATION")
        reports.append(dict(package=package, member=name, sha256=sha(data),
                            capture_sha256=report["capture_sha256"], N=report["N"], response=report["response"],
                            long_case=report["long_case"], published=report["counts"]["P"],
                            min_age=report["min_request_to_result_cycles"], max_age=report["max_request_to_result_cycles"],
                            deadline_misses=report["deadline_misses"], source_calendar_min_age=predicted["age_excludes_admission_edge"],
                            historical_result_not_replayed=True))
        payloads[name] = data
    archive.close()
    if not reports:
        raise ValueError("MISSING_PRIOR_REPORTS:"+package)
    provenance = dict(package=package, manifest=pinned(manifest_path), carrier=pinned(carrier_path),
                      zip_sha256=sha(raw), receipt_sha256=sha(receipt_raw),
                      verification="carrier/archive SHA and selected report/receipt member SHA; no new capture replay")
    return reports, provenance, payloads


def capacity_evidence():
    result = capacities()
    package = DOC / "B0_20261009"
    manifest_path = package / "manifest.json"
    carrier_path = package / "evidence.zip.b64"
    pins = [pinned(manifest_path), pinned(carrier_path)]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = base64.b64decode(carrier_path.read_bytes(), validate=True)
    if sha(raw) != manifest["zip_sha256"]:
        raise ValueError("CAPACITY_SEAL_SHA")
    name = result["source"]["path"]
    item = next(item for item in manifest["members"] if item["member"] == name)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        data = archive.read(name)
    if sha(data) != item["sha256"] or data != (ROOT/name).read_bytes():
        raise ValueError("CAPACITY_ORIGINAL_CHANGED")
    result["B0_seal_provenance"] = dict(zip_sha256=sha(raw), manifest=pins[0], carrier=pins[1])
    return result, pins, {name: data}


def operators():
    rows = []
    for module, names in (
            ("pitch_mod_fcw_pipeline", ("bend_product", "mod_product", "sine_product_s1", "ratio_s4", "fcw_product_s5")),
            ("adsr_piano_envelope", ("step_product_q", "sustain_product_q", "sustain_q16")),
            ("b2_audio_backend", ("product",))):
        text = clean_source(source_path(module).read_text(encoding="utf-8"))
        for name in names:
            matches = list(re.finditer(r"\b"+name+r"\s*(?:<=|=)\s*([^;]+\*[^;]+);", text))
            # Reset assignments contain no product; each arithmetic expression
            # is one source site. Constants are NOT promoted to physical DSPs.
            if len(matches) != 1:
                raise ValueError("MULTIPLIER_ANCHOR:"+module+":"+name)
            match = matches[0]
            rows.append(dict(module=module, field=name, expression=match[1].strip(),
                             line=text[:match.start()].count("\n")+1,
                             source=identity(source_path(module)),
                             module_copies="1" if module == "b2_audio_backend" else "N",
                             mapped_DSP_blocks=None))
    return rows


def render(report):
    lines = ["# B2i 实际混合候选账本（同一 JSON 对象生成）", "",
             "仅 L0 源码审计／L1 软件自检；没有新增 RTL、综合、PnR 或设备结果。", "",
             "现候选不是 B0 的单完整上下文引擎：N 份连续 ADSR/PitchMod，单共享 piano ROM／增益／串行混音，B1 CW=74。",
             "声明位数不是映射 FF，也不能按比特除以某个块大小冒充 BSRAM；未使用／输出未接状态可能被优化。", "",
             "| N | 声明时序载荷 bit | 运行 ROM bit | 源级乘法表达式实例 | R1 首次 F−J | age=F−J−1 |", "|---|---:|---:|---:|---:|---:|"]
    for row in report["configurations"]:
        c = row["R1_calendar"]
        lines.append(f'| {row["N"]} | {row["declared_sequential_payload_bits"]} | {row["runtime_ROM_bits"]} | {row["multiply_expression_instances"]} | {c["wrapper_first_valid_offset"]} | {c["age_excludes_admission_edge"]} |')
    lines += ["", "## 源级日历与边界", "",
              "空闲路由条件：C−J=12+6N；C→首次 wrapper F=16+N(R+3)；F−J=28+N(R+9)。",
              "旧报告 min/max 的 cycles 实际为 age=F−J−1，不能当原始沿差；833 检查使用 age。",
              "Pitch 输入 II=1，E+6 NBA 输出、E+7 消费；逐槽 ROM/gain/accum II=R+3，不等于整帧 II。",
              "router 待清空时间、输出握手、归还 idle、完整事件服务最坏界仍 UNKNOWN；R 仅响应保持参数，非物理 RAM 延迟。", "",
              "## 既有封存结果引用（不重跑、不升级原结论）", "",
              "| N | R | long | P | age min–max | late |", "|---|---:|---|---:|---:|---:|"]
    for row in report["historical_reports"]:
        lines.append(f'| {row["N"]} | {row["response"]} | {row["long_case"]} | {row["published"]} | {row["min_age"]}–{row["max_age"]} | {row["deadline_misses"]} |')
    lines += ["", "## 状态与 ROM 明细", "",
              "JSON configurations[].storage/roms 包含每个字段的源码路径／SHA／行号、位宽、数组深度、副本数、生命周期。",
              "256 身份控制在 control snapshot 与 B1 bank 分别保留；CC64 控制器、wrapper shadow、bank pedal 不去重。",
              "Pitch sub_source 仅初始化置换暂存，另列不加入运行 ROM；note_pitch 的 12 项半音 case 与八度移位另列，不假造 128 项 RAM。",
              "源码表达式 8N+1 个乘法含常数乘，既非 DSP 块数也非完整布线成本。", "",
              "## M2 尚需决定", "",
              "正式架构与接入档位、资源准入／代表配置与综合授权、整机事件服务及新整机 STA。",
              "当前 Logic/Register/DSP/BSRAM/SSRAM 映射全部 UNKNOWN；旧 138K 容量只作单位来源，不借旧整机余量。",
              "完整 T060/T061 不关闭；不修改共享状态表，登记交 M2。", ""]
    return "\n".join(lines)


def build():
    sources = {module: pinned(source_path(module)) for module in FIELDS}
    source_pins = list(sources.values()) + [pinned(source_path("note_pitch"))]
    source_pins += [pinned(FROZEN / "sources" / name) for name in ("audio_defs_pkg.sv", "sustain_control_contract_pkg.sv")]
    source_pins += [pinned(FROZEN / "rom" / row["name"]) for row in rom_inventory()]
    capacity, capacity_pins, capacity_payload = capacity_evidence()
    source_pins += capacity_pins
    configurations = []
    for n in (4, 8, 16, 32):
        fields = []
        for module in FIELDS:
            for field in storage(module, source_path(module).read_text(encoding="utf-8"), n):
                fields.append(dict(field, source=sources[module]))
        rom_rows = roms(n)
        configurations.append(dict(N=n, slot_bits=slot_width(n), full_tag_bits=72+slot_width(n),
                                   B1_context_bits=74, storage=fields, roms=rom_rows,
                                   declared_sequential_payload_bits=sum(f["declared_bits"] for f in fields),
                                   runtime_ROM_bits=sum(r["logical_runtime_bits"] for r in rom_rows),
                                   initialization_only_sub_source_bits=20480*n,
                                   multiply_expression_instances=8*n+1,
                                   R1_calendar=calendar(n, 1),
                                   response_calendars=[calendar(n, r) for r in range(1, 65)],
                                   mapped_resources={key: None for key in ("Logic", "Register", "DSP", "BSRAM", "SSRAM")},
                                   physical_40MHz_STA=None, production_admitted=False))
    reports, provenance, payloads = [], [], dict(capacity_payload)
    for package in ("B2D_20261010", "B2E_20261011", "B2F_20261011", "B2H_20261011"):
        rows, origin, files = sealed_reports(package)
        reports.extend(rows)
        provenance.append(origin)
        payloads.update(files)
    result = dict(status=STATUS, stage="T061_B2I_ACTUAL_HYBRID_SOURCE_BUDGET", pin_commit=PIN,
                  task_complete=False, new_validation="L0 source audit / L1 executable software tests only",
                  new_RTL_simulation=False, new_synthesis=False, new_PnR=False, device_operations=False,
                  source_pins=source_pins, configurations=configurations, historical_reports=reports,
                  historical_provenance=provenance, capacities=capacity,
                  operators=operators(),
                  combinational_note_pitch=dict(source=identity(source_path("note_pitch")),
                      semitone_case_entries=12, base_step_width=32,
                      arithmetic="note division/modulo by12, octave shift; combinational, no clocked storage",
                      mapped_Logic=None, inferred_ROM_blocks=None),
                  operator_calendar=dict(pitch=dict(input_II=1, output_NBA_latency=6, consumer_latency=7,
                      instances="N; not shared"),
                      envelope=dict(instances="N; continuous pipeline, sample and note event qualified",
                                    precompute_product_register_latency=2, full_sample_service_bound=None),
                      shared_wave_gain_mix=dict(lane_II="R+3", first_lane_after_C="15+R",
                                                physical_RAM_latency=None, full_frame_II=None)),
                  alternative_architectures="Historical B0 analytic comparisons retained unchanged; only ONE hybrid RTL implemented",
                  unknowns=["mapped resources/replication", "formal architecture/N selection", "general event service/deadline bound", "physical STA", "sustained board performance", "unconditional generation-wrap/ABA exclusion"],
                  M2_notification="待用户转发，尚未送达")
    return result, payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT / "code/output")
    output.mkdir(parents=True, exist_ok=False)
    try:
        result, historical = build()
        for name, data in historical.items():
            path = output / "historical_selected" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (output / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        (output / "audit.md").write_text(render(result), encoding="utf-8", newline="\n")
        print(json.dumps(dict(status=result["status"], configurations=len(result["configurations"]),
                              historical_reports=len(result["historical_reports"]), task_complete=False)))
        return 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(status="REJECT", reason=str(error))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
