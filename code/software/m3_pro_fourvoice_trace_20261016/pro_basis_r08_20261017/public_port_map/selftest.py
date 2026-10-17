"""Coordinator-only S public-port cases; import runs no case."""
import importlib.util
from pathlib import Path
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("public_port_map", "m3r08_02")
f = c.load_component("plan_consumption_guard", "m3r08_fixture_builders")


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    cases = {"02_actual_A": ("actual", "ACCEPT"), "02_ready_double_driver": ("ready", "REJECT:MULTIPLE_PUBLIC_DRIVERS:ready"),
             "02_wrong_width": ("width", "REJECT:PUBLIC_WIDTH_MISMATCH:data"),
             "02_missing_wrapper": ("missing_wrapper", "REJECT:MISSING_WRAPPER_OR_MODULE:absent_wrapper"),
             "02_private_expression": ("private", "REJECT:PRIVATE_HIERARCHY"),
             "02_missing_required_input": ("missing_input", "REJECT:MISSING_REQUIRED_INPUT:rst_n"),
             "02_unknown_width": ("unknown_width", "PENDING_UNKNOWN"), "02_parameter_override": ("parameters", "ACCEPT"),
             "02_output_constant": ("output_constant", "REJECT:OUTPUT_EXPRESSION_NOT_WRITABLE:ready"),
             "02_output_slice_overlap": ("output_slice", "PENDING_UNKNOWN"),
             "02_caller_parameter_scope": ("caller_parameters", "ACCEPT"),
             "02_unknown_caller_parameter": ("unknown_caller_parameters", "PENDING_UNKNOWN")}
    mode, expected = cases[case_id]
    if mode == "actual":
        tb = c.ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016"
        rtl = c.ROOT / "code/rtl/board/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017"
        paths = [rtl / "m2_138k_pro_fourvoice_observer_top_r06.sv", tb / "pro_basis_r06_20261017/midi_stimulus/midi_public_port_driver.sv",
                 tb / "pro_basis_r07_20261017/public_capture_tb/r7a_public_observer.sv"]
        request = {"schema": "M3_R08_PORT_MAP_REQUEST_V1", "module_files": [c.fixture(out, p.name, p.read_bytes()) for p in paths],
                   "top_file": c.fixture(out, "tb_r7a_public_capture.sv", (tb / "pro_basis_r07_20261017/public_capture_tb/tb_r7a_public_capture.sv").read_bytes()),
                   "required_modules": ["m2_138k_pro_fourvoice_observer_top_r06", "midi_public_port_driver", "r7a_public_observer"],
                   "direction_rules": [{"module": "midi_public_port_driver", "port": "event_ready", "direction": "output"},
                                       {"module": "m2_138k_pro_fourvoice_observer_top_r06", "port": "obs_core_clk", "direction": "output"}]}
    else:
        request = f.toy_ports(out, mode)
    def assertions(actual):
        if mode == "caller_parameters":
            c.need(actual["report"]["instance_parameters"][0]["numeric_values"]["N"] == 4, "CALLER_SCOPE_NOT_CALLEE_DEFAULT")
        if mode == "actual":
            report = actual["report"]
            d = report["modules"]["midi_public_port_driver"]["ports"]
            c.need(d["event_ready"]["direction"] == "output" and d["event_ready"]["width"] == 1 and
                   d["event_data"]["width"] == 64, "ACTUAL_DRIVER_DECLARATIONS")
            c.need(report["drivers"]["driver_ready_not_connected"] == ["u_driver.event_ready"] and
                   report["drivers"]["obs_event_ready"] == ["dut.obs_event_ready"], "READY_SEPARATE_DRIVERS")
    return c.run_case_record(case_id, out, expected, request, m.evaluate, assertions)
