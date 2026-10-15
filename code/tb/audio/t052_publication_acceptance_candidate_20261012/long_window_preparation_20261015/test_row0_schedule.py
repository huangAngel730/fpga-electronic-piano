"""Source-bound, pure-software driver schedule proof; never invoke HDL tools."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time


EDGE_COUNT = 8_536_336
SOURCE_SHA = "daf67848153214d791d1f51e348dbbe7c7995c06424f0a819a23080c1fba3e20"
CONTROLS_SHA = "fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0"
CONTROLS_BYTES = 375_598_784

# This is deliberately a closed source template, not a general SV interpreter.
# The whole-file SHA additionally locks other processes, EOF test and timescale.
DRIVER = """
initial begin
    clk = 0;
    driver_index = 0;
    cycle = 0;
    input_file = $fopen("controls.hex", "r");
    if (!input_file) $fatal(1, "CONTROL_OPEN_FAILED");
    apply_next();
    forever #10 clk = ~clk;
end
always @(negedge clk) begin
    if (($time > 0) && (driver_index < LAST_CYCLE)) begin
        driver_index = driver_index + 1;
        apply_next();
    end
end
always @(posedge clk) begin
    if (cycle == LAST_CYCLE) begin
        #1;
        status = $fscanf(input_file, "%h", control_word);
        if (status != -1) $fatal(1, "EXTRA_CONTROL_INPUT");
        $fclose(input_file);
        $display("T052_LONG_CAPTURE_FINISHED_NOT_ACCEPTANCE_PASS");
        $finish(0);
    end else cycle <= cycle + 1;
end
"""


def stripped(text: str) -> str:
    """Only used for this closed template; not a general SV lexer."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return re.sub(r"\s+", "", text)


def require(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise ValueError(diagnostic)


def validate_source(raw: bytes, enforce_sha: bool = True) -> None:
    source = raw.decode("utf-8")
    region = source.split("// DRIVER_BEGIN:", 1)[1]
    region = region.split("\n", 1)[1].split("// DRIVER_END", 1)[0]
    compact = stripped(region)
    if "#0" in compact:
        raise ValueError("DELTA_TIME_NOT_GUARD")
    if "if(($time>0)&&(driver_index<LAST_CYCLE))" not in compact:
        raise ValueError("SOURCE_NO_TIME_GUARD")
    if compact != stripped(DRIVER):
        raise ValueError("SOURCE_DRIVER_TEMPLATE_MISMATCH")
    if "localparamintegerLAST_CYCLE=8536335;" not in stripped(source):
        raise ValueError("SOURCE_EDGE_COUNT_MISMATCH")
    if enforce_sha and hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError("SOURCE_IDENTITY_MISMATCH")


def schedule(guard: bool, t0_callback: bool) -> dict:
    """Enumerate row labels, not DUT ports or expected algorithm outputs.

    A callback that executes after row0 is the adverse legal t0 ordering.
    If it executes before initialization, the guard still excludes it.
    A #0 callback has t=0 too, so guard=False represents that counterexample.
    """
    row, reads = 0, 1
    if t0_callback and not guard:
        row, reads = 1, 2
    for edge in range(EDGE_COUNT):
        posedge_ns = 10 + 20 * edge
        if row != edge:
            raise ValueError(
                f"SCHEDULE_ROW_MISMATCH edge={edge} time_ns={posedge_ns} "
                f"expected_row={edge} actual_row={row} reads={reads}"
            )
        if edge != EDGE_COUNT - 1:
            negedge_ns = 20 * (edge + 1)
            require(posedge_ns < negedge_ns < posedge_ns + 20,
                    "SCHEDULE_EDGE_ORDER")
            row += 1
            reads += 1
    require(reads == EDGE_COUNT and row == EDGE_COUNT - 1,
            "SCHEDULE_ROW_COUNT")
    last_ns = 10 + 20 * (EDGE_COUNT - 1)
    require(last_ns + 1 < 20 * EDGE_COUNT, "SCHEDULE_EXTRA_NEGEDGE")
    return {
        "posedge_count": EDGE_COUNT,
        "row_reads": reads,
        "first_posedge_ns": 10,
        "first_row": 0,
        "first_positive_negedge_ns": 20,
        "first_updated_row": 1,
        "last_posedge_ns": last_ns,
        "last_row": row,
        "finish_ns": last_ns + 1,
        "next_negedge_ns": 20 * EDGE_COUNT,
        "t0_callback": t0_callback,
    }


def reject(call, diagnostic: str) -> str:
    try:
        call()
    except ValueError as error:
        actual = str(error)
        if not actual.startswith(diagnostic):
            raise AssertionError((diagnostic, actual)) from error
        return actual
    raise AssertionError(f"false acceptance: expected {diagnostic}")


def file_identity(path: Path) -> dict:
    digest = hashlib.sha256()
    size, lines = 0, 0
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(data)
            size += len(data)
            lines += data.count(b"\n")
    return {"path": str(path.resolve()), "bytes": size,
            "sha256": digest.hexdigest(), "lf_count": lines}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Fresh output only: no prior evidence can be overwritten.
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    source_path = Path(__file__).with_name("tb_t052_long.sv")
    source = source_path.read_bytes()
    receipt = {
        "kind": "STATIC_SOURCE_BOUND_SCHEDULE_ONLY",
        "argv": sys.orig_argv,
        "cwd": str(Path.cwd()),
        "hdl_compile_count": 0,
        "rtl_execution_count": 0,
        "cases": [],
        "status": "FAIL",
    }
    try:
        source_before = file_identity(source_path)
        control_before = file_identity(args.controls)
        receipt["source_before"] = source_before
        receipt["controls_before"] = control_before
        require(control_before["sha256"] == CONTROLS_SHA, "CONTROLS_SHA")
        require(control_before["bytes"] == CONTROLS_BYTES, "CONTROLS_SIZE")
        require(control_before["lf_count"] == EDGE_COUNT, "CONTROLS_ROWS")
        validate_source(source)
        receipt["cases"].append({"name": "exact_source_and_frozen_controls",
                                 "status": "PASS"})
        for delivered in (False, True):
            result = schedule(True, delivered)
            receipt["cases"].append({"name": f"full_schedule_t0_{delivered}",
                                     "status": "PASS", "result": result})
        guard = b"(($time > 0) && (driver_index < LAST_CYCLE))"
        for name, replacement, diagnostic in (
            ("old_unguarded", b"(driver_index < LAST_CYCLE)",
             "SOURCE_NO_TIME_GUARD"),
            ("delta_only", b"(driver_index < LAST_CYCLE)",
             "DELTA_TIME_NOT_GUARD"),
        ):
            mutant = source.replace(guard, replacement)
            if name == "delta_only":
                mutant = mutant.replace(b"always @(negedge clk) begin\n",
                                        b"always @(negedge clk) begin\n        #0;\n")
            (args.output / f"{name}.sv.txt").write_bytes(mutant)
            structural = reject(lambda: validate_source(mutant), diagnostic)
            behavioral = reject(lambda: schedule(False, True),
                                "SCHEDULE_ROW_MISMATCH")
            receipt["cases"].append({
                "name": name, "status": "EXPECTED_REJECT",
                "source_sha256": hashlib.sha256(mutant).hexdigest(),
                "diagnostic": structural, "counterexample": behavioral,
                "compiled": False,
            })
        mutant = source.replace(b"forever #10 clk", b"forever #11 clk")
        receipt["cases"].append({
            "name": "wrong_clock_period", "status": "EXPECTED_REJECT",
            "diagnostic": reject(lambda: validate_source(mutant),
                                 "SOURCE_DRIVER_TEMPLATE_MISMATCH"),
        })
        mutant = source.replace(b"LAST_CYCLE = 8536335", b"LAST_CYCLE = 8536334")
        receipt["cases"].append({
            "name": "shortened_window", "status": "EXPECTED_REJECT",
            "diagnostic": reject(lambda: validate_source(mutant),
                                 "SOURCE_EDGE_COUNT_MISMATCH"),
        })
        source_after = file_identity(source_path)
        controls_after = file_identity(args.controls)
        receipt["source_after"] = source_after
        receipt["controls_after"] = controls_after
        require(source_before == source_after, "SOURCE_CHANGED_DURING_TEST")
        require(control_before == controls_after, "CONTROLS_CHANGED_DURING_TEST")
        receipt["status"] = "PASS_STATIC_ONLY"
        receipt["exit_code"] = 0
    except Exception as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
        receipt["exit_code"] = 1
    receipt["elapsed_seconds"] = time.monotonic() - start
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
