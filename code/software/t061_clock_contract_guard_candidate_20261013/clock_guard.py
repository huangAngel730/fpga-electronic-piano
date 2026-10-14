"""N32-D prepare-only static contract; never launches an HDL or EDA tool.

This is an allow-list validator, not a Tcl/SDC interpreter.  It accepts the
small generated project dialect only.  A positive result proves identity and
explicit constraint transmission, never synthesis mapping or physical timing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import socket
import xml.etree.ElementTree as ET


TRUSTED_EVIDENCE = {
    "A": "da5451dd7f75f9d9cb01bae4fac47298f389e83fbd8e9c84a96c5046a0d2b1b0",
    "B": "ec8b918d598f205b6b4a37aa2ee670e809180778941184a9eecbeb62c8f48409",
    "C": "ab5f5d3b08ecc1002323b59547007d9021ecee653feb1529cb33472e844a726e",
    "B_plan": "e93518fdb751fe2204936b469271c85c2b83afe7343b3850ed9a309e4381686b",
    "A_result": "650db857665f2520587d583a58c7051bade033fcf40af04207392cb3c1f96bb1",
    "prior_tool_reference": "f77a526318cd213b164e9bed5d0d1d0f2ca19aad89a61813f082d7d5971151bf",
}
TRUSTED_TOP_SHA = "a7d193a27994a218fa6961b7eae66be29e648b9df2a2470d436982f063ecbb3f"
TOOL_PATHS = {
    "shell": "IDE/bin/gw_sh.exe", "engine": "IDE/bin/GowinSynthesis.exe",
    "core_library": "IDE/bin/gowin.dll", "device_db": "IDE/data/device/device_info.csv",
    "package_db": "IDE/data/device/device_package.csv",
    "package_json": "IDE/data/device/GW5AST-138C/PBGA484A.json",
    "release_note": "IDE/doc/RN100-1.9.11.03EducationE_Gowin Software Education Version Release Note.pdf",
    "user_guide": "IDE/doc/EN/SUG100-4.4.2E_Gowin Software User Guide.pdf",
}
INVENTORY_SCOPE = ["IDE/bin/**", "IDE/data/device/GW5AST-138C/**"]
TRUSTED_TOOL_INVENTORY_SHA = "b99201ced24fbf9023a10e8ddd466bbad9951327c56d54a29ae9ef8a8802394a"
DEVICE = {
    "name": "GW5AST-138C",
    "pn": "GW5AST-LV138PG484AC1/I0",
    "index": "gw5ast138c-007",
}
CLOCK = {
    "port": "clk", "name": "sys_clk", "period_ns": 25.0,
    "setup_uncertainty_ns": 1.0, "hold_uncertainty_ns": 0.65,
}
CONFIGURATION = {
    "N": 32, "response": 1,
    "profile": "audio_and_public_read_no_injection",
}
EXECUTION = {
    "authorized": False, "tool_calls": 0, "resources": "UNKNOWN",
    "STA": "NOT_RUN", "PnR": False, "device_operation": False,
}
SDC = (
    "create_clock -name sys_clk -period 25.000 [get_ports {clk}]\n"
    "set_clock_uncertainty -setup 1.000 [get_clocks {sys_clk}]\n"
    "set_clock_uncertainty -hold 0.650 [get_clocks {sys_clk}]\n"
)


class ContractError(ValueError):
    """A specific static rejection, never an EDA verdict."""


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ContractError(diagnostic)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_file(path: Path) -> dict:
    def no_duplicates(pairs):
        answer = {}
        for key, value in pairs:
            require(key not in answer, "D_DUPLICATE_JSON_KEY")
            answer[key] = value
        return answer
    value = json.loads(path.read_text(encoding="utf-8"),
                       object_pairs_hook=no_duplicates)
    require(isinstance(value, dict), "D_JSON_OBJECT_REQUIRED")
    return value


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def local_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and "\\" not in relative,
            "D_NON_CANONICAL_PATH")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ":" not in relative and
            all(part not in (".", "..") for part in pure.parts) and
            str(pure) == relative, "D_PATH_ESCAPE")
    result = root.joinpath(*pure.parts)
    require(result.resolve().is_relative_to(root.resolve()), "D_PATH_ESCAPE")
    require(not any(p.is_symlink() for p in (result, *result.parents)),
            "D_LINK_REJECTED")
    return result


def identity(path: Path, entry: dict, label: str) -> None:
    require(path.is_file(), "D_MISSING_" + label)
    require(type(entry.get("bytes")) is int and entry["bytes"] >= 0,
            "D_SIZE_TYPE_" + label)
    require(re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256"))) is not None,
            "D_SHA_TYPE_" + label)
    require(path.stat().st_size == entry["bytes"] and
            sha256(path) == entry["sha256"], "D_IDENTITY_" + label)


def command_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def tcl_text(root: Path, project: dict, top: str) -> str:
    """The only accepted inactive future synthesis recipe."""
    includes = ";".join(str(local_path(root, p)).replace("\\", "/")
                        for p in project["include_dirs"])
    root_text = str(root.resolve()).replace("\\", "/")
    gprj = str(local_path(root, project["gprj"])).replace("\\", "/")
    return (f"cd {{{root_text}}}\nopen_project {{{gprj}}}\n"
            f"set_option -top_module {top}\n"
            "set_option -verilog_std sysv2017\n"
            f"set_option -include_path {{{includes}}}\nrun syn\n")


def check_project(root: Path, manifest: dict, file_map: dict) -> None:
    project = manifest["project"]
    require(set(project) == {"gprj", "tcl", "sdc", "top_source",
                             "include_dirs", "source_order"},
            "D_PROJECT_FIELDS")
    sources = project["source_order"]
    require(isinstance(sources, list) and len(sources) == 19 and
            len(set(sources)) == len(sources) and
            sources[-1] == project["top_source"], "D_SOURCE_ORDER")
    for path in sources:
        require(file_map.get(path, {}).get("role") in ("source", "top"),
                "D_SOURCE_NOT_IN_MANIFEST")
    require(file_map[project["top_source"]]["role"] == "top",
            "D_TOP_ROLE")
    require(project["include_dirs"] == ["include"], "D_INCLUDE_DIRS")
    for key, role in (("gprj", "gprj"), ("tcl", "tcl"), ("sdc", "sdc")):
        require(file_map.get(project[key], {}).get("role") == role,
                "D_ENGINEERING_FILE_ROLE")
    sdc = local_path(root, project["sdc"])
    require(file_map.get(project["sdc"], {}).get("role") == "sdc",
            "D_SDC_NOT_IN_MANIFEST")
    require(command_lines(sdc.read_text(encoding="utf-8")) ==
            command_lines(SDC), "D_40MHZ_SDC_CONTRACT")
    gprj = ET.fromstring(local_path(root, project["gprj"]).read_bytes())
    require(gprj.tag == "Project" and
            [node.tag for node in gprj] ==
            ["Template", "Version", "Device", "FileList"],
            "D_GPRJ_DIALECT")
    require(gprj.findtext("Template") == "FPGA" and
            gprj.findtext("Version") == "5", "D_GPRJ_FORMAT")
    device = gprj.find("Device")
    require(device is not None and device.attrib ==
            {"name": DEVICE["name"], "pn": DEVICE["pn"]} and
            device.text == DEVICE["index"], "D_GPRJ_DEVICE")
    expected = [(str(local_path(root, p).resolve()).replace("\\", "/"),
                 "file.verilog") for p in sources]
    expected.append((str(sdc.resolve()).replace("\\", "/"), "file.sdc"))
    observed = []
    for item in gprj.find("FileList"):
        require(item.tag == "File" and set(item.attrib) ==
                {"path", "type", "enable"} and
                item.attrib["enable"] == "1", "D_GPRJ_FILE_FIELDS")
        observed.append((item.attrib["path"].replace("\\", "/"),
                         item.attrib["type"]))
    require(observed == expected, "D_GPRJ_SDC_SOURCE_TRANSMISSION")
    actual = local_path(root, project["tcl"]).read_text(encoding="utf-8")
    require(command_lines(actual) ==
            command_lines(tcl_text(root, project, manifest["top"])),
            "D_TCL_TOP_SDC_TRANSMISSION")
    top = local_path(root, project["top_source"]).read_text(encoding="utf-8")
    clean = re.sub(r"//[^\n]*|/\*.*?\*/", "", top, flags=re.S)
    require(re.findall(r"\bmodule\s+(\w+)", clean) == [manifest["top"]],
            "D_TOP_MODULE")
    require(re.search(r"b_n32_event_audio_prom\s*#\s*\(\s*\.N\(32\)\s*,\s*"
                      r"\.RESPONSE\(1\)\s*\)", clean) is not None,
            "D_TOP_N32_R1")
    for port, value in (("inject_valid", "1'b0"), ("inject_tag", "77'd0"),
                        ("inject_context", "74'd0")):
        require(re.search(r"\." + port + r"\s*\(\s*" + re.escape(value) +
                          r"\s*\)", clean) is not None,
                "D_TOP_INJECTION_ENABLED")
    require(sha256(local_path(root, project["top_source"])) == TRUSTED_TOP_SHA,
            "D_TOP_BYTE_CONTRACT")


def validate(project_root: Path, manifest_path: Path | None = None,
             trusted_manifest_sha: str | None = None) -> dict:
    root = project_root.resolve()
    path = manifest_path or root / "manifest.json"
    if trusted_manifest_sha is not None:
        require(sha256(path) == trusted_manifest_sha, "D_MANIFEST_ANCHOR")
    manifest = json_file(path)
    require(manifest.get("schema") == "N32_D_PREPARE_V1",
            "D_MANIFEST_SCHEMA")
    require(manifest.get("status") == "PREPARED_NOT_EXECUTED",
            "D_STATUS_NOT_PREPARE")
    require(manifest.get("top") == "m3_n32_resource", "D_TOP_IDENTITY")
    for key, expected in (("device", DEVICE), ("clock", CLOCK),
                          ("configuration", CONFIGURATION),
                          ("execution", EXECUTION)):
        require(canonical(manifest.get(key)) == canonical(expected),
                "D_" + key.upper() + "_CONTRACT")
    require(manifest.get("T061_complete") is False, "D_COMPLETE_CLAIM")
    require(manifest.get("macros") == [], "D_MACROS_FORBIDDEN")
    require(manifest.get("synthesis_default_frequency_mhz") == 100 and
            type(manifest["synthesis_default_frequency_mhz"]) is int and
            manifest.get("synthesis_frequency_is_physical_sta") is False,
            "D_DEFAULT100_IS_NOT_STA40")
    entries = manifest.get("files")
    require(isinstance(entries, list) and entries, "D_EMPTY_FILE_CLOSURE")
    file_map = {}
    for entry in entries:
        relative = entry["path"]
        require(relative not in file_map, "D_DUPLICATE_FILE")
        require(entry.get("role") in {"source", "top", "rom", "include",
                                      "sdc", "gprj", "tcl", "evidence"},
                "D_FILE_ROLE")
        identity(local_path(root, relative), entry, "FILE")
        file_map[relative] = entry
    evidence = manifest.get("evidence", {})
    require(set(evidence) >= set(TRUSTED_EVIDENCE), "D_EVIDENCE_CLOSURE")
    for entry in evidence.values():
        require(file_map.get(entry["path"], {}).get("sha256") ==
                entry["sha256"] and file_map[entry["path"]]["role"] == "evidence",
                "D_EVIDENCE_FILE_BINDING")
    for name, expected_sha in TRUSTED_EVIDENCE.items():
        entry = evidence[name]
        require(entry["sha256"] == expected_sha and
                file_map.get(entry["path"], {}).get("sha256") == expected_sha,
                "D_TRUSTED_EVIDENCE_" + name)
        require(sha256(local_path(root, entry["path"])) == expected_sha,
                "D_TRUSTED_EVIDENCE_" + name)
    a_result = json_file(local_path(root, evidence["A_result"]["path"]))
    require(a_result.get("status") == "ALLOCATOR_COMPARISON_AND_MUTATIONS_PASS",
            "D_A_FUNCTION_RESULT")
    plan = json_file(local_path(root, evidence["B_plan"]["path"]))
    # Exactly the eighteen functional HDL dependencies, not the observation
    # shell, simulator primitive model, testbenches or software helpers.
    functional = [x for x in plan["inputs"] if x["role"] == "HDL"][:18]
    support = [x for x in plan["inputs"] if
               x["snapshot"].endswith((".svh", ".mem"))]
    pins = {x["snapshot"]: x for x in functional + support}
    copies = [x for x in entries if x["role"] in
              {"source", "include", "rom"}]
    require(len(copies) == len(pins) and
            {x.get("origin_snapshot") for x in copies} == set(pins),
            "D_TESTED_DEPENDENCY_CLOSURE")
    for entry in copies:
        pin = pins[entry["origin_snapshot"]]
        require(entry["sha256"] == pin["sha256"] and
                entry["bytes"] == pin["bytes"], "D_OLD_OR_CHANGED_SOURCE")
        suffix = PurePosixPath(pin["snapshot"]).suffix
        role = "include" if suffix == ".svh" else (
            "rom" if suffix == ".mem" else "source")
        directory = {"source": "sources", "include": "include", "rom": "rom"}[role]
        require(entry["role"] == role and entry["path"] ==
                directory + "/" + PurePosixPath(pin["snapshot"]).name,
                "D_DEPENDENCY_LOCATION")
    observed_order = [file_map[x].get("origin_snapshot")
                      for x in manifest["project"]["source_order"][:-1]]
    require(observed_order == [x["snapshot"] for x in functional],
            "D_TESTED_SOURCE_ORDER")
    check_project(root, manifest, file_map)
    tool = manifest.get("tool", {})
    require(tool.get("machine") == socket.gethostname(), "D_MACHINE_BINDING")
    identities = tool.get("identities", {})
    required_tools = {"shell", "engine", "core_library", "device_db",
                      "package_db", "package_json", "release_note", "user_guide"}
    require(set(identities) == required_tools, "D_TOOL_CLOSURE")
    home = Path(tool["home"]).resolve()
    prior = json_file(local_path(root, evidence["prior_tool_reference"]["path"]))
    prior_identities = prior["tool"]["identities"]
    missing = []
    for name, entry in identities.items():
        require(Path(entry["path"]).resolve() ==
                local_path(home, TOOL_PATHS[name]).resolve(),
                "D_TOOL_PATH_" + name)
        if entry.get("availability") == "MISSING":
            require(entry.get("bytes") is None and entry.get("sha256") is None
                    and not Path(entry["path"]).is_file(),
                    "D_FAKE_MISSING_TOOL_" + name)
            missing.append(name)
        else:
            require(entry.get("availability", "AVAILABLE") == "AVAILABLE",
                    "D_TOOL_AVAILABILITY")
            identity(Path(entry["path"]), entry, "TOOL_" + name)
            require({key: entry[key] for key in ("bytes", "sha256")} ==
                    {key: prior_identities[name][key] for key in ("bytes", "sha256")},
                    "D_TRUSTED_INSTALLED_TOOL_" + name)
    require(tool.get("execution_ready") is (not missing) and
            tool.get("missing_required") == sorted(missing),
            "D_TOOL_READINESS")
    require(tool.get("inventory_scope") == INVENTORY_SCOPE,
            "D_TOOL_INVENTORY_SCOPE")
    inventory = tool.get("static_inventory")
    require(isinstance(inventory, dict) and bool(inventory),
            "D_TOOL_INVENTORY_REQUIRED")
    actual_inventory = set()
    for relative_directory in ("IDE/bin", "IDE/data/device/GW5AST-138C"):
        directory = local_path(home, relative_directory)
        require(directory.is_dir(), "D_TOOL_INVENTORY_DIRECTORY")
        for item in directory.rglob("*"):
            require(not item.is_symlink() and
                    not (hasattr(item, "is_junction") and item.is_junction()),
                    "D_TOOL_INVENTORY_LINK")
            if item.is_file():
                actual_inventory.add(item.relative_to(home).as_posix())
    require(set(inventory) == actual_inventory, "D_TOOL_INVENTORY_MEMBER_SET")
    for relative, entry in inventory.items():
        identity(local_path(home, relative), entry, "TOOL_INVENTORY")
    require(hashlib.sha256(canonical(inventory).encode("utf-8")).hexdigest() ==
            TRUSTED_TOOL_INVENTORY_SHA, "D_TRUSTED_TOOL_INVENTORY")
    declared_files = set(file_map) | {path.relative_to(root).as_posix()}
    actual_files = {p.relative_to(root).as_posix()
                    for p in root.rglob("*") if p.is_file()}
    require(actual_files == declared_files, "D_UNMANIFESTED_OR_OLD_REPORT")
    return {
        "schema": "N32_D_STATIC_CONTRACT_RESULT_V1",
        "status": "PASS_PREPARE_ONLY_NO_TOOL_EXECUTION",
        "manifest_sha256": sha256(path), "files": len(file_map),
        "source_count": 19, "clock_period_ns": 25.0,
        "setup_uncertainty_ns": 1.0, "hold_uncertainty_ns": 0.65,
        "actual_tool_calls": 0, "resources": "UNKNOWN", "STA": "NOT_RUN",
        "tool_ready": not missing, "missing_required_tools": sorted(missing),
        "T061_complete": False,
        "evidence_scope": "A function; B audio; C segmented function/math",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--manifest-sha")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "D_OUTPUT_EXISTS")
    require(not args.output.resolve().is_relative_to(args.project.resolve()),
            "D_OUTPUT_MUST_BE_OUTSIDE_PROJECT")
    try:
        result = validate(args.project, trusted_manifest_sha=args.manifest_sha)
        code = 0
    except (ContractError, KeyError, OSError, ValueError, TypeError,
            AttributeError, IndexError, ET.ParseError) as error:
        result = {"status": "REJECTED", "diagnostic": str(error),
                  "actual_tool_calls": 0}
        code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
