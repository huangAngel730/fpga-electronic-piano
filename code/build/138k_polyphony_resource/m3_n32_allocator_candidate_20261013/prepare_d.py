"""Build/verify the exact N32-D resource project. No tool launch exists here."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import socket
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GUARD_DIR = ROOT / "code/software/t061_clock_contract_guard_candidate_20261013"
sys.path.insert(0, str(GUARD_DIR))
import clock_guard as guard

DEFAULT_TOOL_HOME = Path("E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03")
SEALS = {
    "A": ROOT / "code/software/t061_allocator_reference_candidate_20261013/SEALED_FUNCTION_RECOVERY_RESULT_20261014_R01",
    "B": ROOT / "code/tb/audio/t061_n32_allocator_candidate_20261013/B/SEALED_RESULT_R01",
    "C": ROOT / "code/tb/audio/t061_n32_allocator_candidate_20261013/C/SEALED_SEGMENTED_RESULT_R07",
}
SEAL_PINS = {
    "A": "da5451dd7f75f9d9cb01bae4fac47298f389e83fbd8e9c84a96c5046a0d2b1b0",
    "B": "ec8b918d598f205b6b4a37aa2ee670e809180778941184a9eecbeb62c8f48409",
    "C": "ab5f5d3b08ecc1002323b59547007d9021ecee653feb1529cb33472e844a726e",
}
B_PLAN_PIN = "e93518fdb751fe2204936b469271c85c2b83afe7343b3850ed9a309e4381686b"
ROM_MAP_PIN = "6622c4210ed6abeb89a80f50db5898624f72df3a6a416b54aa3a73fea1378882"
TOOL_REFERENCE = ROOT / "code/build/138k_polyphony_resource/prom_candidate_20261013_01/resource_receipt.json"
TOOL_REFERENCE_PIN = "f77a526318cd213b164e9bed5d0d1d0f2ca19aad89a61813f082d7d5971151bf"
TOOL_INVENTORY_PIN = "b99201ced24fbf9023a10e8ddd466bbad9951327c56d54a29ae9ef8a8802394a"


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def blob_identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def identity(path):
    return {"bytes": Path(path).stat().st_size, "sha256": guard.sha256(Path(path))}


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def checked_archive(stage):
    folder = SEALS[stage]
    seal_raw = (folder / "seal.json").read_bytes()
    require(blob_identity(seal_raw)["sha256"] == SEAL_PINS[stage], "D_SEAL_ANCHOR_" + stage)
    seal = json.loads(seal_raw)
    manifest_raw = (folder / "MANIFEST.json").read_bytes()
    if "manifest" in seal:
        require(blob_identity(manifest_raw) == seal["manifest"], "D_SEAL_MANIFEST_" + stage)
    else:
        require(stage == "A", "D_MISSING_MANIFEST_BINDING_" + stage)
        # A binds the entire ZIP; its original manifest is an anchored member.
    raw = base64.b64decode((folder / "snapshot.zip.b64").read_bytes().strip(), validate=True)
    require(blob_identity(raw) == seal["snapshot"], "D_SEAL_ARCHIVE_" + stage)
    bundle = zipfile.ZipFile(io.BytesIO(raw))
    manifest = json.loads(manifest_raw)
    require(len(bundle.namelist()) == len(set(bundle.namelist())) and
            set(bundle.namelist()) == set(manifest["files"]) | {"MANIFEST.json"},
            "D_SEAL_MEMBER_CLOSURE_" + stage)
    require(bundle.read("MANIFEST.json") == manifest_raw, "D_ARCHIVED_MANIFEST_" + stage)
    for name, expected_id in manifest["files"].items():
        require(blob_identity(bundle.read(name)) == expected_id, "D_ARCHIVE_MEMBER_" + name)
    return bundle, seal_raw, manifest_raw


def tool_identity(home):
    home = home.resolve()
    require(identity(TOOL_REFERENCE)["sha256"] == TOOL_REFERENCE_PIN, "D_OLD_TOOL_REFERENCE_PIN")
    reference = json.loads(TOOL_REFERENCE.read_text(encoding="utf-8"))["tool"]
    paths = {
        "shell": "IDE/bin/gw_sh.exe", "engine": "IDE/bin/GowinSynthesis.exe",
        "core_library": "IDE/bin/gowin.dll", "device_db": "IDE/data/device/device_info.csv",
        "package_db": "IDE/data/device/device_package.csv",
        "package_json": "IDE/data/device/GW5AST-138C/PBGA484A.json",
        "release_note": "IDE/doc/RN100-1.9.11.03EducationE_Gowin Software Education Version Release Note.pdf",
        "user_guide": "IDE/doc/EN/SUG100-4.4.2E_Gowin Software User Guide.pdf",
    }
    identities = {}
    for name, relative in paths.items():
        path = home / relative
        actual = identity(path)
        require(actual == {key: reference["identities"][name][key] for key in ("bytes", "sha256")},
                "D_INSTALLED_TOOL_VERSION_DRIFT_" + name)
        identities[name] = {"path": str(path), **actual, "availability": "AVAILABLE"}
    rows = {}
    for name in ("device_db", "package_db"):
        database = Path(identities[name]["path"])
        matches = [row for row in csv.reader(database.read_text(encoding="utf-8-sig").splitlines())
                   if row and row[0] == guard.DEVICE["index"]]
        require(len(matches) == 1 and matches[0] == reference["installed_rows"][name],
                "D_INSTALLED_DEVICE_ROW_" + name)
        rows[name] = matches[0]
    inventory = {}
    for directory in (home / "IDE/bin", home / "IDE/data/device/GW5AST-138C"):
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                require(not path.is_symlink(), "D_TOOL_LINK")
                inventory[path.relative_to(home).as_posix()] = identity(path)
    inventory_raw = json.dumps(inventory, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    require(blob_identity(inventory_raw)["sha256"] == TOOL_INVENTORY_PIN, "D_STATIC_TOOL_INVENTORY_ANCHOR")
    return {"machine": socket.gethostname(), "home": str(home),
            "installed_release": reference["installed_release"], "identities": identities,
            "installed_device_rows": rows, "execution_ready": True, "missing_required": [],
            "static_inventory": inventory,
            "inventory_scope": ["IDE/bin/**", "IDE/data/device/GW5AST-138C/**"],
            "dynamic_loader_and_license": "NOT_EXECUTED_NOT_PROVEN"}


def expected(project, tool_home=DEFAULT_TOOL_HOME):
    """Reconstruct every byte from immutable A/B/C archives and local tool files."""
    project = Path(project).resolve()
    require(re.fullmatch(r"[A-Za-z0-9_./:\\-]+", str(project)), "D_ASCII_PROJECT_REQUIRED")
    bundles, payload, evidence, entries = {}, {}, {}, []

    def add(name, raw, role, origin=None):
        require(name not in payload, "D_DESTINATION_COLLISION")
        payload[name] = raw
        entry = {"path": name, **blob_identity(raw), "role": role}
        if origin is not None:
            entry["origin_snapshot"] = origin
        entries.append(entry)
        return entry

    def add_evidence(name, filename, raw):
        row = add("evidence/" + filename, raw, "evidence")
        evidence[name] = {"path": row["path"], "sha256": row["sha256"]}

    for stage in ("A", "B", "C"):
        bundles[stage], seal_raw, manifest_raw = checked_archive(stage)
        add_evidence(stage, stage + "_seal.json", seal_raw)
        add_evidence(stage + "_manifest", stage + "_MANIFEST.json", manifest_raw)
    bplan_raw = bundles["B"].read("prepared/plan.json")
    require(blob_identity(bplan_raw)["sha256"] == B_PLAN_PIN, "D_B_PLAN_PIN")
    add_evidence("B_plan", "b_plan.json", bplan_raw)
    a_result = bundles["A"].read("evidence/m3_n32_a_function_recovery_run_20261014_02/receipt.json")
    b_result = bundles["B"].read("evidence/continuation/receipt.json")
    c_result = bundles["C"].read("execution/receipt.json")
    require(json.loads(a_result)["status"] == "ALLOCATOR_COMPARISON_AND_MUTATIONS_PASS", "D_A_NOT_PASS")
    require(json.loads(b_result)["status"] == "N32_B_R1_EVENT_AUDIO_AND_MUTANTS_PASS_T061_PARTIAL", "D_B_NOT_PASS")
    require(json.loads(c_result)["status"] == "N32_C_STRESS_PASS_T061_PARTIAL", "D_C_SUFFIX_NOT_PASS")
    c_manifest = json.loads(payload["evidence/C_MANIFEST.json"])
    require(c_manifest["status"] == "N32_C_SEGMENTED_FUNCTION_MATH_PASS_T061_PARTIAL" and
            c_manifest["composition"]["single_continuous_full_C_run"] is False, "D_C_SCOPE")
    for name, raw in (("A_result", a_result), ("B_result", b_result), ("C_suffix_result", c_result),
                      ("C_prefix_report", bundles["C"].read("composition/prefix_report.json")),
                      ("C_prefix_receipt", bundles["C"].read("history/n32cpe02/receipt.json"))):
        add_evidence(name, name + ".json", raw)
    plan = json.loads(bplan_raw)
    functional = [row for row in plan["inputs"] if row["role"] == "HDL"][:18]
    support = [row for row in plan["inputs"] if row["snapshot"].endswith((".svh", ".mem"))]
    require(len(functional) == 18 and len(support) == 7, "D_FUNCTIONAL_SOURCE_COUNT")
    source_order = []
    for row in functional + support:
        original = row["snapshot"]
        raw = bundles["B"].read("prepared/snapshot/" + original)
        require(blob_identity(raw) == {key: row[key] for key in ("bytes", "sha256")}, "D_B_SOURCE_PIN")
        suffix = Path(original).suffix
        role = "source" if suffix == ".sv" else "include" if suffix == ".svh" else "rom"
        folder = {"source": "sources", "include": "include", "rom": "rom"}[role]
        target = folder + "/" + Path(original).name
        add(target, raw, role, original)
        if role == "source":
            source_order.append(target)
    top_name = "sources/m3_n32_resource.sv"
    add(top_name, (HERE / "m3_n32_resource.sv").read_bytes(), "top")
    source_order.append(top_name)
    rom_map = ROOT / "code/rtl/common/m2_n32_prom_candidate_20261013/candidate_receipt.json"
    require(identity(rom_map)["sha256"] == ROM_MAP_PIN, "D_ROM_MAPPING_PIN")
    add_evidence("ROM_mapping", "prom_candidate_receipt.json", rom_map.read_bytes())
    add_evidence("prior_tool_reference", "prior_resource_receipt.json", TOOL_REFERENCE.read_bytes())
    project_fields = {"gprj": "n32_resource.gprj", "tcl": "run_synthesis_only.tcl",
                      "sdc": "clock.sdc", "top_source": top_name,
                      "include_dirs": ["include"], "source_order": source_order}
    xml = ET.Element("Project")
    ET.SubElement(xml, "Template").text = "FPGA"
    ET.SubElement(xml, "Version").text = "5"
    ET.SubElement(xml, "Device", name=guard.DEVICE["name"], pn=guard.DEVICE["pn"]).text = guard.DEVICE["index"]
    listing = ET.SubElement(xml, "FileList")
    for relative in source_order + ["clock.sdc"]:
        ET.SubElement(listing, "File", path=(project / relative).as_posix(),
                      type="file.sdc" if relative.endswith(".sdc") else "file.verilog", enable="1")
    add("n32_resource.gprj", ET.tostring(xml, encoding="utf-8", xml_declaration=True) + b"\n", "gprj")
    add("clock.sdc", guard.SDC.encode("ascii"), "sdc")
    add("run_synthesis_only.tcl", guard.tcl_text(project, project_fields, "m3_n32_resource").encode("ascii"), "tcl")
    add_evidence("generator", "prepare_d.py", Path(__file__).read_bytes())
    add_evidence("static_guard", "clock_guard.py", (GUARD_DIR / "clock_guard.py").read_bytes())
    manifest = {"schema": "N32_D_PREPARE_V1", "status": "PREPARED_NOT_EXECUTED",
                "top": "m3_n32_resource", "configuration": guard.CONFIGURATION,
                "device": guard.DEVICE, "clock": guard.CLOCK, "execution": guard.EXECUTION,
                "macros": [], "project": project_fields, "files": entries, "evidence": evidence,
                "tool": tool_identity(Path(tool_home)), "T061_complete": False,
                "synthesis_default_frequency_mhz": 100, "synthesis_frequency_is_physical_sta": False,
                "synthesis_default_basis": "HISTORICAL_SAME_TOOL_DEFAULT_NOT_A_NEW_REPORT",
                "new_top_validation": "STATIC_ONLY_NOT_RTL_EXECUTED",
                "C_scope": "TWO_SEPARATELY_QUALIFIED_SEGMENTS_NOT_ONE_CONTINUOUS_RUN"}
    payload["manifest.json"] = canonical(manifest)
    return payload, manifest


def verify(project):
    project = Path(project).resolve()
    actual_manifest = guard.json_file(project / "manifest.json")
    payload, _ = expected(project, Path(actual_manifest["tool"]["home"]))
    actual_files = {p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file()}
    require(actual_files == set(payload), "D_EXACT_PROJECT_FILE_SET")
    for name, raw in payload.items():
        require((project / name).read_bytes() == raw, "D_EXACT_RECONSTRUCTION:" + name)
    return guard.validate(project, trusted_manifest_sha=blob_identity(payload["manifest.json"])["sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify", "execute"))
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--tool-home", type=Path, default=DEFAULT_TOOL_HOME)
    args = parser.parse_args()
    if args.command == "execute":
        print(json.dumps({"status": "REJECTED", "diagnostic": "D_NEW_EXACT_SYNTHESIS_PERMISSION_REQUIRED",
                          "actual_tool_calls": 0}))
        return 1
    started = time.monotonic()
    try:
        project = args.project.resolve()
        base = (HERE / "prepared").resolve()
        require(project != base and project.is_relative_to(base), "D_NEW_PROJECT_SCOPE")
        if args.command == "prepare":
            require(not project.exists(), "D_PROJECT_ALREADY_EXISTS")
            payload, _ = expected(project, args.tool_home)
            project.mkdir(parents=True)
            for name, raw in payload.items():
                target = project / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(raw)
        result = verify(project)
        require(time.monotonic() - started < 900, "D_PREPARATION_TOTAL_BUDGET")
        print(json.dumps({**result, "elapsed_seconds": time.monotonic() - started}, sort_keys=True))
        return 0
    except (ValueError, KeyError, OSError, ET.ParseError) as error:
        print(json.dumps({"status": "REJECTED", "diagnostic": str(error), "actual_tool_calls": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
