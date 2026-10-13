"""Prepare/read back exact pROM+clipped N32/R1 synthesis-only project; no EDA."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import prepare_n32_prom_candidate_20261013 as candidate
import prepare_138k_polyphony_resource as original

ROOT = candidate.ROOT
DEST = ROOT / "code/build/138k_polyphony_resource/prom_candidate_20261013_01"
PROJECT = "n32_prom_resource.gprj"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expected():
    generated, candidate_record = candidate.expected()
    if {p.name: p.read_bytes() for p in candidate.DEST.iterdir() if p.is_file()} != generated:
        raise ValueError("EXACT_PROM_CANDIDATE_SHA")
    frozen = original.verify(candidate.BASE)
    top = (candidate.BASE / "b2l_resource_probe.sv").read_text()
    top = candidate.replace_once(top, "module b2l_resource_probe (", "module m2_n32_prom_resource (")
    top = candidate.replace_once(top, "output wire late, aborted, idle, fault, publish,", "output wire late, clipped, aborted, idle, fault, publish,")
    top = candidate.replace_once(top, "b2d_event_audio #(", "m2_b2d_event_audio_prom #(")
    top = candidate.replace_once(top, ".left(left), .right(right), .late(late),", ".left(left), .right(right), .late(late), .clipped(clipped),")
    replacements = {"adsr_piano_envelope.sv", "pitch_mod_fcw_pipeline.sv", "b2_audio_backend.sv", "b2d_event_audio.sv", "b2l_resource_probe.sv"}
    old_list = ET.parse(candidate.BASE / original.PROJECT).getroot().find("FileList")
    sources = [Path(n.attrib["path"]) for n in old_list if n.attrib["path"].endswith(".sv") and Path(n.attrib["path"]).name not in replacements]
    wrappers = [candidate.DEST / ("m2_prom_" + n + ".sv") for n in ("gain", "oct", "sub", "lfo", "wave")]
    sources += wrappers + [candidate.DEST / n for n in ("m2_adsr_piano_prom.sv", "m2_pitch_mod_prom.sv", "m2_b2_backend_prom.sv", "m2_b2d_event_audio_prom.sv")]
    sources.append(DEST / "m2_n32_prom_resource.sv")
    project = ET.Element("Project")
    ET.SubElement(project, "Template").text = "FPGA"
    ET.SubElement(project, "Version").text = "5"
    device = frozen["device"]
    ET.SubElement(project, "Device", name=device["name"], pn=device["pn"]).text = device["index"]
    listing = ET.SubElement(project, "FileList")
    for path in sources:
        ET.SubElement(listing, "File", path=path.as_posix(), type="file.verilog", enable="1")
    ET.SubElement(listing, "File", path=(DEST / "clock.sdc").as_posix(), type="file.sdc", enable="1")
    tcl = "\n".join(["cd {" + DEST.as_posix() + "}", "open_project {" + (DEST / PROJECT).as_posix() + "}",
                     "set_option -top_module m2_n32_prom_resource", "set_option -verilog_std sysv2017",
                     "set_option -include_path {" + (candidate.BASE / "include").as_posix() + "}", "run syn"]) + "\n"
    payload = {"m2_n32_prom_resource.sv": top.encode(), "clock.sdc": (candidate.BASE / "clock.sdc").read_bytes(),
               PROJECT: ET.tostring(project, encoding="utf-8", xml_declaration=True) + b"\n", "run_synthesis_only.tcl": tcl.encode("ascii")}
    receipt = dict(schema=1, status="EXACT_PROM_PROJECT_PREPARED_NO_SYNTHESIS_PERMISSION", configuration=frozen["configuration"],
                   device=device, tool=frozen["tool"], source_order=[str(p) for p in sources],
                   candidate_receipt_sha256=sha((candidate.DEST / "candidate_receipt.json").read_bytes()),
                   input_SHA={str(p): sha(p.read_bytes()) for p in sources[:-1]},
                   include_SHA={str(p): sha(p.read_bytes()) for p in (candidate.BASE / "include").iterdir() if p.is_file()},
                   generator_sha256=sha(Path(__file__).read_bytes()), primitive_count_N32=161,
                   primitive_count_not_native_resource_report=True, read_port_preserved=True, injection_disabled=True,
                   accurate_clipped_public=True, synthesis_authorized=False, actual_tool_calls=0, resources="UNKNOWN", STA="NOT_RUN",
                   old_synthesis_permission_reused=False, PnR=False, device_operation=False,
                   artifacts={n: dict(bytes=len(b), sha256=sha(b)) for n, b in payload.items()})
    payload["resource_receipt.json"] = candidate.canonical(receipt)
    return payload, receipt


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check", action="store_true")
    cli.add_argument("--execute", action="store_true")
    args = cli.parse_args()
    if args.execute:
        print("REJECT NEW_EXACT_SYNTHESIS_PERMISSION_REQUIRED")
        return 1
    payload, receipt = expected()
    if args.check:
        if {p.name: p.read_bytes() for p in DEST.iterdir() if p.is_file()} != payload:
            raise ValueError("EXACT_PREPARED_PROJECT_SHA")
    else:
        if DEST.exists():
            raise ValueError("REFUSE_EXISTING_PROJECT")
        DEST.mkdir(parents=True)
        for name, raw in payload.items():
            with (DEST / name).open("xb") as stream:
                stream.write(raw)
    print(json.dumps(dict(status=receipt["status"], HDL_files=len(receipt["source_order"]), new_EDA_calls=0, clipped=True)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
