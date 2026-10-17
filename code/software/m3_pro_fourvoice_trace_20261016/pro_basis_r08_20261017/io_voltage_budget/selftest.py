"""H arithmetic/mismatch fixtures; all numbers are explicitly synthetic."""
import importlib.util
from pathlib import Path
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("io_voltage_budget", "m3r08_20")


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    source = c.fixture(out, "SYNTHETIC_LIMITS.txt", b"SYNTHETIC arithmetic fixture only, not FPGA or peripheral specifications.\n")
    def v(number):
        return {"value": number, "unit": "V", "evidence_id": "mock", "page": 1, "quote": "SYNTHETIC TEST VALUE " + number + " V"}
    request = {"schema": "M3_R08_IO_BUDGET_REQUEST_V1", "origin": "SYNTHETIC", "interface_id": "MOCK_LOGIC_ONLY_DO_NOT_WIRE",
               "fpga_endpoint": "sink", "bank_id": "MOCK_BANK", "observed_bank_id": "MOCK_BANK", "common_ground": True,
               "level_shifter": False, "evidence": [{"id": "mock", "kind": "SYNTHETIC", "file": source}],
               "driver": {"direction": "OUTPUT", "name": "MOCK_SOURCE", "voh_min": v("3.0"), "vol_max": v("0.2"), "signal_peak_max": v("3.3")},
               "sink": {"direction": "INPUT", "name": "MOCK_SINK", "bank_id": "MOCK_BANK", "five_v_tolerant": False,
                        "vih_min": v("2.0"), "vil_max": v("0.8"), "abs_input_max": v("3.6")},
               "bank": {"vccio_measured_min": v("3.2"), "vccio_measured_max": v("3.4"), "vccio_allowed_min": v("3.0"), "vccio_allowed_max": v("3.6")}}
    expected = "ACCEPT"
    if case_id == "20_negative_margin": request["driver"]["voh_min"] = v("1.0"); expected = "REJECT:NEGATIVE_VOLTAGE_MARGIN"
    elif case_id == "20_direct_five_volts": request["driver"]["signal_peak_max"] = v("5.0"); expected = "REJECT:FIVE_V_DIRECT_TO_NON_TOLERANT_FPGA"
    elif case_id == "20_bank_mismatch": request["observed_bank_id"] = "OTHER_BANK"; expected = "REJECT:BANK_ID_MISMATCH"
    elif case_id == "20_bank_unknown": request["observed_bank_id"] = None; expected = "PENDING_UNKNOWN"
    elif case_id == "20_wrong_direction": request["driver"]["direction"] = "INPUT"; expected = "REJECT:DIRECTION_MISMATCH"
    elif case_id == "20_missing_ground": request["common_ground"] = False; expected = "REJECT:NO_COMMON_GROUND"
    elif case_id == "20_missing_quote": request["sink"]["vih_min"]["quote"] = None; expected = "REJECT:VALUE_SOURCE_PAGE_QUOTE_REQUIRED"
    elif case_id == "20_real_stays_unknown": request["origin"] = "REAL_CANDIDATE"; expected = "PENDING_UNKNOWN"
    else: c.need(case_id == "20_synthetic_margins", "UNKNOWN_CASE")
    def assertions(actual):
        if actual["status"] != "REJECT":
            c.need(actual["report"]["safe_to_wire"] is None and not actual["real_pass"], "NO_WIRING_APPROVAL")
        if case_id == "20_synthetic_margins": c.need(actual["report"]["minimum_margin_V"] == "0.2", "DECIMAL_MARGIN")
    return c.run_case_record(case_id, out, expected, request, m.evaluate, assertions)
