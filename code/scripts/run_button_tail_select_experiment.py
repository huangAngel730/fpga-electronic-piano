"""One bounded M2 button-counter tail-select experiment, production RTL untouched.

Functional replay creates new output-only files, including deliberate mutants.
--reports A B reads completed actual Gowin reports and decides the pre-agreed
adoption criteria. This entry never runs PnR, selects seeds or programs a board.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "code/tb/common/button_tail_select_candidate"
CAD = Path("D:/Gowin/oss-cad-suite")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_frozen_patch(before, patch):
    lines = patch.splitlines(keepends=True)
    source = before.splitlines(keepends=True)
    if not lines[0].startswith("--- a/") or not lines[1].startswith("+++ b/"):
        raise ValueError("bad reviewed patch header")
    index, cursor, output = 2, 0, []
    while index < len(lines):
        match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[index])
        if not match:
            raise ValueError("bad patch hunk")
        start = int(match[1]) - 1
        if start < cursor:
            raise ValueError("overlapping hunks")
        output.extend(source[cursor:start]); cursor = start; index += 1
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if line[:1] in (" ", "-"):
                if cursor >= len(source) or source[cursor] != line[1:]:
                    raise ValueError("patch does not match frozen oracle")
                cursor += 1
            if line[:1] in (" ", "+"):
                output.append(line[1:])
            if line[:1] not in (" ", "+", "-"):
                raise ValueError("unknown patch row")
            index += 1
    return "".join(output + source[cursor:])


def audit_ready_dependencies(netlist):
    module = json.loads(netlist.read_text(encoding="utf-8"))["modules"]["button_event_converter"]
    drivers = {}
    for name, cell in module["cells"].items():
        for port, direction in cell["port_directions"].items():
            if direction == "output":
                for bit in cell["connections"][port]:
                    if isinstance(bit, int): drivers.setdefault(bit, []).append((name, cell))
    ready = set(module["ports"]["event_ready"]["bits"])
    def cone(bits):
        visited, stack, touched = set(), list(bits), set()
        while stack:
            bit = stack.pop()
            if not isinstance(bit, int) or bit in visited: continue
            visited.add(bit)
            if bit in ready: touched.add(bit)
            for _, cell in drivers.get(bit, []):
                if any(kind in cell["type"].lower() for kind in ("dff", "latch", "mem")): continue
                for port, direction in cell["port_directions"].items():
                    if direction == "input": stack.extend(cell["connections"][port])
        return touched
    names = module["netnames"]
    checked = ("drops_no_pop", "drops_with_pop", "count_no_pop", "count_with_pop")
    for name in checked:
        if cone(names[name]["bits"]): raise RuntimeError("ready reentered precomputed branch: " + name)
    counter_bits = set(module["ports"]["overflow_count"]["bits"])
    registers = [cell for cell in module["cells"].values() if "dff" in cell["type"].lower()
                 and counter_bits.intersection(cell["connections"].get("Q", []))]
    if len(registers) != 1 or "EN" in registers[0]["connections"]:
        raise RuntimeError("counter register still has a late enable or unexpected stages")
    data = registers[0]["connections"]["D"]
    selectors = {name: cell for bit in data for name, cell in drivers.get(bit, [])}
    if len(selectors) != 1:
        raise RuntimeError("counter input is not a single final selector")
    selector = next(iter(selectors.values()))
    if (selector["type"] != "$mux" or selector["connections"]["A"] != names["count_no_pop"]["bits"]
            or selector["connections"]["B"] != names["count_with_pop"]["bits"]
            or selector["connections"]["S"] != names["counter_pop"]["bits"]):
        raise RuntimeError("unexpected ready-to-counter structure")
    return {"optimized_generic_branches_independent_of_ready": list(checked),
            "counter_register_has_ready_enable": False, "final_counter_D_is_pop_mux": True,
            "evidence_scope": "actual Yosys optimized generic netlist, NOT decrypted Gowin implementation"}


def compare_reports(a_folder, b_folder):
    from check_audio_visual_probe import check
    from check_hdmi_link_report import ReportParser
    reports = {}
    for label, folder in (("A", a_folder), ("B", b_folder)):
        errors, facts = check(folder)
        timing = folder / "impl/pnr/audio_visual_coexistence_top_tr_content.html"
        parser = ReportParser(); parser.feed(timing.read_text(encoding="utf-8"))
        per_clock = {}
        for clock in ("sys_clk", "video_pixel", "video_serial"):
            rows = [row for section, row in parser.rows if section.startswith("Setup_Slack_Table")
                    and len(row) >= 6 and row[0].isdigit() and row[4].startswith(clock + ":") and row[5].startswith(clock + ":")]
            if not rows: raise RuntimeError("missing per-clock paths: " + clock)
            per_clock[clock] = min(rows, key=lambda row: float(row[1]))
        reports[label] = {"errors": errors, "facts": facts, "per_clock_setup": per_clock,
                          "timing_report_sha256": digest(timing)}
    # The real project file lists must differ in ONE converter and nothing else.
    projects = [ET.parse(folder / "audio_visual_coexistence_top.gprj").getroot().find("FileList")
                for folder in (a_folder, b_folder)]
    if len(projects[0]) != len(projects[1]): raise RuntimeError("A/B file lists differ")
    differences = [(a.attrib, b.attrib) for a, b in zip(*projects) if a.attrib != b.attrib]
    if len(differences) != 1: raise RuntimeError("A/B changed more than one source")
    a_source, b_source = [Path(row["path"]) for row in differences[0]]
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    if digest(a_source) != manifest["baseline_sha256"] or digest(b_source) != manifest["candidate_sha256"]:
        raise RuntimeError("A/B converter is not the frozen reviewed source")
    for node in projects[0]:
        if not Path(node.attrib["path"]).is_file(): raise RuntimeError("missing A/B input")
    a, b = reports["A"], reports["B"]
    delta = round(float(b["per_clock_setup"]["sys_clk"][1]) - float(a["per_clock_setup"]["sys_clk"][1]), 6)
    resources = {key: b["facts"]["resources"][key] - a["facts"]["resources"][key]
                 for key in ("Logic", "Register", "DSP", "BSRAM")}
    criteria = {"functional_exact": True, "system_setup_delta_at_least0_1": delta >= .1,
                "logic_increase_at_most128": resources["Logic"] <= 128,
                "Register_DSP_BSRAM_not_increased": all(resources[key] <= 0 for key in ("Register", "DSP", "BSRAM")),
                "all_original_timing_interfaces_pass": not a["errors"] and not b["errors"]}
    return {"reports": reports, "system_setup_delta_ns": delta, "resource_delta": resources,
            "criteria": criteria, "adopt_candidate": all(criteria.values()),
            "selection_policy": "one fixed A and one fixed B; no seeds or alternative RTL trials",
            "formal_M3_module_applied": False}


def prepare_ab_projects(output, frozen_combo, baseline, candidate):
    # Freeze existing validated combo inputs. Do NOT silently use current
    # production parser/audio if collaborators have advanced since the report.
    evidence = frozen_combo / "M2_combo_override.json"
    if not evidence.is_file():
        evidence = frozen_combo / "combo_override.json"
    if not evidence.is_file():
        raise ValueError("frozen combo must provide actual input identity")
    metadata = json.loads(evidence.read_text(encoding="utf-8"))
    actual = metadata.get("actual_input_SHA", metadata.get("actual_input_sha256"))
    if not actual:
        raise ValueError("missing frozen actual input hashes")
    for path, expected in actual.items():
        if digest(Path(path)) != expected:
            raise ValueError("frozen combo input changed: " + path)
    original = ET.parse(frozen_combo / "audio_visual_coexistence_top.gprj").getroot()
    common = output / "frozen_common_inputs"; common.mkdir()
    files = []
    replaced = 0
    for node in original.find("FileList"):
        source = Path(node.attrib["path"])
        if source.name == "button_event_converter.sv":
            if digest(source) != digest(baseline):
                raise ValueError("combo baseline converter differs from6055bb8")
            files.append((None, node.attrib["type"])); replaced += 1
        else:
            dest = common / source.name
            if dest.exists(): raise ValueError("colliding input basenames")
            dest.write_bytes(source.read_bytes())
            files.append((dest, node.attrib["type"]))
    if replaced != 1:
        raise ValueError("must replace exactly one converter input")
    stages = []
    for label, converter in (("A_baseline", baseline), ("B_tail_select", candidate)):
        folder = output / label; folder.mkdir()
        project = ET.Element("Project")
        ET.SubElement(project, "Template").text = "FPGA"
        ET.SubElement(project, "Version").text = "5"
        device = original.find("Device")
        ET.SubElement(project, "Device", **device.attrib).text = device.text
        listing = ET.SubElement(project, "FileList")
        inputs = []
        for source, kind in files:
            path = converter if source is None else source
            ET.SubElement(listing, "File", path=path.as_posix(), type=kind, enable="1")
            inputs.append(path)
        gprj = folder / "audio_visual_coexistence_top.gprj"
        ET.ElementTree(project).write(gprj, encoding="utf-8", xml_declaration=True)
        tcl = folder / "run.tcl"
        tcl.write_text(f"open_project {{{gprj.as_posix()}}}\nset_option -top_module audio_visual_coexistence_top\nset_option -verilog_std sysv2017\nrun all\n", encoding="ascii")
        record = {"fixed_audio_visual_source": str(frozen_combo),
                  "sole_modified_component": "button_event_converter", "physical_run_started": False,
                  "constraints_modified": False, "inputs": {str(path): digest(path) for path in inputs},
                  "scope": "independent experiment only; NEVER PROGRAM or publish as production"}
        (folder / "input_manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        stages.append(str(folder))
    return {"project_folders": stages, "prepared_only": True, "PnR_runs_performed": 0,
            "all_other_inputs_share_identical_paths": True, "no_seed_search": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reports", nargs=2, type=Path, metavar=("A_FOLDER", "B_FOLDER"))
    parser.add_argument("--prepare-ab", type=Path, metavar="FROZEN_COMBO",
                        help="prepare fair A/B projects from immutable validated combo; never build automatically")
    cfg = parser.parse_args()
    output = cfg.output.resolve(); output.relative_to(ROOT / "code/output")
    if output.exists(): parser.error("output already exists; preserve previous evidence")
    output.mkdir(parents=True)
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files_sha256"].items():
        if digest(HERE / name) != expected: raise ValueError("frozen candidate artifact changed: " + name)
    baseline_bytes = subprocess.check_output(["git", "-C", str(ROOT), "show", manifest["baseline_commit"] + ":" + manifest["baseline_path"]])
    if hashlib.sha256(baseline_bytes).hexdigest() != manifest["baseline_sha256"]: raise ValueError("bad baseline")
    baseline = output / "button_baseline_6055bb8.sv"; baseline.write_bytes(baseline_bytes)
    oracle = output / "button_baseline_reference.sv"
    oracle.write_text(baseline_bytes.decode("utf-8").replace("module button_event_converter", "module button_reference", 1), encoding="utf-8", newline="\n")
    candidate = output / "button_tail_select.sv"
    candidate.write_text(apply_frozen_patch(baseline_bytes.decode("utf-8"), (HERE / "candidate.patch").read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if digest(candidate) != manifest["candidate_sha256"]: raise ValueError("candidate changed")
    record = {"formal_module_changed": False, "latency_added": 0, "candidate_sha256": digest(candidate), "runs": {}}
    environment = dict(os.environ)
    environment["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + environment["PATH"]
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    def run(name, command, success=True, marker=None, timeout=120):
        path = output / (name + ".log")
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout, check=False)
        text = path.read_text(encoding="utf-8", errors="replace")
        record["runs"][name] = {"exit": result.returncode, "expected_success": success, "command": list(map(str, command)), "log_sha256": digest(path)}
        if (result.returncode == 0) != success or (marker and marker not in text):
            print(text[-3000:]); raise RuntimeError("unexpected verdict: " + name)
        print(name, "exit", result.returncode, flush=True)
        return text
    common = [ROOT / "code/rtl/common/audio_defs_pkg.sv", ROOT / "code/rtl/common/performance_event_fifo.sv", oracle, candidate,
              ROOT / "code/tb/input/button_counter_timing/fifo_reference.sv", ROOT / "code/tb/input/button_counter_timing/fifo_no_full_bypass.sv", HERE / "tb_button_tail_select.sv"]
    record["scoreboard_verdicts"] = []
    for depth, local in ((3, 2), (32, 2), (3, 1), (32, 4)):
        label = f"D{depth}_L{local}"; binary = output / (label + ".vvp")
        run(label + "_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_button_tail_select", "-P", f"tb_button_tail_select.DEPTH={depth}",
            "-P", f"tb_button_tail_select.LOCAL={local}", "-o", str(binary), *map(str, common)])
        text = run(label, [str(CAD / "bin/vvp.exe"), str(binary)], marker="PASS button_counter_timing")
        record["scoreboard_verdicts"].append(next(row for row in text.splitlines() if row.startswith("PASS button_counter_timing")))
    record["exhaustive_verdicts"] = []
    for buttons, local in ((2, 4), (1, 1), (2, 1), (2, 2), (4, 4), (4, 8)):
        label = f"B{buttons}_L{local}"; binary = output / (label + ".vvp")
        run(label + "_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_tail_select_exhaustive", "-P", f"tb_tail_select_exhaustive.BUTTONS={buttons}",
            "-P", f"tb_tail_select_exhaustive.LOCAL={local}", "-o", str(binary), str(common[0]), str(oracle), str(candidate), str(HERE / "tb_tail_select_exhaustive.sv")])
        text = run(label, [str(CAD / "bin/vvp.exe"), str(binary)], marker="PASS tailselect exhaustive")
        record["exhaustive_verdicts"].append(next(row for row in text.splitlines() if row.startswith("PASS tailselect exhaustive")))
    binary = output / "original.vvp"
    run("original_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_button_event_converter", "-o", str(binary), str(common[0]), str(candidate), str(ROOT / "code/tb/input/tb_button_event_converter.sv")])
    run("original_T022", [str(CAD / "bin/vvp.exe"), str(binary)], marker="PASS: tb_button_event_converter")
    text = candidate.read_text(encoding="utf-8"); header, body = text.split("    import audio_defs_pkg::*;", 1)
    delayed = header + "    logic [31:0] counter_accumulator;\n    always_ff @(posedge clk) begin\n        if(!rst_n) overflow_count<=0;\n        else overflow_count<=counter_accumulator;\n    end\n    import audio_defs_pkg::*;" + body.replace("overflow_count", "counter_accumulator")
    mutations = {"delayed": delayed, "wrong_pop": text.replace("total_with_pop = total_no_pop - TOTAL_W'(1);", "total_with_pop = total_no_pop;"), "no_full_pop": text}
    for name, mutation in mutations.items():
        mutant = output / (name + ".sv"); mutant.write_text(mutation, encoding="utf-8", newline="\n")
        sources = common.copy(); sources[3] = mutant
        if name == "no_full_pop":
            wrong_fifo = output / "wrong_fifo.sv"
            wrong_fifo.write_text(common[1].read_text(encoding="utf-8").replace("((count < DEPTH) || pop)", "(count < DEPTH)"), encoding="utf-8", newline="\n")
            sources[1] = wrong_fifo
        binary = output / (name + ".vvp")
        run(name + "_compile", [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_button_tail_select", "-o", str(binary), *map(str, sources)])
        run(name, [str(CAD / "bin/vvp.exe"), str(binary)], success=False, marker="FATAL")
    script = output / "audit.ys"; netlist = output / "generic.json"
    script.write_text("read_slang --top button_event_converter " + common[0].as_posix() + " " + candidate.as_posix() + "\nproc\nopt\nwrite_json " + netlist.as_posix() + "\n", encoding="ascii")
    run("generic_netlist", [str(CAD / "bin/yosys.exe"), "-Q", "-T", "-s", str(script)])
    record["ready_dependency_audit"] = audit_ready_dependencies(netlist)
    record["functional_exact"] = True
    if cfg.reports:
        record["AB_adoption"] = compare_reports(*[folder.resolve() for folder in cfg.reports])
    if cfg.prepare_ab:
        record["prepared_AB"] = prepare_ab_projects(output, cfg.prepare_ab.resolve(), baseline, candidate)
    (output / "review.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Functional experiment passes; physical adoption recorded separately; formal M3 source unchanged.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
