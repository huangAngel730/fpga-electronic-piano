"""Coordinator-only S file identities; fixture exe bytes never executed."""
import importlib.util
from pathlib import Path
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("tool_dependency_identity", "m3r08_05")
f = c.load_component("plan_consumption_guard", "m3r08_fixture_builders")


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    if case_id == "05_actual_native_file_inventory":
        document = c.parse((c.DOC / "tool_dependency_identity/NATIVE_READ_REQUESTS.json").read_bytes())
        def scenario(data):
            results = []
            for i, tool in enumerate(data["tools"], 1):
                actual = m.evaluate(tool["request"])
                c.write_json(out / (f"NATIVE_{i:02d}_ACTUAL.json"), {"name": tool["name"], "actual": actual})
                c.need(actual["status"] == "PENDING_UNKNOWN" and actual["report"]["executables_started"] == 0 and
                       actual["report"]["DLLs_loaded"] == 0, "ACTUAL_FILES_ONLY_NOT_EXECUTION")
                results.append({"name": tool["name"], "request": tool["request"], "actual": actual})
            return c.result("M3_R08_ACTUAL_FILE_IDENTITY_INVENTORY_V1", "PENDING_UNKNOWN", tools=results)
        return c.run_case_record(case_id, out, "PENDING_UNKNOWN", document, scenario)
    cases = {"05_static_identity_graph": ("valid", "ACCEPT"), "05_changed_tool": ("changed", "REJECT:FILE_IDENTITY_MISMATCH"),
             "05_missing_dependency": ("missing", "REJECT:DEPENDENCY_MISSING:helper"),
             "05_version_is_not_identity": ("version", "REJECT:TOOL_FILE_IDENTITY_REQUIRED"),
             "05_dynamic_dependency_unknown": ("dynamic", "PENDING_UNKNOWN"),
             "05_PE_import_missing": ("pe", "REJECT:DEPENDENCY_MISSING:missing.dll")}
    mode, expected = cases[case_id]
    request = f.tool_request(out, mode)
    def assertions(actual):
        if mode == "valid":
            report = actual["report"]
            c.need(len(report["static_edges"]) == 1 and report["executables_started"] == 0 and report["DLLs_loaded"] == 0 and
                   not report["process_cleanup_proven"], "FILE_IDENTITY_ONLY")
    return c.run_case_record(case_id, out, expected, request, m.evaluate, assertions)
