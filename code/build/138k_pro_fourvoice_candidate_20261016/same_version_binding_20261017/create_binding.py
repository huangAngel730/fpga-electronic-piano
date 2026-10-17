"""Seal existing P10 bytes and a source-based observation gap map, without tools."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/same_version_binding_20261017"
STAGE = REPO / "code/build/138k_pro_fourvoice_candidate_20261016/repro_stage_20261017/stage_a"
EVIDENCE = REPO / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016"
M3_TREE = REPO / "code/output/m2_live_tasks_publish_20261017"
M3_COMMIT = "f32f1210d097fbe9292a3c34bbd9f50f57e1fb81"
STATUS = "PARTIAL_PENDING_PRO_MAPPING_TOOL_OR_PHYSICAL"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def main() -> None:
    artifact = OUT / "artifact"
    if artifact.exists():
        raise FileExistsError("preserve previous artifact; create a new revision instead")
    p10_manifest = json.loads((STAGE / "MANIFEST.json").read_text(encoding="utf-8"))
    assert len(p10_manifest["files"]) == 93
    for row in p10_manifest["files"]:
        data = (STAGE / row["path"]).read_bytes()
        assert len(data) == row["bytes"] and sha(data) == row["sha256"], row["path"]
    current_inputs = {
        "candidate/m2_138k_pro_fourvoice_candidate_top.sv": REPO / "code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/m2_138k_pro_fourvoice_candidate_top.sv",
        "candidate/pro_fourvoice_candidate.cst": REPO / "code/constraints/m2_138k_pro_fourvoice_candidate_20261016/pro_fourvoice_candidate.cst",
        "candidate/pro_fourvoice_candidate.sdc": REPO / "code/constraints/m2_138k_pro_fourvoice_candidate_20261016/pro_fourvoice_candidate.sdc",
    }
    for relative, path in current_inputs.items():
        assert path.read_bytes() == (STAGE / relative).read_bytes(), relative
    references = {
        "B1_OBSERVATION_CONTRACT.json": "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/OBSERVATION_CONTRACT.json",
        "B1_OBSERVATION_CONTRACT.md": "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/OBSERVATION_CONTRACT.md",
        "B2_REQUIRED_PUBLIC_OBSERVATIONS.md": "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/REQUIRED_PUBLIC_OBSERVATIONS.md",
        "B2_BRIDGE_CONTRACT.md": "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/BRIDGE_CONTRACT.md",
    }
    reference_data = {}
    for dest, relative in references.items():
        committed = subprocess.run(["git", "show", f"{M3_COMMIT}:{relative}"], cwd=REPO, capture_output=True, check=True).stdout
        assert committed == (M3_TREE / relative).read_bytes(), relative
        reference_data[dest] = (relative, committed)

    artifact.mkdir(parents=True)
    for row in p10_manifest["files"]:
        copy(STAGE / row["path"], artifact / "source_closure" / row["path"])
    copy(STAGE / "MANIFEST.json", artifact / "source_closure/MANIFEST.json")
    originals = {
        "R05_SOURCE_ARCHIVE.zip": REPO / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R05_XSAFE_ModelSim输入_20261015.zip",
        "R05_INPUT_BINDING.json": REPO / "code/docs/test/m3_r05_functional_integration_20261015/PREFLIGHT_2020_02/INPUT_BINDING.json",
        "P0_IDENTITY_RECEIPT.json": EVIDENCE / "p0_baseline_identity_20261017/P0_IDENTITY_RECEIPT.json",
        "P10_RECEIPT.json": EVIDENCE / "repro_stage_20261017/P10_RECEIPT.json",
        "NIGHT_RECEIPT_20261017.json": EVIDENCE / "NIGHT_RECEIPT_20261017.json",
    }
    for dest, source in originals.items():
        copy(source, artifact / "originals" / dest)
    for dest, (_, data) in reference_data.items():
        path = artifact / "references" / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    copy(HERE / "check_binding.py", artifact / "tools/check_binding.py")

    prefix = "source_closure/inputs/sources/"

    def ref(name: str, needle: str, wrapper: bool = False) -> dict[str, object]:
        relative = ("source_closure/candidate/" if wrapper else prefix) + name
        path = artifact / relative
        lines = path.read_text(encoding="utf-8").splitlines()
        hits = [i + 1 for i, text in enumerate(lines) if needle in text]
        assert hits, (name, needle)
        return {"path": relative, "sha256": sha(path.read_bytes()), "line": hits[0], "text": lines[hits[0] - 1].strip()}

    frame = "m2_fourvoice_timbre_delay_frame_core.sv"
    board = "m2_fourvoice_timbre_delay_board_top.sv"
    bank = "m1td_polyphonic_envelope_bank.sv"
    chain = "m1td_timbre_delay_chain.sv"
    router = "m1td_polyphonic_event_router.sv"
    adapter = "premixed_frame_adapter.sv"
    wrapper = "m2_138k_pro_fourvoice_candidate_top.sv"
    definitions: dict[str, tuple[str, str, list[dict[str, object]], str]] = {}

    def put(names: str, category: str, note: str, refs: list[dict[str, object]], visibility: str) -> None:
        for name in names.split():
            definitions[name] = (category, note, refs, visibility)

    public = "EXISTING_PUBLIC_PORT"
    m2 = "M2_INTERNAL_PENDING_CONTROLLED_EXPORT"
    m1 = "M1_INTERNAL_PENDING_OWNER_MAPPING"
    missing = "NOT_IMPLEMENTED_IN_CURRENT_SOURCE"
    put("cycle epoch", missing, "Capture wrapper must count actual core posedges and observed reset-entry epochs; no live capture or counters exist in this source closure.", [ref(frame, "input logic clk, rst_n, frame_tick")], "CAPTURE_DERIVATION_NOT_YET_IMPLEMENTED")
    put("rst_n", public, "frame_core.rst_n is the local synchronized reset; Pro sys_rst_n alone does not include PLL-lock loss. Route the existing reset port explicitly before capture.", [ref(frame, "input logic clk, rst_n, frame_tick"), ref(board, "wire core_async_rst_n =")], "MODULE_PUBLIC_ONLY_NOT_PRO_TOP")
    put("frame_tick", public, "frame_core.frame_tick is connected to i2s_tx.frame_tick. Observe the same pre-NBA core edge; no LRCLK-edge substitution.", [ref(frame, "input logic clk, rst_n, frame_tick"), ref(board, ".frame_tick(i2s_frame_tick)"), ref("i2s_tx.sv", "assign frame_tick = frame_start")], "MODULE_PUBLIC_ONLY_NOT_PRO_TOP")
    put("event_valid event_ready event_data", public, "Existing frame_core event handshake and 64-bit payload prove input acceptance only. They do not prove the allocator application edge.", [ref(frame, "input logic event_valid"), ref(frame, "output wire event_ready"), ref(frame, "input logic [63:0] event_data")], "MODULE_PUBLIC_ONLY_NOT_PRO_TOP")
    put("apply_valid apply_data", m1, "Router holds an accepted event and applies it over several states; no application-valid/data export exists. M1 must confirm the exact application boundary; do not use accept+1 or infer from final slot.", [ref(router, "performance_event_t held_event"), ref(router, "ALLOC_APPLY:if(slot_valid)")], "PRIVATE_ROUTER_STATE_NOT_A_PUBLIC_TRACE")
    put("apply_event_seq", missing, "No application sequence token is implemented. A future observer must explicitly preserve the independent input-plan sequence through the confirmed apply boundary.", [ref(router, "performance_event_t held_event")], "NO_IMPLEMENTED_SIGNAL")
    slot_refs = [ref(router, "output logic [3:0] slot_note_on"), ref(router, "output wire [15:0] slot_source_ids"), ref(bank, ".slot_note_on(slot_note_on)")]
    put("occupied_mask releasing_mask note_on_mask note_off_mask slot_sources slot_channels slot_notes slot_generations", m1, "Router has real public slot outputs, consumed internally by the M1 bank; the chain/frame_core/Pro top do not export them. Proposed packed lane i uses source/channel[4*i+:4], note[8*i+:8], generation[32*i+:32]. Owner mapping and an explicit controlled route remain pending.", slot_refs, "ROUTER_PUBLIC_PORTS_HIDDEN_INSIDE_M1_BANK")
    put("retire_mask", m1, "The actual allocator retirement strobe is alloc_retire in the router; release_done is a separate envelope request and is not interchangeable with retirement.", [ref(router, "wire [3:0] alloc_retire="), ref(bank, "assign release_done[i]")], "PRIVATE_ROUTER_STATE")
    put("req_valid req_ready", m2, "frame_core internally joins adapter request_valid with chain_calc_ready and !config_valid. request_accept is public, but cannot reconstruct both valid and ready from the acceptance pulse.", [ref(frame, "wire candidate_cancel, request_valid, request_ready"), ref(frame, "assign request_ready ="), ref(frame, "assign request_accept =")], "M2_INTERNAL_NET_AT_PUBLIC_CHILD_PORTS")
    put("req_id", public, "frame_core.request_id is the frame transaction ID. Slot/lane indices are separate domains; epoch must accompany any reset-reused ID.", [ref(frame, "output wire [31:0] request_id, committed_id")], "MODULE_PUBLIC_ONLY_NOT_PRO_TOP")
    put("advance_mask advance_frame_req_id", m1, "One actual shared lane_tick advances all four voice and ADSR instances on the same edge; proposed mask is 1111 on that one strobe and frame ID is pending_req_id. These are private bank wires and are not yet a public export. Never fabricate four staggered lane requests or mask with occupied slots.", [ref(bank, "wire lane_tick="), ref(bank, "for(genvar i=0;i<4;i++)"), ref(bank, ".sample_tick(lane_tick)"), ref(bank, "logic [31:0] pending_req_id")], "PRIVATE_M1_BANK_WIRES")
    put("result_valid result_ready result_id result_left result_right result_clip_mask", m2, "The m1td_timbre_delay_chain result ports are real, bound to frame_core local wires, but not exported by frame_core. First-valid ownership and complete backpressure payload need those exact ports. Proposed clip packing is {right,left}; no capture implements that packing yet.", [ref(chain, "output wire result_valid"), ref(chain, "input logic result_ready"), ref(chain, "output wire [31:0] result_id"), ref(chain, "output wire signed [23:0] result_left,result_right"), ref(chain, "output wire clipped_left,clipped_right"), ref(frame, ".candidate_clipped(clip_left | clip_right)")], "PUBLIC_CHAIN_PORTS_ON_M2_INTERNAL_NETS")
    put("commit commit_id commit_left commit_right commit_clip", public, "Use frame_core commit_pulse and committed_* ports, not the first result-valid edge. The frame adapter ORs left/right clip and buffers a complete tuple. Current board instantiation drops committed_clip, so a new explicit route remains required.", [ref(frame, "output wire pending_valid, commit_pulse"), ref(frame, "output wire [31:0] request_id, committed_id"), ref(frame, "output wire signed [23:0] committed_left, committed_right"), ref(frame, "output wire committed_clip"), ref(board, ".committed_right(produced_right), .committed_clip()")], "MODULE_PUBLIC_ONLY_NOT_PRO_TOP")
    put("cancel", public, "premixed_frame_adapter.candidate_cancel equals frame_tick. A raw frame pulse alone does not identify an outstanding cancelled transaction or reason. Request context and reset/deadline priority remain unbound.", [ref(adapter, "assign candidate_cancel=frame_tick")], "MODULE_PUBLIC_ONLY_NOT_PRO_TOP")
    put("cancel_reason", missing, "No encoded cancellation reason exists. Width and enum stay null; do not invent a frame/reset/identity reason code from PCM or an old toy calendar.", [ref(adapter, "assign candidate_cancel=frame_tick")], "NO_IMPLEMENTED_SIGNAL")
    put("config_valid config_ready", public, "Use frame_core configuration handshake. Board initialization supplies one enable/delay/gain payload after reset. Configuration acceptance is distinct from effect audio acceptance.", [ref(frame, "input logic config_valid"), ref(frame, "output wire config_ready"), ref(board, "logic m1_config_pending")], "MODULE_PUBLIC_ONLY_NOT_PRO_TOP")
    put("config_payload", missing, "No packed payload port exists. Existing independent ports total 62 bits (enable1 + delay16 + dry15 + wet15 + feedback15); proposed concatenation {enable,delay,dry,wet,feedback} must be approved and implemented before filling B1's null width.", [ref(frame, "input logic config_enable"), ref(frame, "input logic [15:0] config_delay_samples"), ref(frame, "input logic [14:0] config_dry_gain, config_wet_gain, config_feedback")], "ONLY_UNPACKED_COMPONENT_PORTS_EXIST")
    put("effect_input_valid effect_input_ready effect_input_id effect_input_left effect_input_right effect_input_clip_mask", m1, "m1td_stereo_delay input ports are connected to private audio_* nets in the M1 chain. Observe the actual input handshake and stereo metadata only after M1 confirms and exports the mapping.", [ref(chain, "wire audio_valid,audio_ready"), ref(chain, ".input_valid(audio_valid),.input_ready(audio_ready),.input_id(audio_id)"), ref(chain, ".input_left(audio_left),.input_right(audio_right)")], "PUBLIC_CHILD_PORTS_HIDDEN_IN_M1_CHAIN")
    put("tx_sample_valid tx_frame_id tx_req_id tx_clip tx_hold tx_startup_zero", missing, "No TX-adoption identity/clip/HOLD/startup sidecar exists. pcm_frame_buffer stores pending/held PCM but no pending/held ID or clip; commit/current request ID cannot reconstruct an actual held selection. A controlled read-only observer must preserve selected tuple identity at the real TX sampling edge.", [ref("pcm_frame_buffer.sv", "logic signed [PCM_WIDTH-1:0] pending_left, pending_right"), ref("pcm_frame_buffer.sv", "assign play_left ="), ref("i2s_tx.sv", "end else if (frame_start && valid)"), ref(board, ".valid     (1'b1)")], "NO_IMPLEMENTED_TX_IDENTITY_SIDECAR")
    put("tx_left tx_right", public, "i2s_tx has signed24 pcm_left/right inputs and samples them at frame_start && valid. These public inputs are the proposed PCM observation point only; no actual sidecar capture, ID, clip or HOLD fact is supplied. Do not infer adoption from commit or play values alone.", [ref("i2s_tx.sv", "input  logic signed [PCM_WIDTH-1:0] pcm_left"), ref("i2s_tx.sv", "input  logic signed [PCM_WIDTH-1:0] pcm_right"), ref("i2s_tx.sv", "end else if (frame_start && valid)")], "PUBLIC_TX_INPUTS_WITHOUT_ADOPTION_SIDECAR")
    for field, port in (("bclk", "i2s_bclk"), ("ws", "i2s_lrck"), ("din", "i2s_din"), ("pa_en", "pa_en")):
        put(field, public, f"Existing Pro top {port} output; capture raw values on the common core sample axis. PA is active high, forced low on external reset; pins are static candidates until electrical and physical admission.", [ref(wrapper, f"output logic       {port}", wrapper=True)], "PRO_TOP_PUBLIC_PORT")
    put("pll_locked", m2, "The legacy board receives visual_pll_locked and uses it in core_async_rst_n. It is not a Pro top output. Simulation uses a nominal self-running clock stub, not a physical PLL proof.", [ref(board, "wire core_clk, visual_pll_locked"), ref(board, "wire core_async_rst_n ="), ref("clock_plan_sim.v", "initial begin #1000;lock=1;end")], "M2_INTERNAL_PLL_PORT_CONNECTION")
    put("audio_stable", missing, "No independent audio_stable signal exists. PA enable or synchronized reset cannot silently be renamed as proof of stable audio startup.", [ref(board, "assign pa_en = ~rst_sync_n | ~core_async_rst_n")], "NO_IMPLEMENTED_SIGNAL")
    put("finish", missing, "A real capture finish/END and unique MONITOR_END with successful non-timeout receipt are absent. P10 source closure and EOF do not establish capture completion.", [ref(frame, "module m2_fourvoice_timbre_delay_frame_core")], "CAPTURE_COMPLETION_NOT_IMPLEMENTED")

    contract = json.loads((artifact / "references/B1_OBSERVATION_CONTRACT.json").read_text(encoding="utf-8"))
    assert set(definitions) == {f["name"] for f in contract["fields"]}, set(definitions) ^ {f["name"] for f in contract["fields"]}
    fields = []
    for field in contract["fields"]:
        category, note, refs, visibility = definitions[field["name"]]
        fields.append({**field, "category": category, "source_visibility": visibility, "bound_at_pro_top": field["name"] in {"bclk", "ws", "din", "pa_en"}, "proposed_mapping_only": True, "note": note, "references": refs})
    mapping = {"schema": "M2_PRO_PUBLIC_OBSERVABILITY_STATIC_GAP_MAP_V1", "status": STATUS, "basis": "EXACT_P10_SOURCE_CLOSURE_AND_M3_R03_REFERENCE", "field_count": len(fields), "category_counts": dict(Counter(f["category"] for f in fields)), "real_public_trace_exported": False, "private_hierarchical_read_authorized": False, "formal_interface_changed": False, "fields": fields, "pro_dut_pass": False, "board_release_allowed": False}
    dump(artifact / "PUBLIC_OBSERVATION_MAP.json", mapping)
    manifest_by_name = {r["path"]: r for r in p10_manifest["files"]}
    roms = [{"path": "source_closure/" + r["path"], "bytes": r["bytes"], "sha256": r["sha256"]} for r in p10_manifest["files"] if r["path"].startswith("inputs/rom/")]
    compile_lines = (artifact / "source_closure/inputs/compile.f").read_text(encoding="utf-8").splitlines()
    binding = {
        "schema": "M2_PRO_SAME_VERSION_STATIC_BINDING_V1", "scope": "STATIC_SOURCE_IDENTITY_AND_OBSERVABILITY_ONLY", "status": STATUS,
        "target": {"family_package_candidate": "Tang Mega 138K Pro / FPG676", "complete_device_symbol": None, "device_version": None, "actual_core_revision": None, "actual_dock_revision": None, "bank_voltage_verified": None, "reference_core_schematic": "4072 Rev1.10 2024-03-25", "reference_dock_schematic": "4071f Rev1.5 2025-03-25", "schematic_revisions_are_physical_identity": False},
        "source_basis": {"r05_archive_path": "originals/R05_SOURCE_ARCHIVE.zip", "r05_archive_sha256": sha((artifact / "originals/R05_SOURCE_ARCHIVE.zip").read_bytes()), "r05_binding_path": "originals/R05_INPUT_BINDING.json", "r05_binding_sha256": sha((artifact / "originals/R05_INPUT_BINDING.json").read_bytes()), "p10_manifest_path": "source_closure/MANIFEST.json", "p10_manifest_sha256": sha((STAGE / "MANIFEST.json").read_bytes()), "p10_original_member_count_including_manifest": 94, "p10_original_level": "L0_REPRODUCIBLE_SOURCE_CLOSURE", "p10_original_a_b_tree_sha256": "0e8e8f18059b451c57e777ca5efb3369a4c51f86a3b8658c8312b291cfe580c8", "authority": "R05_ORIGINAL_ZIP_AND_INPUT_BINDING_NOT_MUTATED_STAGED_MIRROR"},
        "candidate_top": {"module": "m2_138k_pro_fourvoice_candidate_top", "path": "source_closure/candidate/m2_138k_pro_fourvoice_candidate_top.sv", "sha256": manifest_by_name["candidate/m2_138k_pro_fourvoice_candidate_top.sv"]["sha256"], "underlying_top_sha256": manifest_by_name["inputs/sources/m2_fourvoice_timbre_delay_board_top.sv"]["sha256"], "port_adaptation": "sys_clk_50m/sys_rst_n/key_n/midi_rx passthrough; Pro pa_en=sys_rst_n && !legacy_pa_disable", "formal_top_or_algorithm_modified": False},
        "constraints": [{"path": "source_closure/" + p, "sha256": manifest_by_name[p]["sha256"], "level": "L0_CANDIDATE_ONLY_NOT_RESOLVED_PRO_NETLIST"} for p in ("candidate/pro_fourvoice_candidate.cst", "candidate/pro_fourvoice_candidate.sdc")],
        "simulation_source_list": {"path": "source_closure/inputs/compile.f", "sha256": manifest_by_name["inputs/compile.f"]["sha256"], "line_count": len(compile_lines), "units": compile_lines, "includes_testbench": True, "includes_pro_wrapper": False, "reason": "Frozen R05 list compiles legacy top + testbench; Pro wrapper is a separate archived candidate, not a claim of compiled P10 Pro top"},
        "roms": roms,
        "pll_ip": {"reference_hz_candidate": 50000000, "core_hz_candidate": 40000000, "pixel_hz_candidate": 25000000, "serial_hz_candidate": 125000000, "simulation_model_path": "source_closure/inputs/sources/clock_plan_sim.v", "simulation_model_sha256": manifest_by_name["inputs/sources/clock_plan_sim.v"]["sha256"], "simulation_model_scope": "Self-running nominal clocks; lock set after 1000ns; clkin not used to derive outputs; not analog lock/loss/MTBF proof", "physical_candidate_path": "source_closure/inputs/sources/TMDS_PLL_800_600_60.v", "physical_candidate_sha256": manifest_by_name["inputs/sources/TMDS_PLL_800_600_60.v"]["sha256"], "physical_candidate_scope": "Offline primitive migration with old GW5AT-LV60PG484AC1/I0 / device B / V1.9.10.01 header; not GUI-generated Pro IP", "dvi_sim_stub_path": "source_closure/inputs/sources/dvi_sim_stub.v", "dvi_sim_stub_sha256": manifest_by_name["inputs/sources/dvi_sim_stub.v"]["sha256"], "dvi_physical_candidate_path": "source_closure/inputs/sources/DVI_TX_Top.v", "dvi_physical_candidate_sha256": manifest_by_name["inputs/sources/DVI_TX_Top.v"]["sha256"], "new_pro_ip_generated": False},
        "m3_reference": {"commit": M3_COMMIT, "basis": "Exact committed B1/B2 files byte-compared with git show; reference only, no adoption or signature inference", "files": [{"path": "references/" + dest, "committed_path": relative, "sha256": sha(data)} for dest, (relative, data) in reference_data.items()]},
        "input_originals": [{"path": "originals/" + dest, "original_repository_path": source.relative_to(REPO).as_posix(), "bytes": source.stat().st_size, "sha256": sha(source.read_bytes())} for dest, source in originals.items()],
        "remaining": ["M1 owner confirmation/export of real event application, slot lifecycle, common advance and effect input; M2 controlled route of request/result/commit/reset/PLL ports", "Actual TX-adoption ID/clip/HOLD/startup sidecar, same-axis raw pins and real capture completion", "B1 61-field to B2 29-column semantic normalization; M1 independent same-source PCM/clip golden and C/D ledger", "P1 compile/P7 executor guard remains blocked; no new compiler, simulation or old budget use", "Actual Pro full device/version/core+dock revision/Bank and MIDI isolation electrical originals", "Real commercial Gowin permission and Pro PLL/IP/netlist/complete STA/new .fs and separate SRAM admission"],
        "pro_dut_pass": False, "board_release_allowed": False, "physical_ip_verified": False, "capture_completed": False,
    }
    dump(artifact / "SOURCE_BINDING.json", binding)
    note = """# M2 Pro 同版来源绑定与观察缺口（基础 P1，2026-10-17）

状态：**PARTIAL_PENDING_PRO_MAPPING_TOOL_OR_PHYSICAL**。本包完成既有来源原件身份封存及61字段逐项静态清点，只达到L0。它不是四声基础、真实Pro功能、仿真、综合、STA或板测通过；board_release_allowed=false。

source_closure/逐字节保留P10 stage_a原94件（原MANIFEST列93个payload加MANIFEST本体）；originals/包含R05原ZIP、原INPUT_BINDING和P0/P10/NIGHT收据。没有重新执行旧P0/P10、编译、RTL、EDA或设备，没有把旧正常/负例日志重新包装为新测试。三份现行候选top/CST/SDC与该闭包本体核同。原历史收据中路径仅为原始溯源；本包SOURCE_BINDING/MANIFEST引用均为相对artifact根目录路径。

R05原ZIP而非旧staged mirror是冻结输入依据；P0已记录后者3项ROM字节差异。本包直接取P10原闭包及原ZIP，并逐SHA核验。9份ROM均附本体和SHA，未重新生成或改变数学。P10 compile.f是原R05仿真列表（legacy top + TB），不包含Pro wrapper，也不是新的Pro物理source list。模型clock_plan_sim.v自生125/25/40MHz、1000ns置lock，clkin不参与产生时钟；dvi_sim_stub.v也是仿真stub。原物理PLL文件带60K PG484/工具V1.9.10.01/device B旧header，仅为离线候选，不能签Pro GUI IP、锁定/失锁或真实网表。

完整Pro料号、device version、实际4072/4071板修订、Bank电压均保持null；4072 Rev1.10与4071f Rev1.5只是参考原理图身份。CST里P16时钟、K16复位、F15/G15键、R17 MIDI、E22/F24/G24音频为静态候选；H17高有效PA和P15 UART仍缺参考CST/电气现场闭合。不得拿旧PG484码流或旧下载额度替代。

PUBLIC_OBSERVATION_MAP.json按B1的61字段全部登记既有公开模块端口、M2待受控导出连线、M1内部待其确认映射、当前不存在四类。除bclk/ws/din/pa_en外，没有字段已在Pro外层top绑定成公开观察。模块公开口不等于Pro trace已导出。静态识别真实共同lane_tick可以同沿推进四路，未来应记录一次mask1111及帧请求ID；不造四笔错开的lane请求。应用/退休和TX采纳必须另有实观，不能从accept+1、PCM、commit或slot最终状态反推。无层级私有读授权、无新RTL端口、无M1算法改动。null的cancel_reason/config_payload维持原合同；62位config拼接只是建议，尚未写入接口。

B1/B2参考文件均逐字节核自提交f32f1210d097fbe9292a3c34bbd9f50f57e1fb81，不能因为主工作区ad2未含5aa文件而捏造不存在。引用不表示B1 metadata已认证真实来源，更不表示B2已有真实串行、HOLD/startup/finish/END。旧D3返修和P7执行器停跑保持各自原状态。

可移植校验：解压本ZIP后，直接把artifact根目录传给tools/check_binding.py；必须从独立交接回执取MANIFEST SHA，不从待校文件自行相信。示例（在解压根执行，替换尖括号内容）：

```powershell
python -B -X utf8 tools/check_binding.py --artifact-root . --expected-manifest-sha256 <independently_frozen_manifest_sha256>
```

退出0仅代表本包SHA、范围、候选null身份、9 ROM及61字段清单一致；退出2为拒收。checker不解析HDL语义、不认证作者、不证明真实逐沿日历、PLL、PCM或硬件。正确原件、source改1byte、缺ROM、混scope、冒签完整料号及路径逃逸的新软件自检仅验证这个checker，原双流另放外层selftest/，不会升级DUT等级。

M1接手：按同一原ZIP/ROM确认应用、slot、advance/effect边界和独立黄金；M3接手：保留实物/电气原件及C/D独立输入，在M2落实公开出口和有效执行许可后接真实观察。以上为交接材料准备，真人消息仍待用户转发，尚未送达。
"""
    (artifact / "README.md").write_text(note, encoding="utf-8", newline="\n")
    files = [{"path": p.relative_to(artifact).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in sorted(artifact.rglob("*")) if p.is_file()]
    dump(artifact / "MANIFEST.json", {"schema": "M2_PRO_SOURCE_BUNDLE_MANIFEST_V1", "files": files, "scope": "STATIC_IDENTITY_ONLY", "board_release_allowed": False})
    manifest_sha = sha((artifact / "MANIFEST.json").read_bytes())
    archive_path = OUT / "M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip"
    assert not archive_path.exists()
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(artifact.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(artifact).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files) + 1
        assert all(archive.read(name) == (artifact / name).read_bytes() for name in archive.namelist())
    archive_sha = sha(archive_path.read_bytes())
    receipt = {"schema": "M2_PRO_STATIC_BINDING_CREATION_RECEIPT_V1", "result": "SEALED_STATIC_IDENTITY_ONLY", "status": STATUS, "artifact_root": "artifact", "manifest_sha256": manifest_sha, "archive": archive_path.name, "archive_bytes": archive_path.stat().st_size, "archive_sha256": archive_sha, "payload_files": len(files), "zip_members": len(files) + 1, "p10_original_members": 94, "roms": len(roms), "fields": len(fields), "category_counts": mapping["category_counts"], "old_tests_rerun": False, "compiler_or_eda_invoked": False, "board_release_allowed": False}
    dump(OUT / "CREATION_RECEIPT.json", receipt)
    (OUT / "README.md").write_text(note + f"\n原件ZIP：{archive_path.name}\n\nZIP SHA256：`{archive_sha}`\n\nMANIFEST SHA256：`{manifest_sha}`\n", encoding="utf-8", newline="\n")
    (OUT / (archive_path.name + ".sha256")).write_text(f"{archive_sha}  {archive_path.name}\n", encoding="ascii", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
