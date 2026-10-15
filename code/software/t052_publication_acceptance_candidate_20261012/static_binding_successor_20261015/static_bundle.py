"""Read-only identity check for the existing T052 R01 static preparation.

This module never launches HDL tools and never grants execution permission.
An identity match authenticates neither an operator nor a future RTL capture.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[4]
BASE = Path("code/software/t052_publication_acceptance_candidate_20261012/")
BASE /= "long_window_preparation_20261015"
TB = Path("code/tb/audio/t052_publication_acceptance_candidate_20261012/")
TB /= "long_window_preparation_20261015"
SOURCE_MANIFEST = Path("code/docs/test/t052_publication_acceptance_20261012/")
SOURCE_MANIFEST /= "CONTROL_PREPARATION_20261012/source_manifest.json"
PLAN = "T052_LONG_50M1042_FROZEN_FCW_R01"
ROWS = 8536336
CONTROL_BYTES = 375598784
CONTROL_SHA = "fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0"
LEDGER_SHA = "5096c3ce4596574efb0c9e13629e27ae9b27f49d0a7e777c39cf324c80f136f6"
M1_SHA = "56574246ebd7fe75bf59ea7f583ffe2c00f5593b8567230dbb6992cfe857b555"
PYTHON_NAMES = {
    "plan.py", "prepare.py", "check_capture.py", "test_long.py",
    "run_checks.py", "run_preparation.py", "qualify_tools.py",
}
TB_NAMES = {"tb_t052_long.sv", "t052_long_observer.sv"}
FROZEN_NAMES = {
    "t052_polyphony_test_source.sv", "dds_oscillator.sv",
    "pcm_mixer_4voice.sv", "sine_1024_8192.mem",
}


class BindingError(ValueError):
    """A contradictory identity, contract or preparation claim."""


def require(condition, diagnostic):
    if not condition:
        raise BindingError(diagnostic)


def strict_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (left.keys() == right.keys()
                and all(strict_equal(left[k], right[k]) for k in left))
    if isinstance(left, list):
        return (len(left) == len(right)
                and all(strict_equal(a, b) for a, b in zip(left, right)))
    return left == right


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY:" + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise BindingError("NONFINITE_JSON:" + value)

    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=pairs, parse_constant=nonfinite)


def identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def check_prepared(prepared, root=ROOT):
    """Verify actual files twice against the fixed R01 preparation contract."""
    prepared, root = Path(prepared).resolve(), Path(root).resolve()
    checked = {}

    def bind(spec, expected_path=None):
        require(isinstance(spec, dict), "IDENTITY_OBJECT")
        require(isinstance(spec.get("path"), str), "IDENTITY_PATH")
        path = Path(spec["path"])
        require(path.is_absolute(), "IDENTITY_PATH_NOT_ABSOLUTE")
        path = path.resolve()
        if expected_path is not None:
            require(path == Path(expected_path).resolve(), "IDENTITY_WRONG_PATH")
        require(type(spec.get("bytes")) is int and spec["bytes"] >= 0,
                "IDENTITY_SIZE_TYPE")
        require(isinstance(spec.get("sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", spec["sha256"]) is not None,
                "IDENTITY_SHA_FORMAT")
        actual = identity(path)
        require(actual["bytes"] == spec["bytes"]
                and actual["sha256"] == spec["sha256"], "FILE_IDENTITY_MISMATCH")
        if str(path) in checked:
            require(strict_equal(checked[str(path)], actual), "CONFLICTING_IDENTITY")
        checked[str(path)] = actual
        return actual

    proposal_path = prepared / "proposal.json"
    checked[str(proposal_path)] = identity(proposal_path)
    proposal = load_json(proposal_path)
    require(isinstance(proposal, dict), "PROPOSAL_OBJECT")
    require(proposal.get("schema") == "T052_LONG_STATIC_PREPARATION_R01"
            and proposal.get("plan") == PLAN, "WRONG_PREPARATION_VERSION")
    require(proposal.get("execution_authorized") is False, "EXECUTION_MUST_BE_LOCKED")
    require(proposal.get("phase") == "STATIC_PREPARATION_ONLY", "NOT_STATIC_PREPARATION")
    for field in ("actual_HDL_calls", "actual_RTL_runs", "actual_EDA_calls"):
        require(type(proposal.get(field)) is int and proposal[field] == 0,
                "NONZERO_OR_INVALID_TOOL_CLAIM:" + field)
    require(proposal.get("PCM_math_verified") is False
            and proposal.get("old_4207_completeness") == "UNKNOWN", "EVIDENCE_UPGRADE")
    require(type(proposal.get("rows")) is int and proposal["rows"] == ROWS,
            "WRONG_WINDOW")
    totals = dict(type="END", rows=ROWS, accepted=8207, published=8201,
                  cancelled=6, open=0)
    require(strict_equal(proposal.get("expected_end"), totals), "WRONG_STATIC_TOTALS")
    require(strict_equal(proposal.get("proposed_limits_seconds"),
                         dict(compile=90, run=300, check=300, total=900)),
            "BUDGET_CONTRACT_CHANGED")
    fixed_limits = dict(proposed_output_limit_bytes=1200 * (1 << 20),
                        proposed_capture_limit_bytes=750 * (1 << 20),
                        last_posedge_ns=170726710, finish_ns=170726711,
                        simulation_timeout_ns=170726720)
    require(all(strict_equal(proposal.get(k), v) for k, v in fixed_limits.items()),
            "WINDOW_OR_OUTPUT_LIMIT_CHANGED")

    control = bind(proposal["input"], prepared / "controls.hex")
    require(control["bytes"] == CONTROL_BYTES and control["sha256"] == CONTROL_SHA,
            "FROZEN_CONTROL_CHANGED")
    ledger = bind(proposal["expected_ledger"], prepared / "expected_publications.jsonl")
    require(ledger["sha256"] == LEDGER_SHA, "FROZEN_LEDGER_CHANGED")
    confirmation = bind(proposal["m1_confirmation"])
    require(confirmation["sha256"] == M1_SHA, "M1_CONFIRMATION_CHANGED")
    copy = identity(prepared / "M1_INPUT_CONFIRMATION.md")
    bind(copy)
    require(copy["sha256"] == M1_SHA, "M1_COPY_CHANGED")

    qualification = bind(proposal["tool_qualification"])
    qualified = load_json(qualification["path"])
    require(isinstance(qualified, dict)
            and qualified.get("status") == "TOOL_METADATA_PASS", "TOOL_METADATA_NOT_PASS")
    tools = proposal["tools"]
    require(isinstance(tools, dict), "TOOL_INVENTORY_OBJECT")
    require(strict_equal(qualified.get("after"), tools), "TOOL_INVENTORY_DISAGREES")
    require(tools.get("missing") == [], "TOOL_FILES_MISSING")
    require(isinstance(tools.get("files"), list) and tools["files"], "EMPTY_TOOL_INVENTORY")
    versions = qualified.get("steps")
    require(isinstance(versions, list) and len(versions) == 2
            and all(isinstance(step, dict) for step in versions), "TOOL_VERSIONS_INCOMPLETE")
    require(strict_equal(proposal.get("tool_versions"),
                         [step.get("version") for step in versions]), "TOOL_VERSION_MISMATCH")
    require(all(isinstance(v, str) and v.strip() and "UNKNOWN" not in v.upper()
                for v in proposal["tool_versions"]), "UNKNOWN_TOOL_VERSION")
    tool_paths = []
    for spec in tools["files"]:
        tool_paths.append(Path(bind(spec)["path"]))
    require(len(tool_paths) == len(set(tool_paths)), "DUPLICATE_TOOL_PATH")
    suite = Path(tools["requested_suite"]).resolve()
    require(suite / "bin/iverilog.exe" in tool_paths
            and suite / "bin/vvp.exe" in tool_paths, "EXECUTABLE_NOT_BOUND")

    source_paths = {root / BASE / name for name in PYTHON_NAMES}
    source_paths.update(root / TB / name for name in TB_NAMES)
    source_paths.update((root / SOURCE_MANIFEST, Path(confirmation["path"]),
                         Path(qualification["path"])))
    sources = proposal["source_files"]
    require(isinstance(sources, dict), "SOURCE_MANIFEST_OBJECT")
    require({Path(p).resolve() for p in sources} == source_paths
            and len(sources) == len(source_paths), "SOURCE_CLOSURE_MISMATCH")
    for path, spec in sources.items():
        bind(spec, path)
    for name in TB_NAMES:
        original = checked[str((root / TB / name).resolve())]
        actual_copy = identity(prepared / name)
        bind(actual_copy)
        require(actual_copy["sha256"] == original["sha256"], "TB_COPY_CHANGED")

    manifest = load_json(root / SOURCE_MANIFEST)
    require(isinstance(manifest, dict), "SOURCE_ARCHIVE_MANIFEST_OBJECT")
    frozen = proposal["frozen_sources"]
    require(isinstance(frozen, dict) and set(frozen) == FROZEN_NAMES,
            "FROZEN_SOURCE_CLOSURE")
    seen = set()
    for group in (manifest["raw_archive"], manifest["readonly_archive"]):
        require(isinstance(group, dict), "ARCHIVE_GROUP_OBJECT")
        archive_path = (root / group["path"]).resolve()
        require(archive_path.is_relative_to(root), "ARCHIVE_OUTSIDE_REPOSITORY")
        archive_id = identity(archive_path)
        require(archive_id["sha256"] == group["sha256"], "ARCHIVE_SHA_MISMATCH")
        bind(archive_id)
        with zipfile.ZipFile(archive_path) as archive:
            require(len(archive.namelist()) == len(set(archive.namelist())),
                    "DUPLICATE_ARCHIVE_MEMBER")
            for member, spec in group["members"].items():
                name = Path(member).name
                require(name in frozen and name not in seen, "FROZEN_MEMBER_MAPPING")
                seen.add(name)
                data = archive.read(member)
                require(type(spec["bytes"]) is int and len(data) == spec["bytes"]
                        and hashlib.sha256(data).hexdigest() == spec["sha256"],
                        "ARCHIVE_MEMBER_IDENTITY")
                mapped = frozen[name]
                require(mapped.get("archive") == group["path"]
                        and mapped.get("member") == member
                        and mapped.get("bytes") == spec["bytes"]
                        and mapped.get("sha256") == spec["sha256"], "FROZEN_SOURCE_MAPPING")
                bind(mapped, prepared / "readonly" / name)
    require(seen == FROZEN_NAMES, "FROZEN_MEMBER_MISSING")

    compiler = str(suite / "bin/iverilog.exe")
    expected_compile = [compiler, "-g2012", "-s", "tb_t052_long", "-o", "long.vvp",
                        "readonly/t052_polyphony_test_source.sv",
                        "readonly/dds_oscillator.sv", "readonly/pcm_mixer_4voice.sv",
                        "t052_long_observer.sv", "tb_t052_long.sv"]
    require(strict_equal(proposal.get("compile_argv"), expected_compile), "COMPILE_ARGV_CHANGED")
    require(strict_equal(proposal.get("run_argv"),
                         [str(suite / "bin/vvp.exe"), "long.vvp"]), "RUN_ARGV_CHANGED")
    python = bind(proposal["python"])
    expected_check = [python["path"], "-B", "-X", "utf8",
                      str(root / BASE / "check_capture.py"), "--capture", str(prepared),
                      "--report", str(prepared / "capture_review.json")]
    require(strict_equal(proposal.get("check_argv"), expected_check), "CHECK_ARGV_CHANGED")
    require(proposal.get("cwd") == str(prepared), "CWD_CHANGED")
    for path, before in checked.items():
        require(strict_equal(identity(path), before), "FILE_CHANGED_DURING_CHECK")
    return dict(status="STATIC_IDENTITY_MATCH_ONLY", plan=PLAN,
                execution_authorized=False, actual_HDL_calls=0, actual_RTL_runs=0,
                actual_EDA_calls=0, PCM_math_verified=False,
                old_4207_completeness="UNKNOWN", complete_T052=False,
                proposed_machine=proposal.get("machine", "UNKNOWN"),
                execution_machine_verified=False,
                tool_binding="STATIC_INVENTORY_ONLY_NOT_DYNAMIC_LOAD_CLOSURE",
                checked_files=checked, proposed_commands_executed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("REPORT_EXISTS")
    try:
        result, code = check_prepared(args.prepared), 0
    except (FileNotFoundError, PermissionError) as exc:
        result, code = dict(status="INCOMPLETE", diagnostic=str(exc)), 3
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile, OSError) as exc:
        result, code = dict(status="STATIC_BINDING_FAIL", diagnostic=str(exc)), 1
    result.update(exit_code=code, execution_authorized=False, complete_T052=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "checked_files"}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
