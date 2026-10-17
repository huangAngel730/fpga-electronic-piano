"""Static file identity and import references; never loads or starts a tool."""
import ast
import importlib.util
from pathlib import Path
import struct
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]


def pe_imports(raw):
    c.need(len(raw) >= 64 and raw[:2] == b"MZ", "PE_HEADER")
    off = struct.unpack_from("<I", raw, 60)[0]
    c.need(off + 24 <= len(raw) and raw[off:off + 4] == b"PE\0\0", "PE_HEADER")
    sections, optional_size = struct.unpack_from("<H", raw, off + 6)[0], struct.unpack_from("<H", raw, off + 20)[0]
    optional = off + 24
    c.need(optional + optional_size <= len(raw) and optional_size >= 112, "PE_HEADER")
    magic = struct.unpack_from("<H", raw, optional)[0]
    c.need(magic in (0x10B, 0x20B), "PE_OPTIONAL_MAGIC")
    directory = optional + (96 if magic == 0x10B else 112)
    c.need(directory + 16 <= optional + optional_size, "PE_DIRECTORY")
    import_rva = struct.unpack_from("<I", raw, directory + 8)[0]
    table = optional + optional_size
    c.need(sections <= 128 and table + 40 * sections <= len(raw), "PE_SECTION_TABLE")
    regions = []
    for i in range(sections):
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", raw, table + i * 40 + 8)
        regions.append((virtual_address, max(virtual_size, raw_size), raw_offset, raw_size))

    def offset(rva):
        for start, size, raw_offset, raw_size in regions:
            if start <= rva < start + size:
                delta = rva - start
                c.need(delta < raw_size and raw_offset + delta < len(raw), "PE_RVA_OUTSIDE_FILE")
                return raw_offset + delta
        raise c.CheckError("PE_RVA_UNRESOLVED")

    imports = []
    if import_rva:
        pos = offset(import_rva)
        for i in range(1024):
            c.need(pos + i * 20 + 20 <= len(raw), "PE_IMPORT_TABLE")
            item = struct.unpack_from("<IIIII", raw, pos + i * 20)
            if not any(item):
                break
            start = offset(item[3])
            end = raw.find(b"\0", start, min(start + 512, len(raw)))
            c.need(end != -1, "PE_IMPORT_NAME")
            imports.append(raw[start:end].decode("ascii"))
        else:
            raise c.CheckError("PE_IMPORT_LIMIT")
    return imports


def evaluate(request):
    c.need(request.get("schema") == "M3_R08_TOOL_IDENTITY_REQUEST_V1", "TOOL_IDENTITY_SCHEMA")
    origin = request.get("origin")
    c.need(origin in ("SYNTHETIC", "REAL_CANDIDATE"), "TOOL_ORIGIN")
    coverage = request.get("coverage", "STATIC_IMPORT_CLOSURE")
    c.need(coverage in ("STATIC_IMPORT_CLOSURE", "IDENTITY_ONLY"), "TOOL_COVERAGE")
    tool = request["tool"]
    c.need(type(tool) is dict and {"file", "kind"} <= set(tool), "TOOL_FILE_IDENTITY_REQUIRED")
    path, tool_id = c.checked_file(tool["file"], external=True)
    dependencies, identities = {}, [tool_id]
    for dep in request["dependencies"]:
        key = dep["name"].casefold()
        c.need(key not in dependencies, "DUPLICATE_DEPENDENCY")
        p, ident = c.checked_file(dep["file"], external=True)
        dependencies[key] = {**dep, "path": p, "identity": ident}
        identities.append(ident)
    c.need(len({x["path"] for x in identities}) == len(identities), "DUPLICATE_TOOL_PATH")
    for name in request["expected_dependencies"]:
        c.need(name.casefold() in dependencies, "DEPENDENCY_MISSING:" + name)
    if tool["kind"] == "PYTHON_SCRIPT":
        c.need("interpreter" in request, "INTERPRETER_IDENTITY_REQUIRED")
        _, interpreter = c.checked_file(request["interpreter"], external=True)
        identities.append(interpreter)
    queue = [("tool", path, tool["kind"])]; visited, edges, unknown = set(), [], []
    while queue:
        name, source, kind = queue.pop(0)
        if str(source) in visited:
            continue
        visited.add(str(source))
        raw = source.read_bytes()
        imports = []
        if kind == "PYTHON_SCRIPT":
            try:
                tree = ast.parse(raw.decode("utf-8"), filename=str(source))
            except (SyntaxError, UnicodeError) as error:
                raise c.CheckError("SCRIPT_STATIC_PARSE") from error
            for node in ast.walk(tree):
                if isinstance(node, ast.Import): imports.extend(x.name for x in node.names)
                if isinstance(node, ast.ImportFrom):
                    if node.level: unknown.append({"source": name, "kind": "RELATIVE_IMPORT"})
                    elif node.module: imports.append(node.module)
                if isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id == "__import__") or
                    (isinstance(node.func, ast.Attribute) and node.func.attr in ("import_module", "CDLL", "WinDLL"))):
                    unknown.append({"source": name, "kind": "DYNAMIC_IMPORT_NOT_EXECUTED"})
        elif kind == "PE":
            try:
                imports = pe_imports(raw)
            except (c.CheckError, UnicodeError, struct.error) as error:
                if coverage != "IDENTITY_ONLY":
                    raise
                unknown.append({"source": name, "kind": "NATIVE_STATIC_PARSE_UNRESOLVED", "reason": str(error)})
            unknown.append({"source": name, "kind": "NATIVE_DELAY_OR_DYNAMIC_DEPENDENCIES_NOT_PROVEN"})
        elif kind == "OPAQUE_FIXTURE" and origin == "SYNTHETIC":
            pass
        else:
            raise c.CheckError("TOOL_KIND_OR_UNRESOLVED_BINARY")
        for imported in imports:
            key = imported.casefold()
            if key not in dependencies and coverage == "IDENTITY_ONLY":
                unknown.append({"source": name, "kind": "DEPENDENCY_FILE_IDENTITY_UNKNOWN", "reference": imported})
                continue
            c.need(key in dependencies, "DEPENDENCY_MISSING:" + imported)
            dep = dependencies[key]
            edges.append({"source": name, "reference": imported, "identity": dep["identity"]})
            queue.append((imported, dep["path"], dep["kind"]))
    unknown.extend({"source": "caller", "kind": x} for x in request.get("unresolved_dynamic_dependencies", []))
    if origin == "REAL_CANDIDATE":
        unknown.append({"source": "scope", "kind": "REAL_EXECUTION_AND_RUNTIME_LOADER_NOT_QUALIFIED"})
    report = {"origin": origin, "coverage": coverage, "files": identities, "static_edges": edges, "unknown": unknown,
              "executables_started": 0, "DLLs_loaded": 0, "version_probe": "NOT_RUN",
              "process_cleanup_proven": False, "execution_permission": "NOT_GRANTED"}
    return c.result("M3_R08_TOOL_DEPENDENCY_IDENTITY_V1", "PENDING_UNKNOWN" if unknown else "ACCEPT",
                    report=report, artifacts={"tool_dependency_identity.json": report})


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
