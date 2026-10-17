"""Read-only source assembly audit; lexical inventory, never HDL elaboration."""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path, PurePosixPath


class Rejected(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected("DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def load(data):
    return json.loads(data, object_pairs_hook=unique)


def relative(name):
    if (not isinstance(name, str) or not name or "\\" in name or
            ":" in name or name.startswith("/") or
            any(p in {"", ".", ".."} for p in name.split("/"))):
        raise Rejected("PATH_ESCAPE:" + str(name))
    return name


def disk(root, name):
    path = (root / relative(name)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise Rejected("PATH_ESCAPE:" + name)
    return path.read_bytes()


def checked(data, digest, label):
    if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
        raise Rejected("MISSING_SHA:" + label)
    if sha(data) != digest:
        raise Rejected("SHA_MISMATCH:" + label)
    return data


def clean(text):
    # Preserve strings and line count; comments cannot introduce fake modules.
    return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                  lambda m: m[0] if m[0].startswith('"') else
                  "\n" * m[0].count("\n") + " ", text)


def balanced(text, start):
    depth = 0
    tokens = re.finditer(r'"(?:\\.|[^"\\])*"|[()]', text[start:])
    for match in tokens:
        token = match[0]
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth == 0:
                end = start + match.end()
                return text[start + 1:end - 1], end
    raise Rejected("UNBALANCED_PARENTHESES")


def inventory(text, path):
    """Supported: ANSI/non-ANSI modules, named/positional instances, packages.

    This deliberately does not resolve preprocessor branches, parameter values,
    widths, generate activation or dynamic ROM overrides. They remain pending.
    """
    text = clean(text)
    modules, instances, unresolved = [], [], []
    for match in re.finditer(r"\bmodule\s+(\w+)\s*", text):
        name, pos = match[1], match.end()
        if text[pos:pos + 1] == "#":
            pos += 1
            while text[pos].isspace():
                pos += 1
            _, pos = balanced(text, pos)
        while text[pos].isspace():
            pos += 1
        header = ""
        if text[pos] == "(":
            header, pos = balanced(text, pos)
        end_match = re.search(r"\bendmodule\b", text[pos:])
        if not end_match:
            raise Rejected("MISSING_ENDMODULE:" + name)
        body = text[pos:pos + end_match.start()]
        ports, direction, width = [], None, None
        for fragment in header.split(","):
            direct = re.search(r"\b(input|output|inout)\b", fragment)
            if direct:
                direction = direct[1]
                ranges = re.findall(r"\[[^]]+\]", fragment)
                width = " ".join(ranges) or "scalar"
            identifiers = re.findall(r"\b[A-Za-z_]\w*\b",
                                     re.sub(r"\[[^]]+\]", "", fragment).split("=")[0])
            if identifiers:
                port = identifiers[-1]
                nonansi = re.search(r"\b(input|output|inout)\s+([^;]*\b" +
                                   re.escape(port) + r"\b[^;]*);", body)
                ports.append({"name": port, "direction": direction or
                              (nonansi[1] if nonansi else None),
                              "width_expression": width, "width_evaluated": False})
        modules.append({"name": name, "path": path, "ports": ports})
    # Instance signatures: type [#(params)] instance [array] (connections).
    pattern = re.compile(r"\b([A-Za-z_]\w*)\s+(?:(#)\s*)?")
    excluded = set("module function task automatic input output inout wire logic reg integer parameter localparam assign return if else for while case always always_ff always_comb initial begin end typedef signed unsigned bit int string real time genvar generate endgenerate import export package".split())
    for match in pattern.finditer(text):
        kind = match[1]
        if kind in excluded or match.start() and text[match.start()-1] in "$.'":
            continue
        pos = match.end()
        if match[2]:
            if text[pos:pos+1] != "(":
                continue
            _, pos = balanced(text, pos)
        tail = re.match(r"\s*([A-Za-z_]\w*)\s*(?:\[[^]]+\]\s*)?\(", text[pos:])
        if not tail:
            continue
        connections, end = balanced(text, pos + tail.end() - 1)
        if not re.match(r"\s*;", text[end:]):
            unresolved.append("MULTI_INSTANCE_OR_UNSUPPORTED:" + kind)
            continue
        instances.append({"type": kind, "instance": tail[1], "path": path,
                          "named_ports": re.findall(r"\.\s*(\w+)\s*\(", connections)})
    directives = re.findall(r"`(\w+)", text)
    if any(d not in {"timescale", "default_nettype"} for d in directives):
        unresolved.append("PREPROCESSOR_NOT_ELABORATED:" + path)
    if re.search(r"\$readmem[hb]\s*\(\s*[^\s\"]", text):
        unresolved.append("DYNAMIC_ROM_ARGUMENT_OR_PARAMETER:" + path)
    packages = re.findall(r"\bpackage\s+(\w+)\s*;", text)
    imports = re.findall(r"\b(\w+)\s*::", text)
    roms = re.findall(r'"([^"\n]+\.(?:mem|hex))"', text)
    includes = re.findall(r'`include\s+"([^"]+)"', text)
    return modules, instances, packages, imports, roms, includes, unresolved


def audit(config, root):
    errors, pending = [], []
    mode = config["mode"]
    if mode not in {"simulation", "physical"}:
        raise Rejected("MODE")
    arc = config["archive"]
    raw = checked(disk(root, arc["path"]), arc["sha256"], "archive")
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        payload = {}
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = relative(entry.filename)
            if name.casefold() in {n.casefold() for n in payload}:
                raise Rejected("DUPLICATE_ARCHIVE_PATH:" + name)
            if entry.file_size > 20_000_000 or sum(map(len, payload.values())) > 80_000_000:
                raise Rejected("ARCHIVE_SIZE_LIMIT")
            payload[name] = archive.read(entry)
    manifest_data = checked(payload["MANIFEST.json"], arc["manifest_sha256"], "manifest")
    manifest = load(manifest_data)
    seen = set()
    for item in manifest["files"]:
        name = relative(item["path"])
        if name in seen:
            raise Rejected("DUPLICATE_MANIFEST_PATH:" + name)
        seen.add(name)
        data = checked(payload[name], item["sha256"], name)
        if type(item["bytes"]) is not int or len(data) != item["bytes"]:
            raise Rejected("SIZE_MISMATCH:" + name)
    if set(payload) != seen | {"MANIFEST.json"}:
        raise Rejected("UNMANIFESTED_ARCHIVE_MEMBER")
    binding = load(payload["SOURCE_BINDING.json"])
    list_path = binding["simulation_source_list"]["path"]
    list_data = checked(payload[list_path], binding["simulation_source_list"]["sha256"], list_path)
    cwd = str(PurePosixPath(list_path).parent)
    source_list = [relative(cwd + "/" + relative(line.strip()))
                   for line in list_data.decode("utf-8").splitlines() if line.strip()]
    wrapper = binding["candidate_top"]
    if config["assembly"] == "bound_list_plus_wrapper":
        source_list.append(wrapper["path"])
    elif config["assembly"] != "bound_list_only":
        raise Rejected("ASSEMBLY_MODE")
    overlays = []
    for item in config.get("candidates", []):
        name = relative(item["stage_as"])
        if name.casefold() in {n.casefold() for n in payload}:
            raise Rejected("CANDIDATE_OVERWRITE:" + name)
        data = checked(disk(root, item["path"]), item["sha256"], item["path"])
        payload[name] = data
        if item.get("replaces"):
            old = relative(item["replaces"])
            if old not in source_list:
                raise Rejected("REPLACEMENT_NOT_LISTED:" + old)
            source_list[source_list.index(old)] = name
        else:
            source_list.append(name)
        overlays.append(item)
    for name in config.get("remove_sources", []):
        if name not in source_list:
            raise Rejected("REMOVE_NOT_LISTED:" + name)
        source_list.remove(name)
    if len(source_list) != len(set(source_list)):
        errors.append("DUPLICATE_SOURCE_PATH")
    if wrapper["path"] not in source_list and not any(
            i.get("replaces") == wrapper["path"] for i in overlays):
        errors.append("WRAPPER_NOT_IN_SOURCE_LIST")
    modules, instances, packages, imports, rom_refs, include_refs = [], [], [], [], [], []
    for name in source_list:
        if name not in payload:
            errors.append("MISSING_SOURCE:" + name)
            continue
        m, inst, pk, im, rom, inc, un = inventory(payload[name].decode("utf-8-sig"), name)
        modules.extend(m); instances.extend(inst); packages.extend(pk); imports.extend(im)
        rom_refs.extend((name, r) for r in rom)
        include_refs.extend((name, r) for r in inc)
        pending.extend(un)
    definitions = {}
    for module in modules:
        if module["name"] in definitions:
            errors.append("DUPLICATE_MODULE:" + module["name"])
        definitions[module["name"]] = module
    top = config.get("top", wrapper["module"])
    if top not in definitions:
        errors.append("MISSING_TOP:" + top)
    for inst in instances:
        if inst["type"] not in definitions:
            errors.append("MISSING_MODULE:" + inst["type"])
        else:
            ports = {p["name"] for p in definitions[inst["type"]]["ports"]}
            for port in inst["named_ports"]:
                if port not in ports:
                    errors.append("UNKNOWN_NAMED_PORT:" + inst["type"] + "." + port)
    for package in set(imports) - set(packages):
        errors.append("MISSING_PACKAGE:" + package)
    for origin, name in include_refs:
        candidate = str(PurePosixPath(origin).parent / relative(name))
        if candidate not in payload:
            errors.append("MISSING_INCLUDE:" + candidate)
    for origin, name in rom_refs:
        relative(name)
        if cwd + "/" + name not in payload:
            errors.append("MISSING_ROM_REFERENCE:" + origin + ":" + name)
    deps = []
    roms = binding["roms"]
    if len(roms) != 9 or len({r["path"] for r in roms}) != 9:
        errors.append("NINE_DISTINCT_ROMS_REQUIRED")
    for category, rows in [("ROM", roms), ("CONSTRAINT", binding["constraints"])]:
        for item in rows:
            name = relative(item["path"])
            checked(payload[name], item["sha256"], name)
            deps.append({"category": category, "path": name, "bytes": len(payload[name]),
                         "sha256": sha(payload[name])})
    for key, name in binding["pll_ip"].items():
        if key.endswith("_path"):
            relative(name)
            digest = binding["pll_ip"].get(key[:-5] + "_sha256")
            checked(payload[name], digest, name)
            deps.append({"category": "IP", "path": name, "sha256": sha(payload[name]),
                         "bytes": len(payload[name]), "listed": name in source_list})
    target = binding["target"]
    missing_id = [k for k in ["complete_device_symbol", "device_version", "actual_core_revision",
                             "actual_dock_revision", "bank_voltage_verified"] if not target.get(k)]
    if not binding["pll_ip"].get("new_pro_ip_generated"):
        missing_id.append("verified_Pro_PLL")
    forbidden = [n for n in source_list if re.search(
        r"stub|_sim\.|PG484|LV60|\bforce\b|\$finish", n + "\n" + payload[n].decode("utf-8-sig"), re.I)]
    physical_status = "PENDING_PHYSICAL_ID" if missing_id or forbidden else "METADATA_ONLY_M2_PHYSICAL_REVIEW_REQUIRED"
    if mode == "physical":
        pending.extend(["PHYSICAL_ID:" + k for k in missing_id])
        pending.extend(["SIMULATION_OR_LEGACY_IN_PHYSICAL:" + n for n in forbidden])
        pending.append("M2_PHYSICAL_IDENTITY_AND_IP_REVIEW_REQUIRED")
    status = "REJECTED" if errors else ("PENDING_PHYSICAL_ID" if mode == "physical" and
             (missing_id or forbidden) else "PENDING_STATIC_ELABORATION" if pending else "STATIC_CLOSURE_READY")
    result = {"status": status, "level": "L0_STATIC_ASSEMBLY", "mode": mode,
              "physical_status": physical_status, "board_release_allowed": False,
              "pro_dut_pass": False, "hdl_calls": 0, "top": top, "cwd": cwd,
              "source_list": source_list, "modules": modules, "instances": instances,
              "dependencies": deps, "rom_references": rom_refs,
              "candidate_inputs": overlays, "target": target,
              "errors": sorted(set(errors)), "pending": sorted(set(pending)),
              "limits": "Lexical inventory only; no macro/generate elaboration, width evaluation, mathematical or physical proof."}
    return result, payload


def write_result(result, payload, output):
    output.mkdir(parents=True, exist_ok=False)
    (output / "RESULT.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Stage all authenticated source_closure inputs (ROM relative paths preserved).
    selected = {n for n in payload if n.startswith("source_closure/")} | set(result["source_list"])
    manifest = []
    for name in sorted(selected):
        p = output / "stage" / relative(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(payload[name])
        manifest.append({"path": name, "bytes": len(payload[name]), "sha256": sha(payload[name])})
    # Resolve from declared stage/cwd so original ROM strings retain their meaning.
    lines = [posixpath.relpath(n, result["cwd"]) for n in result["source_list"]]
    (output / "source-list.f").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result, payload = audit(load(args.config.read_bytes()), args.root)
        write_result(result, payload, args.output)
        print(json.dumps({"status": result["status"], "errors": result["errors"]}))
        return 2 if result["errors"] else 3 if result["status"].startswith("PENDING") else 0
    except (Rejected, KeyError, ValueError, OSError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "REJECTED", "diagnostic": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
