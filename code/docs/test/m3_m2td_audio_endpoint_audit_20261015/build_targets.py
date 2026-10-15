"""Produce a small, explicitly pending target proposal from exact raw observations."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DESCRIPTIONS = [
    ("post_right_ram_address", "post_effect_storage", "wr_ptr_s1 -> right delay buffer address"),
    ("voice_lane2_phase_to_rom", "audio_sample_datapath", "piano phase accumulator -> wavetable address"),
    ("pitch_lane3_total_to_oct", "pitch_mod", "total_s2 -> octave ratio lookup address"),
    ("pitch_lane0_total_to_sub", "pitch_mod", "total_s2 -> sub-octave ratio lookup address"),
    ("event_fifo_to_audio_slot", "event_ingress_not_sample_path", "event FIFO -> audio allocator CE"),
]


def literal_glob(name):
    return name.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def main():
    source = ROOT / "observed_r03/observations.json"
    observation = json.loads(source.read_text(encoding="utf-8"))
    targets = []
    for path, (name, category, reason) in zip(observation["selected_paths"], DESCRIPTIONS, strict=True):
        target = {"id": name, "category": category, "reason": reason,
                  "from_node": path["from_node"], "to_node": path["to_node"],
                  "from_register": path["from_node"].rsplit("/", 1)[0],
                  "to_object_kind": "ram_input_pin" if category != "event_ingress_not_sample_path" else "register_enable_pin",
                  "clock": "sys_clk", "clock_period_ns": "25.000",
                  "required_analyses": ["Setup", "Hold"], "minimum_slack_ns": "0.000",
                  "observed_analyses": {path["analysis"]: {"slack_ns": path["slack_ns"], "raw_location": path["raw_location"],
                                                         "detail_candidates": path["detail_candidates"],
                                                         "routed_node_locations": path["routed_node_locations"]}},
                  "missing_analysis": "Setup" if path["analysis"] == "Hold" else "Hold",
                  "exact_pair_both_analyses": "UNKNOWN", "query_existence_executed": False,
                  "activity_for_new_directed_queries": "UNKNOWN_NOT_EXECUTED"}
        targets.append(target)
    document = {"schema": "M3_M2TD_ENDPOINT_TARGET_PROPOSAL_V1", "scope": "PREPARATION_ONLY_NOT_STA_ACCEPTANCE",
                "source_archive": observation["source_archive"],
                "report_member": "pnr/timing.html", "report_sha256": observation["member_identities"]["pnr/timing.html"]["sha256"],
                "board_release_allowed": False, "new_sta_executed": False, "targets": targets,
                "requested_register_pair": {"source_relation": "base_s1[31:0] -> base_s2[31:0]",
                                            "source_sha256": "5997ae2eddb483f95dbb10cdac6cfdac3d61a857046e95e136099e11cf0ecabb",
                                            "source_classification": "DERIVED_RECONSTRUCTION_NOT_ORIGINAL",
                                            "synthesis_cell_from": None, "synthesis_cell_to": None,
                                            "routed_cell_from": None, "routed_cell_to": None,
                                            "same_pair_setup_hold": "UNKNOWN_MISSING_SAME_RUN_NETLIST_AND_REPORT",
                                            "not_inferred": "No automatic new prefix + base_s1_18_s0/base_s2_18_s0 construction"}}
    destination = ROOT / "targets.json"
    if destination.exists():
        raise ValueError("refuse overwrite targets")
    destination.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# PROPOSAL ONLY. Do not source this file in Gowin. No STA has been executed.",
             "# M2 must first approve the exact implementation database, tool/commands/budget/output.",
             "# Confirm vendor collection cardinality/name inspection semantics before using guards.",
             "# get_regs queries below must return exactly one cell; get_pins exactly one named terminal.",
             "# Escaped square brackets represent literal bus/lane names, not wildcard character classes.",
             "# Record returned object names, associated clock pins, and sys_clk=25.000ns before reporting.",
             "# Never remove escapes or accept a broader wildcard just to get a nonempty result.", ""]
    for t in targets:
        register = literal_glob(t["from_register"])
        terminal = literal_glob(t["to_node"])
        lines.extend(["# " + t["id"], "# Source register existence query (must have 1 exact object):",
                      "get_regs {" + register + "}", "# Destination terminal existence query (must have 1 exact object):",
                      "get_pins {" + terminal + "}",
                      "# sys_clk collection must be exact singleton, active, 25.000ns; clock-pin association must be checked.",
                      "get_clocks {sys_clk}"])
        for mode in ("setup", "hold"):
            lines.append("report_timing -" + mode + " -from [get_regs {" + register + "}] -to [get_pins {" + terminal + "}] -max_paths 1 -max_common_paths 1")
        lines.extend(["# Reject absent/inactive query or no actual path; require exact from/to pin, sys_clk:[R] on both sides,",
                      "# finite slack >= 0.000 for BOTH Setup and Hold from the SAME implementation identity.", ""])
    (ROOT / "STA_PROPOSAL_NOT_EXECUTABLE.tcl.txt").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": "PROPOSAL_ONLY", "targets": len(targets), "base_register_pair": "UNKNOWN", "board_release_allowed": False}))


if __name__ == "__main__":
    main()
