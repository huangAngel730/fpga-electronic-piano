"""R08-A fixture construction only when called by the coordinator's run_case."""
import copy
import importlib.util
import io
from pathlib import Path
import struct
import sys
import zipfile

_p = Path(__file__).with_name("m3r08_common.py")
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]


def zipped(out, payload, name="source.zip"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path, raw in payload.items():
            z.writestr("inputs/" + path, raw)
    return c.fixture(out, name, buffer.getvalue())


def include_request(out, mode="literal"):
    payload = {"compile.f": b"+incdir+include\nsources/base.sv\n", "sources/base.sv":
               b'module base; `include "a.svh"\nreg [7:0] mem[0:1]; initial $readmemh("rom/a.hex",mem); endmodule\n',
               "include/a.svh": b'`include "b.svh"\n', "include/b.svh": b"localparam N=1;\n", "rom/a.hex": b"00\n01\n"}
    if mode == "missing_header": del payload["include/b.svh"]
    elif mode == "wrong_incdir": payload["compile.f"] = b"+incdir+wrong\nsources/base.sv\n"
    elif mode == "duplicate_module":
        payload["compile.f"] += b"sources/duplicate.sv\n"
        payload["sources/duplicate.sv"] = b"module base; endmodule\n"
    elif mode == "escape": payload["include/a.svh"] = b'`include "../../outside.svh"\n'
    elif mode == "macro": payload["include/b.svh"] = b"`include HEADER_FROM_MACRO\n"
    elif mode == "missing_rom": del payload["rom/a.hex"]
    return {"schema": "M3_R08_INCLUDE_AUDIT_REQUEST_V1", "archive": zipped(out, payload), "selected_list": "compile.f"}


def toy_ports(out, mode="valid"):
    module = b"module fixture_dut(input wire clk,input wire rst_n,output wire ready,output wire [7:0] data); endmodule\nmodule fixture_driver(input wire clk,output wire ready); endmodule\n"
    top = "module fixture_top; logic clk=0,rst_n=0; wire ready,unused_ready; wire [7:0] data; fixture_dut dut(.clk(clk),.rst_n(rst_n),.ready(ready),.data(data)); fixture_driver drv(.clk(clk),.ready(unused_ready)); endmodule\n"
    if mode == "ready": top = top.replace(".ready(unused_ready)", ".ready(ready)")
    elif mode == "width": top = top.replace("[7:0] data", "[3:0] data")
    elif mode == "private": top = top.replace(".clk(clk)", ".clk(dut.private_clk)", 1)
    elif mode == "missing_input": top = top.replace(".rst_n(rst_n),", "")
    elif mode == "output_constant": top = top.replace(".ready(ready)", ".ready(1'b1)", 1)
    elif mode == "output_slice":
        top = top.replace("wire ready,unused_ready;", "wire ready,unused_ready; wire [1:0] bits;")
        top = top.replace(".ready(ready)", ".ready(bits[0])", 1).replace(".ready(unused_ready)", ".ready(bits[0])")
    elif mode == "unknown_width": module = module.replace(b"[7:0] data", b"[`UNRESOLVED_WIDTH-1:0] data")
    elif mode in ("parameters", "caller_parameters", "unknown_caller_parameters"):
        module = module.replace(b"module fixture_dut(", b"module fixture_dut #(parameter N=8)(").replace(b"[7:0] data", b"[N-1:0] data")
        top = top.replace("fixture_dut dut", "fixture_dut #(.N(8)) dut")
        if mode == "caller_parameters":
            top = top.replace("module fixture_top;", "module fixture_top #(parameter N=4);")
            top = top.replace(".N(8)", ".N(N)").replace("[7:0] data", "[3:0] data")
        elif mode == "unknown_caller_parameters":
            top = top.replace(".N(8)", ".N(N)")
    file = c.fixture(out, "modules.sv", module)
    request = {"schema": "M3_R08_PORT_MAP_REQUEST_V1", "module_files": [file],
               "top_file": c.fixture(out, "top.sv", top.encode("utf-8")),
               "required_modules": ["fixture_dut", "fixture_driver"],
               "direction_rules": [{"module": "fixture_driver", "port": "ready", "direction": "output"}]}
    if mode == "missing_wrapper": request["required_modules"].append("absent_wrapper")
    return request


def guard_request(out):
    guard = c.load_component("plan_consumption_guard", "m3r08_03")
    validation_root = Path(out) / "guard_validation"
    (validation_root / "RUN_01").mkdir(parents=True, exist_ok=False)
    # Read the signed constants only; no existing test or runner is imported.
    c.write_json(Path(out) / "GUARD_LOAD_INPUT.json", {"validation_root": str(validation_root),
                                                      "signed_validator": c.identity(guard.LEGACY)})
    module = guard.validator(validation_root)
    trust = c.parse(module.TRUST_PATH.read_bytes())
    tb = c.ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter"
    def entry(path):
        item = c.identity(path)
        return {"path": Path(path).relative_to(c.ROOT).as_posix(), "sha256": item["sha256"]}
    spec = {"schema": "M3_R6_TOOL_PLAN_SPEC_V1", "mode": "SOFTWARE_FIXTURE", "approved": False,
            "tool_kind": "PYTHON_SOFTWARE_FIXTURE", "fixture_authority": "R06_M3_SOFTWARE_FIXTURE_ONLY",
            "sources": [entry(tb / "fixture_source.sv")], "roms": [entry(tb / "fixture_rom.hex")],
            "testbenches": [entry(tb / "fixture_tb.sv")],
            "executable": {"path": trust["python"]["path"], "sha256": trust["python"]["sha256"]},
            "dependencies": [entry(Path(trust[k]["path"])) for k in ("worker", "job_helper", "legacy")] + [entry(guard.LEGACY)],
            "argv": [trust["python"]["path"], "-I", "-S", "-B", trust["worker"]["path"], "stream"],
            "cwd": module.HERE.relative_to(c.ROOT).as_posix(),
            "output_dir": (validation_root / "RUN_01/NEVER_CREATED").relative_to(c.ROOT).as_posix(),
            "consumption_marker": (validation_root / "RUN_01/NEVER_CREATED.json").relative_to(c.ROOT).as_posix(),
            "timeout_seconds": 5}
    sp, pp = validation_root / "RUN_01/spec.json", validation_root / "RUN_01/plan.json"
    c.write_json(sp, spec)
    c.write_json(Path(out) / "GUARD_REBUILD_INPUT.json", {"spec": spec, "pinned_spec": c.identity(sp),
                                                         "validation_root": str(validation_root)})
    normalized = module.rebuild(sp.relative_to(c.ROOT).as_posix(), c.identity(sp)["sha256"])
    c.write_json(pp, normalized)
    return {"schema": "M3_R08_GUARD_REQUEST_V1", "validation_root": str(validation_root),
            "spec": c.identity(sp), "plan": c.identity(pp), "requested_action": "VALIDATE_ONLY"}


def reservation_request(out, plan_sha="1" * 64):
    return {"schema": "M3_R08_RESERVATION_REQUEST_V1", "action": "RESERVE", "root": str(Path(out) / "reservation"),
            "capture_id": "SYNTHETIC_CAPTURE", "plan_sha256": plan_sha, "nonce": "a" * 32,
            "guard": {"validated_plan_sha256": plan_sha, "permission": "NOT_GRANTED"}, "outcome": None}


def tool_request(out, mode="valid"):
    script = c.fixture(out, "tool.py", b"import helper\n")
    helper = c.fixture(out, "helper.py", b"VALUE=1\n")
    interpreter = c.fixture(out, "interpreter.identity", b"SYNTHETIC INTERPRETER FILE, NEVER EXECUTED\n")
    request = {"schema": "M3_R08_TOOL_IDENTITY_REQUEST_V1", "origin": "SYNTHETIC",
               "tool": {"kind": "PYTHON_SCRIPT", "file": script}, "interpreter": interpreter,
               "dependencies": [{"name": "helper", "kind": "PYTHON_SCRIPT", "file": helper}],
               "expected_dependencies": ["helper"], "unresolved_dynamic_dependencies": []}
    if mode == "changed":
        c.fixture(out, "tool.original.py", Path(script["path"]).read_bytes())
        Path(script["path"]).write_bytes(b"import changed\n")
    elif mode == "missing": request["dependencies"] = []
    elif mode == "version": request["tool"] = {"version": "CALLER_VERSION_ONLY"}
    elif mode == "dynamic": request["unresolved_dynamic_dependencies"] = ["DYNAMIC_REFERENCE_UNKNOWN"]
    elif mode == "pe":
        raw = bytearray(1024); raw[:2] = b"MZ"; struct.pack_into("<I", raw, 60, 128)
        raw[128:132] = b"PE\0\0"; struct.pack_into("<H", raw, 134, 1); struct.pack_into("<H", raw, 148, 224)
        struct.pack_into("<H", raw, 152, 0x10B); struct.pack_into("<II", raw, 256, 0x1000, 40)
        struct.pack_into("<IIII", raw, 384, 512, 0x1000, 512, 512)
        struct.pack_into("<IIIII", raw, 512, 0, 0, 0, 0x1040, 0); raw[576:588] = b"missing.dll\0"
        request["tool"] = {"kind": "PE", "file": c.fixture(out, "synthetic_not_executable.exe", bytes(raw))}
        request["dependencies"], request["expected_dependencies"] = [], []
    return request
