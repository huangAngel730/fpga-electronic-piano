"""Audit actual GUI PnR reports and export a non-accepted research bitstream."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "build/candidate_20261002_141443_r2"
ATTEMPT = ROOT / "build/pnr_attempt_2"
PNR = ATTEMPT / "impl/pnr"
DEST = ROOT / "output/bitstream_v3_research_20261002"
REPO = Path("E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(content):
    return [[html.unescape(re.sub(r"<[^>]*>", "", cell)).strip()
             for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)(?=</t[dh]>|<t[dh]\b|$)", row, re.S)]
            for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", content, re.S)]


def main():
    if DEST.exists():
        raise SystemExit("Refusing to overwrite existing delivery")
    gate = load(ROOT / "design/DESIGN_READY.json")
    frozen = load(SNAP / "frozen_input_manifest.json")
    preparation = load(ATTEMPT / "preparation_manifest.json")
    assert sha(ROOT / "design/DESIGN_READY.json") == frozen["gate_sha256"]
    for name, item in gate["source_files"].items():
        assert sha(ROOT / name) == item["sha256"], name
    for name, expected in preparation["frozen_design_files"].items():
        assert sha(ROOT / name) == expected, name
    for item in frozen["staged_files"]:
        assert sha(SNAP / item["path"]) == item["sha256"], item["path"]
    baseline = load(ROOT / "verification/baseline_reference_manifest.json")
    for name, item in baseline["files"].items():
        assert sha(Path(name)) == item["sha256"], name
        assert sha(Path(item["destination"])) == item["sha256"], item["destination"]
    for name, expected in preparation["unchanged_constraints"].items():
        assert sha(ATTEMPT / "constraints" / name) == expected, name
    old = load(ROOT / "verification/old_versions_final_audit.json")
    assert old["old_files_unchanged"] and not old["differences"]
    head = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(REPO), "status", "--short"], text=True).strip()
    assert head == "427f3d33d6559e83b31e7e5347993db7dc4fa124" and not status
    subprocess.run(["git", "-C", str(REPO), "diff", "--check"], check=True)

    timing_text = (PNR / "electronic_piano_v3_tr_content.html").read_text(encoding="utf-8")
    all_rows = rows(timing_text)

    def summary(label):
        matching = [row[1] for row in all_rows if len(row) == 2 and row[0] == label]
        assert len(matching) == 1, label
        return matching[0]

    timing = {
        "analyzed_paths": int(summary("Numbers of Paths Analyzed")),
        "analyzed_endpoints": int(summary("Numbers of Endpoints Analyzed")),
        "setup_violated_endpoints": int(summary("Numbers of Setup Violated Endpoints")),
        "hold_violated_endpoints": int(summary("Numbers of Hold Violated Endpoints")),
        "setup_corner": summary("Setup Delay Model"),
        "hold_corner": summary("Hold Delay Model"),
        "unconstrained_path_count": "NOT_REPORTED_IN_GENERATED_REPORT",
    }
    assert timing["setup_violated_endpoints"] == timing["hold_violated_endpoints"] == 0
    assert timing["analyzed_paths"] > 0
    clock = [row for row in all_rows if len(row) == 10 and row[1:3] == ["sys_clk", "Base"]]
    assert len(clock) == 1 and clock[0][3:5] == ["20.000", "50.000"]
    fmax = [row for row in all_rows if len(row) == 6 and row[1] == "sys_clk" and "(MHz)" in row[2]]
    assert len(fmax) == 1
    timing.update(clock_hz=50_000_000, period_ns=20.0,
                  actual_fmax_mhz=float(fmax[0][3].split("(")[0]))
    for mode in ("Setup", "Hold", "Recovery", "Removal"):
        block = timing_text.split(f'name="{mode}_Slack_Table"', 1)[1].split("</table>", 1)[0]
        paths = [row for row in rows(block) if len(row) == 9 and row[0].isdigit()]
        assert paths and all(float(row[1]) >= 0 for row in paths), mode
        timing[mode.lower() + "_min_reported_slack_ns"] = min(float(row[1]) for row in paths)
        timing[mode.lower() + "_reported_paths"] = len(paths)
        timing[mode.lower() + "_worst_path"] = paths[0]
    # The generated table has no stable anchor across IDE releases; use its heading.
    pulse_block = timing_text.split("Minimum Pulse Width Table:", 1)[1].split("</table>", 1)[0]
    pulse_paths = [row for row in rows(pulse_block) if len(row) == 7 and row[0].isdigit()]
    assert pulse_paths and all(float(row[1]) >= 0 for row in pulse_paths)
    timing["min_pulse_width_slack_ns"] = min(float(row[1]) for row in pulse_paths)

    log = (PNR / "electronic_piano_v3.log").read_text(encoding="utf-8")
    assert "Placement and routing completed" in log and "Bitstream generation completed" in log
    assert "ERROR" not in log
    warnings = [line for line in log.splitlines() if "WARN" in line]
    config = load(ATTEMPT / "impl/electronic_piano_v3_process_config.json")
    assert config["TopModule"] == "electronic_piano_top"
    assert config["Verilog_Standard"] == "Vlg_Std_Sysv2017"
    synth_log = (ATTEMPT / "impl/gwsynthesis/electronic_piano_v3.log").read_text(encoding="utf-8")
    assert "GowinSynthesis finish" in synth_log and "ERROR" not in synth_log
    report = (PNR / "electronic_piano_v3.rpt.txt").read_text(encoding="utf-8")
    assert "V1.9.11.03 Education" in report and "GW5AT-LV60PG484AC1/I0" in report
    expected_pins = {"sys_clk": ("V22/7", "LVCMOS33"),
                     "sys_rst_n": ("AA13/9", "LVCMOS15"),
                     "key_n[0]": ("AB13/9", "LVCMOS15"),
                     "key_n[1]": ("Y12/9", "LVCMOS15"),
                     "midi_rx": ("R17/6", "LVCMOS33"),
                     "i2s_bclk": ("Y17/7", "LVCMOS33"),
                     "i2s_lrck": ("AB17/7", "LVCMOS33"),
                     "i2s_din": ("AA16/7", "LVCMOS33"),
                     "pa_en": ("AB16/7", "LVCMOS33"),
                     "uart_tx": ("U15/6", "LVCMOS33")}
    for port, (pin, standard) in expected_pins.items():
        match = re.search(r"^" + re.escape(port) + r"\s*\|.*$", report, re.M)
        assert match and pin in match[0] and standard in match[0], port

    def resource(name):
        match = re.search(r"^\s*" + re.escape(name) + r"\s*\|\s*(\d+)/(\d+)", report, re.M)
        assert match, name
        return {"used": int(match[1]), "available": int(match[2])}

    fs = PNR / "electronic_piano_v3.fs"
    assert fs.stat().st_size > 1_000_000
    DEST.mkdir()
    target = DEST / "electronic_piano_v3_RESEARCH_NOT_ACCEPTED_427f3d3_20261002.fs"
    shutil.copy2(fs, target)
    assert sha(fs) == sha(target)
    evidence = [ATTEMPT / "run_pnr.tcl", ATTEMPT / "preparation_manifest.json",
                ATTEMPT / "electronic_piano_v3.gprj",
                ATTEMPT / "impl/electronic_piano_v3_process_config.json",
                ATTEMPT / "impl/gwsynthesis/electronic_piano_v3.prj",
                ATTEMPT / "impl/gwsynthesis/electronic_piano_v3.log",
                ATTEMPT / "impl/gwsynthesis/electronic_piano_v3.vg",
                ROOT / "design/DESIGN_READY.json", SNAP / "frozen_input_manifest.json",
                ROOT / "verification/old_versions_final_audit.json"]
    evidence += [p for p in PNR.iterdir() if p.suffix in {".html", ".txt", ".log", ".do", ".cfg"}]
    evidence += list((ATTEMPT / "constraints").iterdir())
    manifest = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "status": "PNR_STA_PASS_RESEARCH_BITSTREAM_ONLY",
        "beat_perception": "NOT_ACCEPTED", "board_programming": "NOT_RUN",
        "board_measurement": "NOT_RUN", "hdmi": "NOT_PRESENT_IN_BASELINE_NOT_ADDED",
        "bitstream": {"origin": str(fs), "path": str(target), "bytes": target.stat().st_size,
                      "sha256": sha(target)},
        "tool": "Gowin V1.9.11.03 Education installed IDE Tcl console",
        "device": "GW5AT-60B-PBGA484A-1", "part": "GW5AT-LV60PG484AC1/I0",
        "top": "electronic_piano_top", "formal_base_git_head": head,
        "git_status": status, "source_snapshot": str(SNAP),
        "gate_sha256": frozen["gate_sha256"],
        "source22_staged72_formal46_design_constraints_sha": "PASS",
        "old_files_verified": sum(len(files) for files in old["roots"].values()),
        "old_file_differences": 0,
        "implementation": "IDE run pnr automatically reran synthesis in corrected Sysv2017 configuration; original r2 netlist is preserved but NOT used as final PnR input",
        "copied_original_synthesis_metadata": "impl/gwsynthesis/result.json, command.json and actual_synthesis.log are preparation copies of r2 provenance, NOT current GUI run results; current .prj/.log/.vg and PnR reports are authoritative",
        "timing": timing, "warnings": warnings,
        "resources": {name: resource(name) for name in ("Logic", "Register", "BSRAM", "DSP")},
        "io_constraints": "Original CST/SDC bytes unchanged; all 10 ports have explicit matching pin assignments in actual report",
        "limits": ["Very small setup/hold slack; PR1014 generic clock routing retained",
                   "Generated report does not enumerate unconstrained paths; asynchronous MIDI/buttons/reset have no input delay, pa_en/uart_tx have no output delay in original SDC",
                   "I2S output-delay 5/0 ns is original empirical placeholder, not physical PT8211 timing acceptance",
                   "No post-PnR simulation or bitstream ROM INIT decode; ROM provenance/hash and synthesis extraction verified",
                   "No full simulation rerun in this build phase; frozen snapshot previous actual PASS evidence reused",
                   "Low-note objective remains NOT_ACCEPTED; no algorithm/source/design changes"],
        "evidence": {str(path): {"sha256": sha(path), "bytes": path.stat().st_size} for path in evidence},
    }
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("PASS source22/staged72/formal46/design/constraints/old190/git; actual PnR+STA")
    print(json.dumps(timing, ensure_ascii=False))
    print("FS", target, "SHA256", sha(target))


if __name__ == "__main__":
    main()
