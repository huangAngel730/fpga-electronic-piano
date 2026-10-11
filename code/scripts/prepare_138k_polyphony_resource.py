"""Prepare/verify ONE N32/R1 synthesis-only resource project; never run EDA."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = ROOT / "code/build/138k_polyphony_resource/prepared"
PREPARATION_PIN = "2bc96a562a4faa92d5a4b8ab8bae44ea9dc54152"
FUNCTIONAL_PIN = "52ad3dc5e27f499bc79bad5c1a6b8d4bbf8a4387"
TOOL_HOME = Path("D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64")
DEVICE = dict(name="GW5AST-138C", pn="GW5AST-LV138PG484AC1/I0", index="gw5ast138c-007")
PROJECT = "n32_r1_resource.gprj"
VERSION = "m2_n32_resource_prepare_v1"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def source_blob(commit: str, relative: str) -> bytes:
    result = subprocess.run(["git", "show", commit + ":" + relative],
                            cwd=ROOT, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("SOURCE_GIT_UNAVAILABLE:" + relative)
    return result.stdout


def helper():
    names = ("b2l_prepare", "b2d_run", "b2i_audit", "inventory", "b2_clock", "b1_run", "b2_run", "b2c_run")
    provenance = {}
    folder = ROOT / "code/software/polyphony_scaling_candidate"
    for name in names:
        path = folder / (name + ".py")
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        if raw != source_blob(PREPARATION_PIN, rel).replace(b"\r\n", b"\n"):
            raise ValueError("PREPARATION_HELPER_CHANGED:" + rel)
        provenance[rel] = digest(raw)
    sys.path.insert(0, str(folder))
    return importlib.import_module("b2l_prepare"), provenance


def destination(output: Path) -> Path:
    output = output.resolve()
    base = BUILD_ROOT.resolve()
    if output == base or not output.is_relative_to(base):
        raise ValueError("OUTPUT_OUTSIDE_NEW_PREPARED_CHILD")
    if not re.fullmatch(r"[A-Za-z0-9_./:\-]+", output.as_posix()):
        raise ValueError("UNSAFE_PROJECT_PATH")
    return output


def tool_identity(home: Path = TOOL_HOME) -> dict:
    """Read installation evidence, no shell or project execution."""
    home = home.resolve()
    paths = dict(shell="IDE/bin/gw_sh.exe", engine="IDE/bin/GowinSynthesis.exe",
                 core_library="IDE/bin/gowin.dll", device_db="IDE/data/device/device_info.csv",
                 package_db="IDE/data/device/device_package.csv",
                 package_json="IDE/data/device/GW5AST-138C/PBGA484A.json",
                 release_note="IDE/doc/RN100-1.9.11.03EducationE_Gowin Software Education Version Release Note.pdf",
                 user_guide="IDE/doc/EN/SUG100-4.4.2E_Gowin Software User Guide.pdf")
    identities = {}
    for label, rel in paths.items():
        path = home / rel
        raw = path.read_bytes()
        identities[label] = dict(path=path.as_posix(), bytes=len(raw), sha256=digest(raw))
    matched = {}
    for label in ("device_db", "package_db"):
        rows = list(csv.reader((home / paths[label]).read_text(encoding="utf-8-sig").splitlines()))
        match = [r for r in rows if len(r) > 3 and r[0] == DEVICE["index"]]
        if len(match) != 1 or match[0][1] != DEVICE["pn"] or match[0][3] != DEVICE["name"]:
            raise ValueError("INSTALLED_DEVICE_OR_PACKAGE_ROW:" + label)
        matched[label] = match[0]
    ref = ROOT / "code/rtl/138K_try/preparation_20261005/toolchain/138K_C/tool_probe.gprj"
    raw = ref.read_bytes()
    device = ET.fromstring(raw).find("Device")
    if device is None or device.attrib != {"name": DEVICE["name"], "pn": DEVICE["pn"]} or device.text.strip() != DEVICE["index"]:
        raise ValueError("EXISTING_C_PROJECT_DEVICE")
    return dict(home=home.as_posix(), installed_release="1.9.11.03 Education",
                release_evidence="Bundled RN100 title, not a CLI version query",
                identities=identities, installed_rows=matched,
                reference_project=dict(path=ref.relative_to(ROOT).as_posix(), sha256=digest(raw)),
                tool_executed_by_preparation=False,
                standalone_synthesis_license_or_success_verified=False)


def expected(output: Path) -> tuple[dict[str, bytes], dict]:
    output = destination(output)
    prep, helpers = helper()
    base, payload = prep.generated(output, 32, 1)
    if base["source_pin"] != FUNCTIONAL_PIN or len(base["inputs"]) != 22:
        raise ValueError("B2L_PIN_OR_INPUT_SET")
    data = dict(payload)
    data["b2l_inputs_plan.json"] = canonical(base)
    tool = tool_identity()
    project = ET.Element("Project")
    ET.SubElement(project, "Template").text = "FPGA"
    ET.SubElement(project, "Version").text = "5"
    ET.SubElement(project, "Device", name=DEVICE["name"], pn=DEVICE["pn"]).text = DEVICE["index"]
    listing = ET.SubElement(project, "FileList")
    for relative in base["source_order"]:
        ET.SubElement(listing, "File", path=(output / relative).as_posix(), type="file.verilog", enable="1")
    ET.SubElement(listing, "File", path=(output / "clock.sdc").as_posix(), type="file.sdc", enable="1")
    data[PROJECT] = ET.tostring(project, encoding="utf-8", xml_declaration=True) + b"\n"
    commands = ["cd {" + output.as_posix() + "}",
                "open_project {" + (output / PROJECT).as_posix() + "}",
                "set_option -top_module b2l_resource_probe",
                "set_option -verilog_std sysv2017",
                "set_option -synthesis_tool GowinSynthesis",
                "set_option -include_path {" + (output / "include").as_posix() + "}",
                "run syn"]
    data["run_synthesis_only.tcl"] = ("\n".join(commands) + "\n").encode("ascii")
    scripts = {}
    for name in ("prepare_138k_polyphony_resource.py", "preflight_138k_polyphony_synthesis.py", "inspect_polyphony_synthesis_report.py"):
        path = ROOT / "code/scripts" / name
        scripts[path.relative_to(ROOT).as_posix()] = digest(path.read_bytes())
    record = dict(schema=1, version=VERSION, source_pin=FUNCTIONAL_PIN,
                  preparation_pin=PREPARATION_PIN, preparation_helpers=helpers,
                  M2_scripts=scripts, configuration=base["configuration"],
                  output=output.as_posix(), device=DEVICE, tool=tool,
                  top="b2l_resource_probe", profile=base["configuration"]["profile"],
                  original_inputs=base["inputs"], source_files=14, project_files=15,
                  include_files=2, ROM_files=7, synthesis_authorized=False,
                  tool_run_count=0, proposed_stage="synthesis only; no PnR/STA/bitstream",
                  proposed_timeout_seconds=900, attempt_policy="ONE fresh attempt, no retry or fallback",
                  physical_resources="UNKNOWN", physical_STA="NOT_RUN", CST=None,
                  board_release_allowed=False, production_changed=False,
                  artifacts={n: dict(bytes=len(b), sha256=digest(b)) for n, b in sorted(data.items())})
    return data, record


def verify(output: Path) -> dict:
    output = destination(output)
    data, record = expected(output)
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    if actual != set(data) | {"frozen_receipt.json"}:
        raise ValueError("EXACT_PROJECT_FILE_SET")
    if (output / "frozen_receipt.json").read_bytes() != canonical(record):
        raise ValueError("CANONICAL_FROZEN_RECEIPT")
    for rel, raw in data.items():
        if (output / rel).read_bytes() != raw:
            raise ValueError("PROJECT_ARTIFACT_IDENTITY:" + rel)
    return dict(status="PREPARED_IDENTITY_PASS_NOT_AUTHORIZED", **record)


def prepare(output: Path) -> dict:
    output = destination(output)
    if output.exists():
        raise ValueError("REFUSE_EXISTING_PROJECT")
    data, record = expected(output)
    output.mkdir(parents=True, exist_ok=False)
    for rel, raw in data.items():
        path = output / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    with (output / "frozen_receipt.json").open("xb") as stream:
        stream.write(canonical(record))
    return verify(output)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--check", action="store_true")
    args = cli.parse_args()
    try:
        result = verify(args.output) if args.check else prepare(args.output)
        print(json.dumps({k: result[k] for k in ("status", "configuration", "device", "source_files", "project_files", "synthesis_authorized")}, indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps(dict(status="REJECT", reason=str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
