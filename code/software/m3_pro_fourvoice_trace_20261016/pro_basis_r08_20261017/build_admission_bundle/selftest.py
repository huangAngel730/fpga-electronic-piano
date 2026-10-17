"""Coordinator-only S cross-component request fixtures. No worker/tool launch."""
import importlib.util
from pathlib import Path
import sys
import zipfile

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s); sys.modules[_s.name] = _m; _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
m = c.load_component("build_admission_bundle", "m3r08_06")
f = c.load_component("plan_consumption_guard", "m3r08_fixture_builders")


def synthetic_request(out, missing_header=False):
    dut = b'module fixture_dut(input wire clk,input wire rst_n,output wire ready,output wire [7:0] data);\n`include "fixture.svh"\nreg [7:0] mem[0:1]; initial $readmemh("rom/mock.hex",mem); endmodule\n'
    driver = b"module fixture_driver(input wire clk,output wire ready); endmodule\n"
    observer = b"module fixture_observer(input wire clk,input wire rst_n,input wire ready,input wire [7:0] data); endmodule\n"
    top = b"module fixture_tb; logic clk=0,rst_n=0; wire ready,unused; wire [7:0] data; fixture_dut dut(.clk(clk),.rst_n(rst_n),.ready(ready),.data(data)); fixture_driver drv(.clk(clk),.ready(unused)); fixture_observer obs(.clk(clk),.rst_n(rst_n),.ready(ready),.data(data)); endmodule\n"
    payload = {"compile.f": b"+incdir+include\nsources/dut.sv\n", "sources/dut.sv": dut,
               "include/fixture.svh": b"localparam FIXTURE_ONLY=1;\n", "rom/mock.hex": b"00\n01\n"}
    if missing_header: del payload["include/fixture.svh"]
    archive = f.zipped(out, payload)
    dut_file = c.fixture(out, "dut.sv", dut)
    files = {"DRIVER": c.fixture(out, "driver.sv", driver), "OBSERVER": c.fixture(out, "observer.sv", observer), "TB": c.fixture(out, "tb.sv", top)}
    return {"schema": "M3_R08_ADMISSION_APPLICATION_REQUEST_V1", "origin": "SYNTHETIC", "approved": False, "authenticated": False,
            "environment": {}, "bundle_output": str(out / "bundle"), "future_cwd": (out / "bundle/inputs").relative_to(c.ROOT).as_posix(),
            "future_output": (out / "future_output").relative_to(c.ROOT).as_posix(), "future_marker": (out / "future_marker.json").relative_to(c.ROOT).as_posix(),
            "append_sources": [{"role": role, "file": file} for role, file in files.items()], "rom_aliases": [],
            "top": "fixture_tb", "clock_model": {"kind": "SYNTHETIC_NONEXECUTED_FIXTURE", "member": "sources/dut.sv", "sha256": c.digest(dut)},
            "dependency_requests": {"01": {"schema": "M3_R08_INCLUDE_AUDIT_REQUEST_V1", "archive": archive, "selected_list": "compile.f"},
                "02": {"schema": "M3_R08_PORT_MAP_REQUEST_V1", "module_files": [dut_file, files["DRIVER"], files["OBSERVER"]], "top_file": files["TB"],
                       "required_modules": ["fixture_dut", "fixture_driver", "fixture_observer"], "direction_rules": []},
                "03": None, "05": f.tool_request(out)},
            "reservation_receipt": None, "reservation_nonce": None,
            "window_parameters": {"CAPTURE_ID": "SYNTHETIC_CAPTURE", "PLAN_STOP_ID": "SYNTHETIC_STOP", "STOP_DRIVER_CYCLE": 16,
                                  "EXPECTED_FINISH_CORE_CYCLE": 15, "MAX_CORE_SAMPLES": 32, "MAX_SIM_TIME_PS": 1000000},
            "timeout_seconds": 3, "argv": ["SYNTHETIC_APPLICATION_ONLY_NO_EXECUTION"], "stimulus_inputs": [], "driver_parameter_paths": {},
            "expected_assertions": ["NO_PROCESS_ROUTE", "SYNTHETIC_APPLICATION_ONLY"]}


def bind_pure_guard_and_reservation(out, request):
    guard_request = f.guard_request(out)
    request["dependency_requests"]["03"] = guard_request
    c.write_json(out / "STAGE_03_FULL_INPUT.json", guard_request)
    guard = c.load_component("plan_consumption_guard", "m3r08_03").evaluate(guard_request)
    c.write_json(out / "STAGE_03_FULL_ACTUAL.json", guard)
    reserve = f.reservation_request(out, guard["audit"]["plan"]["sha256"])
    c.write_json(out / "STAGE_04_FULL_INPUT.json", reserve)
    actual = c.load_component("output_reservation", "m3r08_04").evaluate(reserve)
    path = out / "STAGE_04_FULL_ACTUAL.json"
    c.write_json(path, actual)
    request["reservation_receipt"] = c.identity(path)
    request["reservation_nonce"] = reserve["nonce"]
    request["future_output"] = Path(actual["output"]).relative_to(c.ROOT).as_posix()
    request["future_marker"] = Path(actual["claim"]["path"]).relative_to(c.ROOT).as_posix()


def actual_request(out):
    archive = c.fixture(out, "OFFICIAL_C6.zip", c.C6.read_bytes())
    payload, _ = c.archive(archive)
    tb = c.ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016"
    paths = {"DRIVER": tb / "pro_basis_r06_20261017/midi_stimulus/midi_public_port_driver.sv",
             "OBSERVER": tb / "pro_basis_r07_20261017/public_capture_tb/r7a_public_observer.sv",
             "TB": tb / "pro_basis_r07_20261017/public_capture_tb/tb_r7a_public_capture.sv"}
    files = {role: c.fixture(out, path.name, path.read_bytes()) for role, path in paths.items()}
    wrapper = c.fixture(out, "C6_observer_top.sv", payload["selected/m2_138k_pro_fourvoice_observer_top_r06.sv"])
    old = c.ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/midi_stimulus/RUN_02/products"
    stimulus = [c.fixture(out, n, (old / n).read_bytes()) for n in ("bytes.drv", "reset.drv", "ready.drv", "plan.json")]
    native = c.parse((c.DOC / "tool_dependency_identity/NATIVE_READ_REQUESTS.json").read_bytes())
    c.write_json(out / "ACTUAL_NATIVE_REQUESTS_INPUT.json", native)
    modelsim = next(item["request"] for item in native["tools"] if item["name"] == "ModelSim_SE_candidate")
    return {"schema": "M3_R08_ADMISSION_APPLICATION_REQUEST_V1", "origin": "REAL_CANDIDATE", "approved": False, "authenticated": False,
            "environment": {}, "bundle_output": str(out / "C6_A_REQUEST"), "future_cwd": (out / "C6_A_REQUEST/inputs").relative_to(c.ROOT).as_posix(),
            "future_output": "code/output/m3_r08_first_public_capture_PENDING_M2", "future_marker": "code/output/m3_r08_first_public_capture_PENDING_M2.claim.json",
            "append_sources": [{"role": role, "file": file} for role, file in files.items()],
            "rom_aliases": [{"path": n, "source": "rom/" + n} for n in ("sine_wavetable.hex", "triangle_wavetable.hex")],
            "top": "tb_r7a_public_capture", "clock_model": {"kind": "SIMULATION_ONLY", "member": "sources/clock_plan_sim.v", "sha256": c.digest(payload["sources/clock_plan_sim.v"])},
            "dependency_requests": {"01": {"schema": "M3_R08_INCLUDE_AUDIT_REQUEST_V1", "archive": archive, "selected_list": "compile.f"},
                "02": {"schema": "M3_R08_PORT_MAP_REQUEST_V1", "module_files": [wrapper, files["DRIVER"], files["OBSERVER"]], "top_file": files["TB"],
                       "required_modules": ["m2_138k_pro_fourvoice_observer_top_r06", "midi_public_port_driver", "r7a_public_observer"],
                       "direction_rules": [{"module": "midi_public_port_driver", "port": "event_ready", "direction": "output"}]}, "03": None, "05": modelsim},
            "known_tool_requests": native,
            "reservation_receipt": None, "reservation_nonce": None,
            "window_parameters": {k: None for k in m.WINDOW}, "timeout_seconds": None, "argv": [],
            "stimulus_inputs": stimulus, "driver_parameter_paths": {"BYTE_PLAN": "bytes.drv", "RESET_PLAN": "reset.drv", "READY_PLAN": "ready.drv"},
            "expected_assertions": ["PUBLIC_38_OBS_AND_5_PINS_PRE_NBA", "SEPARATE_FRAME_F_AND_ACCEPT_A", "INDEPENDENT_RESET_EDGES",
                                    "UNIQUE_END_MONITOR_END", "MISSING_M1_FIELDS_REMAIN_NULL", "NO_PRIVATE_DSP_OR_FORCE",
                                    "READY_DRIVER_DIAGNOSTIC_DISCONNECTED", "REAL_TOOL_EXIT_AND_CLEANUP_RECEIPT_REQUIRED"]}


def run_case(case_id, output_dir):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    expected = "ACCEPT"
    if case_id == "06_C6_A_application":
        request = actual_request(out); expected = "PENDING_UNKNOWN"
    else:
        request = synthetic_request(out, missing_header=case_id == "06_missing_header")
        if case_id in ("06_synthetic_application", "06_tool_dependency_unknown", "06_foreign_reservation"):
            bind_pure_guard_and_reservation(out, request)
        if case_id == "06_tool_dependency_unknown":
            request["dependency_requests"]["05"]["unresolved_dynamic_dependencies"] = ["UNKNOWN_RUNTIME_REFERENCE"]
            expected = "PENDING_UNKNOWN"
        elif case_id == "06_foreign_reservation":
            request["future_output"] = (out / "different_output").relative_to(c.ROOT).as_posix()
            expected = "REJECT:RESERVATION_APPLICATION_MISMATCH"
        elif case_id == "06_approved_rejected": request["approved"] = True; expected = "REJECT:SELF_APPROVAL_FORBIDDEN"
        elif case_id == "06_legacy_P7_rejected": request["environment"] = {"P7_ALLOW_EXECUTION": "1"}; expected = "REJECT:LEGACY_EXECUTION_SWITCH"
        elif case_id == "06_missing_TB": request["append_sources"] = [x for x in request["append_sources"] if x["role"] != "TB"]; expected = "REJECT:REQUIRED_TB_OBSERVER_DRIVER"
        elif case_id == "06_missing_header": expected = "REJECT:INCLUDE_MISSING_OR_INCDIR:fixture.svh"
        elif case_id == "06_foreign_port_map":
            request["dependency_requests"]["02"]["top_file"] = c.fixture(out, "foreign_top.sv", b"module foreign; endmodule\n")
            expected = "REJECT:PORT_MAP_TB_SOURCE_MISMATCH"
        else: c.need(case_id == "06_synthetic_application", "UNKNOWN_CASE")
    def assertions(actual):
        if actual["status"] != "REJECT":
            app = actual["application"]
            c.need(app["approved"] is False and app["execution_allowed"] is False and not actual["real_pass"], "APPLICATION_NOT_ADMISSION")
            if case_id == "06_C6_A_application":
                c.need(len(app["source_graph"]["units"]) == 74 and len(app["stimulus_inputs"]) == 4 and app["pending"], "C6_A_BODY_AND_GAPS")
                with zipfile.ZipFile(actual["source_archive"]["path"]) as z:
                    c.need("inputs/include/sine_table.svh" in z.namelist() and "inputs/bytes.drv" in z.namelist(), "C6_INPUT_BODIES")
    return c.run_case_record(case_id, out, expected, request, m.evaluate, assertions)
