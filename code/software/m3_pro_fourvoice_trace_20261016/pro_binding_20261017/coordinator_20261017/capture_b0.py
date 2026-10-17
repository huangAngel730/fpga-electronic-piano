"""Capture B0's existing source identities and unresolved physical evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

SOFT = Path(__file__).resolve().parent
ROOT = SOFT.parents[4]
DOC = ROOT / "code/docs/hardware/pro_fourvoice_board_intake_20261017"
BASE = ROOT / "code/rtl/138K_Pro"
REPORT = BASE / "Pro_引脚核对_CST_R02_20261016/pin_relationships.json"
CST = BASE / "tang_mega_138k-pro_pins.cst"


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main():
    out = DOC / "AUDIT_R01"
    out.mkdir(exist_ok=False)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    names = ["TANG_MEGA-138K-Pro_4072_Schematics.pdf",
             "TANG_MEGA-138K_Dock-4071f3__Schematics.pdf",
             "tang_mega_138k-pro_pins.cst"]
    sources = []
    for name in names:
        observed = identity(BASE / name)
        declared = next(row for row in report["sources"] if row["name"] == name)
        sources.append({"observed": observed, "prior_declared": declared,
                        "exact_identity_match": observed["bytes"] == declared["bytes"]
                        and observed["sha256"] == declared["sha256"]})
    reference_lines = CST.read_text(encoding="utf-8").splitlines()
    selected_balls = {"P16", "U4", "K16", "F15", "G15", "R17", "P15", "N16",
                      "H17", "E22", "F24", "G24"}
    constraints = []
    for line_number, line in enumerate(reference_lines, 1):
        match = re.match(r'\s*IO_LOC\s+"([^"]+)"\s+(\w+)\s*;', line)
        if match and match[2] in selected_balls:
            alias = match[1]
            electrical = [{"line": i, "text": text} for i, text in enumerate(reference_lines, 1)
                          if re.match(r'\s*IO_PORT\s+"' + re.escape(alias) + r'"\s+', text)]
            constraints.append({"alias": alias, "ball": match[2], "line": line_number,
                                "text": line, "electrical": electrical})
    observed_balls = {row["ball"] for row in constraints}
    fields = ["group", "net", "ball", "bank", "voltage", "endpoint", "source",
              "note", "cst_alias", "cst_lines", "cst_coverage"]
    rows = [{key: row.get(key) for key in fields} for row in report["rows"]
            if row["ball"] in selected_balls]
    inputs = [REPORT, CST, ROOT/"code/constraints/electronic_piano.cst", Path(__file__), DOC/"README.md"]
    value = {"utc": datetime.now(timezone.utc).isoformat(), "actual_level": "L0_IDENTITY_ONLY",
             "B0_status": "PARTIAL_PENDING_PHYSICAL_INPUT", "sources": sources,
             "inputs": [identity(path) for path in inputs], "reference_cst_observations": constraints,
             "reference_cst_missing_balls": sorted(selected_balls-observed_balls),
             "prior_report_selected_rows_readonly": rows,
             "interpretation": "Reuse prior static candidate annotations; not a new schematic or electrical signoff",
             "physical_observations": {key: None for key in (
                 "actual_core_revision", "actual_dock_revision", "full_fpga_part_step",
                 "measured_vccio", "midi_fpga_voltage_ground", "actual_reset_pll_pa",
                 "actual_audio_serial", "Pro_fs_identity", "single_SRAM_permission")},
             "ModelSim_Gowin_device_calls": 0, "board_release_allowed": False}
    with (out/"B0_INPUT_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    stable = all(row["exact_identity_match"] for row in sources)
    print(json.dumps({"source_identities_match_prior": stable,
                      "reference_cst_missing_balls": value["reference_cst_missing_balls"],
                      "B0_status": value["B0_status"], "actual_level": value["actual_level"]}))
    return 0 if stable else 1


if __name__ == "__main__":
    raise SystemExit(main())
