"""Read-only historical D/C_FULL evidence association, never an EDA launcher.

The production entry point is pinned to independent accepted archive identities.
Pure contract helpers are public for targeted software counterexample tests.
No archive member is extracted, imported, evaluated, or executed.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import traceback
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass


EXPECTED_SHA256 = "d64d70fbd99d505459cf893b2307d630920799c7b5f94cc64eb696232c93b824"
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
SCOPE = {
    "status": "STATIC_BINDING_ONLY", "T061_complete": False,
    "resources": "UNKNOWN", "STA": "NOT_RUN", "actual_EDA_calls": 0,
    "RTL_calls": 0, "device_calls": 0, "synthesis_authorized": False,
}


class BindingError(ValueError):
    """A stable machine-readable rejection code, not a simulation result."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise BindingError(code, detail)


def digest(raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _strict_equal(actual, expected) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _strict_equal(actual[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _strict_equal(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


def equal(actual, expected, code: str, detail: str) -> None:
    require(_strict_equal(actual, expected), code, detail)


def load_strict_json(raw: bytes, label: str = "JSON"):
    """Decode JSON without duplicate keys, NaN, Infinity, or excessive nesting."""
    require(type(raw) is bytes, "JSON_TYPE", label)
    require(len(raw) <= 16 * 1024 * 1024, "JSON_SIZE", label)

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "JSON_DUPLICATE", f"{label}: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise BindingError("JSON_NONFINITE", f"{label}: {value}")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=reject_constant)
    except BindingError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise BindingError("JSON_MALFORMED", f"{label}: {exc}") from exc

    def walk(item, depth=0):
        require(depth <= 64, "JSON_DEPTH", label)
        if isinstance(item, float):
            require(math.isfinite(item), "JSON_NONFINITE", label)
        elif isinstance(item, dict):
            for child in item.values():
                walk(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                walk(child, depth + 1)
    walk(value)
    return value


def validate_identity(raw: bytes, record: dict, label: str = "IDENTITY") -> None:
    require(type(record) is dict and set(record) == {"bytes", "sha256"},
            "IDENTITY_FIELDS", label)
    require(type(record["bytes"]) is int and 0 <= record["bytes"] <= 268435456,
            "IDENTITY_BYTES", label)
    require(type(record["sha256"]) is str and SHA_RE.fullmatch(record["sha256"]) is not None,
            "IDENTITY_SHA", label)
    equal(digest(raw), record, "IDENTITY_MISMATCH", label)


def safe_member_name(name: str) -> str:
    require(type(name) is str and bool(name), "ZIP_PATH", repr(name))
    require(not name.startswith("/") and "\\" not in name and ":" not in name,
            "ZIP_PATH", name)
    require(unicodedata.normalize("NFC", name) == name,
            "ZIP_PATH", f"non-normalized: {name}")
    require(len(name) <= 1024, "ZIP_PATH", "member name too long")
    for component in name.split("/"):
        require(component not in ("", ".", "..") and not component.endswith((".", " ")),
                "ZIP_PATH", name)
        require(not any(ord(c) < 32 or c in '<>"|?*' for c in component),
                "ZIP_PATH", name)
        stem = component.split(".")[0].upper()
        require(stem not in {"CON", "PRN", "AUX", "NUL"}
                and not re.fullmatch(r"(?:COM|LPT)[1-9]", stem), "ZIP_PATH", name)
    return name


def validate_manifest_records(records: dict) -> dict:
    require(type(records) is dict and 0 < len(records) <= 1024,
            "MANIFEST_FILES", "files must be a nonempty bounded object")
    seen = set()
    for name, record in records.items():
        safe_member_name(name)
        require(name.casefold() not in seen, "MANIFEST_COLLISION", name)
        seen.add(name.casefold())
        require(type(record) is dict and set(record) == {"bytes", "sha256"},
                "IDENTITY_FIELDS", name)
        require(type(record["bytes"]) is int and 0 <= record["bytes"] <= 67108864,
                "IDENTITY_BYTES", name)
        require(type(record["sha256"]) is str and SHA_RE.fullmatch(record["sha256"]) is not None,
                "IDENTITY_SHA", name)
    return records


@dataclass(frozen=True)
class ZipLimits:
    max_members: int = 1024
    max_member_bytes: int = 67108864
    max_total_bytes: int = 268435456
    max_ratio: int = 128
    max_archive_bytes: int = 67108864


class ValidatedZip:
    def __init__(self, raw: bytes, label: str, limits: ZipLimits):
        self.label = label
        require(type(raw) is bytes and len(raw) <= limits.max_archive_bytes,
                "ZIP_ARCHIVE_SIZE", label)
        self._buffer = io.BytesIO(raw)
        try:
            self._zip = zipfile.ZipFile(self._buffer)
            infos = self._zip.infolist()
            require(0 < len(infos) <= limits.max_members, "ZIP_MEMBER_COUNT", label)
            folded = set()
            total = 0
            for info in infos:
                safe_member_name(info.filename)
                require(info.orig_filename == info.filename,
                        "ZIP_PATH", f"{label}: NUL-truncated filename")
                require(info.filename.casefold() not in folded, "ZIP_DUPLICATE",
                        f"{label}: {info.filename}")
                folded.add(info.filename.casefold())
                require(not info.is_dir(), "ZIP_DIRECTORY", info.filename)
                mode = (info.external_attr >> 16) & 0xFFFF
                require(stat.S_IFMT(mode) in (0, stat.S_IFREG), "ZIP_SPECIAL", info.filename)
                require(not info.flag_bits & 1, "ZIP_ENCRYPTED", info.filename)
                require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                        "ZIP_COMPRESSION", info.filename)
                require(0 <= info.file_size <= limits.max_member_bytes,
                        "ZIP_MEMBER_SIZE", info.filename)
                total += info.file_size
                require(total <= limits.max_total_bytes, "ZIP_TOTAL_SIZE", label)
                require(info.file_size <= max(info.compress_size, 1) * limits.max_ratio,
                        "ZIP_RATIO", info.filename)
            self.names = tuple(info.filename for info in infos)
            # Bounded streaming reads check CRC and overlap/truncation before use.
            for info in infos:
                size = 0
                with self._zip.open(info) as handle:
                    while chunk := handle.read(1048576):
                        size += len(chunk)
                        require(size <= limits.max_member_bytes,
                                "ZIP_MEMBER_SIZE", info.filename)
                equal(size, info.file_size, "ZIP_LENGTH", info.filename)
        except BindingError:
            raise
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile,
                NotImplementedError, EOFError, zlib.error) as exc:
            raise BindingError("ZIP_MALFORMED", f"{label}: {exc}") from exc

    def read(self, name: str) -> bytes:
        require(name in self.names, "ZIP_MISSING", f"{self.label}: {name}")
        try:
            return self._zip.read(name)
        except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, zlib.error) as exc:
            raise BindingError("ZIP_MALFORMED", f"{self.label}: {name}: {exc}") from exc

    def verify_manifest(self, manifest_name: str = "MANIFEST.json") -> dict:
        manifest = load_strict_json(self.read(manifest_name), self.label + "/manifest")
        require(type(manifest) is dict and "files" in manifest,
                "MANIFEST_SCHEMA", self.label)
        records = validate_manifest_records(manifest["files"])
        equal(set(self.names), set(records) | {manifest_name},
              "MANIFEST_MEMBER_SET", self.label)
        require(manifest_name not in records, "MANIFEST_SELF_REFERENCE", self.label)
        for name, identity in records.items():
            validate_identity(self.read(name), identity, f"{self.label}/{name}")
        return manifest


def inspect_zip_bytes(data: bytes, label: str = "ZIP",
                      limits: ZipLimits | None = None) -> ValidatedZip:
    return ValidatedZip(data, label, limits or ZipLimits())


def _identity_fields(record: dict) -> dict:
    return {"bytes": record["bytes"], "sha256": record["sha256"]}


def _fields(obj: dict, expected: dict, code: str, label: str) -> None:
    require(type(obj) is dict, code, label)
    for key, value in expected.items():
        require(key in obj, code, f"{label}: missing {key}")
        equal(obj[key], value, code, f"{label}: {key}")


def validate_project_contract(project: dict, expected: dict) -> None:
    """Pure D project semantic checks; does not trust candidate role/count labels."""
    required = {"C_scope", "T061_complete", "clock", "configuration", "device",
                "evidence", "execution", "files", "macros", "new_top_validation",
                "project", "schema", "status", "synthesis_default_basis",
                "synthesis_default_frequency_mhz", "synthesis_frequency_is_physical_sta",
                "tool", "top"}
    require(type(project) is dict and set(project) == required,
            "D_FIELDS", "project manifest fields")
    _fields(project, {
        "schema": "N32_D_PREPARE_V1", "status": "PREPARED_NOT_EXECUTED",
        "top": "m3_n32_resource", "T061_complete": False, "macros": [],
        "C_scope": "TWO_SEPARATELY_QUALIFIED_SEGMENTS_NOT_ONE_CONTINUOUS_RUN",
        "new_top_validation": "STATIC_ONLY_NOT_RTL_EXECUTED",
        "synthesis_frequency_is_physical_sta": False,
    }, "D_SCOPE", "D")
    equal(project["execution"], {"PnR": False, "STA": "NOT_RUN", "authorized": False,
          "device_operation": False, "resources": "UNKNOWN", "tool_calls": 0},
          "D_EXECUTION", "D is prepare only")
    equal(project["clock"], {"hold_uncertainty_ns": 0.65, "name": "sys_clk",
          "period_ns": 25.0, "port": "clk", "setup_uncertainty_ns": 1.0},
          "D_CLOCK", "clock contract, not measured slack")
    equal(project["configuration"], {"N": 32, "profile": "audio_and_public_read_no_injection",
          "response": 1}, "D_CONFIGURATION", "N32/R1")
    equal(project["device"], {"index": "gw5ast138c-007", "name": "GW5AST-138C",
          "pn": "GW5AST-LV138PG484AC1/I0"}, "D_DEVICE", "device")
    records = project["files"]
    require(type(records) is list and len(records) == 45, "D_FILE_COUNT", "45 inputs")
    paths = []
    counts = collections.Counter()
    for row in records:
        require(type(row) is dict and set(row) in (
            {"bytes", "path", "role", "sha256"},
            {"bytes", "path", "role", "sha256", "origin_snapshot"}),
            "D_RECORD_FIELDS", repr(row))
        safe_member_name(row["path"])
        validate_manifest_records({row["path"]: _identity_fields(row)})
        require(row["path"].casefold() not in paths, "D_DUPLICATE", row["path"])
        paths.append(row["path"].casefold())
        require(type(row["role"]) is str, "D_ROLE", row["path"])
        counts[row["role"]] += 1
        prefixes = {"source": "sources/", "top": "sources/", "include": "include/",
                    "rom": "rom/", "evidence": "evidence/"}
        if row["role"] in prefixes:
            require(row["path"].startswith(prefixes[row["role"]]), "D_ROLE", row["path"])
        if row["role"] in ("source", "include", "rom"):
            require("origin_snapshot" in row, "D_ORIGIN", row["path"])
            safe_member_name(row["origin_snapshot"])
        else:
            require("origin_snapshot" not in row, "D_ORIGIN", row["path"])
    equal(dict(counts), expected["counts"], "D_ROLES", "exact 45 role split")
    order = ["sources/" + name for name in expected["source_order"]]
    equal(project["project"], {"gprj": "n32_resource.gprj", "include_dirs": ["include"],
          "sdc": "clock.sdc", "source_order": order, "tcl": "run_synthesis_only.tcl",
          "top_source": "sources/m3_n32_resource.sv"}, "D_SOURCE_ORDER", "19 HDL")
    actual_sources = {r["path"] for r in records if r["role"] in ("source", "top")}
    equal(actual_sources, set(order), "D_SOURCE_SET", "no wrapper, TB or vendor sim model")
    tops = [r for r in records if r["role"] == "top"]
    equal({k: tops[0][k] for k in ("path", "bytes", "sha256")}, expected["d_top"],
          "D_TOP", "resource top is not simulation wrapper")
    equal({r["path"] for r in records if r["role"] == "include"},
          {"include/sine_table.svh", "include/sustain_controller_ports.svh"},
          "D_INCLUDE_SET", "2 include inputs")
    equal({r["path"] for r in records if r["role"] == "rom"},
          {"rom/velocity_gain_rom.mem", "rom/piano_band_4x256_8191.mem",
           "rom/oct_ratio_q16.mem", "rom/sub_ratio_q16.mem", "rom/lfo_sine_q15.mem"},
          "D_ROM_SET", "5 ROM inputs")


def _input_index(rows: list, label: str) -> dict:
    require(type(rows) is list and 0 < len(rows) <= 1024, "C_INPUTS", label)
    result = {}
    for row in rows:
        require(type(row) is dict and set(row) == {"bytes", "origin", "sha256", "snapshot"},
                "C_INPUT_FIELDS", label)
        safe_member_name(row["snapshot"])
        require(type(row["origin"]) is str and bool(row["origin"]), "C_ORIGIN", label)
        validate_manifest_records({row["snapshot"]: _identity_fields(row)})
        require(row["snapshot"].casefold() not in {n.casefold() for n in result},
                "C_INPUT_DUPLICATE", row["snapshot"])
        result[row["snapshot"]] = row
    return result


def validate_shared_inputs(d_records: list, c_inputs: list, original_inputs: list,
                           d_read, c_read, original_read) -> list:
    """Validate all 25 business/include/ROM paths in D, R02 and original R01."""
    current = _input_index(c_inputs, "current")
    original = _input_index(original_inputs, "original")
    selected = [r for r in d_records if r.get("role") in ("source", "include", "rom")]
    equal(len(selected), 25, "SHARED_COUNT", "18 HDL + 2 include + 5 ROM")
    require(len({r["path"].casefold() for r in selected}) == 25,
            "SHARED_DUPLICATE", "D duplicate paths")
    origins = set()
    mappings = []
    for row in selected:
        origin = row.get("origin_snapshot")
        safe_member_name(origin)
        require(origin not in origins, "SHARED_ORIGIN_DUPLICATE", origin)
        origins.add(origin)
        require(origin in current and origin in original, "SHARED_MISSING", origin)
        identity = _identity_fields(row)
        equal(_identity_fields(current[origin]), identity, "SHARED_IDENTITY", origin)
        equal(_identity_fields(original[origin]), identity, "SHARED_ORIGINAL_IDENTITY", origin)
        payload = d_read(row["path"])
        validate_identity(payload, identity, row["path"])
        validate_identity(c_read(origin), identity, "current/" + origin)
        validate_identity(original_read(origin), identity, "original/" + origin)
        equal(payload, c_read(origin), "SHARED_BYTES", origin)
        equal(payload, original_read(origin), "SHARED_ORIGINAL_BYTES", origin)
        mappings.append({"d_path": row["path"], "role": row["role"],
                         "cfull_snapshot": origin, **identity})
    return mappings


def _steps(receipt: dict, names: list, exits: list, code: str) -> None:
    require(type(receipt.get("steps")) is list, code, "steps")
    equal([s.get("name") for s in receipt["steps"]], names, code, "step names")
    equal([s.get("exit_code") for s in receipt["steps"]], exits, code, "step exits")
    for step in receipt["steps"]:
        equal(step.get("timeout"), False, code, "no timeout")
        require(type(step.get("argv")) is list and bool(step["argv"])
                and all(type(v) is str for v in step["argv"]), code, "argv")


def validate_cfull_contract(manifest: dict, original_plan: dict, original_receipt: dict,
                            current_plan: dict, current_receipt: dict, report: dict,
                            mutations: dict, expected: dict) -> None:
    """Pure continuity/reuse contract checks, not another mathematics checker."""
    _fields(manifest, {"schema": "T061_N32_C_SEAL_MANIFEST_V4", "EDA_calls": 0,
            "T061_complete": False, "capture_composition": False,
            "single_continuous_full_C_run": True, "physical_STA": "NOT_RUN",
            "review_key": "T061-N32-C-FULL-CONTINUOUS-20261014-R02",
            "status": "N32_C_FULL_CONTINUOUS_FUNCTION_MATH_PASS_T061_PARTIAL",
            "capture": expected["capture"], "plan": expected["current_plan"],
            "receipt": expected["current_receipt"]}, "C_FULL_SCOPE", "C_FULL manifest")
    _fields(original_receipt, {"status": "FAIL_PARTIAL", "exit_code": 1,
            "failure": "ValueError:C_STEP_FAILED:mutations", "EDA_calls": 0,
            "T061_complete": False, "automatic_retries": 0,
            "plan": expected["original_plan"],
            "review_key": "T061-N32-C-FULL-CONTINUOUS-20261014-R01"},
            "C_ORIGINAL_RECEIPT", "preserve checker-only first failure")
    _steps(original_receipt, ["compile", "simulate", "check", "mutations"],
           [0, 0, 0, 1], "C_ORIGINAL_STEPS")
    equal(original_receipt["steps"][1]["stdout"], expected["capture"],
          "C_CAPTURE_CHAIN", "original simulated output")
    qualification = {"changed_scope": "FULL_SOFTWARE_RECHECK_AND_EXACT_STEAL_MUTATION_ONLY",
                     "execution_mode": "RTL_REUSED_NO_NEW_SIMULATION",
                     "original_failure": "ValueError:C_STEP_FAILED:mutations",
                     "original_status": "FAIL_PARTIAL",
                     "status": "KNOWN_CHECKER_ONLY_FAILURE_FULL_CAPTURE_QUALIFIED"}
    _fields(current_receipt, {"status": "N32_C_STRESS_PASS_T061_PARTIAL", "exit_code": 0,
            "failure": None, "EDA_calls": 0, "T061_complete": False,
            "automatic_retries": 0, "execution_mode": "RTL_REUSED_NO_NEW_SIMULATION",
            "full_reuse_qualification": qualification, "plan": expected["current_plan"],
            "review_key": "T061-N32-C-FULL-CONTINUOUS-20261014-R02"},
            "C_CURRENT_RECEIPT", "R02 software-only successor")
    _steps(current_receipt, ["check", "mutations"], [0, 0], "C_CURRENT_STEPS")
    for label, plan in (("R01", original_plan), ("R02", current_plan)):
        _fields(plan, {"hostname": "LAPTOP-KSS1MRR7", "EDA_calls": 0,
                "T061_complete": False, "automatic_retries": 0}, "C_PLAN", label)
        equal([s.get("name") for s in plan["steps"]],
              ["compile", "simulate", "check", "mutations"] if label == "R01"
              else ["check", "mutations"], "C_PLAN_STEPS", label)
    equal(current_plan["full_reuse_qualification"], qualification, "C_REUSE", "qualification")
    equal(current_plan["reused_simulation"], current_receipt["reused_simulation"],
          "C_REUSE", "plan and actual receipt")
    _fields(current_plan["reused_simulation"], {
        "capture": expected["capture"], "receipt": expected["original_receipt"],
        "status": "REUSED_COMPLETED_RTL_CAPTURE_ONLY", "origin_profile": "full-v6"},
        "C_REUSE", "only original continuous capture")
    equal(original_plan["tool_files"], current_plan["tool_files"],
          "C_TOOL_IDENTITIES", "no replacement tool bytes")
    equal(original_plan["tools"], current_plan["tools"], "C_TOOL_IDENTITIES", "tool paths")
    _fields(report, {"T061_complete": False, "task_complete": False,
            "capture_composition": False, "complete_C_capture": True,
            "single_continuous_full_C_run": True, "physical_STA": "NOT_RUN",
            "profile": "FULL_C00_C09_SINGLE_CONTINUOUS_CAPTURE",
            "capture_bytes": expected["capture"]["bytes"],
            "capture_sha256": expected["capture"]["sha256"],
            "operations": 10376, "publications": 4942,
            "cases": [f"C{i:02d}" for i in range(10)]}, "C_REPORT", "historical report")
    _fields(report["live_qualification"], {"accepts": 4945, "publications": 4942,
            "live_at_end": None}, "C_REPORT", "closed accepted samples")
    _fields(report["independent_clocked_math"], {"max_request_to_result_cycles": 347},
            "C_REPORT", "historical math report, not recomputed")
    equal(report["independent_clocked_math"]["counts"]["L"], 158144,
          "C_REPORT", "slot results")
    equal(report["independent_clocked_math"]["lifecycle"]["retirements"], 4,
          "C_REPORT", "retirements")
    _fields(report["observed_payload_scope"], {"clipped_values": [0],
            "clipped_one_observation_edges": 0, "unequal_stereo_observation_edges": 0},
            "C_LIMITATIONS", "no nonzero clip or unequal stereo coverage")
    _fields(mutations, {"status": "N32_C_MUTATIONS_PASS", "rejected": 24,
            "original_sha256": expected["capture"]["sha256"],
            "profile": "FULL_C00_C09_SINGLE_CONTINUOUS_CAPTURE"}, "C_MUTATIONS", "software only")
    rows = mutations["mutations"]
    require(type(rows) is list and len(rows) == 24, "C_MUTATIONS", "24 named tests")
    equal(len({r["name"] for r in rows}), 24, "C_MUTATIONS", "unique names")
    equal(len({r["capture_sha256"] for r in rows}), 23, "C_MUTATIONS", "23 unique payloads")
    for row in rows:
        require(type(row.get("exit_code")) is int and row["exit_code"] != 0,
                "C_MUTATIONS", "nonzero rejected mutation")


def _check_project_text(dzip: ValidatedZip, project: dict, expected: dict) -> dict:
    raw_xml = dzip.read("project/n32_resource.gprj")
    require(b"<!DOCTYPE" not in raw_xml.upper() and b"<!ENTITY" not in raw_xml.upper(),
            "GPRJ_XML", "DTD/entities prohibited")
    try:
        tree = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise BindingError("GPRJ_XML", str(exc)) from exc
    equal(tree.tag, "Project", "GPRJ_XML", "root")
    files = tree.findall("./FileList/File")
    equal(len(files), 20, "GPRJ_FILES", "19 HDL plus SDC")
    first = files[0].attrib.get("path", "")
    suffix = "/sources/" + expected["source_order"][0]
    require(first.endswith(suffix), "GPRJ_PATH", first)
    base = first[:-len(suffix)]
    references = ["sources/" + name for name in expected["source_order"]] + ["clock.sdc"]
    for item, rel in zip(files, references):
        equal(item.attrib, {"path": base + "/" + rel,
              "type": "file.sdc" if rel == "clock.sdc" else "file.verilog", "enable": "1"},
              "GPRJ_FILES", rel)
    device = tree.find("Device")
    require(device is not None, "GPRJ_DEVICE", "missing device")
    equal(device.attrib, {"name": project["device"]["name"], "pn": project["device"]["pn"]},
          "GPRJ_DEVICE", "attributes")
    equal(device.text, project["device"]["index"], "GPRJ_DEVICE", "index")
    sdc = dzip.read("project/clock.sdc").decode("utf-8").splitlines()
    equal(sdc, ["create_clock -name sys_clk -period 25.000 [get_ports {clk}]",
          "set_clock_uncertainty -setup 1.000 [get_clocks {sys_clk}]",
          "set_clock_uncertainty -hold 0.650 [get_clocks {sys_clk}]"],
          "D_SDC", "no physical timing result claimed")
    tcl = dzip.read("project/run_synthesis_only.tcl").decode("utf-8").splitlines()
    equal(tcl, ["cd {" + base + "}", "open_project {" + base + "/n32_resource.gprj}",
          "set_option -top_module m3_n32_resource", "set_option -verilog_std sysv2017",
          "set_option -include_path {" + base + "/include}", "run syn"],
          "D_TCL", "text only, never run")
    top = dzip.read("project/" + expected["d_top"]["path"])
    validate_identity(top, _identity_fields(expected["d_top"]), "D top")
    text = top.decode("utf-8")
    for needle in ("b_n32_event_audio_prom #(.N(32), .RESPONSE(1))", ".clipped(clipped)",
                   ".inject_valid(1'b0)", ".inject_tag(77'd0)", ".inject_context(74'd0)"):
        require(needle in text, "D_TOP_CONNECTION", needle)
    return {"gprj_original_project_path": base,
            "gprj_references": references, "tcl_executed": False,
            "reset": "rst_n asynchronous low assertion; upstream synchronous release required; no reset synchronizer in D top",
            "cst": "ABSENT; board endpoint and voltage admission remain M2 responsibilities"}


def _load_expected() -> dict:
    path = Path(__file__).with_name("EXPECTED_IDENTITIES.json")
    raw = path.read_bytes()
    equal(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA256,
          "EXPECTED_FILE_IDENTITY", "independent expectations modified")
    expected = load_strict_json(raw, "EXPECTED_IDENTITIES")
    equal(expected["schema"], "N32_D_CFULL_INDEPENDENT_EXPECTATIONS_V1",
          "EXPECTED_SCHEMA", "fixed expectation schema")
    equal(expected["scope"], SCOPE, "EXPECTED_SCOPE", "no execution authorization")
    return expected


def _no_reparse(path: Path) -> None:
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            attributes = item.lstat()
            require(not item.is_symlink() and not getattr(attributes, "st_file_attributes", 0) & 0x400,
                    "FILE_REPARSE", str(item))


def read_input(path: Path, max_bytes: int = 67108864) -> bytes:
    path = Path(path).absolute()
    _no_reparse(path)
    require(path.is_file(), "INPUT_MISSING", str(path))
    require(path.stat().st_size <= max_bytes, "INPUT_SIZE", str(path))
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    require(len(raw) <= max_bytes, "INPUT_SIZE", str(path))
    return raw


def _nested(outer: ValidatedZip, prefix: str, expected: dict) -> tuple:
    snapshot = outer.read(prefix + "/snapshot.zip")
    raw_manifest = outer.read(prefix + "/MANIFEST.json")
    raw_seal = outer.read(prefix + "/seal.json")
    validate_identity(snapshot, expected["snapshot"], prefix + " snapshot")
    validate_identity(raw_manifest, expected["manifest"], prefix + " manifest")
    validate_identity(raw_seal, expected["seal"], prefix + " seal")
    seal = load_strict_json(raw_seal, prefix + "/seal")
    _fields(seal, {"manifest": expected["manifest"], "snapshot": expected["snapshot"],
            "members": expected["members"], "T061_complete": False},
            "SEAL_IDENTITY", prefix)
    inner = inspect_zip_bytes(snapshot, prefix + " inner")
    equal(len(inner.names), expected["members"], "ZIP_MEMBER_COUNT", prefix)
    equal(inner.read("MANIFEST.json"), raw_manifest, "INNER_MANIFEST", prefix)
    return inner, inner.verify_manifest(), seal


def verify_bundle(abcd: Path, cfull: Path, receipt: Path) -> dict:
    """Verify immutable accepted evidence and return a new static association."""
    expected = _load_expected()
    inputs = {"abcd": Path(abcd).absolute(), "cfull": Path(cfull).absolute(),
              "m2_receipt": Path(receipt).absolute()}
    raw = {key: read_input(path) for key, path in inputs.items()}
    before = {key: digest(data) for key, data in raw.items()}
    for key in ("abcd", "cfull"):
        validate_identity(raw[key], _identity_fields(expected[key]), key)
    equal(before["m2_receipt"]["sha256"], expected["sources"]["m2_receipt"]["sha256"],
          "M2_RECEIPT_IDENTITY", "independent M2 acceptance receipt")
    review = load_strict_json(raw["m2_receipt"], "M2 receipt")
    _fields(review, {"schema": 1, "reviewer": "M2",
            "status": "LIMITED_A_B_C_D_C_FULL_ACCEPTED_T061_PARTIAL",
            "source_commits": [expected["abcd"]["commit"], expected["cfull"]["commit"]],
            "D": {"scope": "PREPARE_ONLY_L0_L1", "actual_EDA_calls": 0,
                  "resources": "UNKNOWN", "STA": "NOT_RUN"}, "T061_complete": False},
            "M2_RECEIPT_SCOPE", "independent receipt")
    for label, name in (("abcd", "M3_N32_ABCD_20261014_COMPLETE.zip"),
                        ("cfull", "M3_N32_C_FULL_20261014.zip")):
        equal(review["packages"][name], {k: expected[label][k] for k in ("bytes", "sha256", "members")},
              "M2_PACKAGE_IDENTITY", name)
    az = inspect_zip_bytes(raw["abcd"], "ABCD outer")
    cz = inspect_zip_bytes(raw["cfull"], "C_FULL outer")
    outer_summaries = {}
    for key, archive in (("abcd", az), ("cfull", cz)):
        equal(len(archive.names), expected[key]["members"], "ZIP_MEMBER_COUNT", key)
        manifest = archive.verify_manifest()
        _fields(manifest, {"commit": expected[key]["commit"], "EDA_calls": 0,
                "T061_complete": False}, "OUTER_SCOPE", key)
        outer_summaries[key] = {"manifest": digest(archive.read("MANIFEST.json")),
                                "members": len(archive.names), "crc": "PASS"}
    dz, dm, ds = _nested(az, "D", expected["d_inner"])
    fz, fm, fs = _nested(cz, "C_FULL", expected["cfull_inner"])
    _fields(dm, {"C_scope": "SEGMENTED_NOT_CONTINUOUS", "RTL_calls": 0,
            "STA": "NOT_RUN", "T061_complete": False, "actual_EDA_calls": 0,
            "resources": "UNKNOWN", "synthesis_authorized": False,
            "status": "PREPARED_L0_L1_ONLY"}, "D_OLD_SCOPE", "unchanged historical D")
    project_raw = dz.read("project/manifest.json")
    validate_identity(project_raw, expected["d_project_manifest"], "D project manifest")
    project = load_strict_json(project_raw, "D project manifest")
    validate_project_contract(project, expected)
    for row in project["files"]:
        validate_identity(dz.read("project/" + row["path"]), _identity_fields(row), row["path"])
    actual_project_names = {n[8:] for n in dz.names if n.startswith("project/")}
    equal(actual_project_names, {r["path"] for r in project["files"]} | {"manifest.json"},
          "D_PROJECT_MEMBER_SET", "no hidden project inputs")
    for key, row in project["evidence"].items():
        equal(hashlib.sha256(dz.read("project/" + row["path"])).hexdigest(), row["sha256"],
              "D_EVIDENCE_REFERENCE", key)
    project_text = _check_project_text(dz, project, expected)
    fixed = {"reused/capture.log": "capture", "reused/original_plan.json": "original_plan",
             "reused/original_receipt.json": "original_receipt", "prepared/plan.json": "current_plan",
             "execution/receipt.json": "current_receipt"}
    for path, key in fixed.items():
        validate_identity(fz.read(path), expected[key], path)
    op = load_strict_json(fz.read("reused/original_plan.json"), "R01 plan")
    ore = load_strict_json(fz.read("reused/original_receipt.json"), "R01 receipt")
    cp = load_strict_json(fz.read("prepared/plan.json"), "R02 plan")
    cre = load_strict_json(fz.read("execution/receipt.json"), "R02 receipt")
    report = load_strict_json(fz.read("execution/report.json"), "C_FULL report")
    mutations = load_strict_json(fz.read("execution/mutation_report.json"), "C_FULL mutations")
    validate_cfull_contract(fm, op, ore, cp, cre, report, mutations, expected)
    for plan, prefix in ((cp, "prepared/snapshot/"), (op, "history/n32cfp01/snapshot/")):
        indexed = _input_index(plan["inputs"], prefix)
        equal({n[len(prefix):] for n in fz.names if n.startswith(prefix)}, set(indexed),
              "C_INPUT_SET", prefix)
        for path, row in indexed.items():
            validate_identity(fz.read(prefix + path), _identity_fields(row), prefix + path)
    for plan, run in ((op, ore), (cp, cre)):
        equal(run["tools_after"], plan["tool_files"], "C_TOOL_AFTER", "frozen tool closure")
        equal(run["inputs_after"], {r["snapshot"]: _identity_fields(r) for r in plan["inputs"]},
              "C_INPUT_AFTER", "frozen inputs")
    mappings = validate_shared_inputs(project["files"], cp["inputs"], op["inputs"],
        lambda n: dz.read("project/" + n), lambda n: fz.read("prepared/snapshot/" + n),
        lambda n: fz.read("history/n32cfp01/snapshot/" + n))
    wrapper = expected["c_wrapper"]
    validate_identity(fz.read("prepared/snapshot/" + wrapper["path"]),
                      _identity_fields(wrapper), "C simulation wrapper")
    require(not any("m3_n32_resource.sv" in r["snapshot"] for r in cp["inputs"]),
            "TOP_WRAPPER_DIFFERENCE", "D resource top must not be described as C simulated top")
    compile_argv = op["steps"][0]["argv"]
    equal(compile_argv[compile_argv.index("-s") + 1], "tb_c_n32_r1_v6",
          "C_SIMULATION_TOP", "actual compiled testbench")
    equal(ore["steps"][0]["argv"], compile_argv, "C_COMPILE_CHAIN", "original receipt argv")
    equal(ore["steps"][1]["argv"], op["steps"][1]["argv"],
          "C_SIMULATE_CHAIN", "single original VVP invocation")
    capture = fz.read("reused/capture.log")
    equal(sum(line.startswith(b"END ") for line in capture.splitlines()), 1,
          "C_CAPTURE_END", "one END, no segmented composition")
    after = {key: digest(read_input(path)) for key, path in inputs.items()}
    equal(after, before, "INPUT_DRIFT", "input archives and M2 receipt before/after")
    return {
        "schema": "N32_D_CFULL_STATIC_BINDING_V1", **SCOPE,
        "independent_expectations": {"sha256": EXPECTED_SHA256,
                                     "sources": expected["sources"]},
        "inputs": {key: {"path": str(path), **before[key]} for key, path in inputs.items()},
        "inputs_after": after, "outer_archives": outer_summaries,
        "d_inner": expected["d_inner"], "cfull_inner": expected["cfull_inner"],
        "d_project_manifest": expected["d_project_manifest"],
        "d_project_roles": dict(collections.Counter(r["role"] for r in project["files"])),
        "shared_inputs": mappings, "shared_count": 25,
        "project_contract": project_text,
        "top_difference": {"d_resource_top": expected["d_top"],
                           "c_simulation_wrapper": wrapper, "c_simulation_top": "tb_c_n32_r1_v6",
                           "resource_top_simulated": False, "claim": "shared business bytes only"},
        "historical_d_evidence": {"scope": dm["C_scope"], "unchanged": True,
                                  "automatically_rebound_to_C_FULL": False},
        "cfull": {"capture": expected["capture"], "R01": "compile0/simulate0/check0/mutations1 preserved",
                  "R02": "check0/mutations0; RTL_REUSED_NO_NEW_SIMULATION",
                  "counts": expected["limits"], "END_records": 1,
                  "tool_identity_entries": len(cp["tool_files"]),
                  "input_identity_entries": {"R01": len(op["inputs"]), "R02": len(cp["inputs"])}},
        "limitations": ["L0/L1 static association only, not new N32 functional acceptance",
                        "D historical manifest and C segmented qualification unchanged",
                        "D resource top was not C_FULL simulation top",
                        "C_FULL clipped all zero; left/right equal; 24 names but 23 unique mutation payloads",
                        "No synthesis, PnR, STA, SRAM/Flash, serial, board or audible output",
                        "Historical tool identity metadata checked, current installed tools not executed or requalified",
                        "M2 final acceptance and resource admission remain pending"],
    }


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _write_new(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)


def _source_identities() -> dict:
    folder = Path(__file__).absolute().parent
    return {name: digest(read_input(folder / name, 16777216))
            for name in ("binding_check.py", "EXPECTED_IDENTITIES.json", "README.txt")}


def _input_probe(paths: dict) -> dict:
    result = {}
    for key, path in paths.items():
        try:
            result[key] = {"path": str(Path(path).absolute()), **digest(read_input(path))}
        except Exception as exc:
            result[key] = {"path": str(Path(path).absolute()), "unavailable": str(exc)}
    return result


def task_output_path(path: Path) -> Path:
    """The only mutation boundary is this task's new code/output prefix."""
    require(".." not in Path(path).parts, "OUTPUT_BOUNDARY", str(path))
    absolute = Path(path).absolute()
    root = Path(__file__).absolute().parents[3] / "code" / "output"
    _no_reparse(absolute)
    try:
        relative = absolute.relative_to(root)
    except ValueError as exc:
        raise BindingError("OUTPUT_BOUNDARY", str(path)) from exc
    require(bool(relative.parts)
            and relative.parts[0].startswith("n32_d_cfull_binding_"),
            "OUTPUT_BOUNDARY", str(path))
    return absolute


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    prepare = sub.add_parser("prepare", help="create new static association, no tools")
    prepare.add_argument("--abcd", required=True, type=Path)
    prepare.add_argument("--cfull", required=True, type=Path)
    prepare.add_argument("--receipt", required=True, type=Path)
    verify = sub.add_parser("verify", help="recheck new successor association and original bytes")
    verify.add_argument("--prepared", required=True, type=Path)
    for child in (prepare, verify):
        child.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.absolute()
    receipt = {"schema": "N32_D_CFULL_CHECK_RECEIPT_V1", **SCOPE,
               "operation": args.operation, "argv": list(sys.argv if argv is None else argv),
               "cwd": str(Path.cwd()), "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "output": str(output), "exit_code": 1, "status": "FAIL_PARTIAL"}
    created = False
    input_paths = {}
    try:
        task_output_path(args.output)
        _no_reparse(output)
        require(not output.exists(), "OUTPUT_EXISTS", str(output))
        output.mkdir(parents=True, exist_ok=False)
        created = True
        receipt["sources_before"] = _source_identities()
        receipt["runtime"] = {"python": str(Path(sys.executable).absolute()),
                              **digest(read_input(Path(sys.executable))) }
        event = {"event": "START", "operation": args.operation, "scope": SCOPE}
        _write_new(output / "events.jsonl", json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")
        if args.operation == "prepare":
            input_paths = {"abcd": args.abcd, "cfull": args.cfull, "m2_receipt": args.receipt}
            receipt["input_identities_before"] = _input_probe(input_paths)
            result = verify_bundle(args.abcd, args.cfull, args.receipt)
        else:
            prepared_path = task_output_path(args.prepared)
            prepared_raw = read_input(prepared_path / "prepared.json", 16777216)
            prepared = load_strict_json(prepared_raw, "prepared successor")
            require(type(prepared) is dict and set(prepared) == {"schema", "scope", "binding", "inputs"},
                    "PREPARED_FIELDS", "successor")
            equal(prepared["schema"], "N32_D_CFULL_PREPARED_V1", "PREPARED_SCHEMA", "successor")
            equal(prepared["scope"], SCOPE, "PREPARED_SCOPE", "static only")
            saved_raw = read_input(prepared_path / "binding.json", 16777216)
            validate_identity(saved_raw, prepared["binding"], "prepared binding")
            require(type(prepared["inputs"]) is dict and set(prepared["inputs"]) == {"abcd", "cfull", "m2_receipt"},
                    "PREPARED_INPUTS", "three original inputs")
            input_paths = {key: Path(prepared["inputs"][key]["path"])
                           for key in ("abcd", "cfull", "m2_receipt")}
            receipt["input_identities_before"] = _input_probe(input_paths)
            result = verify_bundle(*(Path(prepared["inputs"][key]["path"])
                                     for key in ("abcd", "cfull", "m2_receipt")))
            equal(result["inputs"], prepared["inputs"], "PREPARED_INPUT_DRIFT", "input identity")
            equal(load_strict_json(saved_raw, "saved binding"), result,
                  "PREPARED_BINDING_DRIFT", "fresh association must exactly match")
            receipt["prepared_source"] = {"path": str(prepared_path), **digest(prepared_raw)}
        binding_raw = _json_bytes(result)
        _write_new(output / "binding.json", binding_raw)
        successor = {"schema": "N32_D_CFULL_PREPARED_V1", "scope": SCOPE,
                     "binding": digest(binding_raw), "inputs": result["inputs"]}
        _write_new(output / "prepared.json", _json_bytes(successor))
        receipt["result"] = digest(binding_raw)
        receipt["input_identities"] = result["inputs"]
        receipt["input_identities_after"] = result["inputs_after"]
        receipt["sources_after"] = _source_identities()
        equal(receipt["sources_after"], receipt["sources_before"], "SOURCE_DRIFT", "checker/docs/expectations")
        receipt["exit_code"] = 0
        receipt["status"] = "PASS_STATIC_BINDING_ONLY_T061_PARTIAL"
    except Exception as exc:
        receipt["failure"] = {"code": getattr(exc, "code", type(exc).__name__), "message": str(exc),
                              "traceback": traceback.format_exc()}
        if created:
            receipt["input_identities_after_failure"] = _input_probe(input_paths)
            try:
                receipt["sources_after"] = _source_identities()
            except Exception as source_exc:
                receipt["source_after_failure"] = str(source_exc)
    receipt["ended_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if created:
        _write_new(output / "receipt.json", _json_bytes(receipt))
        with (output / "events.jsonl").open("ab") as handle:
            handle.write(json.dumps({"event": "END", "exit_code": receipt["exit_code"],
                                     "status": receipt["status"]}, ensure_ascii=False).encode("utf-8") + b"\n")
    print(json.dumps({"status": receipt["status"], "exit_code": receipt["exit_code"],
                      "output": str(output), "failure": receipt.get("failure", {}).get("code")},
                     ensure_ascii=False))
    if not created and receipt["exit_code"]:
        print(json.dumps(receipt, ensure_ascii=False), file=sys.stderr)
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
