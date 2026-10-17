"""Seal C6 file identities and include coverage; never launch an HDL tool.

C5 remains immutable.  C6 adds its two omitted frozen headers and declares the
required input directory and include-search semantics.  HDL preprocessing,
elaboration, simulator option support and execution admission remain pending.
"""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
DOC = ROOT / (
    "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
    "r06_public_chain_20261017"
)
BASE = ROOT / (
    "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
    "same_version_binding_20261017/"
    "M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip"
)
C5 = DOC / "SOURCE_CLOSURE_R06C5.zip"
C5_SHA = "2fc5518a35600f67d025aa2efe55e6b436daa5a04b592053f7326385b42134fb"
BASE_SHA = "931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2"
HEADER_SHA = {
    "sine_table.svh":
        "969fc7d1036e359fc55c3b0ca18eaf3c8a123a146ed95c32a81e52ee10519cca",
    "sustain_controller_ports.svh":
        "8c51459cd47a7e21609cc02780a93af7d6be0fd5bf2d2278edda92e8a7ef486d",
}
C3_SHA = {
    "m2_fourvoice_timbre_delay_frame_core_r06.sv":
        "83cedc321555733c669246b65fd8760156da73e336e6bc66a2c447797419e919",
    "m2_fourvoice_timbre_delay_board_top_r06.sv":
        "25de50b627776adbb52f8edad0090bb07c8bb005a9cb279b4345330275683373",
    "m2_138k_pro_fourvoice_observer_top_r06.sv":
        "92baee3987ccf447c0880bb657862c16d1ea52e2868afff99a83e3b4da004ff8",
    "m2_r06_tx_identity_sidecar.sv":
        "67e5aba7d697687ac31acb1347483314c67adeb4b37046b9626a5551fdb7c69c",
}
INCLUDE_OPTION = "+incdir+include"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def ident(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def safe_relative(name):
    require(isinstance(name, str) and bool(name), "EMPTY_PATH")
    require("\\" not in name and ":" not in name, "NON_PORTABLE_PATH:" + name)
    path = PurePosixPath(name)
    require(not path.is_absolute(), "ABSOLUTE_PATH:" + name)
    require(all(part not in {"", ".", ".."} for part in name.split("/")),
            "PATH_ESCAPE_OR_NONCANONICAL:" + name)
    return name


def zip_payloads(archive):
    payloads = {}
    folded = set()
    with zipfile.ZipFile(archive) as package:
        require(package.testzip() is None, "ZIP_CRC")
        for member in package.infolist():
            if member.is_dir():
                continue
            name = safe_relative(member.filename)
            require(name.casefold() not in folded, "DUPLICATE_ZIP_PATH:" + name)
            folded.add(name.casefold())
            payloads[name] = package.read(member)
    return payloads


def without_comments(text):
    # Preserve quoted strings; a comment marker inside a string is data.
    pattern = r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pattern, lambda item: item[0] if item[0].startswith('"')
                  else "\n" * item[0].count("\n") + " ", text)


def include_coverage(payloads, source_units):
    visited = set()
    edges = []

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        require(name in payloads, "MISSING_INCLUDE_INPUT:" + name)
        text = without_comments(payloads[name].decode("utf-8-sig"))
        for line_number, line in enumerate(text.splitlines(), 1):
            if not re.search(r"`include\b", line):
                continue
            match = re.fullmatch(r'\s*`include\s+"([^"\n]+)"\s*', line)
            require(match is not None, "UNRESOLVED_INCLUDE_DIRECTIVE:" + name)
            include = safe_relative(match[1])
            resolved = "inputs/include/" + include
            require(resolved in payloads, "MISSING_INCLUDE:" + resolved)
            edges.append({"source": name, "line": line_number,
                          "include": include, "resolved": resolved,
                          "sha256": ident(payloads[resolved])["sha256"]})
            visit(resolved)

    for source in source_units:
        visit("inputs/" + source)
    return {"method": "recursive literal includes; comments removed; no preprocessing",
            "search_directories_relative_to_cwd": ["include"],
            "edges": edges,
            "visited_headers": sorted(n for n in visited
                                      if n.startswith("inputs/include/")),
            "unresolved_literal_includes": []}


def main():
    archive = DOC / "SOURCE_CLOSURE_R06C6.zip"
    decision_path = DOC / "SOURCE_DECISION_R06C6.json"
    list_path = HERE / "SOURCE_LIST_R06C6.f"
    for path in (archive, decision_path, list_path):
        require(not path.exists(), "EXCLUSIVE_OUTPUT_EXISTS:" + str(path))

    c5_raw = C5.read_bytes()
    base_raw = BASE.read_bytes()
    require(ident(c5_raw)["sha256"] == C5_SHA, "C5_ARCHIVE_SHA")
    require(ident(base_raw)["sha256"] == BASE_SHA, "FROZEN_ARCHIVE_SHA")
    payloads = zip_payloads(C5)
    previous = json.loads(payloads.pop("MANIFEST.json"))
    require(set(payloads) == set(previous["payloads"]), "C5_MANIFEST_MEMBERS")
    for name, expected in previous["payloads"].items():
        require(ident(payloads[name]) == expected, "C5_PAYLOAD_IDENTITY:" + name)

    sources = payloads["inputs/compile.f"].decode("utf-8").splitlines()
    require(len(sources) == 71 and len(set(sources)) == 71, "SOURCE_COUNT")
    for name in sources:
        safe_relative(name)
        require("inputs/" + name in payloads, "MISSING_LIST_SOURCE:" + name)
    for name, digest in C3_SHA.items():
        require(ident(payloads["inputs/selected/" + name])["sha256"] == digest,
                "PUBLISHED_C3_IDENTITY:" + name)

    frozen = zip_payloads(BASE)
    header_identities = {}
    for name, digest in HEADER_SHA.items():
        original_name = "source_closure/inputs/include/" + name
        require(original_name in frozen, "FROZEN_HEADER_MISSING:" + name)
        raw = frozen[original_name]
        require(ident(raw)["sha256"] == digest, "FROZEN_HEADER_SHA:" + name)
        destination = "inputs/include/" + name
        require(destination not in payloads, "HEADER_OVERWRITE:" + name)
        payloads[destination] = raw
        header_identities[destination] = {
            "source_archive_member": original_name, **ident(raw)}

    coverage = include_coverage(payloads, sources)
    require(len(coverage["visited_headers"]) == 2, "HEADER_COVERAGE_COUNT")
    modules = {}
    for name in sources:
        text = without_comments(payloads["inputs/" + name].decode("utf-8-sig"))
        text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
        for module in re.findall(r"\bmodule\s+(\w+)", text):
            require(module not in modules, "DUPLICATE_LITERAL_MODULE:" + module)
            modules[module] = name
    require(len(modules) == 73, "LITERAL_MODULE_COUNT")
    require(modules["sine_wavetable_1024"] == "sources/m1td_dds_oscillator.sv",
            "SHARED_ROM_OWNER")
    require(modules["dds_oscillator"] == "selected/dds_oscillator_leaf.sv",
            "DDS_LEAF_OWNER")
    roms = sorted(n for n in payloads if n.startswith("inputs/rom/"))
    require(len(roms) == 9, "NINE_ROM_COUNT")
    for name in roms:
        require(payloads[name] == frozen["source_closure/" + name],
                "ROM_FROZEN_IDENTITY:" + name)

    source_list = (INCLUDE_OPTION + "\n" + "\n".join(sources) + "\n").encode("utf-8")
    payloads["inputs/compile.f"] = source_list
    decision = dict(previous)
    decision.update({
        "schema": "M2_R06C6_SELECTED_SIMULATION_SOURCE_V1",
        "status": "SELECTED_STATIC_HEADERS_PRESENT_NOT_COMPILED_NOT_ADMITTED",
        "repair_of": {"archive": "SOURCE_CLOSURE_R06C5.zip", **ident(c5_raw),
                      "defect": "two literal include headers omitted; include search not bound",
                      "old_archive_preserved": True},
        "builder": {"path": str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"),
                    **ident(Path(__file__).read_bytes())},
        "list_base": "unpacked inputs directory; all relative paths use this cwd",
        "source_units_only": sources,
        "selected_units": len(sources),
        "compile_file_nonempty_lines": len(sources) + 1,
        "compile_file_options": [INCLUDE_OPTION],
        "header_count": len(header_identities),
        "headers": header_identities,
        "include_coverage": coverage,
        "module_to_source_literal_only": modules,
        "tool_neutral_usage_conditions": {
            "cwd_relative_to_unpacked_root": "inputs",
            "source_file_list_relative_to_cwd": "compile.f",
            "include_directories_relative_to_cwd": ["include"],
            "runtime_ROM_paths_relative_to_cwd": "rom/<frozen filename>",
            "top": "m2_138k_pro_fourvoice_observer_top_r06",
            "list_option_spelling": INCLUDE_OPTION,
            "compiler_option_compatibility": "NOT_TESTED; requires precise tool admission",
            "adapter_requirement": "preserve cwd, source order and include directory semantics; map the include option only after the exact compiler syntax is verified",
            "no_compiler_invocation_or_example_is_authorized": True},
        "static_scope": "identities, canonical paths, recursive literal include coverage and literal module uniqueness only; no macro expansion or elaboration",
        "HDL_executed": False,
        "execution_admission": None,
        "physical_mode_allowed": False,
        "board_release_allowed": False,
        "payloads": {name: ident(raw) for name, raw in sorted(payloads.items())},
    })
    manifest_raw = (json.dumps(decision, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for name, raw in sorted(payloads.items()):
            package.writestr(name, raw)
        package.writestr("MANIFEST.json", manifest_raw)
    readback = zip_payloads(archive)
    require(readback.pop("MANIFEST.json") == manifest_raw, "MANIFEST_READBACK")
    require(readback == payloads, "PAYLOAD_READBACK")
    require(C5.read_bytes() == c5_raw and BASE.read_bytes() == base_raw,
            "INPUT_CHANGED_DURING_SEAL")
    decision["archive"] = {
        "path": str(archive.relative_to(ROOT)).replace("\\", "/"),
        **ident(archive.read_bytes())}
    with decision_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(decision, ensure_ascii=False, indent=2) + "\n")
    with list_path.open("xb") as stream:
        stream.write(source_list)
    print(json.dumps({
        "result": "PASS_FILE_PACKAGE_ONLY",
        "level": "L0_STATIC_SOURCE_PACKAGE",
        "selected_units": len(sources), "ROMs": len(roms),
        "headers": len(header_identities), "literal_modules": len(modules),
        "literal_include_edges": len(coverage["edges"]),
        "payloads": len(payloads), "archive": decision["archive"],
        "HDL_calls": 0, "compiler_option_compatibility": "NOT_TESTED",
        "execution_admission": None, "board_release_allowed": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
