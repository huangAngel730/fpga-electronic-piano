#!/usr/bin/env python3
"""Snapshot verified standalone HDMI build evidence after successful gates."""
import hashlib
import json
from pathlib import Path
import re
import sys

from check_hdmi_link_report import analyze, analyze_pins


def one(text: str, pattern: str, label: str) -> str:
    hits = re.findall(pattern, text, re.MULTILINE)
    if len(hits) != 1:
        raise ValueError(f"Expected exactly one {label}, got {len(hits)}")
    return hits[0]


def capture(repo: Path) -> dict:
    out = repo / "code/output/hdmi_link_probe"
    report = out / "impl/pnr/hdmi_link_probe_tr_content.html"
    usage = out / "impl/pnr/hdmi_link_probe.rpt.txt"
    timing = analyze(report.read_text(encoding="utf-8"))
    pins, errors = analyze_pins(usage.read_text(encoding="utf-8"))
    if timing["errors"] or errors:
        raise ValueError(f"Gowin gates failed: {timing['errors']} {errors}")
    text = usage.read_text(encoding="utf-8")
    resources = {
        "Logic": int(one(text, r"^  Logic\s+\|\s+(\d+)/", "Logic")),
        "Register": int(one(text, r"^  Register\s+\|\s+(\d+)/", "Register")),
        "PLLA": int(one(text, r"^  PLLA\s+\|\s+(\d+)/", "PLLA")),
        "OSER10": int(one(text, r"^    --OSER10\s+\|\s+(\d+)", "OSER10")),
    }
    lut_alu = one(text, r"^    --LUT,ALU,ROM16\s+\|\s+\d+\((\d+ LUT, \d+ ALU, 0 ROM16)\)", "LUT/ALU")
    resources["LUT"] = int(one(lut_alu, r"(\d+) LUT", "LUT count"))
    resources["ALU"] = int(one(lut_alu, r"(\d+) ALU", "ALU count"))
    sources = [
        "code/rtl/board/hdmi_link_probe.sv",
        "code/constraints/hdmi_link_probe.cst",
        "code/constraints/hdmi_link_probe.sdc",
        "code/scripts/build_hdmi_link_probe.ps1",
        "code/output/hdmi_link_probe/vendor/TMDS_PLL_800_600_60.v",
        "code/output/hdmi_link_probe/vendor/DVI_TX_Top.v",
        "code/output/hdmi_link_probe/impl/pnr/hdmi_link_probe.fs",
        "code/output/hdmi_link_probe/impl/pnr/hdmi_link_probe_tr_content.html",
        "code/output/hdmi_link_probe/impl/pnr/hdmi_link_probe.rpt.txt",
    ]
    hashes = {s: hashlib.sha256((repo / s).read_bytes()).hexdigest() for s in sources}
    log = (out / "build.log").read_text(encoding="utf-8", errors="replace")
    return {
        "level": "L5 standalone PnR only; no board or monitor test",
        "source_commit": "f0347d830305ef3efb921f47bb51701e569beefd",
        "mode": "640x480, 25MHz pixel, 125MHz serial, 59.5238095Hz",
        "tool": one(text, r"^  <Tool Version>: (.+)$", "tool version"),
        "part": one(text, r"^  <Part Number>: (.+)$", "device part"),
        "summary": timing["summary"], "clocks": timing["clocks"],
        "worst": timing["worst"], "pins": pins,
        "resources": resources,
        "warnings": ["PR1014: clock input generic route; board PLL lock and physical video pending"]
        if "PR1014" in log else [],
        "sha256": hashes,
    }


def main() -> int:
    if len(sys.argv) not in (2, 4):
        raise SystemExit("Usage: snapshot_hdmi_link_evidence.py REPO_ROOT [OUTPUT_FILE GUI_IP_DIR]")
    repo = Path(sys.argv[1])
    result = capture(repo)
    if len(sys.argv) == 4:
        gui_dir = Path(sys.argv[3])
        artifacts = (
            "DVI_TX_Top.ipc", "DVI_TX_Top.v", "DVI_TX_Top.vo",
            "temp/DviTx/DVI_TX_Top.log", "temp/DviTx/dvi_tx_defines.v",
        )
        result["gui_ip_sha256"] = {
            rel: hashlib.sha256((gui_dir / rel).read_bytes()).hexdigest()
            for rel in artifacts
        }
        if result["gui_ip_sha256"]["DVI_TX_Top.v"] != result["sha256"]["code/output/hdmi_link_probe/vendor/DVI_TX_Top.v"]:
            raise ValueError("Compiled DVI TX differs from reviewed GUI IP")
        result["gui_ip_device"] = "GW5AT-LV60PG484AC1/I0"
    dest = Path(sys.argv[2]) if len(sys.argv) == 4 else repo / "code/docs/evidence/hdmi_link_probe_20260927.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"PASS captured current HDMI evidence, {len(result['sha256'])} hashes: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
