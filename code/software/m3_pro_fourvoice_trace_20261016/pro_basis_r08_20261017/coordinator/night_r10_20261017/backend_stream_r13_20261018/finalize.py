"""Terminal checks and the single atomic R13 completion barrier."""
from __future__ import annotations

import hashlib
from itertools import zip_longest
import json
import os
from pathlib import Path

import resources
from stream_bridge import CHUNK, require
from volume_io import VolumeStore

AUTHORITY_FLAGS = ("execution_allowed", "real_verified", "math_verified",
                   "board_release_allowed")
MATH_OUTPUT_SUFFIXES = frozenset({
    "MATH_INPUT_BUNDLE.json", "RECEIPT.json", "MATH_ROW_INDEX.jsonl",
    "FX_HISTORY.jsonl", "ADVANCE_HISTORY.jsonl",
    "INPUT_AND_APPLY_HISTORY.jsonl",
})


def _path(root: Path, descriptor: dict) -> Path:
    value = Path(descriptor["path"])
    return (value if value.is_absolute() else root / value).resolve()


def _identity(path: Path) -> dict:
    digest, count = hashlib.sha256(), 0
    with resources.accounting_open(path, "rb") as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            digest.update(block)
            count += len(block)
    return {"bytes": count, "sha256": digest.hexdigest()}


def _descriptor(root: Path, store: VolumeStore, descriptor: dict,
                mismatch_reason="FINAL_ARTIFACT_IDENTITY") -> dict:
    require(type(descriptor) is dict and
            {"path", "bytes", "sha256"} <= descriptor.keys(),
            "FINAL_DESCRIPTOR")
    path = _path(root, descriptor)
    is_volume = (path.is_relative_to(store.workspace) and
                 store.is_volume(path))
    if is_volume:
        actual = store.descriptor(path)
    else:
        require(path.is_file(), "FINAL_ARTIFACT_MISSING:" + str(path))
        actual = _identity(path)
    require(actual == {"bytes": descriptor["bytes"],
                       "sha256": descriptor["sha256"]},
            mismatch_reason + ":" + str(path))
    stable_path = (path.relative_to(store.workspace).as_posix()
                   if path.is_relative_to(store.workspace) else str(path))
    return {"path": stable_path,
            "path_root": "FINAL_OUTPUT" if path.is_relative_to(
                store.workspace) else "EXTERNAL_ABSOLUTE",
            **actual,
            "storage": "VOLUME" if is_volume else "PLAIN"}


def _open(root, store, descriptor, mode="rb"):
    path = _path(root, descriptor)
    if path.is_relative_to(store.workspace) and store.is_volume(path):
        return store.open(path, mode, {"bytes": descriptor["bytes"],
                                      "sha256": descriptor["sha256"]})
    return resources.accounting_open(
        path, mode, encoding=None if "b" in mode else "utf-8")


def _json(root, store, descriptor):
    require(descriptor["bytes"] <= 8 * CHUNK, "FINAL_CONTROL_BOUND")
    blocks, count = [], 0
    with _open(root, store, descriptor) as stream:
        while True:
            block = stream.read(min(CHUNK, 8 * CHUNK + 1 - count))
            if not block:
                break
            count += len(block)
            require(count <= 8 * CHUNK, "FINAL_CONTROL_BOUND")
            blocks.append(block)
    return json.loads(b"".join(blocks))


def _jsonl(root, store, descriptor):
    with _open(root, store, descriptor) as stream:
        line_number = 0
        while True:
            raw = stream.readline(CHUNK)
            if not raw:
                return
            line_number += 1
            if not raw.endswith(b"\n"):
                extra = stream.read(1)
                require(not extra and len(raw) < CHUNK,
                        "FINAL_JSONL_LINE_TOO_LONG:" + str(line_number))
                require(False, "FINAL_JSONL_LINE_MISSING_LF:" +
                        str(line_number))
            yield json.loads(raw)


def _terminal_rows(result, root, store, artifacts):
    inputs = result.get("inputs", {})
    require(all(role in inputs for role in ("raw", "end", "stdout", "window_plan")),
            "FINAL_INPUT_ROLES")
    public, roundtrip = artifacts["public_rows"], artifacts["csv_roundtrip"]
    rows, finishes, last_cycle = 0, 0, None
    for rows, triple in enumerate(zip_longest(
            _jsonl(root, store, inputs["raw"]),
            _jsonl(root, store, public),
            _jsonl(root, store, roundtrip)), 1):
        raw, row, decoded = triple
        require(raw is not None and row is not None and decoded is not None,
                "FINAL_STREAM_COVERAGE")
        require(row == decoded, "FINAL_PUBLIC_CSV_ROUNDTRIP")
        require(row.get("raw_ports") == raw.get("ports"),
                "FINAL_RAW_PUBLIC_PORTS")
        fields = row.get("fields", {})
        finish = fields.get("finish")
        require(finish in (0, 1), "FINAL_FINISH_VALUE")
        finishes += finish
        last_cycle = fields.get("cycle")
    end = _json(root, store, inputs["end"])
    window = _json(root, store, inputs["window_plan"])
    require(rows > 0 and finishes == 1 and
            rows == end["row_count"] == end["finish_cycle"] + 1 and
            rows == window["row_count"] and
            end["finish_cycle"] == window["finish_cycle"] == last_cycle,
            "FINAL_ROW_FINISH_WINDOW")
    marker = (f"MONITOR_END capture_id={result['capture_id']} "
              f"cycle={end['finish_cycle']} time_ps={end['time_ps']} "
              f"rows={end['row_count']} reason=PLANNED_WINDOW_END")
    markers = 0
    with _open(root, store, inputs["stdout"]) as stream:
        while True:
            raw_line = stream.readline(CHUNK)
            if not raw_line:
                break
            if len(raw_line) == CHUNK and not raw_line.endswith(b"\n"):
                require(not stream.read(1), "FINAL_STDOUT_LINE_TOO_LONG")
            line = raw_line.decode("utf-8").removeprefix("# ").strip()
            if "MONITOR_END" in line:
                require(line == marker, "FINAL_MONITOR_END_MISMATCH")
                markers += 1
    require(markers == 1, "FINAL_MONITOR_END_UNIQUE")
    return {"rows": rows, "finish_count": finishes,
            "last_cycle": last_cycle, "monitor_end_count": markers}


def _workspace_inventory(store: VolumeStore):
    physical, logical = [], []
    for path in sorted(store.workspace.rglob("*"), key=lambda item: str(item)):
        if path.is_file():
            physical.append({"path": path.relative_to(store.workspace).as_posix(),
                             **_identity(path)})
    if store.root.exists():
        for manifest_path in sorted(store.root.glob("*/MANIFEST.json")):
            require(manifest_path.stat().st_size <= CHUNK,
                    "FINAL_VOLUME_MANIFEST_BOUND")
            with resources.accounting_open(manifest_path, "r",
                                           encoding="utf-8") as stream:
                value = json.load(stream)
            require(value.get("schema") == "M3_R13_LOGICAL_VOLUME_V1",
                    "FINAL_VOLUME_MANIFEST_SCHEMA")
            logical.append({"path": value["logical_path"],
                            **value["original"],
                            "parts": len(value["parts"])})
    return {"physical_files": physical, "logical_volumes": logical,
            "physical_bytes": sum(item["bytes"] for item in physical),
            "logical_bytes": sum(item["bytes"] for item in logical)}


def _semantic_role_map(inventory: dict) -> dict:
    """Bind B08 semantic families to this run's actual returned artifacts."""
    families = {
        "public": ("public_rows", ("public_csv", "csv_roundtrip")),
        "advance": ("math_advance_history", ()),
        "cancel_intake": (
            "intake_ledger",
            ("intake_legacy_rows", "intake_c9_sidecar",
             "intake_preserved_rows"),
        ),
        "serial": ("serial", ()),
        "frame_plan": (
            "frame_plan", ("calendar_projection", "tx_projection"),
        ),
    }
    mapped = {}
    for semantic, (required_role, supporting) in families.items():
        require(required_role in inventory,
                "FINAL_B08_ROLE_MISSING:" + semantic)
        supporting_present = [role for role in supporting
                              if role in inventory]
        mapped[semantic] = {
            "required_artifact_role": required_role,
            "required_actual": inventory[required_role],
            "supporting_artifact_roles": supporting_present,
            "supporting_actual": {
                role: inventory[role] for role in supporting_present
            },
            "identity_source": "CURRENT_BACKEND_RESULT_NOT_PREDECLARED_SHA",
        }
    return mapped


def audit(result: dict, repo_root: Path, workspace_dir: Path) -> dict:
    require(type(result) is dict and
            result.get("schema") in ("M3_C9_CHAIN_HANDOFF_V1",
                                     "M3_R11_CAPTURE_SUCCESSOR_RESULT_V1"),
            "FINAL_RESULT_SCHEMA")
    require(all(result.get(flag) is False for flag in AUTHORITY_FLAGS),
            "FINAL_FALSE_AUTHORITY")
    require(result.get("status") not in (None, "PARTIAL_FAILURE_OR_REJECT"),
            "FINAL_STATUS")
    artifacts = result.get("artifacts")
    require(type(artifacts) is dict and artifacts, "FINAL_ARTIFACTS")
    store = VolumeStore(workspace_dir)
    inputs = result.get("inputs")
    require(type(inputs) is dict and "raw" in inputs, "FINAL_INPUT_ROLES")
    input_inventory = {
        role: _descriptor(repo_root, store, descriptor,
                          "FINAL_INPUT_IDENTITY_CHANGED")
        for role, descriptor in sorted(inputs.items())
    }
    inventory = {role: _descriptor(repo_root, store, descriptor)
                 for role, descriptor in sorted(artifacts.items())}
    math_bundle_role = next((role for role in inventory
                             if role.endswith("math_input_bundle")), None)
    require(math_bundle_role is not None, "FINAL_MATH_BUNDLE")
    math_bundle_path = _path(repo_root, artifacts[math_bundle_role])
    math_receipt_path = math_bundle_path.with_name("RECEIPT.json")
    require(math_receipt_path.is_file(), "FINAL_MATH_RECEIPT")
    inventory["math_receipt_unreturned_by_D4"] = {
        "path": math_receipt_path.relative_to(store.workspace).as_posix(),
        "path_root": "FINAL_OUTPUT", **_identity(math_receipt_path),
        "storage": "PLAIN"}
    names = {Path(item["path"]).name for role, item in inventory.items()
             if role.startswith("math_")}
    require(MATH_OUTPUT_SUFFIXES <= names, "FINAL_SIX_MATH_OUTPUTS")
    summary = result.get("summary", {})
    require(type(summary.get("rows")) is int and summary["rows"] > 0,
            "FINAL_NONZERO_ROWS")
    require(any(role == "public_rows" for role in inventory),
            "FINAL_PUBLIC_ROWS")
    require({"public_csv", "csv_roundtrip"} <= inventory.keys(),
            "FINAL_CSV_ROUNDTRIP")
    # The real frozen D4 provenance already checks raw/public coordinates,
    # unique finish and exact MONITOR_END.  Require that product here rather
    # than inventing a second finish representation.
    require(any(role.endswith("provenance") for role in inventory),
            "FINAL_D4_PROVENANCE")
    terminal = _terminal_rows(result, repo_root, store, artifacts)
    require(terminal["rows"] == summary["rows"], "FINAL_SUMMARY_ROWS")
    workspace = _workspace_inventory(store)
    semantic_roles = _semantic_role_map(inventory)
    return {"schema": "M3_R13_TERMINAL_AUDIT_V1",
            "status": "SOFTWARE_CHAIN_COMPLETE_PENDING_AUTHORITY",
            "rows": summary["rows"], "artifacts": inventory,
            "inputs": input_inventory,
            "raw_input": input_inventory["raw"],
            "B08_semantic_roles": semantic_roles,
            "terminal": terminal,
            "workspace_inventory": workspace,
            "six_D4_math_outputs": sorted(MATH_OUTPUT_SUFFIXES),
            "seven_M1_math_input_roles": [
                "mechanical_index", "public_rows", "raw_capture",
                "independent_plan", "frame_plan", "reset_edges",
                "provenance"],
            "consumer_compatibility":
                "PENDING_M1_STREAMING_INDEX_AND_RESET_PROJECTION_ADAPTER",
            **{flag: False for flag in AUTHORITY_FLAGS}}


def atomic_json(path: Path, value: dict, category=None) -> dict:
    raw = (json.dumps(value, ensure_ascii=False, indent=2,
                      allow_nan=False) + "\n").encode("utf-8")
    require(len(raw) <= 8 * CHUNK, "FINAL_CONTROL_TOO_LARGE")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with resources.accounting_open(temporary, "xb",
                                   category=category) as stream:
        offset = 0
        while offset < len(raw):
            block = raw[offset:offset + CHUNK]
            require(stream.write(block) == len(block), "FINAL_SHORT_WRITE")
            offset += len(block)
        stream.flush()
        os.fsync(stream.fileno())
    resources.get_budget().check()
    resources.accounting_replace(temporary, path)
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
