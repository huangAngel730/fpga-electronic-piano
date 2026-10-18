"""R11 complete-originals successor; declared bindings never prove execution.

This file is a static, unexecuted successor. The only processing implementation
remains the frozen R10/D4 chain. New processing permission is required separately.
The receipt schema below already exists in R7D; no M2 launch schema is invented.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[7]
LEGACY = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
                 "pro_basis_r08_20261017/coordinator/night_r10_20261017/"
                 "capture_link_r01/entry.py")
LEGACY_SHA = "ca175b497bd8438f198d5c0777ae0d073383702a868129c5b8eae00f61fec80a"
RECEIPT_FIELDS = {"schema", "capture_id", "argv", "cwd", "bindings",
                  "exit_code", "timeout", "cleanup_complete", "consumption"}
PENDING = ["M2_TRUSTED_EXECUTOR_AND_NATIVE_C9_RECEIPT_MAPPING",
           "M2_EXACT_PROCESSING_AND_HDL_ADMISSION", "M1_INDEPENDENT_MATH",
           "ACTUAL_AUDIO_STABLE_BACKPRESSURE_AND_PHYSICAL_EVIDENCE"]


def legacy_module():
    """Load only pinned old source, using the same bytes for hash and compile."""
    for path in (LEGACY, *LEGACY.parents):
        if path.is_symlink() or path.is_junction():
            raise ValueError("R11_LEGACY_SOURCE_ALIAS")
    raw = LEGACY.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEGACY_SHA:
        raise ValueError("R11_LEGACY_SOURCE_CHANGED")
    module = types.ModuleType("_r11_frozen_capture_link")
    module.__file__ = str(LEGACY)
    exec(compile(raw, str(LEGACY), "exec", dont_inherit=True), module.__dict__)
    return module


def closure_members(c, descriptor, *, tool=False, native=None):
    """Reuse R7D's existing file-closure fields and verify every listed byte."""
    closure = c.read(c.checked(descriptor))
    fields = {"schema", "files", "argv", "cwd", "version"} if tool else {"schema", "files"}
    c.require(type(closure) is dict and set(closure) == fields
              and closure["schema"] == "M3_R7D_FILE_CLOSURE_V1",
              "R11_DECLARED_CLOSURE_FIELDS")
    c.require(type(closure["files"]) is list and 0 < len(closure["files"]) <= 4096,
              "R11_DECLARED_CLOSURE_EMPTY")
    paths = set()
    for member in closure["files"]:
        c.require(type(member) is dict and set(member) == {"path", "bytes", "sha256"},
                  "R11_DECLARED_CLOSURE_MEMBER")
        path = Path(member["path"])
        path = c.no_alias(path if path.is_absolute() else ROOT / path)
        key = str(path).casefold()
        c.require(key not in paths, "R11_DECLARED_CLOSURE_DUPLICATE")
        paths.add(key)
        if path.is_relative_to(ROOT):
            c.checked(member)
        else:
            # Native tools may live outside the repository. Read only the exact
            # application-declared file; this is not dynamic-loader verification.
            expected = (native or {}).get(key)
            c.require(tool and expected is not None
                      and all(member[k] == expected[k] for k in ("bytes", "sha256")),
                      "R11_NATIVE_MEMBER_NOT_IN_APPLICATION")
            c.require(path.is_file() and path.stat().st_size == member["bytes"],
                      "R11_NATIVE_MEMBER_SIZE")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            c.require(digest == member["sha256"], "R11_NATIVE_MEMBER_SHA")
    return closure, paths


def declared_binding(envelope, legacy, c):
    """Validate existing R7D declarations; do not authenticate a native run."""
    c.require(type(envelope) is dict and set(envelope) == {"schema", "mode", "request"}
              and envelope["schema"] == "N10_M3_UNIFIED_PIPELINE_REQUEST_V1"
              and envelope["mode"] == "PROCESS_CAPTURE", "R11_COMPLETE_ENVELOPE")
    request = c.read(c.checked(envelope["request"]))
    c.require(type(request) is dict and type(request.get("inputs")) is dict,
              "R11_COMPLETE_REQUEST_INPUTS")
    inputs = request["inputs"]
    for role in ("stderr", "source_manifest", "rom_manifest", "tool_manifest"):
        c.require(role in inputs, "R11_COMPLETE_ORIGINAL_MISSING:" + role)
    math_inputs = request.get("math_inputs", {})
    c.require(type(math_inputs) is dict and "execution_receipt" in math_inputs,
              "R11_COMPLETE_EXECUTION_RECEIPT_MISSING")
    legacy.capture_preflight(request, c)
    descriptors = {
        "source_manifest": inputs["source_manifest"],
        "rom_manifest": inputs["rom_manifest"],
        "tool_manifest": inputs["tool_manifest"],
        "input_plan": inputs["midi_plan"], "window_plan": inputs["window_plan"],
        "raw_stdout": inputs["stdout"], "raw_stderr": inputs["stderr"],
        "raw_trace": inputs["raw"], "reset_edges": inputs["resets"],
        "finish_receipt": inputs["end"],
    }
    application = c.read(c.checked(inputs["application_request"]))
    capture_sources = application["source"]["capture_sources"]
    descriptors.update(driver=capture_sources["DRIVER"],
                       observer=capture_sources["OBSERVER"])
    receipt_ref = math_inputs["execution_receipt"]
    receipt_path = c.checked(receipt_ref)
    receipt = c.read(receipt_path)
    c.require(type(receipt) is dict and set(receipt) == RECEIPT_FIELDS,
              "R11_DECLARED_RECEIPT_FIELDS")
    c.require(receipt["schema"] == "M3_R7D_DECLARED_EXECUTION_V1"
              and receipt["capture_id"] == request["capture_id"],
              "R11_DECLARED_CAPTURE_ID")
    role_paths = [c.checked(descriptor) for descriptor in descriptors.values()]
    role_paths.append(receipt_path)
    c.require(len({str(path).casefold() for path in role_paths}) == len(role_paths),
              "R11_DECLARED_ROLE_PATH_ALIAS")
    source, source_paths = closure_members(c, descriptors["source_manifest"])
    roms, rom_paths = closure_members(c, descriptors["rom_manifest"])
    # Preserve the immutable archives which define the current 75-source/9-ROM
    # application, rather than pretending a separately described closure matches.
    source_request = application["source"]
    required_source = [source_request["base"], source_request["application"],
                       *source_request["capture_sources"].values()]
    c.require({str(c.checked(item)).casefold() for item in required_source} <= source_paths,
              "R11_SOURCE_CLOSURE_APPLICATION_MISMATCH")
    c.require(str(c.checked(source_request["application"])).casefold() in rom_paths,
              "R11_ROM_CLOSURE_APPLICATION_MISMATCH")
    native = {}
    for identity in application["tools"].values():
        for item in [identity["tool"], *identity.get("dependencies", [])]:
            descriptor = item["file"]
            path = c.no_alias(descriptor["path"])
            key = str(path).casefold()
            c.require(key not in native or native[key] == descriptor,
                      "R11_APPLICATION_NATIVE_IDENTITY_CONFLICT")
            native[key] = descriptor
    tool, tool_paths = closure_members(c, descriptors["tool_manifest"], tool=True, native=native)
    c.require(set(native) <= tool_paths, "R11_TOOL_CLOSURE_APPLICATION_MISMATCH")
    c.require(type(tool.get("argv")) is list and bool(tool["argv"])
              and all(type(arg) is str and bool(arg) for arg in tool["argv"])
              and type(tool.get("cwd")) is str and bool(tool["cwd"])
              and type(tool.get("version")) is str and bool(tool["version"]),
              "R11_DECLARED_TOOL_DESCRIPTION")
    c.require(any(step.get("tool") == "vsim" and tool["argv"] == step["argv"]
                  for step in application["execution_spec"]["steps"]),
              "R11_DECLARED_ARGV_NOT_PROPOSED_C9_CAPTURE_STEP")
    c.require(receipt["argv"] == tool["argv"] and receipt["cwd"] == tool["cwd"],
              "R11_DECLARED_ARGV_CWD")
    c.require(receipt["bindings"] ==
              {role: descriptor["sha256"] for role, descriptor in descriptors.items()},
              "R11_DECLARED_BINDINGS")
    c.require(type(receipt["exit_code"]) is int and receipt["exit_code"] == 0
              and receipt["timeout"] is False and receipt["cleanup_complete"] is True,
              "R11_DECLARED_EXECUTION_NOT_CLEAN")
    consumed = receipt["consumption"]
    c.require(type(consumed) is dict and set(consumed) ==
              {"pid", "group_id", "started_utc", "ended_utc"}, "R11_DECLARED_CONSUMPTION")
    c.require(type(consumed["pid"]) is int and consumed["pid"] > 0
              and type(consumed["group_id"]) is str and bool(consumed["group_id"]),
              "R11_DECLARED_CONSUMPTION_ID")
    begin, end = (datetime.fromisoformat(consumed[key])
                  for key in ("started_utc", "ended_utc"))
    c.require(begin.utcoffset() is not None and end.utcoffset() is not None
              and end >= begin, "R11_DECLARED_CONSUMPTION_TIME")
    return {"request": envelope["request"], "receipt": receipt_ref,
            "bindings": descriptors, "capture_id": request["capture_id"]}


def process(envelope, output_dir):
    """Same envelope/old algorithms; complete-originals mode adds binding only."""
    legacy = legacy_module()
    c = legacy.helpers()
    c.require(type(envelope) is dict, "R11_ENVELOPE_TYPE")
    if envelope.get("mode") == "PREPARE_APPLICATION_ONLY":
        # The old preparation result never claims any complete capture evidence.
        return legacy.process(envelope, output_dir)
    before = declared_binding(envelope, legacy, c)
    result = legacy.process(envelope, output_dir)
    after = declared_binding(envelope, legacy, c)
    c.require(before == after, "R11_DECLARED_INPUT_REBOUND")
    c.require(all(result.get(flag) is False for flag in
                  ("execution_allowed", "real_verified", "math_verified",
                   "board_release_allowed")), "R11_FALSE_AUTHORITY")
    report = {"schema": "M3_R11_DECLARED_ORIGINALS_BINDING_RESULT_V1",
              "status": "DECLARED_IDENTITIES_BOUND_ACTUAL_EXECUTION_UNVERIFIED",
              **before, "pending": PENDING,
              "structural_identity_is_not_authenticity": True,
              "tool_execution_authenticity": "UNKNOWN", "M2_admission": "PENDING",
              "actual_C9_launch_cwd_and_native_receipt_mapping": "PENDING_M2",
              "dynamic_tool_dependency_closure": "NOT_VERIFIED",
              "execution_allowed": False, "real_verified": False,
              "math_verified": False, "board_release_allowed": False}
    out = c.no_alias(output_dir)
    c.save(out / "R11_DECLARED_ORIGINALS.json", report)
    result = {**result, "complete_originals_declared_binding":
              c.ref(out / "R11_DECLARED_ORIGINALS.json"),
              "tool_execution_authenticity": "UNKNOWN", "M2_admission": "PENDING"}
    c.save(out / "R11_HANDOFF.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not sys.dont_write_bytecode or sys.flags.optimize:
        raise ValueError("R11_REQUIRES_PYTHON_B_ASSERTIONS_ON")
    c = legacy_module().helpers()
    c.install_guard()
    result = process(c.read(args.request), args.output)
    print(json.dumps({"status": result["status"], "execution_allowed": False,
                      "real_verified": False, "math_verified": False}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
