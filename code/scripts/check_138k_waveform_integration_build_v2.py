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
import prepare_138k_waveform_integration_v2 as prepared
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
    """Retain exact scope accounting; allow only the predeclared 2/3 RAM case."""
    try:
        root = ET.parse(path).getroot()
        def count(node):
            value = node.attrib.get("T_Bsram", node.attrib.get("Bsram", "0"))
            if not re.fullmatch(r"\d+(?:\(\d+\))?", value):
                raise ValueError("malformed exact RAM count")
            return int(value.split("(")[0])
        def dsp(node):
            for key, value in node.attrib.items():
                if key.startswith(("T_MULT", "MULT", "T_DSP", "DSP")):
                    if not re.fullmatch(r"\d+(?:\(\d+\))?", value):
                        raise ValueError("malformed exact DSP count")
                    if int(value.split("(")[0]):
                        return True
            return False
        scopes = {}
        for name in ["u_waveform", "u_wave_bridge", "g_polyphonic.u_audio_core"]:
            nodes = [node for node in root.iter() if node.attrib.get("name") == name]
            if len(nodes) != 1:
                raise ValueError("missing/duplicate resource scope " + name)
            scopes[name] = nodes[0]
        wave = scopes["u_waveform"]
        bridge = scopes["u_wave_bridge"]
        audio = scopes["g_polyphonic.u_audio_core"]
        if (count(wave) != 3 or count(audio) != 20 or count(bridge) not in (2, 3)
                or dsp(wave) or dsp(bridge)):
            raise ValueError("unexpected waveform/audio/observer RAM or DSP mapping")
        required = 23 + count(bridge)
        if count(root) != required:
            raise ValueError("BSRAM outside exact expected source scopes")
        facts = dict(audio_original_bsram=20, waveform_banks_bsram=3,
                     observer_bsram=count(bridge), total=count(root), new_source_dsp=False,
                     retained_payload_may_preserve_previously_unused_bits=True)
        return facts, required, []
    except (OSError, ET.ParseError, ValueError) as exc:
        return {}, None, ["v2 hierarchical RAM proof: " + str(exc)]


def review(run):
    run = run.resolve()
    run.relative_to((prepared.BUILD_ROOT / "runs").resolve())
    project = run / "project"
    frozen = prepared.validate(project)
    build = json.loads((run / "build_receipt.json").read_text(encoding="utf-8"))
    errors = []
    if (build.get("attempt_count") != 1 or build.get("state") != "finished"
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
        # of originalaudio20 + waveform3 + observer2or3, exact sum.
        result["BSRAM"]=required_bsram if required_bsram is not None else -1
        return result
    globals_copy["profile"]=integrated_profile
    gate=types.FunctionType(baseline_gate.review.__code__,globals_copy)
    facts=gate("138k_c40_hold065",texts["timing"],texts["usage"],texts["pins"],sdc,texts["command"],texts["config"])
    errors+=facts["errors"]
    setup=facts["slacks"].get("Setup")
    if not isinstance(setup,(float,int)) or not math.isfinite(setup) or setup<0.5:
        errors.append("new integrated Setup engineering floor0.5ns not met")
    bus_counts=facts.get("visual_CDC_gate",{}).get("bus_path_count",{})
    if not 1 <= bus_counts.get(ADDITIONAL_BUS[0],0) < 128:errors.append("newpayload explicit surviving path coverage missing/truncated")
    return dict(date="2026-10-08",version="retained_payload_v2",passed=not errors,errors=errors,report_gate=facts,
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
