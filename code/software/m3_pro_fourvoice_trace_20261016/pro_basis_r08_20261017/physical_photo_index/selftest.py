"""H index fixtures. Synthetic images/claims never establish real hardware."""
import importlib.util
from pathlib import Path
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("physical_photo_index", "m3r08_19")


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    source = c.fixture(out, "SYNTHETIC_REFERENCE.txt", b"SYNTHETIC claims only; no board photograph or measurement.\n")
    claims = {name: {"value": "SYNTHETIC_" + name, "evidence_id": "fixture", "page": 1, "region": "fixture text only"} for name in m.FIELDS}
    request = {"schema": "M3_R08_PHOTO_INDEX_REQUEST_V1", "origin": "SYNTHETIC", "board_id": "SYNTHETIC_BOARD",
               "claims": claims, "evidence": [{"id": "fixture", "kind": "SYNTHETIC", "board_id": "SYNTHETIC_BOARD", "file": source}],
               "measurements": [{"id": "SYNTHETIC_MEASUREMENT", "board_id": "SYNTHETIC_BOARD", "evidence_id": "fixture"}]}
    expected = "ACCEPT"
    if case_id == "19_changed_photo_identity":
        request["evidence"][0]["file"]["sha256"] = "0" * 64; expected = "REJECT:FILE_IDENTITY_MISMATCH"
    elif case_id == "19_wrong_board":
        request["evidence"][0]["board_id"] = "OTHER_BOARD"; expected = "REJECT:BOARD_ID_MISMATCH"
    elif case_id == "19_missing_page":
        request["claims"]["device_version"]["page"] = 0; expected = "REJECT:PAGE_REGION_REQUIRED"
    elif case_id == "19_reference_not_physical":
        request["origin"] = "REAL_CANDIDATE"; request["evidence"][0]["kind"] = "REFERENCE_DOCUMENT"; expected = "PENDING_UNKNOWN"
    elif case_id == "19_missing_real_bank_version":
        request["origin"] = "REAL_CANDIDATE"; request["claims"]["device_version"] = None; request["claims"]["bank_map"] = None
        expected = "PENDING_UNKNOWN"
    else: c.need(case_id == "19_synthetic_index", "UNKNOWN_CASE")
    def assertions(actual):
        if actual["status"] != "REJECT":
            c.need(not actual["report"]["physical_identity_signed"] and not actual["real_pass"], "NO_PHYSICAL_SIGNOFF")
    return c.run_case_record(case_id, out, expected, request, m.evaluate, assertions)
