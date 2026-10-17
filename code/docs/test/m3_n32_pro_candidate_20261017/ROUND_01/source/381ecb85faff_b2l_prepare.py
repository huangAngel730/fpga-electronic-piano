"""Prepare-only input contract for one future synthesis probe; never run EDA.

This is not a Gowin project generator or an authorization mechanism. M2 must
choose the representative configuration and approve a separate tool entry.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from b2d_run import sources
from b2i_audit import PIN, pinned
from inventory import FROZEN, ROOT, slot_width

TOP = "b2l_resource_probe"
PROFILE = "audio_and_public_read_no_injection"
ROM_ROOT = "E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/"
STATUS = "B2L_PREPARED_NOT_AUTHORIZED_FOR_SYNTHESIS"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def config(n, response):
    slot_width(n)
    if type(response) is not int or not 1 <= response <= 64:
        raise ValueError("RESPONSE_NOT_SUPPORTED")
    return dict(N=n, response=response, profile=PROFILE)


def wrapper(n, response):
    """Production-facing audio/read ports, not the enormous diagnostic buses.

    Keeping public readback means B1 payload banks remain observable. No sample
    generator, PLL, pin assignments, synchronizers or external device are added.
    Unconnected diagnostic state may be optimized; this is an explicit profile,
    not a promise to retain every source-declared bit in the B2i ledger.
    """
    sw = slot_width(n)
    config(n, response)
    return f"""// Preparation only; M2 has not selected this resource profile.
// Single clk, async low reset assertion; reset release synchronized upstream.
module {TOP} (
    input wire clk, rst_n, cancel,
    input wire event_valid, input wire [63:0] event_data,
    output wire event_ready,
    input wire sample_valid, input wire [31:0] sample_id,
    output wire sample_ready, result_valid,
    input wire result_ready,
    output wire [31:0] result_id,
    output wire signed [23:0] left, right,
    output wire late, aborted, idle, fault, publish,
    output wire [1:0] abort_reason,
    input wire read_valid, input wire [{sw-1}:0] read_slot,
    output wire read_ready, read_out_valid,
    output wire [73:0] read_context
);
    b2d_event_audio #(.N({n}), .RESPONSE({response})) candidate (
        .clk(clk), .rst_n(rst_n), .cancel(cancel),
        .event_valid(event_valid), .event_data(event_data), .event_ready(event_ready),
        .sample_valid(sample_valid), .sample_id(sample_id), .sample_ready(sample_ready),
        .result_valid(result_valid), .result_ready(result_ready), .result_id(result_id),
        .left(left), .right(right), .late(late), .aborted(aborted),
        .abort_reason(abort_reason), .idle(idle), .fault(fault), .publish(publish),
        .read_valid(read_valid), .read_slot(read_slot), .read_ready(read_ready),
        .read_out_valid(read_out_valid), .read_context(read_context),
        .inject_valid(1'b0), .inject_tag({72+sw}'d0), .inject_context(74'd0)
    );
endmodule
""".encode("ascii")


def generated(output, n, response):
    """Reconstruct expected output from immutable Git identity, not manifest SHA."""
    selection = config(n, response)
    functional = sources()[:-1]
    headers = sorted((FROZEN / "include").glob("*.svh"))
    roms = sorted((FROZEN / "rom").glob("*.mem"))
    # The frozen manifest, rather than a fabricated resource estimate, defines
    # the complete 7-ROM set. Actual references below select a strict subset.
    if len(roms) != 7 or len(headers) != 2 or len(functional) != 13:
        raise ValueError("INPUT_SET_CHANGED")
    payload, records = {}, []
    destination_rom = (output / "rom").as_posix() + "/"
    for path in functional + headers + roms:
        original = pinned(path)
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        category = "sources" if path in functional else "include" if path in headers else "rom"
        target = category + "/" + path.name
        # Only quoted exact frozen ROM roots may be relocated. No algorithms,
        # HDL names, numeric constants or include bodies are transformed.
        matches = list(re.finditer(r'"' + re.escape(ROM_ROOT) + r'([^"\n]+)"', raw.decode("utf-8")))
        for match in matches:
            if match[1] not in {p.name for p in roms}:
                raise ValueError("UNKNOWN_ROM_REFERENCE")
        relocated = raw.replace(('"'+ROM_ROOT).encode(), ('"'+destination_rom).encode())
        if relocated.replace(('"'+destination_rom).encode(), ('"'+ROM_ROOT).encode()) != raw:
            raise ValueError("PATH_RELOCATION_NOT_REVERSIBLE")
        payload[target] = relocated
        records.append(dict(original=original, staged=target,
                            rom_path_replacements=len(matches), sha256=digest(relocated),
                            bytes=len(relocated)))
    payload[TOP + ".sv"] = wrapper(n, response)
    # This clock file is preparation, not STA. No I/O timing/exception claims.
    payload["clock.sdc"] = (
        "create_clock -name sys_clk -period 25.000 [get_ports {clk}]\n"
        "set_clock_uncertainty -setup 1.000 [get_clocks {sys_clk}]\n"
        "set_clock_uncertainty -hold 0.650 [get_clocks {sys_clk}]\n"
    ).encode("ascii")
    source_order = ["sources/"+p.name for p in functional] + [TOP+".sv"]
    # JSON carries paths without shell/Tcl quoting ambiguity. No executable
    # tool commands are generated; ROM absolute paths make relocation explicit.
    payload["inputs.json"] = (json.dumps(dict(
        sources=source_order, include="include", top=TOP, clock="clock.sdc",
        source_pin=PIN, configuration=selection), indent=2)+"\n").encode()
    plan = dict(status=STATUS, schema=1, configuration=selection, source_pin=PIN,
                target_proposal=dict(device="GW5AST-LV138PG484AC1/I0",
                                     tool="Gowin 1.9.11.03 Education", verified_here=False),
                new_synthesis=False, new_PnR=False, new_bitstream=False,
                device_operations=False, task_complete=False,
                representative_configuration_approved=False,
                physical_resources="UNKNOWN", physical_STA="NOT_RUN",
                source_order=source_order, inputs=records,
                artifacts={name: dict(sha256=digest(raw), bytes=len(raw))
                           for name, raw in sorted(payload.items())})
    return plan, payload


def destination(path):
    path = path.resolve()
    base = (ROOT / "code/output").resolve()
    if path == base or not path.is_relative_to(base):
        raise ValueError("OUTPUT_OUTSIDE_NEW_CHILD")
    # Generated absolute ROM strings and future tool readers must not interpret
    # quotes, control characters or Tcl metacharacters in the output directory.
    if not re.fullmatch(r"[A-Za-z0-9_./:\-]+", path.as_posix()):
        raise ValueError("UNSAFE_OUTPUT_PATH")
    return path


def prepare(path, n, response):
    path = destination(path)
    if path.exists():
        raise ValueError("REFUSE_EXISTING_OUTPUT")
    plan, payload = generated(path, n, response)
    path.mkdir(parents=True, exist_ok=False)
    for name, raw in payload.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    with (path / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2)
        stream.write("\n")
    return verify(path)


def verify(path):
    path = destination(path)
    value = json.loads((path / "plan.json").read_text(encoding="utf-8"))
    chosen = value["configuration"]
    expected, payload = generated(path, chosen["N"], chosen["response"])
    # Strict JSON type identity: True must not pass as the integer 1.
    if json.dumps(value, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("PLAN_IDENTITY")
    actual = {p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file()}
    if actual != set(payload) | {"plan.json"}:
        raise ValueError("ARTIFACT_SET")
    for name, raw in payload.items():
        if (path / name).read_bytes() != raw:
            raise ValueError("ARTIFACT_IDENTITY:"+name)
    return dict(status=STATUS, configuration=expected["configuration"],
                files=len(actual), input_count=len(expected["inputs"]),
                new_synthesis=False, physical_resources="UNKNOWN", task_complete=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n", type=int, choices=(4, 8, 16, 32))
    parser.add_argument("--response", type=int)
    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            if args.n is None or args.response is None:
                raise ValueError("EXPLICIT_CONFIGURATION_REQUIRED")
            result = prepare(args.output, args.n, args.response)
        else:
            if args.n is not None or args.response is not None:
                raise ValueError("VERIFY_USES_PINNED_CONFIGURATION")
            result = verify(args.output)
        print(json.dumps(result))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps(dict(status="FAIL", error=str(error))))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
