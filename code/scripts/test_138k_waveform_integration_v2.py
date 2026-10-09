"""Bounded preflight/negative checks for the isolated retained-payload revision."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import prepare_138k_waveform_integration_v2 as prepare
import check_138k_waveform_integration_build_v2 as gate

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(prepare.BUILD_ROOT.resolve())
    if output.exists() or output == prepare.BUILD_ROOT.resolve():
        parser.error("require unique new test directory")
    output.mkdir(parents=True)
    results = []
    def check(label, condition):
        results.append({"label": label, "passed": bool(condition)})
        if not condition:
            raise AssertionError(label)
    def rejected(label, fn):
        try:
            fn()
        except (ValueError, OSError):
            check(label, True)
        else:
            check(label, False)
    project = output / "project"
    record = prepare.prepare(project)
    check("exact60input51entries", record["input_count"] == 60 and record["project_file_count"] == 51)
    expected, _, _, _, _ = prepare.inputs(project)
    old_expected = prepare.parent.inputs(project)[0]
    check("all59parentinputsbyteidentical", {k: v for k, v in expected.items() if k != prepare.GSC_REL} == old_expected)
    files = ET.fromstring((project / prepare.PROJECT).read_bytes()).find("FileList")
    check("oneenabledGSC", sum(x.attrib.get("type") == "file.gsc" and x.attrib.get("enable") == "1" for x in files) == 1)
    rejected("overwrite_refused", lambda: prepare.prepare(project))
    receipt = project / "frozen_receipt.json"
    saved = receipt.read_bytes()
    altered = json.loads(saved)
    altered["input_count"] = 59
    receipt.write_text(json.dumps(altered), encoding="utf-8")
    rejected("old59profile_not_relabelled", lambda: prepare.validate(project))
    receipt.write_bytes(saved)
    targets = ["constraints/waveform_payload_preserve.gsc", "constraints/audio_visual_hold055.sdc",
               "constraints/audio_visual.cst", "sources/audio_visual_coexistence_top.sv",
               "sources/pcm_waveform_observer_bridge.sv", "rom/sine_1024_8192.mem"]
    for name in targets:
        path = project / "inputs" / name
        raw = path.read_bytes()
        path.write_bytes(raw + b"\n// hidden change\n")
        rejected("hidden_input_change:" + name, lambda: prepare.validate(project))
        path.write_bytes(raw)
    rogue = project / "inputs" / "rogue.sv"
    rogue.write_text("module rogue; endmodule\n", encoding="ascii")
    rejected("hidden_extra_input_refused", lambda: prepare.validate(project))
    rogue.unlink()
    for name in [prepare.PROJECT, "run.tcl"]:
        path = project / name
        raw = path.read_bytes()
        path.write_bytes(raw + b"\n")
        rejected("project_options_change:" + name, lambda: prepare.validate(project))
        path.write_bytes(raw)
    prepare.validate(project)
    original = ROOT / "code/build/138k_waveform/runs/run_20261008_exact_waveform/project/impl/gwsynthesis/audio_visual_coexistence_top_syn_rsc.xml"
    tree = ET.parse(original).getroot()
    probe = output / "resource_probe.xml"
    def validate_tree(label, value, wanted):
        ET.ElementTree(value).write(probe, encoding="utf-8", xml_declaration=True)
        facts, count, errors = gate.inspect_ram_hierarchy(probe)
        check(label, (not errors) is wanted)
        return facts, count
    facts, count = validate_tree("actual_parentRAM25_proof", tree, True)
    check("actual_observer2_audio20_wave3", count == 25 and facts["observer_bsram"] == 2)
    modified = copy.deepcopy(tree)
    bridge = next(x for x in modified.iter() if x.attrib.get("name") == "u_wave_bridge")
    bridge.attrib["T_Bsram"] = "3(3)"
    modified.attrib["T_Bsram"] = "26(26)"
    validate_tree("predeclared_preserved_packetRAM26_supported", modified, True)
    for name, mutate in [
        ("old_observer1_assumption_refused", lambda t: next(x for x in t.iter() if x.attrib.get("name") == "u_wave_bridge").attrib.update(T_Bsram="1")),
        ("unaccounted_totalRAM_refused", lambda t: t.attrib.update(T_Bsram="27")),
        ("new_branchDSP_refused", lambda t: next(x for x in t.iter() if x.attrib.get("name") == "u_wave_bridge").attrib.update(T_MULT27X36="1")),
        ("audioRAMchange_refused", lambda t: next(x for x in t.iter() if x.attrib.get("name") == "g_polyphonic.u_audio_core").attrib.update(T_Bsram="21")),
        ("malformed_resource_refused", lambda t: t.attrib.update(T_Bsram="unknown")),
    ]:
        altered = copy.deepcopy(tree)
        mutate(altered)
        validate_tree(name, altered, False)
    altered = copy.deepcopy(tree)
    existing = next(x for x in altered.iter() if x.attrib.get("name") == "u_wave_bridge")
    altered.append(copy.deepcopy(existing))
    validate_tree("duplicate_scope_refused", altered, False)
    candidate_run = output / "not_a_gowin_run"
    command = [sys.executable, "-B", "-X", "utf8", str(ROOT / "code/scripts/run_138k_waveform_integration_once_v2.py"),
               "--output", str(candidate_run), "--simulation-receipts", str(receipt), "--timeout-seconds", "0"]
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    (output / "invalid_timeout.stdout.log").write_bytes(result.stdout)
    (output / "invalid_timeout.stderr.log").write_bytes(result.stderr)
    check("bad_timeout_nonzero_beforeGowin_or_output", result.returncode != 0 and not candidate_run.exists())
    identity = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [Path(__file__), Path(prepare.__file__), Path(gate.__file__),
                          ROOT / "code/scripts/run_138k_waveform_integration_once_v2.py",
                          prepare.SCOPE / "revision_manifest.json", prepare.SCOPE / "waveform_payload_preserve.gsc"]}
    receipt_out = dict(passed=True, checks=results, source_sha256=identity,
                       note="preflight and damaged-input refusal; no synthesis/STA claim", programmed=False)
    (output / "receipt.json").write_text(json.dumps(receipt_out, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8", newline="\n")
    print("PASS retained-payload-v2 preflight checks=" + str(len(results)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
