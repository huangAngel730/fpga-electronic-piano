"""Fail-closed report gate for exact integrated59-input T058 build, NO board."""
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
import prepare_138k_waveform_integration as prepared
import check_platform_timing as baseline_gate
from platform_profiles import profile

STEM = "audio_visual_coexistence_top"
ADDITIONAL_STAGES = (("u_wave_bridge/u_mailbox", "ack_meta", "ack_sync"),
                     ("u_wave_bridge/u_mailbox", "req_meta", "req_sync"),
                     ("u_wave_bridge", "source_up_meta", "source_up_sync"))
ADDITIONAL_BUS = ("u_wave_bridge/u_mailbox", "payload_hold", "dst_data")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    ram_facts={}
    required_bsram=None
    if not rsc.is_file():
        errors.append("hierarchical synthesis resourceXML missing")
    else:
        tree=ET.parse(rsc).getroot()
        def nodes(name):return [n for n in tree.iter() if n.attrib.get("name")==name]
        def bsram(node):
            value=node.attrib.get("T_Bsram",node.attrib.get("Bsram","0"))
            if not re.fullmatch(r"\d+(?:\(\d+\))?",value):raise ValueError("malformed exactRAM count")
            return int(value.split("(")[0])
        def has_dsp(node):return any(k.startswith(("T_MULT","MULT","T_DSP","DSP")) and int(v.split("(")[0]) for k,v in node.attrib.items() if re.fullmatch(r"\d+(?:\(\d+\))?",v))
        wave=nodes("u_waveform");bridge=nodes("u_wave_bridge");audio=nodes("g_polyphonic.u_audio_core")
        if len(wave)!=1 or len(bridge)!=1 or len(audio)!=1:
            errors.append("unique waveform/observer/audio resource scopes missing")
        elif bsram(wave[0])!=3 or bsram(audio[0])!=20 or bsram(bridge[0]) not in (0,1) or has_dsp(wave[0]) or has_dsp(bridge[0]):
            errors.append("unexpected waveform/audio/observer RAM or DSP mapping")
        else:
            required_bsram=23+bsram(bridge[0])
            if bsram(tree)!=required_bsram:errors.append("BSRAM outside expected source scopes")
            ram_facts=dict(audio_original_bsram=20,waveform_banks_bsram=3,observer_bsram=bsram(bridge[0]),total=bsram(tree),new_source_dsp=False)
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
        # of originalaudio20 + waveform3 + optional single observerRAM.
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
    return dict(date="2026-10-08",passed=not errors,errors=errors,report_gate=facts,
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
