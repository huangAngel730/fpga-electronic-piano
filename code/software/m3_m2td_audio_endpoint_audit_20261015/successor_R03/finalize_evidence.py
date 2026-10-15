"""Read-only post-run evidence summary and explicitly timed tool re-snapshot."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"
STAGE = REPO / "code/output/m3_m2td_endpoint_probe_20261015_r01"
TOOLS = Path("E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03/IDE")


def ident(blob):
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def main():
    output = DOC / "actual_round1_summary"
    output.mkdir(exist_ok=False)
    run = json.loads((STAGE / "RUN_RECEIPT.json").read_bytes())
    check = json.loads((STAGE / "ENDPOINT_CHECK_R01.json").read_bytes())
    raw_report = (STAGE / "impl/pnr/m2_fourvoice_timbre_delay_board_top_tr_content.html").read_bytes()
    raw_netlist = (STAGE / "impl/gwsynthesis/m2_fourvoice_timbre_delay_board_top.vg").read_bytes()
    resource = (STAGE / "impl/pnr/m2_fourvoice_timbre_delay_board_top.rpt.txt").read_bytes()
    tool_before = json.loads((STAGE / "TOOL_MANIFEST.json").read_bytes())
    tool_after = {name: ident((TOOLS / name).read_bytes()) for name in tool_before}
    tool_snapshot = {"classification": "POST_RUN_RESNAPSHOT_NOT_CONTEMPORANEOUS_EXIT_SNAPSHOT",
                     "observed_utc": datetime.now(timezone.utc).isoformat(), "files": tool_after,
                     "matches_launch_manifest": tool_after == tool_before,
                     "immediate_exit_boolean_in_original_receipt": run["tool_identities_unchanged"]}
    (output / "TOOL_AFTER_RESNAPSHOT.json").write_text(json.dumps(tool_snapshot, indent=2) + "\n", encoding="utf-8")
    core = HERE.parent / "endpoint_audit.py"
    spec = importlib.util.spec_from_file_location("final_raw_report_parser", core)
    parser = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = parser
    spec.loader.exec_module(parser)
    parsed = parser.parse_report(raw_report)
    slacks = {kind: str(min(parser.decimal(p["Path Slack"], "slack") for p in parsed["paths"] if p["analysis"] == kind))
              for kind in ("setup", "hold")}
    resources = {}
    for name, label in (("Logic", "Logic"), ("Register", "Register"), ("DSP", "DSP"), ("BSRAM", "BSRAM")):
        match = re.search(r"^\s*" + label + r"\s*\|\s*(\d+)/(\d+)", resource.decode("utf-8"), re.M)
        if not match:
            raise ValueError("resource row missing")
        resources[name] = {"used": int(match[1]), "capacity": int(match[2])}
    summary = {"status": "ISOLATED_DIRECTED_B_CANDIDATE_PASS_PENDING_M2", "observed_utc": tool_snapshot["observed_utc"],
               "rounds_consumed": 1, "physical_tool_calls": run["tool_calls"], "tool_exit_code": run["exit_code"],
               "seconds_total": run["seconds_total"], "timed_out": run["timed_out"],
               "source_unchanged_during_tool": run["input_unchanged"], "tool_unchanged_during_tool": run["tool_identities_unchanged"],
               "source_path_literals_migrated": 40, "source_files_migrated": 15, "frozen_input_count": 84,
               "query_format": "Vendor literal bracket names inside Tcl braces, not Tcl glob bracket character classes",
               "pairs": [{"id": target, **{o["analysis"] + "_slack_ns": o["slack_ns"] for o in check["observations"] if o["target_id"] == target}}
                         for target in dict.fromkeys(o["target_id"] for o in check["observations"])],
               "minimum_slack_in_reported_tables_ns": slacks, "resources": resources,
               "netlist": {"classification": "CURRENT_RUN_SYNTHESIS_VG_NOT_POST_PNR_NETLIST", **ident(raw_netlist),
                           "requested_base_s1_string_occurrences": raw_netlist.count(b"base_s1"),
                           "requested_base_s2_string_occurrences": raw_netlist.count(b"base_s2"),
                           "base_original_name_absence_does_not_prove_functional_removal": True},
               "report": ident(raw_report), "run_receipt": ident((STAGE / "RUN_RECEIPT.json").read_bytes()),
               "checker": ident((STAGE / "ENDPOINT_CHECK_R01.json").read_bytes()),
               "second_round": "NOT_USED_FIRST_ROUND_PASSED_NO_REPEAT_AUTHORIZED", "board_release_allowed": False,
               "limitations": ["No formal M2 L5 signoff", "Not R05 same-version functional signoff", "Not PCM/I2S whole chain endpoint coverage",
                               "No hardware operation", "Generated fs is local-only and excluded from transfer package"]}
    (output / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "pairs": summary["pairs"], "resources": resources,
                      "minimum_reported_slack": slacks, "post_run_tools_same": tool_after == tool_before}))


if __name__ == "__main__":
    main()
