"""Read-only lexical dependency graph, never a preprocessor or compiler."""
import importlib.util
from pathlib import Path, PurePosixPath
import re
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]


def stripped(text):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def inspect(payload, list_name):
    list_name = c.relative(list_name)
    c.need(list_name in payload, "SELECTED_LIST_MISSING")
    units, dirs = [], []
    for raw in payload[list_name].decode("utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("+incdir+"):
            dirs.extend(c.relative(s) for s in line[len("+incdir+"):].split("+") if s)
        else:
            c.need(not line.startswith(("+", "-")), "UNSUPPORTED_LIST_DIRECTIVE")
            units.append(c.relative(line))
    c.need(len(units) == len(set(units)) and units, "DUPLICATE_OR_EMPTY_SOURCE_LIST")
    queue, seen = list(units), set()
    modules, edges, resources, unknown = {}, [], [], []
    for unit in units:
        c.need(unit in payload, "SOURCE_MISSING")
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        text = stripped(payload[name].decode("utf-8"))
        for module in re.findall(r"\bmodule\s+(\w+)", text):
            c.need(module not in modules, "DUPLICATE_MODULE:" + module)
            modules[module] = name
        for token in re.findall(r"`include\s+([^\n]+)", text):
            match = re.fullmatch(r'"([^"\n]+)"\s*', token.strip())
            if not match:
                unknown.append({"source": name, "kind": "MACRO_INCLUDE", "expression": token.strip()})
                continue
            ref = c.relative(match.group(1))
            options = [str(PurePosixPath(name).parent / ref)] + [d + "/" + ref for d in dirs]
            resolved = next((p for p in options if p in payload), None)
            c.need(resolved is not None, "INCLUDE_MISSING_OR_INCDIR:" + ref)
            edges.append({"source": name, "include": ref, "resolved": resolved, "sha256": c.digest(payload[resolved])})
            queue.append(resolved)
        defaults = dict(re.findall(r'\bparameter\s+(?:string\s+)?(\w+)\s*=\s*"([^"\n]+)"', text))
        for arg in re.findall(r"\$readmem[hb]\s*\(\s*([^,\n]+)", text):
            literal = re.fullmatch(r'"([^"\n]+)"', arg.strip())
            if literal:
                ref = c.relative(literal.group(1))
                c.need(ref in payload, "READMEM_RESOURCE_MISSING:" + ref)
                resources.append({"source": name, "expression": arg.strip(), "resolved": ref, "sha256": c.digest(payload[ref])})
            else:
                default = defaults.get(arg.strip())
                if default:
                    c.relative(default)
                unknown.append({"source": name, "kind": "PARAMETER_OR_RUNTIME_READMEM", "expression": arg.strip(),
                                "declared_default": default, "default_present": default in payload if default else None,
                                "reason": "INSTANCE_OVERRIDE_PLUSARG_NOT_ELABORATED"})
    return {"units": units, "incdirs": dirs, "module_to_source": modules, "include_edges": edges,
            "resolved_readmem": resources, "unknown": unknown,
            "nodes": [{"path": n, "bytes": len(payload[n]), "sha256": c.digest(payload[n])} for n in sorted(seen)],
            "ROM_payloads": [{"path": n, "bytes": len(raw), "sha256": c.digest(raw)}
                             for n, raw in sorted(payload.items()) if n.startswith("rom/") and n.endswith((".mem", ".hex"))]}


def evaluate(request):
    c.need(request.get("schema") == "M3_R08_INCLUDE_AUDIT_REQUEST_V1", "INCLUDE_AUDIT_SCHEMA")
    payload, archive_id = c.archive(request["archive"])
    graph = inspect(payload, request["selected_list"])
    status = "PENDING_UNKNOWN" if graph["unknown"] else "ACCEPT"
    return c.result("M3_R08_DEPENDENCY_GRAPH_V1", status, archive=archive_id, graph=graph,
                    compile_proven=False, artifacts={"dependency_graph.json": graph})


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
