"""Prepare R01 inputs/identities and a LOCKED proposal. Never invokes HDL."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import zipfile

from check_capture import sha
from plan import COUNT, M1_SHA, VERSION, Calendar, controls, pack

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TB = ROOT / "code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"
SOURCE_MANIFEST = ROOT / "code/docs/test/t052_publication_acceptance_20261012/CONTROL_PREPARATION_20261012/source_manifest.json"


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def identity(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))


def archive_members(output):
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    result = {}
    for group in (manifest["raw_archive"], manifest["readonly_archive"]):
        path = ROOT / group["path"]
        if sha(path) != group["sha256"]:
            raise ValueError("ARCHIVE_IDENTITY:" + str(path))
        with zipfile.ZipFile(path) as archive:
            for member, spec in group["members"].items():
                raw = archive.read(member)
                if len(raw) != spec["bytes"] or hashlib.sha256(raw).hexdigest() != spec["sha256"]:
                    raise ValueError("MEMBER_IDENTITY:" + member)
                name = Path(member).name
                destination = output / name
                with destination.open("xb") as stream:
                    stream.write(raw)
                result[name] = dict(identity(destination), archive=group["path"], member=member)
    return result


def audit_sources():
    """Narrow textual checks only; not a parser/elaboration qualification."""
    tb = (TB / "tb_t052_long.sv").read_text(encoding="ascii")
    observer = (TB / "t052_long_observer.sv").read_text(encoding="ascii")
    for text in (tb, observer):
        if "dut." in text or "$root" in text or "$strobe" in text:
            raise ValueError("PUBLIC_PRE_NBA_BOUNDARY")
    if "cycle <= cycle + 1" not in tb or "always @(negedge clk)" not in tb:
        raise ValueError("DRIVER_SCHEDULE")
    if "LAST_CYCLE = 8536335" not in tb or "#170726720" not in tb:
        raise ValueError("SIM_WINDOW")
    if "always @(rst_n)" not in observer or 'transaction("CANCEL", "reset")' not in observer:
        raise ValueError("ASYNC_RESET_SOURCE")
    return dict(status="NARROW_TEXT_AUDIT_PASS", HDL_compiled=False,
                scheduler_semantics_runtime_verified=False)


def inventory(suite):
    executables = [suite / "bin/iverilog.exe", suite / "bin/vvp.exe"]
    existing = [p for p in executables if p.is_file()]
    for directory, pattern in ((suite / "bin", "*.dll"), (suite / "lib", "*.dll"),
                               (suite / "lib/ivl", "*")):
        if directory.exists():
            existing.extend(p for p in directory.glob(pattern) if p.is_file())
    return dict(requested_suite=str(suite),
                missing=[str(p) for p in executables if not p.is_file()],
                files=[identity(p) for p in sorted(set(existing))],
                version="UNKNOWN_NOT_INVOKED", version_queries=0,
                closure="STATIC_SUPERSET_ONLY; actual loaded DLLs not observed")


def prepare(output, confirmation, suite, qualification):
    if output.exists():
        raise ValueError("OUTPUT_EXISTS")
    if sha(confirmation) != M1_SHA:
        raise ValueError("M1_CONFIRMATION_SHA")
    sources = [*HERE.glob("*.py"), *TB.glob("*.sv"), SOURCE_MANIFEST, confirmation]
    before = {str(p.resolve()): identity(p) for p in sources}
    tools = inventory(suite)
    qualified = json.loads(qualification.read_text(encoding="utf-8"))
    if qualified.get("status") != "TOOL_METADATA_PASS" or qualified["after"] != tools:
        raise ValueError("TOOL_QUALIFICATION_IDENTITY")
    before[str(qualification.resolve())] = identity(qualification)
    sources.append(qualification)
    output.mkdir(parents=True)
    (output / "readonly").mkdir()
    frozen = archive_members(output / "readonly")
    for p in TB.glob("*.sv"):
        shutil.copyfile(p, output / p.name)
    shutil.copyfile(confirmation, output / "M1_INPUT_CONFIRMATION.md")
    started = time.monotonic()
    calendar = Calendar()
    input_hash = hashlib.sha256()
    with (output / "controls.hex").open("xb") as control_file, \
            (output / "expected_publications.jsonl").open("x", encoding="ascii", newline="\n") as ledger:
        block = bytearray()
        for cycle in range(COUNT):
            row = controls(cycle)
            block.extend(f"{pack(row):043x}\n".encode("ascii"))
            if len(block) >= 1 << 20:
                control_file.write(block)
                input_hash.update(block)
                block.clear()
            _, events = calendar.step(cycle, row)
            for event in events:
                ledger.write(json.dumps(event, separators=(",", ":"))+"\n")
        control_file.write(block)
        input_hash.update(block)
        ledger.write(json.dumps(calendar.end(COUNT), separators=(",", ":"))+"\n")
    expected_end = dict(type="END", rows=COUNT, accepted=8207, published=8201, cancelled=6, open=0)
    if calendar.end(COUNT) != expected_end:
        raise ValueError("M1_R01_TOTALS")
    control = identity(output / "controls.hex")
    if control["sha256"] != input_hash.hexdigest() or control["bytes"] != COUNT * 44:
        raise ValueError("DRIVER_BYTES_OR_SHA")
    checker = HERE / "check_capture.py"
    proposal = dict(
        schema="T052_LONG_STATIC_PREPARATION_R01", plan=VERSION,
        execution_authorized=False, machine=os.environ.get("COMPUTERNAME", "UNKNOWN"),
        status="PREPARED_TOOL_BINDING_BLOCKED" if tools["missing"] else "PREPARED_PENDING_M2_APPROVAL",
        input=control, m1_confirmation=identity(confirmation),
        tool_qualification=identity(qualification),
        tool_versions=[s["version"] for s in qualified["steps"]],
        expected_ledger=identity(output / "expected_publications.jsonl"),
        frozen_sources=frozen, source_files=before, tools=tools,
        python=dict(identity(Path(sys.executable)), version=sys.version),
        source_audit=audit_sources(), expected_end=expected_end,
        rows=COUNT, last_posedge_ns=170726710, finish_ns=170726711,
        simulation_timeout_ns=170726720,
        compile_argv=[str(suite / "bin/iverilog.exe"), "-g2012", "-s", "tb_t052_long",
                      "-o", "long.vvp", "readonly/t052_polyphony_test_source.sv",
                      "readonly/dds_oscillator.sv", "readonly/pcm_mixer_4voice.sv",
                      "t052_long_observer.sv", "tb_t052_long.sv"],
        run_argv=[str(suite / "bin/vvp.exe"), "long.vvp"],
        check_argv=[sys.executable, "-B", "-X", "utf8", str(checker),
                    "--capture", str(output), "--report", str(output / "capture_review.json")],
        cwd=str(output), proposed_limits_seconds=dict(compile=90, run=300, check=300, total=900),
        proposed_output_limit_bytes=1200 * (1 << 20),
        proposed_capture_limit_bytes=750 * (1 << 20),
        log_estimate=dict(planned_control_bytes=COUNT*44,
                          observation_LF_bytes=COUNT*76+len(f"END {COUNT}\n"),
                          observation_CRLF_upper_bytes=COUNT*77+len(f"END {COUNT}\r\n"),
                          publication_lines=8207+8201+6+1,
                          throughput_or_walltime_measured=False),
        phase="STATIC_PREPARATION_ONLY", actual_HDL_calls=0, actual_RTL_runs=0,
        actual_EDA_calls=0, old_4207_completeness="UNKNOWN", PCM_math_verified=False,
        provenance_checker="raw checker returns 3 even after matching transactions; approved runner binding still required",
        future_execution="one compile + one run only after M2 pins final tools/approval; no auto retry",
        generation_seconds=time.monotonic()-started)
    if before != {str(p.resolve()): identity(p) for p in sources}:
        raise ValueError("SOURCE_DRIFT")
    if tools != inventory(suite):
        raise ValueError("TOOL_DRIFT")
    write_json(output / "proposal.json", proposal)
    return proposal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--m1-confirmation", required=True, type=Path)
    parser.add_argument("--suite", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    parser.add_argument("--tool-qualification", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.output.resolve(), args.m1_confirmation.resolve(),
                         args.suite.resolve(), args.tool_qualification.resolve())
        print(json.dumps({k: result[k] for k in ("plan", "status", "input", "expected_end", "generation_seconds")}))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(status="PREPARATION_FAIL", diagnostic=str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
