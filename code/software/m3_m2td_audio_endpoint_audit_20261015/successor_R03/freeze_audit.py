"""B successor: recover and verify frozen _06 bytes without invoking any EDA.

No execution flag exists. Missing input/object/tool authority leaves the physical
one-shot allowance UNCONSUMED. A path literal reverse-map is a DERIVATION, not an
original recovered netlist or permission to silently relocate ROM references.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"
PHYSICAL = REPO / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip"
PORTABLE = REPO / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip"
P_SHA = "17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff"
S_SHA = "1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf"
TOOL_CANDIDATES = (
    Path("E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe"),
    Path("D:/program/gaoyunFPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe"),
)


def identity(blob: bytes) -> dict:
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def safe_relative(name: str) -> str:
    name = name.replace("\\", "/")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or ":" in name or not name.startswith("inputs/"):
        raise ValueError("invalid frozen relative name")
    return name


def inverse_paths(raw: bytes, operations: list[dict]) -> tuple[bytes, list[dict]]:
    record = []
    seen = set()
    for op in operations:
        old, new = op["old"].encode("utf-8"), op["new"].encode("utf-8")
        pair = old, new
        if pair in seen:
            record.append({**op, "classification": "DUPLICATE_RECORDED_MAPPING", "replacements": 0})
            continue
        seen.add(pair)
        count = raw.count(new)
        raw = raw.replace(new, old)
        record.append({**op, "classification": "REVERSE_PATH_DERIVATION", "replacements": count})
    return raw, record


def audit(output: Path) -> dict:
    output = output.resolve()
    if output.parent != DOC.resolve() or output.exists():
        raise ValueError("fresh direct child of B successor docs required")
    before = {str(p): identity(p.read_bytes()) for p in (PHYSICAL, PORTABLE, Path(__file__))}
    if before[str(PHYSICAL)]["sha256"] != P_SHA or before[str(PORTABLE)]["sha256"] != S_SHA:
        raise ValueError("original input archive SHA mismatch")
    recovered = {}
    missing = []
    with zipfile.ZipFile(PHYSICAL) as physical, zipfile.ZipFile(PORTABLE) as portable:
        original_receipt = physical.read("PREPARATION_RECEIPT.json")
        portable_receipt = portable.read("PREPARATION_RECEIPT.json")
        physical_json, portable_json = json.loads(original_receipt), json.loads(portable_receipt)
        physical_names, portable_names = physical.namelist(), portable.namelist()
        records = []
        for windows_name, expected in physical_json["input_files"].items():
            name = safe_relative(windows_name)
            raw = None
            provenance = None
            if name in portable_names:
                raw, operations = inverse_paths(portable.read(name), portable_json["path_adaptations"].get(name, []))
                provenance = {"archive_sha256": S_SHA, "member": name,
                              "portable_identity": identity(portable.read(name)), "inverse_operations": operations,
                              "classification": "DERIVED_RECONSTRUCTION" if operations else "ORIGINAL_PORTABLE_MEMBER"}
            elif name.removeprefix("inputs/") in physical_names:
                member = name.removeprefix("inputs/")
                raw = physical.read(member)
                provenance = {"archive_sha256": P_SHA, "member": member, "classification": "ORIGINAL_PHYSICAL_ZIP_MEMBER"}
            if raw is None or identity(raw) != expected:
                missing.append({"path": name, "expected": expected,
                                "candidate_identity": identity(raw) if raw is not None else None,
                                "reason": "ABSENT_MEMBER" if raw is None else "RECONSTRUCTED_SHA_MISMATCH"})
                continue
            recovered[name] = raw
            records.append({"path": name, "expected": expected, "actual": identity(raw), "provenance": provenance})
        html = physical.read("pnr/timing.html")
        project = physical.read("project.gprj")
        project_files = [e.attrib["path"] for e in ET.fromstring(project).findall("./FileList/File")
                         if e.attrib.get("enable") == "1"]
        compiled_basenames = {PurePosixPath(name).name for name in project_files}
        source_paths = []
        for name, blob in recovered.items():
            if not name.endswith((".sv", ".v", ".svh")):
                continue
            paths = re.findall(rb'"([A-Za-z]:/[^"\r\n]+\.(?:mem|hex|svh))"', blob)
            for raw_path in paths:
                location = raw_path.decode("utf-8")
                path = Path(location)
                source_paths.append({"source": name, "literal": location,
                                     "exists_on_this_machine": path.is_file(),
                                     "source_in_gprj_filelist": PurePosixPath(name).name in compiled_basenames,
                                     "same_source_execution_relocated": False})
        output.mkdir(parents=True)
        for name, blob in recovered.items():
            dest = output / "derived_original_bytes" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
        for name, blob in (("physical_PREPARATION_RECEIPT.json", original_receipt),
                           ("portable_PREPARATION_RECEIPT.json", portable_receipt),
                           ("original_project.gprj", project)):
            (output / name).write_bytes(blob)
    tools = []
    for path in TOOL_CANDIDATES:
        entry = {"path": str(path), "exists": path.is_file(), "version_executed": False}
        if path.is_file():
            entry.update(identity(path.read_bytes()))
            before[str(path)] = identity(path.read_bytes())
        tools.append(entry)
    after = {name: identity(Path(name).read_bytes()) for name in before}
    result = {
        "schema": "M3_M2TD_R03_FROZEN_INPUT_AUDIT_V1", "status": "BLOCKED_INPUT",
        "level": "L0_L1_DERIVED_IDENTITY_PREPARATION", "input_expected_count": len(physical_json["input_files"]),
        "matched_count": len(records), "matched": records, "missing": missing,
        "physical_archive_netlists": [n for n in physical_names if n.endswith(".vg")],
        "netlist_on_machine": "UNKNOWN_NOT_FOUND_IN_DECLARED_LOCATIONS",
        "report_base_name_count": {n: html.count(n.encode()) for n in ("base_s1", "base_s2")},
        "report_tool_version": "V1.9.11.03 Education", "tool_candidates": tools,
        "frozen_absolute_path_literals": source_paths,
        "unique_absolute_literal_count": len({p["literal"] for p in source_paths}),
        "literal_occurrences_in_gprj_sources": sum(p["source_in_gprj_filelist"] for p in source_paths),
        "literal_occurrences_in_non_gprj_sources": sum(not p["source_in_gprj_filelist"] for p in source_paths),
        "gprj_file_count": len(project_files),
        "compiled_is_not_proof_of_elaboration": True,
        "absolute_literal_unavailable_count": sum(not p["exists_on_this_machine"] for p in source_paths),
        "input_before": before, "input_after": after, "unchanged": before == after,
        "physical_allowance": {"consumed": False, "tool_starts": 0, "one_shot_marker": None,
                               "reason": "Frozen literal paths cannot be resolved in authorized new stage; query/dependency prerequisites unverified",
                               "historical_netlist_absence_alone_does_not_forbid_new_same_source_build": True},
        "board_release_allowed": False, "new_sta_executed": False,
        "not_claimed": ["post-PnR netlist inspected", "missing source byte inferred", "source path rewrite authorized",
                        "same version tool executable launched", "new targeted STA PASS"]}
    (output / "AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "expected": result["input_expected_count"],
                      "matched": len(records), "missing": len(missing), "unavailable_path_literals": result["absolute_literal_unavailable_count"],
                      "physical_tool_starts": 0, "unchanged": result["unchanged"]}))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.output)
        return 0 if result["unchanged"] else 1
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        print(f"FROZEN_INPUT_AUDIT_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
