"""Check actual B run report, immutable run identity and exact directed pairs.

Uses the previously signed raw HTML parser read-only. This new successor checks
vendor literal bracket selectors; it does not alter the old checker or sign M2
approval. A positive result is limited candidate evidence, never board release.
"""
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
STAGE = REPO / "code/output/m3_m2td_endpoint_probe_20261015_r01"
PARSER = HERE.parent / "endpoint_audit.py"
PARSER_SHA = "5e50e8c74f82f01b0640005788ea9e09c8d3c8f5cd82839a88f5bac65de7318e"


def ident(blob):
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def load_parser():
    if ident(PARSER.read_bytes())["sha256"] != PARSER_SHA:
        raise ValueError("READONLY_PARSER_IDENTITY")
    spec = importlib.util.spec_from_file_location("b_signed_raw_parser", PARSER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_paths(parsed, targets, parser):
    if parsed["metadata"]["Tool Version"] != "V1.9.11.03 Education" or parsed["metadata"]["Part Number"] != "GW5AST-LV138PG484AC1/I0":
        raise ValueError("REPORT_TOOL_OR_DEVICE")
    clock = parsed["clocks"].get("sys_clk")
    if not clock or Decimal(clock["period_ns"]) != 25 or Decimal(clock["frequency_mhz"]) != 40:
        raise ValueError("CLOCK_40MHZ")
    if clock["objects"].strip() != "u_visual/u_video_pll/PLLA_inst/CLKOUT2":
        raise ValueError("CLOCK_OBJECT")
    observations = []
    for target in targets:
        rows = [p for p in parsed["paths"] if p["From Node"] == target["from_node"] and p["To Node"] == target["to_node"]]
        if not rows:
            raise ValueError("ENDPOINT_ABSENT:" + target["id"])
        for analysis in ("setup", "hold"):
            expected = "Report Command:report_timing -" + analysis + " -from [get_regs {" + target["from_node"].rsplit("/", 1)[0] + "}] -to [get_pins {" + target["to_node"] + "}] -max_paths 1 -max_common_paths 1"
            selected = [r for r in rows if r["analysis"] == analysis and r["command"] == expected]
            if not selected:
                raise ValueError("DIRECTED_" + analysis.upper() + "_ABSENT:" + target["id"])
            for row in selected:
                if row["From Clock"] != "sys_clk:[R]" or row["To Clock"] != "sys_clk:[R]":
                    raise ValueError("PAIR_CLOCK:" + target["id"])
                if parser.INACTIVE.search(" ".join(row[c] for c in parser.PATH_COLUMNS)):
                    raise ValueError("INACTIVE_PAIR:" + target["id"])
                slack = parser.decimal(row["Path Slack"], "slack")
                delay = parser.decimal(row["Data Delay"], "delay")
                relation = parser.decimal(row["Relation"], "relation")
                if slack < 0 or delay < 0 or relation != (25 if analysis == "setup" else 0) or not re.fullmatch("[1-9][0-9]*", row["Path Number"]):
                    raise ValueError("PAIR_TIMING_VALUE:" + target["id"])
                observations.append({"target_id": target["id"], "analysis": analysis, "slack_ns": str(slack),
                                     "from_node": row["From Node"], "to_node": row["To Node"],
                                     "clock": "sys_clk", "command": row["command"],
                                     "activity": "ACTIVE_EXACT_RAW_TIMING_ROW", "row_span": row["row_span"], "table_span": row["table_span"]})
    return observations


def main():
    parser = load_parser()
    result = {"scope": "M3_AUTHORIZED_ISOLATED_B_CANDIDATE_ONLY", "board_release_allowed": False,
              "m2_final_signoff": False, "parser_sha256": PARSER_SHA}
    try:
        receipt_bytes = (STAGE / "RUN_RECEIPT.json").read_bytes()
        receipt = json.loads(receipt_bytes)
        if receipt["status"] != "TOOL_EXIT0_AWAIT_INDEPENDENT_ENDPOINT_CHECK" or receipt["tool_calls"] != 1 or not receipt["input_unchanged"] or not receipt["tool_identities_unchanged"]:
            raise ValueError("ACTUAL_RUN_NOT_ACCEPTABLE")
        report_path = STAGE / "impl/pnr/m2_fourvoice_timbre_delay_board_top_tr_content.html"
        report = report_path.read_bytes()
        if ident(report) != receipt["reports"][report_path.relative_to(STAGE).as_posix()]:
            raise ValueError("ACTUAL_REPORT_IDENTITY")
        target_path = STAGE / "TARGETS.json"
        target_blob = target_path.read_bytes()
        if ident(target_blob) != receipt["input_before"][str(target_path)]:
            raise ValueError("ACTUAL_TARGET_IDENTITY")
        targets = json.loads(target_blob)["targets"]
        parsed = parser.parse_report(report)
        for key, expected in (("Design File", STAGE / "impl/gwsynthesis/m2_fourvoice_timbre_delay_board_top.vg"),
                              ("Physical Constraints File", STAGE / "inputs/constraints/audio_visual.cst"),
                              ("Timing Constraint File", STAGE / "inputs/constraints/audio_visual_hold055.sdc")):
            normalized = re.sub("/+", "/", parsed["metadata"][key].replace("\\", "/"))
            if normalized != expected.as_posix():
                raise ValueError("REPORT_STAGE_IDENTITY:" + key)
        observations = check_paths(parsed, targets, parser)
        result.update(status="EXACT_DIRECTED_PAIRS_SHOWN_CANDIDATE_ONLY", actual_run_receipt=ident(receipt_bytes),
                      actual_report=ident(report), observations=observations, metadata=parsed["metadata"],
                      tool_process_created=True, historical_report_reused=False,
                      limitations=["Not whole audio pipeline coverage", "Not M2 final physical signoff", "No FPGA/hardware/audio acceptance"])
        code = 0
    except Exception as error:
        result.update(status="REJECTED", diagnostic=type(error).__name__ + ": " + str(error))
        code = 1
    output = STAGE / "ENDPOINT_CHECK_R01.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k in ("status", "diagnostic", "board_release_allowed")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
