"""Freeze a new B stage: exactly 40 reversible path literals, append-only reports."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"
STAGE = REPO / "code/output/m3_m2td_endpoint_probe_20261015_r01"
ORIGINALS = DOC / "input_audit_r01/derived_original_bytes"
OLD_PREFIX = "C:/Users/Angel17/.codex/worktrees/m2-138k-migration/fpga_gowin/code/output/m2_m1td_whole_prepare_20261015_06/"
TOOL_ROOT = Path("E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03/IDE")
PHYSICAL = REPO / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip"
P_SHA = "17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff"


def identity(blob):
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def tool_manifest():
    return {p.relative_to(TOOL_ROOT).as_posix(): identity(p.read_bytes())
            for folder in (TOOL_ROOT / "bin", TOOL_ROOT / "lib")
            for p in sorted(folder.rglob("*")) if p.is_file()}


def report_command(kind, target):
    # Gowin's documented wildcards are only ?/*; literal bracket indices in
    # braced collections are confirmed by the retained original 10-05 report.
    source = target["from_node"].rsplit("/", 1)[0]
    terminal = target["to_node"]
    if any(c in source + terminal for c in "*?{}\n\r"):
        raise ValueError("unsafe exact selector")
    return f"report_timing -{kind} -from [get_regs {{{source}}}] -to [get_pins {{{terminal}}}] -max_paths 1 -max_common_paths 1"


def main():
    if STAGE.exists():
        raise ValueError("stage already exists; never reuse")
    if any(p.is_symlink() for p in (STAGE.parent, REPO)):
        raise ValueError("reparse stage root")
    original_zip = PHYSICAL.read_bytes()
    if identity(original_zip)["sha256"] != P_SHA:
        raise ValueError("physical original changed")
    with zipfile.ZipFile(PHYSICAL) as z:
        prep = json.loads(z.read("PREPARATION_RECEIPT.json"))
        run = json.loads(z.read("RUN_RECEIPT.json"))
        project_raw, tcl_raw = z.read("project.gprj"), z.read("run.tcl")
    tool = TOOL_ROOT / "bin/gw_sh.exe"
    bound_tool = [v for k, v in run["input_before"].items() if k.endswith("gw_sh.exe")]
    if len(bound_tool) != 1 or identity(tool.read_bytes()) != bound_tool[0]:
        raise ValueError("tool launcher identity mismatch")
    dll = (TOOL_ROOT / "bin/gowin.dll").read_bytes()
    if b"V1.9.11.03 Education\x00" not in dll:
        raise ValueError("tool runtime static version mismatch")
    originals = {}
    expected = {k.replace("\\", "/"): v for k, v in prep["input_files"].items()}
    if len(expected) != 84:
        raise ValueError("original manifest count mismatch")
    for name, item in expected.items():
        data = (ORIGINALS / name).read_bytes()
        if identity(data) != item:
            raise ValueError("frozen recovered input mismatch: " + name)
        originals[name] = data
    target_blob = (DOC.parent / "targets.json").read_bytes()
    targets = json.loads(target_blob)["targets"]
    if len(targets) != 5:
        raise ValueError("bounded old target list changed")
    migrated, mappings = {}, []
    prefix_bytes = OLD_PREFIX.encode()
    pattern = re.compile(rb'"(' + re.escape(prefix_bytes) + rb'inputs/(?:rom|include)/[^"\r\n]+)"')
    for name, data in originals.items():
        changes = []
        def replacement(match):
            old = match.group(1).decode("utf-8")
            relative = old.removeprefix(OLD_PREFIX)
            if relative not in expected:
                raise ValueError("missing dependency in original manifest")
            new = (STAGE / relative).as_posix()
            changes.append({"byte_start": match.start(1), "byte_end": match.end(1),
                            "old": old, "new": new, "dependency_relative": relative,
                            "dependency_original_identity": expected[relative],
                            "line_number": data[:match.start()].count(b"\n") + 1,
                            "purpose": "ROM/include path literal only"})
            return b'"' + new.encode() + b'"'
        updated = pattern.sub(replacement, data) if name.endswith((".sv", ".v", ".svh")) else data
        inverse = updated
        for old, new in {(c["old"], c["new"]) for c in changes}:
            inverse = inverse.replace(new.encode(), old.encode())
        if inverse != data:
            raise ValueError("nonreversible migration")
        migrated[name] = updated
        if changes:
            mappings.append({"file": name, "before": identity(data), "after": identity(updated),
                             "inverse_identity": identity(inverse), "inverse_byte_equal": True, "changes": changes})
    if sum(len(x["changes"]) for x in mappings) != 40 or len(mappings) != 15:
        raise ValueError("path-only migration count differs from authorization")
    sdc_name = "inputs/constraints/audio_visual_hold055.sdc"
    appendix = "\n# M3 B R03 isolated exact endpoints; original timing semantics above unchanged.\n"
    for t in targets:
        appendix += "# " + t["id"] + "\n"
        for kind in ("setup", "hold"):
            appendix += report_command(kind, t) + "\n"
    migrated[sdc_name] = originals[sdc_name] + appendix.encode("ascii")
    if not migrated[sdc_name].startswith(originals[sdc_name]):
        raise ValueError("SDC not append-only")
    project = project_raw.replace(OLD_PREFIX.encode(), (STAGE.as_posix() + "/").encode())
    if project.replace((STAGE.as_posix() + "/").encode(), OLD_PREFIX.encode()) != project_raw:
        raise ValueError("project relocation not reversible")
    if len(ET.fromstring(project).findall("./FileList/File")) != 69:
        raise ValueError("project file list changed")
    STAGE.mkdir()
    (STAGE / "originals").mkdir()
    for name, data in originals.items():
        raw_path = STAGE / "originals" / name
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(data)
        dest = STAGE / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(migrated[name])
    for record in mappings:
        for change in record["changes"]:
            if identity((STAGE / change["dependency_relative"]).read_bytes()) != change["dependency_original_identity"]:
                raise ValueError("migration target dependency byte drift")
    project_name = "m2_fourvoice_timbre_delay_board_top.gprj"
    (STAGE / project_name).write_bytes(project)
    (STAGE / "originals/project.gprj").write_bytes(project_raw)
    # Only include search infrastructure is added; its header bytes are frozen.
    tcl = tcl_raw.replace(OLD_PREFIX.encode(), (STAGE.as_posix() + "/").encode()).decode("ascii")
    tcl = tcl.replace("run all", "set_option -include_path {" + (STAGE / "inputs/include").as_posix() + "}\nrun all")
    (STAGE / "run.tcl").write_text(tcl, encoding="ascii", newline="\n")
    environment = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC", "OS", "PROCESSOR_ARCHITECTURE",
                   "NUMBER_OF_PROCESSORS", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "LM_LICENSE_FILE", "GOWIN_LICENSE_FILE") if k in os.environ}
    environment["PATH"] = os.pathsep.join([str(TOOL_ROOT / "bin"), str(TOOL_ROOT / "lib"),
                                          os.environ.get("SystemRoot", "C:/Windows") + "/System32",
                                          os.environ.get("SystemRoot", "C:/Windows")])
    environment.update(TEMP=str(STAGE), TMP=str(STAGE))
    tools = tool_manifest()
    write_json(STAGE / "TOOL_MANIFEST.json", tools)
    write_json(STAGE / "PATH_MIGRATION.json", {"files": mappings, "count": 40, "inverse_all_equal": True})
    write_json(STAGE / "TARGETS.json", {"original_target_list_identity": identity(target_blob), "targets": targets})
    write_json(STAGE / "ENVIRONMENT.json", environment)
    auth_paths = [REPO / "code/docs/M3_四项并行主责授权_2026-10-15.md",
                  REPO / "code/docs/M3_夜间M2候选权限预授权_2026-10-15.md"]
    preflight = {"status": "PREPARED_NOT_EXECUTED", "round": 1, "max_seconds": 1800,
                 "stage": str(STAGE), "argv": [str(tool), str(STAGE / "run.tcl")], "cwd": str(STAGE),
                 "original_archive_identity": identity(original_zip), "original_input_count": 84,
                 "migrated_literal_count": 40, "new_identity_not_original_sha": True,
                 "tool_runtime_version": "V1.9.11.03 Education", "static_version_evidence": identity(dll),
                 "inputs": {name: identity(blob) for name, blob in migrated.items()},
                 "project": identity(project), "tcl": identity(tcl.encode("ascii")),
                 "sdc_original": identity(originals[sdc_name]), "sdc_appendix": identity(appendix.encode("ascii")),
                 "tool_manifest": identity((STAGE / "TOOL_MANIFEST.json").read_bytes()),
                 "authorization": {str(p): identity(p.read_bytes()) for p in auth_paths},
                 "budget_consumed": False, "physical_tool_starts": 0, "board_release_allowed": False}
    write_json(STAGE / "PREFLIGHT.json", preflight)
    print(json.dumps({"status": preflight["status"], "stage": str(STAGE), "literals": 40,
                      "tool_identity_files": len(tools), "preflight": identity((STAGE / "PREFLIGHT.json").read_bytes())}))


if __name__ == "__main__":
    main()
