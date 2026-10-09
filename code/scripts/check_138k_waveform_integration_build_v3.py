"""Fail-closed report gate for exact retained-payload60-input T058 build, NO board."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT / "code/scripts"))
import prepare_138k_waveform_integration_v3 as prepared
import check_platform_timing as baseline_gate
from platform_profiles import profile

STEM = "audio_visual_coexistence_top"
ADDITIONAL_STAGES = (("u_wave_bridge/u_mailbox", "ack_meta", "ack_sync"),
                     ("u_wave_bridge/u_mailbox", "req_meta", "req_sync"),
                     ("u_wave_bridge", "source_up_meta", "source_up_sync"))
ADDITIONAL_BUS = ("u_wave_bridge/u_mailbox", "payload_hold", "dst_data")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()



def inspect_ram_hierarchy(path):
    """Exact new profile derived from v2 actual XML, not a retroactive v2 pass."""
    try:
        root = ET.parse(path).getroot()
        def count(node, name):
            value = node.attrib.get("T_" + name, node.attrib.get(name, "0"))
            if not re.fullmatch(r"\d+(?:\(\d+\))?", value):
                raise ValueError("malformed " + name)
            return int(value.split("(")[0])
        found = {}
        for name in ["u_waveform", "u_wave_bridge", "g_polyphonic.u_audio_core"]:
            nodes = [x for x in root.iter() if x.attrib.get("name") == name]
            if len(nodes) != 1:
                raise ValueError("resource scope missing/duplicate " + name)
            found[name] = nodes[0]
        wave, bridge, audio = (found[n] for n in ["u_waveform", "u_wave_bridge", "g_polyphonic.u_audio_core"])
        if ((count(audio, "Bsram"), count(wave, "Bsram"), count(bridge, "Bsram")) != (20, 3, 0)
                or (count(audio, "Ssram"), count(wave, "Ssram"), count(bridge, "Ssram")) != (32, 0, 28)
                or count(root, "Bsram") != 23 or count(root, "Ssram") != 89):
            raise ValueError("exact v3 BSRAM/SSRAM hierarchy changed")
        for node in [wave, bridge]:
            for key, value in node.attrib.items():
                if key.startswith(("T_MULT", "MULT", "T_DSP", "DSP")) and int(value.split("(")[0]):
                    raise ValueError("new display DSP mapping")
        return dict(audio_BSRAM=20, audio_SSRAM=32, wave_BSRAM=3, observer_BSRAM=0,
                    observer_SSRAM=28, total_BSRAM=23, total_SSRAM=89, new_source_DSP=False), 23, []
    except (OSError, ValueError, ET.ParseError) as error:
        return {}, None, ["v3 resource proof: " + str(error)]


def inspect_constraint_scope(sdc):
    """Reject a broad or weakened exception even if the timing table is green."""
    manifest = json.loads((prepared.SCOPE / "revision_manifest.json").read_bytes())
    old = (prepared.parent.parent.SCOPE / "overlay/audio_visual_hold055.sdc").read_text(encoding="utf-8")
    normalize = lambda value: {re.sub(r"\s+", " ", line.strip()) for line in value.splitlines()
                               if line.strip() and not line.lstrip().startswith("#")}
    original = normalize(old)
    approved = set(manifest["additional_exact_falsepaths"] + [manifest["additional_min_delay"]]
                   + manifest["additional_reports"])
    commands = normalize(sdc)
    if commands != original | approved:
        return ["v3 SDC exact whitelist differs / old constraint weakened"]
    if any("*" in command or "/D}" in command for command in manifest["additional_exact_falsepaths"]):
        return ["reset exception not a precise CLEAR endpoint"]
    return []


def inspect_directed_paths(timing, usage, sdc):
    rows = baseline_gate.parsed(timing)
    errors = inspect_constraint_scope(sdc)
    manifest = json.loads((prepared.SCOPE / "revision_manifest.json").read_bytes())
    active = {r[2] for section, r in rows if section == "SDC_Report" and len(r) == 3 and r[1] == "Actived"}
    wanted = set(manifest["additional_exact_falsepaths"] + [manifest["additional_min_delay"]]
                 + manifest["additional_reports"])
    if not wanted <= active:
        errors.append("v3 exact added constraint/report inactive")
    report_facts = {}
    for command in manifest["additional_reports"]:
        matched = re.fullmatch(r"report_timing -(setup|hold) -from \[get_regs \{(.+)\}\] -to \[get_regs \{(.+)\}\] -max_paths 1", command)
        if not matched:
            errors.append("v3 malformed approved report command")
            continue
        kind, start, stop = matched.groups()
        hits = [(section, row) for section, row in rows if section.startswith(kind.capitalize() + "_Slack_Table")
                and len(row) >= 4 and row[0].isdigit()
                and row[2] == start + "/Q" and row[3] == stop + "/D"]
        if not hits or any(not math.isfinite(float(r[1])) or float(r[1]) < 0 for _, r in hits):
            errors.append("v3 local D path missing/negative " + start + " -> " + stop)
        report_facts[command] = [row for _, row in hits]
    # Other reset paths remain part of full Recovery/Removal; cuts may not target business FFs.
    reset_evidence = {}
    for kind in ["Recovery", "Removal"]:
        values = [r for section, r in rows if section == kind + "_Slack_Table" and len(r) >= 4 and r[0].isdigit()]
        if not values or any(float(r[1]) < 0 for r in values):
            errors.append("v3 remaining " + kind + " missing/negative")
        reset_evidence[kind] = values
    matches = re.findall(r"--SSRAM\(RAM16\)\s*\|\s*(\d+)", usage)
    if matches != ["89"]:
        errors.append("v3 physical SSRAM not exact89")
    return errors, dict(exact_four_async_CLEAR_cuts=manifest["additional_exact_falsepaths"],
                        stricter_audio_min_delay=manifest["additional_min_delay"],
                        local_and_audio_D_reports=report_facts, remaining_reset_tables=reset_evidence)


def review(run):
    run = run.resolve()
    run.relative_to((prepared.BUILD_ROOT / "runs").resolve())
    project = run / "project"
    frozen = prepared.validate(project)
    build = json.loads((run / "build_receipt.json").read_text(encoding="utf-8"))
    errors = []
    if (build.get("version") != "reset_hold_v3" or build.get("attempt_count") != 1 or build.get("state") != "finished"
        or build.get("exit_code") != 0 or build.get("timed_out") is not False
        or build.get("programmed") is not False or not 1 <= build.get("timeout_seconds",0) <= 1800):
        errors.append("exact bounded single-run contract failed")
    for key,path in [("frozen_sha256_before",project/"frozen_receipt.json"),
                     ("frozen_sha256_after",project/"frozen_receipt.json"),
                     ("log_sha256",run/"build.log")]:
        if build.get(key) != sha(path):errors.append("build identity " + key)
    for rel,digest in build.get("tools_and_sources_sha256",{}).items():
        path = Path(rel)
        if not path.is_file() or sha(path) != digest:errors.append("runner/gate identity changed " + rel)
    log = (run / "build.log").read_text(encoding="utf-8",errors="replace")
    for marker in ["GowinSynthesis finish","Placement and routing completed","Timing analysis completed","Bitstream generation completed"]:
        if marker not in log:errors.append("missing completion " + marker)
    if re.search(r"(?:ERROR|FATAL)\s*[:(]",log):errors.append("tool ERROR/FATAL log")
    paths = {"timing":project/"impl/pnr"/(STEM+"_tr_content.html"),
             "usage":project/"impl/pnr"/(STEM+".rpt.txt"),
             "pins":project/"impl/pnr"/(STEM+".pin.html"),
             "command":project/"impl/pnr/cmd.do","config":project/"impl/pnr/device.cfg",
             "bitstream":project/"impl/pnr"/(STEM+".fs")}
    missing = [name for name,path in paths.items() if not path.is_file()]
    if missing:return dict(passed=False,errors=errors+["missing reports " + str(missing)],board_release_allowed=False)
    texts = {name:path.read_text(encoding="utf-8",errors="replace") for name,path in paths.items() if name!="bitstream"}
    sdc=(project/"inputs/constraints/audio_visual_hold055.sdc").read_text(encoding="utf-8")
    # Encrypted vendor netlists are not parsed as plaintext. Derive exact
    # bank mapping from the actual hierarchical synthesis resource XML.
    rsc=project/"impl/gwsynthesis"/(STEM+"_syn_rsc.xml")
    ram_facts, required_bsram, ram_errors = inspect_ram_hierarchy(rsc)
    errors += ram_errors
    # Reuse the entire established pin/clock/resetLOC/TNS/pulse/fmax/latch/SDC
    # gate with ONLY explicit additions: the observer bus and3secondstages.
    original_visual = baseline_gate.visual
    visual_globals = dict(original_visual.check.__globals__)
    visual_globals["FIRST_STAGES"] = original_visual.FIRST_STAGES + ADDITIONAL_STAGES
    visual_globals["BUSS"] = original_visual.BUSS + (ADDITIONAL_BUS,)
    new_visual = types.SimpleNamespace(check=types.FunctionType(original_visual.check.__code__,visual_globals))
    globals_copy = dict(baseline_gate.review.__globals__)
    globals_copy["visual"] = new_visual
    def integrated_profile(name):
        result=profile(name)
        # ExactRAM total is accepted only with explicit hierarchical proof
        # of originalaudio20 + waveform3, observer28SSRAM/0BSRAM exact scope.
        result["BSRAM"]=required_bsram if required_bsram is not None else -1
        return result
    globals_copy["profile"]=integrated_profile
    gate=types.FunctionType(baseline_gate.review.__code__,globals_copy)
    facts=gate("138k_c40_hold065",texts["timing"],texts["usage"],texts["pins"],sdc,texts["command"],texts["config"])
    errors+=facts["errors"]
    extra_errors, directed = inspect_directed_paths(texts["timing"], texts["usage"], sdc)
    errors += extra_errors
    setup=facts["slacks"].get("Setup")
    if not isinstance(setup,(float,int)) or not math.isfinite(setup) or setup<0.5:
        errors.append("new integrated Setup engineering floor0.5ns not met")
    bus_counts=facts.get("visual_CDC_gate",{}).get("bus_path_count",{})
    if not 1 <= bus_counts.get(ADDITIONAL_BUS[0],0) < 128:errors.append("newpayload explicit surviving path coverage missing/truncated")
    return dict(date="2026-10-09",version="reset_hold_v3",directed_reset_hold_proof=directed,passed=not errors,errors=errors,report_gate=facts,
                integrated_frozen_receipt_sha256=sha(project/"frozen_receipt.json"),
                exact_added_stages=ADDITIONAL_STAGES,source_packet_contract_bits=80,
                right_channel_logic_may_be_optimized_when_only_left_displayed=True,
                surviving_physical_packet_paths=bus_counts.get(ADDITIONAL_BUS[0]),
                required_DSP=46,required_BSRAM=required_bsram,actual_RAM_hierarchy=ram_facts,artifact_sha256={name:sha(path) for name,path in paths.items()},
                board_release_allowed=False,not_physical_HDMI_BLE_acceptance=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("run",type=Path)
    args=p.parse_args()
    result=review(args.run)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
