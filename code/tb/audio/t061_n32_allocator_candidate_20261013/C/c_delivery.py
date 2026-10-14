"""Seal exact C evidence without starting a tool or accepting fixture output."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
from c_process import identity, write_json


def require(test, message):
    if not test:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def seal(prepared, output, destination, history, prefix=None):
    require(not destination.exists(), "C_SEAL_NEW_DIRECTORY")
    plan = read_json(prepared/"plan.json")
    receipt = read_json(output/"receipt.json")
    require(receipt["status"] == "N32_C_STRESS_PASS_T061_PARTIAL"
            and receipt["exit_code"] == 0 and receipt["EDA_calls"] == 0,
            "C_SEAL_REAL_PASS_REQUIRED")
    require(identity(prepared/"plan.json") == receipt["plan"], "C_SEAL_PLAN_BINDING")
    report = read_json(output/"report.json")
    mutations = read_json(output/"mutation_report.json")
    if plan.get("profile") == "full-v6":
        require(prefix is None, "C_FULL_NO_PREFIX_COMPOSITION")
        if "reused_simulation" in plan:
            require(plan["reused_simulation"].get("origin_profile") == "full-v6"
                    and receipt.get("execution_mode") == "RTL_REUSED_NO_NEW_SIMULATION"
                    and plan["full_reuse_qualification"]["status"] ==
                        "KNOWN_CHECKER_ONLY_FAILURE_FULL_CAPTURE_QUALIFIED",
                    "C_FULL_REUSED_ORIGINAL_MUST_BE_COMPLETE_FULL")
        require(report.get("single_continuous_full_C_run") is True
                and report.get("complete_C_capture") is True
                and report.get("capture_composition") is False
                and mutations.get("rejected") == 24, "C_FULL_SEAL_SCOPE")
    capture = Path(plan.get("reused_simulation", {}).get("capture_path", output/"simulate.stdout.bin"))
    require(identity(capture)["sha256"] == report["capture_sha256"]
            and mutations["original_sha256"] == report["capture_sha256"], "C_SEAL_CAPTURE_BINDING")
    composition = None
    if plan.get("profile") == "suffix-v6":
        require(prefix is not None, "C_SEGMENTED_PREFIX_REQUIRED")
        qualification = read_json(prefix)
        require(qualification["status"] == "N32_C_C00_C04_PARTIAL_PREFIX_VALID_ONLY"
                and qualification["fabricated_END"] is False
                and qualification["complete_C_capture"] is False,
                "C_PREFIX_SCOPE_REQUIRED")
        original_output = ROOT/"code/output/n32cr05"
        failed = read_json(original_output/"receipt.json")
        original_capture = original_output/"simulate.stdout.bin"
        require(failed["status"] == "FAIL_PARTIAL" and failed["exit_code"] != 0,
                "C_FAILED_ORIGINAL_MUST_REMAIN_FAILED")
        require(identity(original_capture)["sha256"] == qualification["original_capture_sha256"],
                "C_PREFIX_ORIGINAL_CAPTURE_PIN")
        require(qualification["independent_clocked_math"]["lifecycle"]["retirements"] >= 4
                and qualification["live_qualification"]["live_at_end"] is None,
                "C_PREFIX_MATH_RETIREMENT_NOT_CLOSED")
        with original_capture.open("rb") as stream:
            raw_prefix = stream.read(qualification["prefix_bytes"])
        require(hashlib.sha256(raw_prefix).hexdigest() == qualification["prefix_sha256"],
                "C_PREFIX_BYTE_RANGE_PIN")
        composition = {"status": "N32_C_SEGMENTED_FUNCTION_MATH_PASS_T061_PARTIAL",
            "C00_C04": {"source": "QUALIFIED_PREFIX_OF_FAILED_R05_NOT_WHOLE_RUN_PASS",
                "report": identity(prefix), "capture": identity(original_capture),
                "failed_receipt": identity(original_output/"receipt.json"),
                "byte_range": qualification["byte_range"]},
            "C05_C09": {"source": "INDEPENDENT_RESET_SHORT_SUFFIX_ACTUAL_RTL",
                "report": identity(output/"report.json"), "receipt": identity(output/"receipt.json")},
            "single_continuous_full_C_run": False,
            "state_checkpoint_or_trace_concatenation": False,
            "T061_complete": False, "physical_STA": "NOT_RUN"}
        # The original math models and ROM bracket both executions: the asset
        # builder pinned them before R07, and sealing checks the same originals
        # after the prefix software proof. Later delivery-only edits are not
        # falsely presented as unchanged mathematical dependencies.
        asset_receipt = read_json(prepared/"snapshot/assets/asset_build_receipt.json")
        bracket = {}
        for origin, expected in asset_receipt["sources_before"].items():
            path = Path(origin)
            if path.suffix == ".mem" or (path.suffix == ".py" and
                    any(part in path.parts for part in ("audio_math_acceptance_candidate", "polyphony_scaling_candidate"))):
                require(identity(path) == expected, "C_COMPOSE_FROZEN_MATH_DRIFT:"+origin)
                bracket[origin] = expected
        require(bracket, "C_COMPOSE_EMPTY_MATH_BRACKET")
        composition["mathematical_dependencies_before_asset_generation_and_after_proofs"] = bracket
    files = {}
    paths = {}

    def add(name, path):
        path = Path(path)
        require(name not in files and not name.startswith("/") and ".." not in Path(name).parts,
                "C_SEAL_MEMBER")
        files[name] = identity(path)
        paths[name] = path

    for path in sorted(prepared.rglob("*")):
        if path.is_file():
            add("prepared/"+path.relative_to(prepared).as_posix(), path)
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.suffix != ".vvp":
            add("execution/"+path.relative_to(output).as_posix(), path)
    if capture != output/"simulate.stdout.bin":
        add("reused/capture.log", capture)
        old_receipt = Path(plan["reused_simulation"]["receipt_path"])
        add("reused/original_receipt.json", old_receipt)
        old_plan = Path(read_json(old_receipt)["prepared_plan_path"])
        add("reused/original_plan.json", old_plan)
    for folder in history:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix != ".vvp" and path != capture:
                # Old complete large capture is included once, never replaced.
                if path.name == "simulate.stdout.bin" and identity(path) == identity(capture):
                    continue
                add("history/"+folder.name+"/"+path.relative_to(folder).as_posix(), path)
    for name in ("RESULT_20261014.md", "SELF_REVIEW_20261014.md", "NOTICE_TO_M2_20261014.md", "README_V6.md"):
        if (HERE/name).exists():
            add("delivery/"+name, HERE/name)
    if plan.get("profile") == "full-v6":
        for name in ("FULL_RESULT_20261014.md", "FULL_NOTICE_TO_M2_20261014.md"):
            require((HERE/name).is_file(), "C_FULL_CURRENT_DELIVERY_REQUIRED:"+name)
            add("delivery/"+name, HERE/name)
    add("delivery/actual_sealer.py", Path(__file__))
    if prefix is not None:
        add("composition/prefix_report.json", prefix)
    manifest = {"schema": "T061_N32_C_SEAL_MANIFEST_V4", "review_key": plan["review_key"],
                "status": receipt["status"], "files": files,
                "capture": identity(capture), "plan": identity(prepared/"plan.json"),
                "receipt": identity(output/"receipt.json"), "EDA_calls": 0,
                "T061_complete": False, "physical_STA": "NOT_RUN",
                "tool_distribution": "TOOLS_EXTERNAL_PINNED_IN_PREPARED_PLAN"}
    if composition is not None:
        manifest["composition"] = composition
        manifest["status"] = composition["status"]
    if plan.get("profile") == "full-v6":
        manifest.update(single_continuous_full_C_run=True, capture_composition=False,
                        status="N32_C_FULL_CONTINUOUS_FUNCTION_MATH_PASS_T061_PARTIAL")
    destination.mkdir(parents=True)
    write_json(destination/"MANIFEST.json", manifest)
    archive = destination/"snapshot.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, path in paths.items():
            require(identity(path) == files[name], "C_SEAL_INPUT_DRIFT:"+name)
            bundle.write(path, name)
        bundle.write(destination/"MANIFEST.json", "MANIFEST.json")
    # The text representation matches the existing A/B repository convention.
    (destination/"snapshot.zip.b64").write_bytes(base64.b64encode(archive.read_bytes())+b"\n")
    result = {"status": manifest["status"], "review_key": plan["review_key"],
              "manifest": identity(destination/"MANIFEST.json"), "snapshot": identity(archive),
              "members": len(files)+1, "T061_complete": False}
    write_json(destination/"seal.json", result)
    return verify(destination)


def verify(destination):
    seal_info = read_json(destination/"seal.json")
    require(identity(destination/"MANIFEST.json") == seal_info["manifest"], "C_SEAL_MANIFEST_SHA")
    raw = base64.b64decode((destination/"snapshot.zip.b64").read_bytes().strip(), validate=True)
    require({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} == seal_info["snapshot"],
            "C_SEAL_ARCHIVE_SHA")
    manifest = read_json(destination/"MANIFEST.json")
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        require(len(bundle.namelist()) == len(set(bundle.namelist()))
                and set(bundle.namelist()) == set(manifest["files"]) | {"MANIFEST.json"},
                "C_SEAL_MEMBER_SET")
        require(bundle.read("MANIFEST.json") == (destination/"MANIFEST.json").read_bytes(), "C_SEAL_MANIFEST_BYTES")
        for name, expected in manifest["files"].items():
            body = bundle.read(name)
            require({"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()} == expected,
                    "C_SEAL_MEMBER_SHA:"+name)
    return {"status": "C_SEAL_VERIFY_PASS", "members": seal_info["members"],
            "snapshot_sha256": seal_info["snapshot"]["sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal", "verify"))
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--history", type=Path, nargs="*", default=[])
    parser.add_argument("--prefix", type=Path)
    args = parser.parse_args()
    result = (verify(args.destination) if args.command == "verify" else
              seal(args.prepared, args.output, args.destination, args.history, args.prefix))
    print(json.dumps(result))
