"""I: exact delay RTL, once per depth Gowin synthesis, never PnR/bitstream.

Native GowinSynthesis CLI is used when gw_sh is absent. No tool installation.
Failure/resources exceed: preserve the actual report; no shallower reruns.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from run_m3_delay_transaction_candidate import CONTRACT, ROOT, load_module, output_dir, sha

sys.dont_write_bytecode = True
BENCH = ROOT / "code/tb/board/m3_delay_memory_probe"
PART = "GW5AT-LV60PG484AC1/I0"
DEVICE = "GW5AT-60B"
VARIANT = "gw5at60b-002"
DEPTHS = (1024, 4096, 16384)
PROBE_SHA256 = "ece4917989b0b299423432142ca5dff53e5146089ea531a92d806078da837606"


def source_identity():
    """I only: freeze the accepted DUT/probe, not unrelated evolving G/H inputs."""
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    relative = "code/rtl/audio/delay_effect.sv"
    identity = {relative: contract["readonly_source_sha256"][relative],
                "code/tb/board/m3_delay_memory_probe/m3_delay_memory_probe.sv": PROBE_SHA256}
    for relative, expected in identity.items():
        if sha(ROOT / relative) != expected:
            raise ValueError("I frozen source SHA changed: " + relative)
    return identity


def validate_correction_tool(tool):
    if tool is None or tool.name.lower() != "gowinsynthesis.exe":
        raise ValueError("clock correction requires explicit existing native GowinSynthesis.exe")


def stop_after_case(case):
    """Never spend the next depth's one-shot allowance after a failed case."""
    return case["synthesis_executed"] and case["status"] != "synthesis_completed"


def tool_path(explicit):
    if explicit:
        return explicit.resolve() if explicit.is_file() else None
    roots = [os.environ.get("GOWIN_HOME", ""),
             "D:/program/gaoyunFPGA/Gowin/Gowin_V1.9.11.03_Education_x64",
             "D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64"]
    for root in roots:
        if root:
            for name in ("gw_sh.exe", "GowinSynthesis.exe"):
                candidate = Path(root) / "IDE/bin" / name
                if candidate.is_file():
                    return candidate.resolve()
    for name in ("gw_sh.exe", "GowinSynthesis.exe"):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    return None


def review_report(path):
    # Reuse the existing Gowin HTML cell reader, NOT its PnR/STA verdict.
    parser = load_module("existing_gowin_rows", ROOT / "code/scripts/check_t009_fusion_report.py").Rows()
    text = path.read_text(encoding="utf-8", errors="strict")
    parser.feed(text)
    values = {key: "unknown" for key in ("Logic", "Register", "BSRAM", "RAM16", "DSP")}
    for key in ("Logic", "Register", "BSRAM", "DSP"):
        hits = [r[1] for section, r in parser.rows if section == "utilization" and len(r) >= 2 and r[0] == key]
        if len(hits) == 1:
            match = re.fullmatch(r"(\d+)(?:\([^)]*\))?\s*/\s*(\d+)", hits[0])
            if not match:
                raise ValueError("malformed utilization " + key)
            values[key] = dict(used=int(match[1]), capacity=int(match[2]))
        elif len(hits) > 1:
            raise ValueError("ambiguous resource field " + key)
    usage = {r[0].replace("&nbsp", "").strip(): r[1] for section, r in parser.rows if section == "usage" and len(r) == 2}
    primitives = {key: int(value) for key, value in usage.items() if value.isdigit() and re.fullmatch(
        r"(?:DFF\w*|LUT\d+|ALU|SDPB?|DPB|SPB?|RAM16\w+|MULT\w+|PADD\w+)", key)}
    ram16 = [value for key, value in primitives.items() if key.startswith("RAM16")]
    if ram16:
        values["RAM16"] = dict(used=sum(ram16), capacity="unknown", basis="explicit RAM16 primitive rows")
    # The DSP summary's empty cell is UNKNOWN, not zero or inferred block
    # allocation. Actual multiplier primitive units are explicitly listed.
    if usage.get("DSP", "").isdigit():
        values["DSP"] = dict(used=int(usage["DSP"]), capacity="unknown")
    about = {r[0]: r[1] for section, r in parser.rows if section == "about" and len(r) == 2}
    clocks = [r for section, r in parser.rows if section == "clock" and len(r) >= 5 and r[1] == "sys_clk"]
    errors = []
    if about.get("Part Number") != PART or about.get("Device Version") != "B":
        errors.append("target part/B silicon identity missing or changed")
    if len(clocks) != 1 or clocks[0][3:5] != ["20.000", "50.000"]:
        errors.append("actual synthesis clock is not contractual 20ns/50MHz")
    for key in ("Logic", "Register", "BSRAM"):
        if values[key] == "unknown":
            errors.append("missing resource " + key)
        elif values[key]["used"] > values[key]["capacity"]:
            errors.append("resource overflow " + key)
    fmax = [r for section, r in parser.rows if section == "performance" and len(r) >= 2 and "sys_clk" in r]
    return dict(resources=values, primitive_counts=primitives,
                dsp_primitive_units=sum(value for key, value in primitives.items() if key.startswith(("MULT", "PADD"))),
                actual_part=about.get("Part Number", "unknown"), actual_revision=about.get("Device Version", "unknown"),
                actual_tool_version=about.get("Tool Version", "unknown"),
                clock_rows=clocks, estimated_frequency_rows=fmax,
                errors=errors, contract_passed=not errors)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path)
    cli.add_argument("--tool", type=Path)
    cli.add_argument("--prepare-only", action="store_true", help="no synthesis claim")
    cli.add_argument("--review-existing", type=Path, help="recheck archived one-shot synthesis, NEVER rerun tools")
    cli.add_argument("--native-clock-correction", action="store_true",
                     help="M2-authorized one additional run/depth; 1024 must pass before deeper runs")
    args = cli.parse_args()
    if args.native_clock_correction and (not args.tool or args.prepare_only or args.review_existing):
        cli.error("--native-clock-correction requires --tool, without prepare/review")
    out = output_dir(args.output, "m3_delay_memory_")
    evidence = dict(scope="I synthesis-only exact original delay, no STA/full-system/500ms claim",
                    part=PART, device=DEVICE, variant=VARIANT, clock_ns=20,
                    passed=False, synthesis_executed=False, cases=[])
    tool = None if args.review_existing else tool_path(args.tool)
    try:
        evidence["readonly_sources"] = source_identity()
        evidence["runner_sha256"] = sha(Path(__file__))
        evidence["helper_sources_sha256"] = {relative: sha(ROOT / relative) for relative in (
            "code/scripts/run_m3_delay_transaction_candidate.py",
            "code/scripts/check_t009_fusion_report.py",
            "code/tb/board/m3_delay_memory_probe/test_report.py")}
        if args.native_clock_correction:
            validate_correction_tool(tool)
            evidence["authorization"] = "M2 correction: at most one additional synthesis per fixed depth, stop on failure"
            evidence["depth_order"] = list(DEPTHS)
        if args.review_existing:
            review_existing(args.review_existing.resolve(), out, evidence)
            return 0 if evidence["passed"] else 1
        original = ROOT / "code/rtl/audio/delay_effect.sv"
        probe = BENCH / "m3_delay_memory_probe.sv"
        evidence["original_sha256"] = sha(original)
        evidence["probe_template_sha256"] = sha(probe)
        # Archive the exact executed entry, including options and stop policy.
        shutil.copyfile(Path(__file__), out / "driver_executed.py")
        if tool:
            evidence["tool"] = str(tool)
            evidence["tool_binary_sha256"] = sha(tool)
            for label, option in (("version", "-version"), ("help", "-help")):
                process = subprocess.run([str(tool), option], cwd=out, capture_output=True, timeout=30, check=False)
                (out / (label + ".log")).write_bytes(process.stdout + process.stderr)
                evidence[label + "_exit"] = process.returncode
        for depth in DEPTHS:
            folder = out / f"depth{depth}"
            folder.mkdir()
            local = folder / "delay_effect.sv"
            shutil.copyfile(original, local)
            text = probe.read_text(encoding="utf-8")
            if text.count("DEPTH = 1024") != 1:
                raise ValueError("probe depth anchor changed")
            generated = folder / "m3_delay_memory_probe.sv"
            generated.write_text(text.replace("DEPTH = 1024", f"DEPTH = {depth}", 1), encoding="utf-8", newline="\n")
            sdc = folder / "probe.sdc"
            sdc.write_text("create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]\n", encoding="ascii")
            project = ET.Element("Project")
            ET.SubElement(project, "Template").text = "FPGA"
            ET.SubElement(project, "Version").text = "5"
            ET.SubElement(project, "Device", name=DEVICE, pn=PART).text = VARIANT
            listing = ET.SubElement(project, "FileList")
            for path, kind in ((local, "file.verilog"), (generated, "file.verilog"), (sdc, "file.sdc")):
                ET.SubElement(listing, "File", path=path.as_posix(), type=kind, enable="1")
            gprj = folder / "probe.gprj"
            ET.ElementTree(project).write(gprj, encoding="utf-8", xml_declaration=True)
            tcl = folder / "run_syn.tcl"
            tcl.write_text("open_project {" + gprj.as_posix() + "}\nset_option -verilog_std sysv2017\n"
                           "set_option -top_module m3_delay_memory_probe\nrun syn\n", encoding="ascii")
            case = dict(depth=depth, status="prepared_not_run", synthesis_executed=False,
                        resources={k: "unknown" for k in ("Logic", "Register", "BSRAM", "RAM16", "DSP")},
                        primitive_counts="unknown", max_nonzero_delay_ms=(depth - 1) / 48,
                        delay0_ring_ms=depth / 48,
                        inputs_sha256={p.name: sha(p) for p in (local, generated, sdc, gprj, tcl)})
            netlist = folder / "probe.vg"
            if tool and tool.name.lower() == "gw_sh.exe":
                command = [str(tool), str(tcl)]
            else:
                # Documented native help flags. Part selects package/speed; -p
                # selects the B silicon variant instead of relying on part alias.
                command = [str(tool or "GowinSynthesis.exe"), "-p", DEVICE, "-pn", PART,
                           "-i", str(local), str(generated), "-top", "m3_delay_memory_probe",
                           "-verilog_language", "sysv-2017", "-sdc", str(sdc),
                           "-global_freq", "50",
                           "-looplimit", "16384", "-o", str(netlist)]
            case["command"] = command
            if not args.prepare_only and tool:
                case["synthesis_executed"] = evidence["synthesis_executed"] = True
                log = folder / "synthesis.log"
                try:
                    with log.open("wb") as stream:
                        process = subprocess.run(command, cwd=folder, stdout=stream, stderr=subprocess.STDOUT,
                                                 timeout=900, check=False)
                    case["exit_code"] = process.returncode
                except subprocess.TimeoutExpired:
                    case["exit_code"] = 124
                report_files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in (".log", ".rpt", ".html", ".txt", ".vg", ".xml")]
                case["reports_sha256"] = {p.relative_to(folder).as_posix(): sha(p) for p in report_files}
                raw = log.read_text(encoding="utf-8", errors="replace")
                # Nonzero/error/timeout can NEVER become resource PASS.
                case["status"] = "synthesis_failed"
                if case["exit_code"] == 0 and netlist.is_file() and netlist.stat().st_size and not re.search(r"(?:ERROR|FATAL)\s*[:(]", raw):
                    report = folder / "probe_syn.rpt.html"
                    if report.is_file():
                        case.update(review_report(report))
                        case["status"] = "synthesis_completed" if case["contract_passed"] else "contract_report_failed"
            elif not tool:
                case["unexecuted_reason"] = "Gowin synthesis CLI unavailable; reproducible inputs/commands only"
            evidence["cases"].append(case)
            print("I", depth, case["status"], flush=True)
            (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
            if stop_after_case(case):
                evidence["stopped_after_depth"] = depth
                evidence["unexecuted_depths"] = [d for d in DEPTHS if d > depth]
                print("STOP I: failed synthesis/report; remaining depths not executed", flush=True)
                break
        if source_identity() != evidence["readonly_sources"]:
            raise ValueError("original inputs changed during I")
        evidence["prepared"] = True
        evidence["passed"] = len(evidence["cases"]) == len(DEPTHS) and all(
            c["status"] == "synthesis_completed" for c in evidence["cases"])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        evidence["error"] = str(error)
        print("FAIL I:", error)
    (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Evidence:", out / "evidence.json", flush=True)
    return 0 if evidence["passed"] else (2 if not evidence["synthesis_executed"] else 1)


def review_existing(original, out, evidence):
    output_root = (ROOT / "code/output").resolve()
    if output_root not in original.parents or original == out:
        raise ValueError("review only a distinct archived code/output child")
    raw = json.loads((original / "evidence.json").read_text(encoding="utf-8"))
    evidence["original_evidence_sha256"] = sha(original / "evidence.json")
    driver = original / "driver_executed.py"
    if not driver.is_file() or sha(driver) != raw["runner_sha256"]:
        raise ValueError("archived actual driver SHA missing/mismatching")
    evidence["executed_driver_sha256"] = sha(driver)
    evidence["executed_synthesis_commands_unchanged"] = True
    evidence["synthesis_executed"] = raw["synthesis_executed"]
    evidence["review_only_no_new_synthesis"] = True
    evidence["tool"] = raw.get("tool")
    evidence["tool_binary_sha256"] = raw.get("tool_binary_sha256")
    for case in raw["cases"]:
        folder = original / f"depth{case['depth']}"
        for name, digest in case["inputs_sha256"].items():
            if sha(folder / name) != digest:
                raise ValueError("archived input changed " + name)
        for name, digest in case.get("reports_sha256", {}).items():
            if sha(folder / name) != digest:
                raise ValueError("archived report changed " + name)
        revised = dict(case)
        report = folder / "probe_syn.rpt.html"
        revised["original_status"] = case["status"]
        if report.is_file():
            revised.update(review_report(report))
            revised["status"] = "synthesis_completed" if case.get("exit_code") == 0 and revised["contract_passed"] else "contract_report_failed"
        else:
            revised["status"] = "missing_report_failed"
        # Preserve raw driver/evidence/report identities; add the XML whose
        # extension the initial driver's report collector did not include.
        revised["all_artifact_sha256"] = {p.relative_to(folder).as_posix(): sha(p)
                                             for p in folder.rglob("*") if p.is_file()}
        evidence["cases"].append(revised)
    evidence["prepared"] = True
    evidence["passed"] = len(evidence["cases"]) == 3 and all(c["status"] == "synthesis_completed" for c in evidence["cases"])
    (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("I archived reports", "PASS" if evidence["passed"] else "contract FAIL", out / "evidence.json")


if __name__ == "__main__":
    raise SystemExit(main())
