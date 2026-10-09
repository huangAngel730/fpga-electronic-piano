"""Single shared-engine proposal. Conditional calendar is not RTL evidence."""
import argparse
import json
from pathlib import Path

from inventory import capacities, inventory, rom_inventory, slot_width, verify_manifest

DEADLINE = 833
# Serial work slots are DESIGN CONTRACTS for B1/B2, not measured operator timing.
# Pitch consumer latency 7 is read from frozen source; all context adapter costs
# and ADSR scheduling equivalence still need a new implementation and TB.
VOICE_STEPS = (("context_read", 1), ("pitch_to_consumer", 7),
               ("dds_advance", 1), ("wave_read", 1), ("envelope_settle", 6),
               ("gain", 1), ("stereo_accumulate", 2), ("tag_check", 1),
               ("context_write", 1))


def calendar(n, *, dispatch_bound=None, step_contract=VOICE_STEPS,
             rom_ports=1, rom_latency=1):
    slot_width(n)
    if rom_ports != 1 or rom_latency != 1:
        raise ValueError("UNSUPPORTED_ROM_CONTRACT_REBUDGET_REQUIRED")
    names = [name for name, _ in step_contract]
    if names != [name for name, _ in VOICE_STEPS]:
        raise ValueError("MISSING_OR_REORDERED_WORK")
    if dispatch_bound is not None and (type(dispatch_bound) is not int or dispatch_bound < 0):
        raise ValueError("INVALID_DISPATCH_BOUND")
    if any(type(cost) is not int or cost <= 0 for _, cost in step_contract):
        raise ValueError("UNKNOWN_OR_INVALID_OPERATOR_COST")
    segments = []
    end = 0

    def add(name, clocks, voice=None):
        nonlocal end
        segments.append({"stage": name, "slot": voice, "begin": end, "end": end + clocks})
        end += clocks

    if dispatch_bound is not None:
        add("external_dispatch_bound", dispatch_bound)
    add("admission_settle", 8)
    add("atomic_control_snapshot", n + 1)
    for voice in range(n):
        for name, clocks in step_contract:
            add(name, clocks, voice)
    add("pipeline_drain", 2)
    add("result_commit", 2)
    add("guard", 16)
    conditional_status = "CONDITIONAL_FITS" if end < DEADLINE else "CONDITIONAL_EXCEEDS"
    return {"N": n, "conditional_cycles": end, "conditional_slack": DEADLINE - end,
            "conditional_status": conditional_status, "segments": segments,
            "dispatch_bound": dispatch_bound,
            "end_to_end_status": "UNKNOWN" if dispatch_bound is None else conditional_status,
            "actual_shared_engine_II": None, "actual_shared_engine_latency": None,
            "physical_STA": "NOT_RUN", "verified_voice_audio_equivalence": False,
            "contracts": {"ROM_read_ports_per_table": rom_ports,
                          "ROM_read_latency": rom_latency, "voice_launch_II": sum(c for _, c in step_contract),
                          "all_costs_are_unverified_design_contracts": True}}


def resources(n, rows, roms):
    slot = slot_width(n)
    totals = {category: sum(r["bits"] for r in rows if r["class"] == category)
              for category in ("voice_context", "voice_work", "snapshot", "identity", "global")}
    # Conservative context retention + one extra physical engine working copy.
    # These are logical payload allocations, not inferred flip-flop counts.
    working_copy = totals["voice_work"] // n
    tag_width = slot + 4 + 4 + 32 + 32
    new_scheduler = {"context_engine_work_bits": working_copy,
                     "two_tag_registers_bits": 2 * tag_width,
                     "issued_completed_masks_bits": 2 * n,
                     "serial_stereo_accumulators_bits": 2 * 32,
                     "control_FSM_5_bits": 5, "cursor_bits": slot + 1,
                     "active_request_bits": 32, "request_valid_bits": 1}
    return {"N": n, "source_logical_storage_bits": totals,
            "source_logical_total_bits": sum(totals.values()),
            "candidate_extra_logical_allocations": new_scheduler,
            "candidate_logical_allocation_bits": sum(totals.values()) + sum(new_scheduler.values()),
            "active_ROM_payload_bits_one_shared_copy": sum(r["bits_per_copy"] for r in roms if r["active_piano"]),
            "active_ROM_copies_selected": 1,
            "parallel_ROM_payload_bits": n * sum(r["bits_per_copy"] for r in roms if r["active_piano"]),
            "alternative_balanced_stereo_tree": {"internal_nodes": 2 * (n - 1),
                                                 "registered_payload_bits": 2 * (n - 1) * 32,
                                                 "selected": False},
            "selected_mixer": "serial signed32 L/R accumulation, saturate once to signed24",
            "logical_multiplier_operations_in_frozen_voice": 8,
            "actual_Logic": None, "actual_Register": None, "actual_DSP": None,
            "actual_BSRAM_blocks": None, "actual_SSRAM": None,
            "port_mux_decoder_valid_control_and_mapping_overhead": None,
            "physical_resource_fit": "UNKNOWN"}


def report():
    frozen = verify_manifest()
    roms = rom_inventory()
    inventories = {str(n): inventory(n) for n in (4, 8, 16, 32)}
    return {"schema": 1, "stage": "T061_B0_SOURCE_BUDGET_AND_PROTOCOL_ORACLE",
            "scope_result": "PARTIAL_NO_RTL_OR_AUDIO_EQUIVALENCE",
            "selected_independent_candidate": "single time-multiplexed full-context engine",
            "architecture_comparison": {
                "parallel": "simplest state equivalence; N ROM/operator copies; expansion placement unknown",
                "shared_selected": "one table copy and one engine; full saved contexts and identity tags; B2 semantic risk explicit",
                "hybrid": "multiple engines trade ports/resources for cycles; not implemented as a second candidate"},
            "clock_hz": 40000000, "sample_hz": 48000, "shortest_frame_cycles": DEADLINE,
            "source_observations": {
                "pitch_arithmetic_II": 1, "pitch_consumer_latency": 7,
                "pitch_wrapper_min_launch_II": 8, "control_snapshot_consumer_latency_N4": 5,
                "ADSR_note_on_preparation_clocks": 4, "ADSR_note_off_preparation_clocks": 2,
                "L_fraction_address": "value XOR rotl10(value,1) XOR rotl10(value,3)",
                "sub_source": "initialization image only, NOT a second runtime lookup ROM",
                "piano_wave_output": "one synchronous ROM output register per frozen lane"},
            "frozen_inputs": frozen, "capacity_reference": capacities(), "roms": roms,
            "inventories": inventories,
            "budgets": [resources(n, inventories[str(n)], roms) for n in (4, 8, 16, 32)],
            "calendars": [calendar(n) for n in (4, 8, 16, 32)],
            "unknowns_and_required_next_evidence": [
                "Event drain/CC64 release and downstream backpressure have no measured finite end-to-end bound here.",
                "21-cycle serial voice contract is a proposal; actual II/latency unknown until B1/B2 TB.",
                "All voices including silent and Release must execute once. No occupied-only shortcut.",
                "ADSR continuous pipeline + previous-cycle sustain product need exact context/preparation equivalence.",
                "LFO cancellation is non-rollback; protocol oracle does not model or prove DSP progression.",
                "32-bit request/generation wrap needs bounded outstanding-work/flush contract in RTL.",
                "Statebank ports, forwarding, event serialization, pipeline flush and tag fanout await RTL.",
                "Resource bits are logical allocations, NOT FF count/DSP mapping/BSRAM packing.",
                "Board/I2S/display/FIFO/PLL state is outside this audio-kernel inventory; old whole-design totals are reference only.",
                "N4 audio equivalence, N8/16/32 full audio, compiled behavioral mutants, synthesis and new whole STA NOT RUN."]}


def markdown(data):
    lines = ["# T061 B0 独立复音候选：同源预算", "",
             "仅源码清单、条件日历和 Python 协议 oracle。没有新 RTL、音频等价、综合或 STA 通过。", "",
             "主候选：单套分时完整上下文 engine。其它架构只作短对比。生产选型由 M2 决定。", "",
             "21 拍/voice 是待实现设计合同，非实测；未给 dispatch 上界时整体 UNKNOWN。", "",
             "| N | 条件拍数 | 条件余量 | 逻辑状态分配 bits（非 FF） | 整体 |",
             "|---|---:|---:|---:|---|"]
    for budget, schedule in zip(data["budgets"], data["calendars"]):
        lines.append(f"| {budget['N']} | {schedule['conditional_cycles']} | {schedule['conditional_slack']} | "
                     f"{budget['candidate_logical_allocation_bits']} | {schedule['end_to_end_status']} |")
    lines += ["", "## 原冻结 L 状态字段（N4，未来 N 只为缩放提案）", "",
              "重复保存的身份、快照、工作寄存不无证明合并；ADSR pipeline 全保留，另计一套 engine 工作副本。", "",
              "| 源/行 | 字段及位宽 | 类 | 份数 | bits | 生命周期 |",
              "|---|---|---|---:|---:|---|"]
    for row in data["inventories"]["4"]:
        fields = ", ".join(f"{key}:{width}" for key, width in row["fields"].items())
        lines.append(f"| {row['module']}.sv:{row['line']} | {fields} | {row['class']} | {row['copies']} | "
                     f"{row['bits']} | {row['rw_lifecycle_invalidation']} |")
    lines += ["", "## ROM（全部七份，piano 激活五表；替代 sine 不重复计）", "",
              "| 表 | 深×宽 | 单份 bits | piano 激活 | 用途 |", "|---|---:|---:|---|---|"]
    for row in data["roms"]:
        lines.append(f"| {row['name']} | {row['depth']}×{row['width']} | {row['bits_per_copy']} | "
                     f"{row['active_piano']} | {row['use']} |")
    lines += ["", "## 容量来源", "", "冻结 L 原工具报告，不是本轮新综合。"]
    for name, value in data["capacity_reference"]["resources"].items():
        lines.append(f"- {name}: {value['capacity']} {value['unit']}; 原整机用量 {value['old_whole_design_used']}。")
    lines += ["", "## 未验证边界", ""]
    lines.extend("- " + item for item in data["unknowns_and_required_next_evidence"])
    lines += ["", "完整逐周期日历、每字段源 SHA、56 输入 SHA、缩放清单见同次 budget.json。", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    data = report()
    (args.output / "budget.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "BUDGET.md").write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"status": data["scope_result"], "frozen_inputs": len(data["frozen_inputs"]),
                      "ROMs": len(data["roms"]), "N": [4, 8, 16, 32]}, ensure_ascii=False))
