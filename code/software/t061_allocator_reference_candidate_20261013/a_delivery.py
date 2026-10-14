"""Freeze a new, immutable N32-A PLAN or RESULT snapshot for both reviewers."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import types
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import a_harness


def digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def verify_cached_paths(cached):
    """A path-reading diff may only represent the already selected raw bytes."""
    for path, raw in cached.items():
        a_harness.require(Path(path).read_bytes() == raw,
                          "PATCH_CACHED_BYTES_DRIFT:" + str(path))


def binary_diff(paths, expected_bytes=None):
    """Git's binary-safe patch, including every new input absent from base."""
    base = "0b5f45388f974ce4ae0a2081eac7add93181c32a"
    git = shutil.which("git")
    a_harness.require(git is not None, "GIT_MISSING")
    git_before = Path(git).read_bytes()
    expected_bytes = ({Path(path).resolve(): Path(path).read_bytes() for path in paths}
                      if expected_bytes is None else expected_bytes)
    verify_cached_paths(expected_bytes)
    patches = []
    for path in sorted(set(paths)):
        relative = Path(path).resolve().relative_to(a_harness.ROOT).as_posix()
        exists = subprocess.run([git, "cat-file", "-e", base + ":" + relative],
                                cwd=a_harness.ROOT, capture_output=True, timeout=10)
        a_harness.require(exists.returncode in (0, 128), "BASE_LOOKUP_FAILED")
        argv = ([git, "diff", "--binary", base, "--", relative]
                if exists.returncode == 0 else
                [git, "diff", "--no-index", "--binary", "--", "/dev/null", relative])
        result = subprocess.run(argv, cwd=a_harness.ROOT,
                                capture_output=True, timeout=10)
        a_harness.require(result.returncode in (0, 1), "DIFF_FAILED:" + relative)
        patches.append(result.stdout)
    verify_cached_paths(expected_bytes)
    a_harness.require(Path(git).read_bytes() == git_before, "DIFF_TOOL_DRIFT")
    return b"".join(patches), {"path": git, **digest(git_before)}


def seal(plan_path, target, review_key, evidence, permission="Existing bounded N32-A selftest only; no T052/T060/EDA/devices", qualification=None):
    target = Path(target).resolve()
    a_harness.require(target.is_relative_to(HERE) and target != HERE,
                      "DELIVERY_OUTSIDE_A_WRITESET")
    a_harness.require(not target.exists(), "DELIVERY_EXISTS")
    plan_path = Path(plan_path).resolve()
    plan = a_harness.verify(plan_path)
    plan_raw = plan_path.read_bytes()
    a_harness.require(json.loads(plan_raw) == plan, "SEAL_PLAN_DRIFT")
    members = {}
    capsule = Path(plan["capsule_root"]).resolve()
    capsule_bytes = {}
    frozen_inputs = {}
    for relative, expected in plan["capsule_files"].items():
        raw = (capsule / relative).read_bytes()
        a_harness.require(digest(raw) == {key: expected[key] for key in ("bytes", "sha256")},
                          "SEAL_CAPSULE_DRIFT:" + relative)
        capsule_bytes[relative] = raw
        frozen_inputs[expected["source_provenance"]] = raw
    execution_bytes = {}
    execution_binding = None
    config_path = plan_path.parent / "compile_diagnostic.json"
    launch_path = plan_path.parent / "diagnostic_launch.json"
    present = (config_path.is_file(), launch_path.is_file())
    a_harness.require(present[0] == present[1], "DIAGNOSTIC_EXECUTION_PAIR")
    if all(present):
        config_raw, launch_raw = config_path.read_bytes(), launch_path.read_bytes()
        config, launch = json.loads(config_raw), json.loads(launch_raw)
        a_harness.require(config["plan"] == digest(plan_raw), "DIAGNOSTIC_CONFIG_PLAN")
        a_harness.require({key: launch["plan"][key] for key in ("bytes", "sha256")} ==
                          digest(plan_raw), "DIAGNOSTIC_LAUNCH_PLAN")
        a_harness.require(Path(launch["plan"]["path"]).resolve() == plan_path,
                          "DIAGNOSTIC_LAUNCH_PLAN_PATH")
        a_harness.require({key: launch["config"][key] for key in ("bytes", "sha256")} ==
                          digest(config_raw), "DIAGNOSTIC_LAUNCH_CONFIG")
        a_harness.require(Path(launch["config"]["path"]).resolve() == config_path,
                          "DIAGNOSTIC_LAUNCH_CONFIG_PATH")
        a_harness.require(Path(launch["capsule"]).resolve() == capsule
                          and Path(launch["cwd"]).resolve() == capsule,
                          "DIAGNOSTIC_LAUNCH_CAPSULE")
        a_harness.require(Path(launch["worker_argv"][0]).resolve() ==
                          Path(launch["python"]["path"]).resolve(),
                          "DIAGNOSTIC_WORKER_PYTHON")
        a_harness.require(Path(launch["worker"]["path"]).resolve().is_relative_to(capsule)
                          and Path(launch["launcher"]["path"]).resolve().is_relative_to(capsule),
                          "DIAGNOSTIC_SOURCE_OUTSIDE_CAPSULE")
        for key in ("worker", "launcher"):
            source = Path(launch[key]["path"]).resolve()
            relative = source.relative_to(capsule).as_posix()
            a_harness.require(relative in capsule_bytes and digest(capsule_bytes[relative]) ==
                              {name: launch[key][name] for name in ("bytes", "sha256")},
                              "DIAGNOSTIC_SOURCE_SHA:" + key)
        execution_bytes = {config_path: config_raw, launch_path: launch_raw}
        execution_binding = {"config": digest(config_raw), "launch": digest(launch_raw),
                             "execution_output": config["execution_output"],
                             "parent_output": launch["parent_output"]}
    patch_inputs = {}
    qualification_binding = None
    qualification_cache = {}
    qualification_root = None
    if qualification is not None:
        qualification_root = a_harness.under_output(qualification)
        qualifier_relative = "code/software/t061_allocator_reference_candidate_20261013/a_qualify_diagnostic.py"
        qualifier_path = capsule / qualifier_relative
        qualifier_raw = capsule_bytes[qualifier_relative]
        # Authenticate the exact raw bytes before executing any verifier code.
        a_harness.require(digest(qualifier_raw) == {
            key: plan["capsule_files"][qualifier_relative][key]
            for key in ("bytes", "sha256")}, "QUALIFIER_RAW_SHA")
        module = types.ModuleType("verified_diagnostic_qualifier")
        module.__file__ = str(qualifier_path)
        exec(compile(qualifier_raw, str(qualifier_path), "exec"), module.__dict__)
        validated = module.validate_qualification(qualification_root, capsule_bytes)
        a_harness.require(validated["source_bytes"] == capsule_bytes,
                          "QUALIFICATION_FINAL_SOURCE_BYTES")
        # Freeze the validator's verified evidence immediately. No later root
        # walk/read may replace any of these bytes with a live path version.
        for relative, raw in validated["source_bytes"].items():
            qualification_cache[qualification_root / "frozen" / relative] = raw
        for path, raw in validated["evidence_bytes"].items():
            source = Path(path).resolve()
            if source.is_relative_to(qualification_root):
                a_harness.require(source not in qualification_cache or
                                  qualification_cache[source] == raw,
                                  "QUALIFICATION_CACHE_CONFLICT:" + str(source))
                qualification_cache[source] = raw
        qualification_binding = {"scope": "SOFTWARE_ONLY_SOURCE_BOUND_NOT_HDLSIM",
                                 "tests_run": validated["receipt"]["tests_run"],
                                 "qualified_sources": len(validated["source_bytes"]),
                                 "manifest": digest(module.encoded(validated["manifest"])),
                                 "child_receipt": digest(module.encoded(validated["receipt"]))}
    for path, expected in plan["inputs"].items():
        source = Path(path)
        raw = frozen_inputs[path]
        a_harness.require(digest(raw) == expected, "SEAL_INPUT_DRIFT:" + path)
        members["files/" + source.relative_to(a_harness.ROOT).as_posix()] = raw
        patch_inputs[source.resolve()] = raw
    members["plan.json"] = plan_raw
    patch_inputs[plan_path] = plan_raw
    for path, raw in execution_bytes.items():
        members["execution/" + path.name] = raw
        patch_inputs[path.resolve()] = raw
    readme_path = HERE / "README_A.md"
    members["README_A.md"] = (frozen_inputs[str(readme_path)] if str(readme_path) in frozen_inputs
                              else readme_path.read_bytes())
    patch_inputs[readme_path.resolve()] = members["README_A.md"]
    for root in evidence:
        root = a_harness.under_output(root)
        if qualification_root is not None and root.is_relative_to(qualification_root):
            cached = {path: raw for path, raw in qualification_cache.items()
                      if path.is_relative_to(root)}
        else:
            a_harness.require(qualification_root is None or
                              not qualification_root.is_relative_to(root),
                              "QUALIFICATION_ROOT_MUST_BE_EXPLICIT")
            cached = {source.resolve(): source.read_bytes() for source in sorted(root.rglob("*"))
                      if source.is_file() and source.suffix not in (".vvp", ".pyc")}
        for source, raw in cached.items():
            if source.suffix not in (".vvp", ".pyc"):
                name = "evidence/" + root.name + "/" + source.relative_to(root).as_posix()
                a_harness.require(name not in members or members[name] == raw,
                                  "SEAL_MEMBER_CONFLICT:" + name)
                members[name] = raw
                a_harness.require(source not in patch_inputs or patch_inputs[source] == raw,
                                  "PATCH_MEMBER_CONFLICT:" + str(source))
                patch_inputs[source] = raw
    verify_cached_paths(patch_inputs)
    members["changes.patch"], diff_tool = binary_diff(patch_inputs, patch_inputs)
    verify_cached_paths(patch_inputs)
    manifest = {
        "review_key": review_key,
        "base": "0b5f45388f974ce4ae0a2081eac7add93181c32a",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "M3 / main-dialogue-2 / a_delivery.py",
        "diff_tool": diff_tool,
        "diff_scope": "All plan inputs, plan, README and archived evidence; existing unchanged base inputs have empty diffs.",
        "state": "SEALED-UNCOMMITTED", "plan": digest(members["plan.json"]),
        "files": {name: digest(raw) for name, raw in sorted(members.items())},
        "evidence_roots": [str(Path(p).resolve()) for p in evidence],
        "permission": permission,
        "software_qualification": qualification_binding,
        "execution_artifacts": execution_binding,
    }
    manifest_raw = encode(manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in sorted(members.items()):
            bundle.writestr(name, raw)
        bundle.writestr("MANIFEST.json", manifest_raw)
    archive = stream.getvalue()
    # All bytes are determined before exclusive target creation.
    target.mkdir(parents=True, exist_ok=False)
    (target / "snapshot.zip.b64").write_bytes(base64.b64encode(archive) + b"\n")
    (target / "MANIFEST.json").write_bytes(manifest_raw)
    receipt = {"review_key": review_key, "snapshot": digest(archive),
               "scope": digest(manifest_raw), "plan": digest(members["plan.json"]),
               "members": len(members) + 1, "state": "SEALED-UNCOMMITTED"}
    (target / "seal.json").write_bytes(encode(receipt))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--review-key", required=True)
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    parser.add_argument("--permission", default="Existing bounded N32-A selftest only; no T052/T060/EDA/devices")
    parser.add_argument("--qualification", type=Path)
    args = parser.parse_args()
    print(json.dumps(seal(args.plan, args.target, args.review_key, args.evidence, args.permission, args.qualification)))
