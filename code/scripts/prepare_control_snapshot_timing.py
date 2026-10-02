"""Two identical observation wrappers; independent50MHz PnR probes only.
No production GPRJ/SDC/CST modifications. Outputs are not for board download.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--baseline", action="store_true")
    args.add_argument("--decoded-probe", action="store_true", help="compatibility flag: validated reversible wrapper is now always used")
    args.add_argument("--min-route-delay", action="store_true", help="extra1ns minimum path bound, never relax original0.5ns hold uncertainty")
    cfg = args.parse_args()
    folder = ROOT / "code/output/control_snapshot_optimization_20261002" / (("parallel" if cfg.baseline else "serial") + ("_extra_min_validated_PnR" if cfg.min_route_delay else "_validated_probe_PnR"))
    folder.mkdir(parents=True, exist_ok=True)
    input_paths = [ROOT / rel for rel in ["code/rtl/common/audio_defs_pkg.sv", "code/rtl/common/reset_sync.sv",
                   "code/rtl/board/performance_control_state.sv", "code/rtl/board/performance_control_snapshot.sv",
                   "code/tb/board/control_snapshot_timing_probe.sv"]]
    # Exact full-rank GF(2) proof of the common test-only7-tap260-bit
    # stimulus generator: no legal input identity/payload is removed.
    matrix = [sum(1 << ((i + j) % 260) for j in range(7)) for i in range(260)]
    rank = 0
    for bit in range(260):
        pivot = next((i for i in range(rank, 260) if (matrix[i] >> bit) & 1), None)
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        for i in range(260):
            if i != rank and (matrix[i] >> bit) & 1:
                matrix[i] ^= matrix[rank]
        rank += 1
    if rank != 260:
        raise RuntimeError("Probe input transform lost reachable payloads")
    wrapper = folder / "control_snapshot_timing_probe.sv"
    text = input_paths[-1].read_text(encoding="utf-8")
    if cfg.baseline:
        text = text.replace("parameter integer SERIALIZED=1", "parameter integer SERIALIZED=0")
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    paths = input_paths[:-1] + [wrapper]
    sdc = folder / "control_snapshot_probe.sdc"
    sdc.write_text("create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]\n"
                   "set_clock_uncertainty -setup 1.000 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]\n"
                   "set_clock_uncertainty -hold 0.500 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]\n"
                   "set_false_path -from [get_ports {sys_rst_n}] -to [get_regs {u_reset/sync_chain*}]\n"
                   "report_timing -setup -from_clock [get_clocks {sys_clk}] -to_clock [get_clocks {sys_clk}] -max_paths 20\n"
                   "report_timing -hold -from_clock [get_clocks {sys_clk}] -to_clock [get_clocks {sys_clk}] -max_paths 10\n",
                   encoding="ascii", newline="\n")
    if cfg.min_route_delay:
        with sdc.open("a", encoding="ascii", newline="\n") as stream:
            stream.write("# Stricter physical minimum, no hold false paths or uncertainty reduction.\n"
                         "set_min_delay -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}] 1.000\n")
    cst = folder / "control_snapshot_probe.cst"
    cst.write_text('IO_LOC "sys_clk" V22;\nIO_PORT "sys_clk" IO_TYPE=LVCMOS33 BANK_VCCIO=3.3;\n'
                   'IO_LOC "sys_rst_n" AA13;\nIO_PORT "sys_rst_n" IO_TYPE=LVCMOS15 BANK_VCCIO=1.5 PULL_MODE=UP;\n',
                   encoding="ascii", newline="\n")
    proj = ET.Element("Project")
    ET.SubElement(proj, "Template").text = "FPGA"
    ET.SubElement(proj, "Version").text = "5"
    ET.SubElement(proj, "Device", name="GW5AT-60B", pn="GW5AT-LV60PG484AC1/I0").text = "gw5at60b-002"
    listing = ET.SubElement(proj, "FileList")
    for path in paths + [sdc, cst]:
        kind = "file.verilog" if path.suffix == ".sv" else "file." + path.suffix[1:]
        ET.SubElement(listing, "File", path=path.as_posix(), type=kind, enable="1")
    project = folder / "control_snapshot_timing_probe.gprj"
    ET.ElementTree(proj).write(project, encoding="utf-8", xml_declaration=True)
    (folder / "run_all.tcl").write_text("cd {" + folder.as_posix() + "}\nopen_project {" + project.as_posix() +
        "}\nset_option -top_module control_snapshot_timing_probe\nset_option -verilog_std sysv2017\nset_option -correct_hold_violation 1\nrun all\n", encoding="ascii", newline="\n")
    facts = {"variant": "parallel" if cfg.baseline else "serialized", "clock_target_mhz": 50, "extra_min_delay_ns": 1.0 if cfg.min_route_delay else None,
             "original_source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths},
             "actual_build_input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths + [sdc, cst, project]},
             "probe_input_transform_GF2_rank": rank,
             "scope": "same reversible scan observation wrapper internal timing comparison; external scan IO timing not constrained, no board use"}
    (folder / "inputs.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Prepared:", folder / "run_all.tcl")


if __name__ == "__main__":
    main()
