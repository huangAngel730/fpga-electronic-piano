"""Review actual Gowin reports; exit0 alone never signs off STA or boot flags."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import re
import fnmatch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run", type=Path)
parser.add_argument("--output-name", default="EDA_REVIEW_R01.json")
args = parser.parse_args()
run = args.run.resolve()
if Path(args.output_name).name != args.output_name or not args.output_name.endswith(".json"):
    parser.error("output-name must be a plain JSON file name")
out = run / args.output_name
if out.exists():
    raise SystemExit("review already exists; preserve the original")
pnr = run / "gowin/pro_audio/impl/pnr"
timing = pnr / "pro_audio.tr"
text = timing.read_text(encoding="utf-8", errors="replace")
text = text[text.index("Note:Core Timing Report"):]


def between(start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


tables = {
    "setup": between("3.1.1 Setup Paths Table", "3.1.2 Hold Paths Table"),
    "hold": between("3.1.2 Hold Paths Table", "3.1.3 Recovery Paths Table"),
    "recovery": between("3.1.3 Recovery Paths Table", "3.1.4 Removal Paths Table"),
    "removal": between("3.1.4 Removal Paths Table", "3.2 Minimum Pulse Width Table"),
    "pulse": between("3.2 Minimum Pulse Width Table", "3.3 Timing Report By Analysis Type"),
}
worst = {}
for kind, table in tables.items():
    values = [float(x) for x in re.findall(r"^\s+\d+\s+(-?\d+\.\d+)\s+", table, re.M)]
    worst[kind] = min(values) if values else None
violated = {kind: int(re.search(r"<Numbers of " + kind.title() + r" Violated Endpoints>:(\d+)", text).group(1))
            for kind in ("setup", "hold")}
constraint_rows = re.findall(r"^\s+(TC_[A-Z_]+)\s+(\w+)\s+(.+?)\s*$",
                             text.split("3.8 Timing Constraints Report", 1)[1], re.M)
inactive = [command for _, state, command in constraint_rows if state != "Actived"]
executed_sdc = (run / "inputs/project/pro_audio.sdc").read_text(encoding="utf-8")
expected_commands = {" ".join(line.strip().split()) for line in executed_sdc.splitlines()
                     if line.strip().startswith(("create_", "set_"))}
actual_commands = {" ".join(command.split()) for _, _, command in constraint_rows}
missing_commands = sorted(expected_commands - actual_commands)
exception_sections = {
    "setup": between("3.7.1 Setup Analysis Report", "3.7.2 Hold Analysis Report"),
    "hold": between("3.7.2 Hold Analysis Report", "3.7.3 Recovery Analysis Report"),
    "recovery": between("3.7.3 Recovery Analysis Report", "3.7.4 Removal Analysis Report"),
    "removal": between("3.7.4 Removal Analysis Report", "3.8 Timing Constraints Report"),
}
exceptions = []
empty_exception_sections = []
for kind, section in exception_sections.items():
    chunks = re.split(r"Timing Path Constraint\[\d+\]:\s*", section)[1:]
    for chunk in chunks:
        command = chunk.splitlines()[0].strip()
        if not command.startswith(("set_max_delay", "set_min_delay")):
            continue
        slacks = [float(x) for x in re.findall(r"^Slack\s*:\s*(-?\d+\.\d+)", chunk, re.M)]
        item = {"analysis": kind, "command": command,
                "reported_worst_paths": len(slacks),
                "worst_slack_ns": min(slacks) if slacks else None}
        (exceptions if slacks else empty_exception_sections).append(item)
gui = json.loads((run / "inputs/project/impl/pro_audio_process_config.json").read_text(encoding="utf-8"))
cfg = (pnr / "device.cfg").read_text(encoding="utf-8")
external_clock = re.search(r"^set ext_cclk = (true|false)\s*$", cfg, re.M).group(1) == "true"
configuration_match = external_clock == gui["EXTERNAL_MASTER_CONFIG_CLOCK"]
identity_ok = all(x in text for x in ("V1.9.12.04", "GW5AST-LV138FPG676AC1/I0", "<Device Version>: C"))
clock_summary = between("2.2 Clock Summary", "2.3 Max Frequency Summary")
clock_periods = {name: float(period) for name, period in re.findall(
    r"^\s+\d+\s+(\w+)\s+(?:Base|Generated)\s+(\d+\.\d+)\s+", clock_summary, re.M)}
clocks_ok = clock_periods == {"ref_clk": 20.0, "core_clk": 25.0,
                              "serial_clk": 8.0, "pixel_clk": 40.0}
serializer_reset_paths = {}
serializer_natural_records = {}
natural_global_reports = {}
executed_display = (run / "inputs/project/src/extension_visual/display/pro_score_display.sv").read_text(encoding="utf-8")
release_blocks = re.findall(r"always_ff\s*@\(([^)]*)\)\s*begin\s*if\s*\(!rst_n\)\s*dvi_rst_n", executed_display)
release_edge = ("F" if release_blocks[0].strip().startswith("negedge pixel_clk") else
                "R" if release_blocks[0].strip().startswith("posedge pixel_clk") else None) if len(release_blocks) == 1 else None
expected_release_clock = "pixel_clk:[" + release_edge + "]" if release_edge else "UNKNOWN"
nearest_serial_clock = "serial_clk:[R]" if release_edge == "F" else "serial_clk:[F]"
for kind in ("recovery", "removal"):
    natural_global_reports[kind] = []
    for chunk in re.split(r"<Report Command>:\s*", tables[kind])[1:]:
        command = chunk.splitlines()[0]
        if not any(token in command for token in ("-from", "-to", "-through")):
            values = re.findall(r"^\s+\d+\s+(-?\d+\.\d+)\s+", chunk, re.M)
            natural_global_reports[kind].append({"command": command, "nonempty_paths": len(values)})
    rows = re.findall(r"^\s+\d+\s+(-?\d+\.\d+)\s+.*u_OSER10_(clk|r|g|b)/RESET\s+.*$",
                      tables[kind], re.M)
    serializer_reset_paths[kind] = {lane: min(float(slack) for slack, name in rows if name == lane)
                                    for lane in {name for _, name in rows}}
    serializer_natural_records[kind] = []
    for line in tables[kind].splitlines():
        fields = line.split()
        if len(fields) != 9 or not fields[0].isdigit() or "u_OSER10_" not in fields[3] or not fields[3].endswith("/RESET"):
            continue
        lane = re.search(r"u_OSER10_(clk|r|g|b)/RESET$", fields[3]).group(1)
        serializer_natural_records[kind].append({"lane": lane, "slack_ns": float(fields[1]),
            "source": fields[2], "launch_clock": fields[4], "latch_clock": fields[5],
            "relation_ns": float(fields[6]), "clock_skew_ns": float(fields[7]),
            "data_delay_ns": float(fields[8])})
serializer_coverage_ok = all(
    {r["lane"] for r in serializer_natural_records[kind]
     if r["source"] == "u_score_visual/u_display/dvi_rst_n_s1/Q"
     and r["launch_clock"] == expected_release_clock and r["latch_clock"].startswith("serial_clk:")}
    == {"clk", "b", "g", "r"} for kind in ("recovery", "removal"))
serializer_natural_recovery_ok = all(
    any(r["lane"] == lane and r["relation_ns"] == 4.0 and r["latch_clock"] == nearest_serial_clock
        and r["launch_clock"] == expected_release_clock
        and r["slack_ns"] >= 0 for r in serializer_natural_records["recovery"])
    for lane in ("clk", "b", "g", "r"))
serializer_pixel_checks_ok = all(any(
    r["lane"] == lane and r["launch_clock"] == expected_release_clock
    and r["latch_clock"] == "pixel_clk:[R]" and r["slack_ns"] >= 0
    and r["relation_ns"] == ((20.0 if kind == "recovery" else -20.0)
                             if release_edge == "F" else (40.0 if kind == "recovery" else 0.0))
    for r in serializer_natural_records[kind])
    for kind in ("recovery", "removal") for lane in ("clk", "b", "g", "r"))
natural_global_ok = all(any(r["nonempty_paths"] for r in natural_global_reports[kind])
                        for kind in ("recovery", "removal"))
half_cycle_records = {}
for kind in ("setup", "hold"):
    half_cycle_records[kind] = []
    for line in tables[kind].splitlines():
        fields = line.split()
        if len(fields) != 9 or not fields[0].isdigit() or fields[3] != "u_score_visual/u_display/dvi_rst_n_s1/D":
            continue
        half_cycle_records[kind].append({"source": fields[2], "slack_ns": float(fields[1]),
            "launch_clock": fields[4], "latch_clock": fields[5], "relation_ns": float(fields[6]),
            "clock_skew_ns": float(fields[7]), "data_delay_ns": float(fields[8])})
half_cycle_expanded_ok = release_edge != "F" or all(any(
    r["launch_clock"] == "pixel_clk:[R]" and r["latch_clock"] == "pixel_clk:[F]"
    and r["relation_ns"] == (20.0 if kind == "setup" else -20.0) and r["slack_ns"] >= 0
    for r in half_cycle_records[kind]) for kind in ("setup", "hold"))
# A worst-N report is not an endpoint inventory. Accept the native zero-hold
# result for an unexpanded half-cycle endpoint only with a real expanded
# setup path, nonempty global AND identical clock/net hold collections, and
# no false-path coverage of either endpoint. Never invent its exact slack.
hold_report_scopes = []
for chunk in re.split(r"<Report Command>:\s*", tables["hold"])[1:]:
    command = chunk.splitlines()[0]
    slacks = [float(x) for x in re.findall(r"^\s+\d+\s+(-?\d+\.\d+)\s+", chunk, re.M)]
    hold_report_scopes.append({"command": command, "reported_paths": len(slacks),
                              "worst_slack_ns": min(slacks) if slacks else None})
global_hold_reported = any(r["reported_paths"] and r["worst_slack_ns"] >= 0 and
    not any(token in r["command"] for token in ("-from", "-to", "-through")) for r in hold_report_scopes)
same_filter_hold_reported = any(r["reported_paths"] and r["worst_slack_ns"] >= 0 and
    all(token in r["command"] for token in (
        "-from_clock [get_clocks {pixel_clk}]", "-to_clock [get_clocks {pixel_clk}]",
        "-through [get_nets {u_score_visual/u_display/pixel_rst_n}]")) for r in hold_report_scopes)
half_false_paths = []
unparsed_false_paths = []
half_nodes = {"from": {"pins": "u_score_visual/u_display/u_pixel_reset/sync_chain_1_s0/Q",
                       "regs": "u_score_visual/u_display/u_pixel_reset/sync_chain_1_s0",
                       "clocks": "pixel_clk"},
              "to": {"pins": "u_score_visual/u_display/dvi_rst_n_s1/D",
                     "regs": "u_score_visual/u_display/dvi_rst_n_s1", "clocks": "pixel_clk"}}
for line in executed_sdc.splitlines():
    if line.strip().startswith("set_false_path"):
        collections = re.findall(r"-(from|to)\s+\[get_(pins|regs|ports|clocks)\s+\{([^}]+)\}\]", line)
        if not collections:
            unparsed_false_paths.append(line)
        for side, category, patterns in collections:
            node = half_nodes[side].get(category)
            if node and any(fnmatch.fnmatchcase(node, pattern) for pattern in patterns.split()):
                half_false_paths.append(line)
half_setup_expanded = any(r["launch_clock"] == "pixel_clk:[R]" and
    r["latch_clock"] == "pixel_clk:[F]" and r["relation_ns"] == 20.0 and r["slack_ns"] >= 0
    for r in half_cycle_records["setup"])
half_hold_native_accepted = (half_setup_expanded and violated["hold"] == 0 and
    global_hold_reported and same_filter_hold_reported and not half_false_paths and not unparsed_false_paths)
half_cycle_ok = half_cycle_expanded_ok or (release_edge == "F" and half_hold_native_accepted)
executed_cst = (run / "inputs/project/pro_audio.cst").read_text(encoding="utf-8")
requested_site = re.search(r'INS_LOC\s+"u_score_visual/u_display/dvi_rst_n_s1"\s+([^;]+);', executed_cst)
release_sites = set()
for line in text.splitlines():
    if re.search(r"u_score_visual/u_display/dvi_rst_n_s1/(?:Q|CLK)\s*$", line):
        site = re.search(r"\bR\d+C\d+\[[0-3]\]\[[AB]\]", line)
        if site:
            release_sites.add(site.group(0))
placement_ok = not requested_site or release_sites == {requested_site.group(1).strip()}
serializer_exceptions = [e for e in exceptions if "u_OSER10_" in e["command"]]
bundles = [e for e in exceptions if "u_score_visual/u_display" in e["command"] and e not in serializer_exceptions]
extra_data_min = [e for e in exceptions if e not in bundles and e not in serializer_exceptions]
expected_extra = sum(command.startswith("set_min_delay") and
                     "u_score_visual/u_display" not in command and "u_OSER10_" not in command
                     for command in expected_commands)
expected_serializer = sum(command.startswith(("set_max_delay", "set_min_delay")) and "u_OSER10_" in command
                          for command in expected_commands)
expected_delays = {c for c in expected_commands if c.startswith(("set_max_delay", "set_min_delay"))}
covered_delays = {" ".join(e["command"].split()) for e in exceptions}
exception_ok = len({e["command"] for e in bundles}) == sum(c.startswith(("set_max_delay", "set_min_delay")) and "u_score_visual/u_display" in c and "u_OSER10_" not in c for c in expected_commands) and len({e["command"] for e in extra_data_min}) == expected_extra and len({e["command"] for e in serializer_exceptions}) == expected_serializer and expected_delays <= covered_delays and all(
    e["worst_slack_ns"] is not None and e["worst_slack_ns"] >= 0 for e in exceptions)
timing_ok = all(v is not None and v >= 0 for v in worst.values()) and not any(violated.values())
# R10 user acceptance is strictly greater than 0.400 ns at unchanged clocks.
# Retain the native STA result separately: nonnegative Setup alone is insufficient.
setup_exception_slacks = [e["worst_slack_ns"] for e in exceptions
                          if e["analysis"] == "setup" and e["worst_slack_ns"] is not None]
setup_all_checks = ([worst["setup"]] + setup_exception_slacks
                    if worst["setup"] is not None else [])
setup_all_checks_min = min(setup_all_checks) if setup_all_checks else None
setup_margin_ok = setup_all_checks_min is not None and setup_all_checks_min > 0.400
passed = timing_ok and configuration_match and identity_ok and clocks_ok and placement_ok and not inactive and not missing_commands and exception_ok and serializer_coverage_ok and serializer_natural_recovery_ok and natural_global_ok and half_cycle_ok and serializer_pixel_checks_ok
files = [timing, pnr / "pro_audio.rpt.txt", pnr / "device.cfg"]
files += list(pnr.glob("*.fs"))
files += list(pnr.glob("*.pin.html"))
synthesis = pnr.parent / "gwsynthesis"
files += [synthesis / "pro_audio.vg", synthesis / "pro_audio_syn.rpt.html",
          synthesis / "pro_audio_syn_resource.html"]
net = (synthesis / "pro_audio.vg").read_text(encoding="utf-8", errors="replace")
lut1_instance_names = re.findall(r"^\s*LUT1\s+(\S+)\s*\(", net, re.M)


def explicit_identity_count(group):
    # Count declarations by their exact explicit primitive instance name.
    # Nested syn_keep wires can infer extra identity LUTs whose port nets
    # contain the group name; those are not additional u_identity instances.
    return sum(re.search(re.escape(group) + r"\[\d+\].*\.u_identity$", name) is not None
               for name in lut1_instance_names)


identity_luts = {name: explicit_identity_count(name)
                 for name in ("g_fcw_hold", "g_delay_write_hold", "g_score_identity_hold")}
identity_luts_ok = identity_luts == {"g_fcw_hold": 128, "g_delay_write_hold": 20,
                                      "g_score_identity_hold": 75}
hold_identity_luts = {name: explicit_identity_count(name)
                      for name in ("g_score_payload_hold", "g_read_word_hold",
                                   "g_read_word8_hold", "g_live_fault_hold", "g_envelope_hold", "g_generation_capture_hold")}
hold_buffers_expected = {"g_score_payload_hold": 8, "g_read_word_hold": 2,
                         "g_read_word8_hold": 4,
                         "g_live_fault_hold": 2, "g_envelope_hold": 8,
                         "g_generation_capture_hold": 0}
executed_scheduler = (run / "inputs/project/src/extension_visual/scheduler/pro_score_scheduler.sv").read_text(encoding="utf-8")
hold_buffers_required = "score_payload_hold_chain" in executed_scheduler
hold_buffers_ok = hold_identity_luts == hold_buffers_expected if hold_buffers_required else True
post_id_names = [n for n in lut1_instance_names if re.search(r"g_post_id_hold\[(?:20|31)\].*\.u_identity$", n)]
post_id_identity_ok = len(post_id_names) == 4 and all(
    re.search(r"defparam\s+" + re.escape(n) + r"\s*\.INIT\s*=\s*2'h2\s*;", net)
    for n in post_id_names)
snapshot_names = [n for n in lut1_instance_names if re.search(r"g_snapshot_hold\[\d+\].*\.u_identity$", n)]
trace_names = [n for n in lut1_instance_names if re.search(r"g_trace_(?:main|stage)_(?:address|data)_hold\[\d+\]\.u_(?:wr|rd|data)_hold_[01]$", n)]
new_hold_names = snapshot_names + trace_names
new_hold_init_ok = all(re.search(r"defparam\s+" + re.escape(n) + r"\s*\.INIT\s*=\s*2'h2\s*;", net) for n in new_hold_names)
# Any legitimate constant folding requires a separate recorded native-net audit.
new_hold_exact_count_ok = len(snapshot_names) == 592 and len(trace_names) == 3924
previous_state_names = [n for n in lut1_instance_names if re.search(r"g_previous_state_hold\[\d+\]\.u_hold_[01]$", n)]
previous_state_ok = len(previous_state_names) == 424 and all(re.search(r"defparam\s+" + re.escape(n) + r"\s*\.INIT\s*=\s*2'h2\s*;", net) for n in previous_state_names)
passed = passed and identity_luts_ok and setup_margin_ok and hold_buffers_ok and post_id_identity_ok and new_hold_init_ok and new_hold_exact_count_ok and previous_state_ok
result = {"reviewed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
          "status": "PASS_REPORTED_STA_AND_CONFIGURATION" if passed else "FAIL",
          "timing_status": "PASS_REPORTED_PATHS" if timing_ok else "FAIL",
          "required_setup_margin_ns_exclusive": 0.400,
          "setup_including_delay_exceptions_min_ns": setup_all_checks_min,
          "user_setup_margin_pass": setup_margin_ok,
          "worst_slack_ns": worst, "violated_endpoints": violated,
          "constraint_count": len(constraint_rows), "inactive_constraints": inactive,
          "missing_executed_constraints": missing_commands,
          "bundle_constraints": bundles, "additional_data_min_constraints": extra_data_min,
          "serializer_recovery_max_constraints": [e for e in serializer_exceptions if e["command"].startswith("set_max_delay")],
          "serializer_data_min_constraints": [e for e in serializer_exceptions if e["command"].startswith("set_min_delay")],
          "empty_exception_analysis_sections": empty_exception_sections,
          "uncovered_delay_commands": sorted(expected_delays - covered_delays),
          "bundle_report_check": exception_ok,
          "configuration_matches_gui": configuration_match,
          "generated_external_config_clock": external_clock,
          "tool_target_identity_matches": identity_ok,
          "actual_clock_periods_ns": clock_periods, "actual_clock_targets_match": clocks_ok,
          "serializer_reset_paths_individually_in_global_worst25": serializer_reset_paths,
          "serializer_natural_records": serializer_natural_records,
          "serializer_four_lane_recovery_removal_coverage": serializer_coverage_ok,
          "serializer_natural_4ns_recovery_pass": serializer_natural_recovery_ok,
          "serializer_four_lane_pixel_pclk_recovery_removal_pass": serializer_pixel_checks_ok,
          "dvi_release_clock_expected_from_executed_rtl": expected_release_clock,
          "serializer_nearest_4ns_clock_edge": nearest_serial_clock,
          "dvi_release_half_cycle_data_records": half_cycle_records,
          "dvi_release_half_cycle_setup_hold_pass": half_cycle_ok,
          "dvi_release_half_cycle_direct_expansion_complete": half_cycle_expanded_ok,
          "dvi_release_half_cycle_hold_native_accepted": half_hold_native_accepted,
          "dvi_release_half_cycle_hold_exact_slack_ns": min((r["slack_ns"] for r in half_cycle_records["hold"]), default=None),
          "dvi_release_half_cycle_hold_basis": "native global zero violations, nonempty same clock/net hold report and no endpoint false path; exact unexpanded slack is UNKNOWN",
          "half_cycle_false_path_matches": half_false_paths,
          "unparsed_false_path_commands": unparsed_false_paths,
          "actual_hold_report_scopes": hold_report_scopes,
          "unfiltered_natural_reset_reports": natural_global_reports,
          "unfiltered_natural_reset_reports_present": natural_global_ok,
          "serializer_report_scope": "global and diagnostic tables; every lane must have natural recovery/removal from its executed-RTL edge and positive original4ns nearest-edge recovery",
          "dvi_release_requested_site": requested_site.group(1).strip() if requested_site else None,
          "dvi_release_sites_in_actual_report": sorted(release_sites),
          "dvi_release_placement_matches": placement_ok,
          "actual_full_synthesis_identity_luts": identity_luts,
          "actual_full_synthesis_identity_luts_match_r09": identity_luts_ok,
          "actual_wave04_hold_identity_luts": hold_identity_luts,
          "expected_wave04_hold_identity_luts": hold_buffers_expected if hold_buffers_required else None,
          "actual_wave04_hold_identity_luts_match": hold_buffers_ok,
          "explicit_identity_count_basis": "Actual LUT1 declaration names ending .u_identity; exclude inferred syn_keep wire alias LUTs and matching port-net names",
          "additional_read_tick_alias_lut_count": sum(
              ("g_read_word_hold[" in n and not n.endswith(".u_identity"))
              or n.startswith("read_word_hold_ticks_") for n in lut1_instance_names),
          "post_frame_id_identity_names": post_id_names,
          "post_frame_id_four_identity_cells_pass": post_id_identity_ok,
          "r05_snapshot_identity_count": len(snapshot_names),
          "r05_trace_identity_count": len(trace_names),
          "r05_new_hold_INIT2_pass": new_hold_init_ok,
          "r05_new_hold_exact_counts_pass": new_hold_exact_count_ok,
          "r06_previous_state_identity_count": len(previous_state_names),
          "r06_previous_state_identity_pass": previous_state_ok,
          "review_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "report_and_artifact_sha256": {str(p.relative_to(run)).replace("\\", "/"):
              hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
          "scope": "actual report tables/worst paths/declared exceptions; not hardware or complete CDC/C9 sign-off",
          "board_release_allowed": False, "device_operations": False}
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result, indent=2))
raise SystemExit(not passed)
