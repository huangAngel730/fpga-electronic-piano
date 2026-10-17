"""Coordinator-only S cases; no test work at import."""
import importlib.util
from pathlib import Path
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("recursive_include_audit", "m3r08_01")
f = c.load_component("plan_consumption_guard", "m3r08_fixture_builders")


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    cases = {"01_c6_locator": ("c6", "PENDING_UNKNOWN"), "01_recursive_literal": ("literal", "ACCEPT"),
             "01_missing_header": ("missing_header", "REJECT:INCLUDE_MISSING_OR_INCDIR:b.svh"),
             "01_wrong_incdir": ("wrong_incdir", "REJECT:INCLUDE_MISSING_OR_INCDIR:a.svh"),
             "01_duplicate_module": ("duplicate_module", "REJECT:DUPLICATE_MODULE:base"),
             "01_path_escape": ("escape", "REJECT:PATH_ESCAPE"), "01_macro_unknown": ("macro", "PENDING_UNKNOWN"),
             "01_missing_readmem": ("missing_rom", "REJECT:READMEM_RESOURCE_MISSING:rom/a.hex")}
    mode, expected = cases[case_id]
    if mode == "c6":
        request = {"schema": "M3_R08_INCLUDE_AUDIT_REQUEST_V1", "archive": c.fixture(out, "C6.zip", c.C6.read_bytes()), "selected_list": "compile.f"}
    else:
        request = f.include_request(out, mode)
    def assertions(actual):
        if mode == "c6":
            g = actual["graph"]
            c.need(len(g["units"]) == 71 and len(g["module_to_source"]) == 73 and len(g["ROM_payloads"]) == 9 and
                   len(g["include_edges"]) == 3 and len({x["resolved"] for x in g["include_edges"]}) == 2, "C6_FACTS")
            c.need(actual["archive"]["sha256"] == c.C6_SHA and not actual["compile_proven"], "C6_IDENTITY_ONLY")
        elif mode == "literal":
            c.need(len(actual["graph"]["include_edges"]) == 2, "RECURSIVE_HEADER_EDGE")
    return c.run_case_record(case_id, out, expected, request, m.evaluate, assertions)
