"""New pure facade cases; never runs the old 25 cases or any worker."""
import importlib.util
from pathlib import Path
import sys

_p = Path(__file__).with_name("m3r08_common.py")
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("plan_consumption_guard", "m3r08_03")
f = c.load_component("plan_consumption_guard", "m3r08_fixture_builders")


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    request = f.guard_request(out)
    expected = "ACCEPT"
    if case_id == "03_action_is_not_permission":
        request["requested_action"] = "RUN"
        expected = "REJECT:EXECUTION_ACTION_FORBIDDEN"
    elif case_id == "03_unknown_authority_field":
        request["approved"] = True
        expected = "REJECT:GUARD_REQUEST_FIELDS"
    elif case_id == "03_foreign_validation_scope":
        request["validation_root"] = str(c.ROOT)
        expected = "REJECT:VALIDATION_SCOPE"
    elif case_id == "03_request_scope_binding":
        request["validation_root"] = str(out / "different_root")
        expected = "REJECT:SIGNED_GUARD_REJECT:CANDIDATE_PATH_SCOPE"
    elif case_id == "03_request_identity_pin":
        request["spec"]["sha256"] = "0" * 64
        expected = "REJECT:FILE_IDENTITY_MISMATCH"
    else:
        c.need(case_id in ("03_pure_facade_receipt", "03_no_native_loader_import"), "UNKNOWN_CASE")
    def assertions(actual):
        if expected == "ACCEPT":
            c.need(actual["permission"] == "NOT_GRANTED" and actual["process_route"] == "ABSENT", "NO_EXECUTION_ROUTE")
            normalized = actual["normalized_plan"]
            c.need(not Path(normalized["output_dir"]).exists() and not Path(normalized["consumption_marker"]).exists(), "PURE_NO_RESERVATION")
            c.need(actual["reused_validator"]["sha256"] == m.LEGACY_SHA, "SIGNED_CORE_REUSED")
            if case_id == "03_no_native_loader_import":
                for derived in actual["pure_derivation"].values():
                    if type(derived) is dict:
                        c.need(not {"ctypes", "wintypes", "subprocess", "load_job", "run_fixture", "SpawnGuard"} &
                               set(derived["module_globals"]), "PURE_IMPORT_NATIVE_OR_PROCESS_ROUTE")
                        c.need(not derived["normalization_algorithm_nodes_changed"], "REUSED_AST_BODY")
    return c.run_case_record(case_id, out, expected, request, m.evaluate, assertions)
