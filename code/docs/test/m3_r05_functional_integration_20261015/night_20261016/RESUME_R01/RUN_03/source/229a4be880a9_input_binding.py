"""Read-only exact R05 manifest, compile dependency and physical source audit."""
from collections import Counter
from pathlib import Path, PurePosixPath
import zipfile

from common import (
    R05, R05_SHA, TB_SHA, PHYSICAL, PHYSICAL_SHA, Refusal, sha, json_load,
)


def safe_name(name):
    p = PurePosixPath(name)
    return (
        bool(name) and not p.is_absolute() and ".." not in p.parts
        and "\\" not in name and ":" not in name and str(p) == name
    )


def inspect_archive(path=R05):
    raw = Path(path).read_bytes()
    if sha(raw) != R05_SHA:
        raise Refusal("R05_SHA", "not the authorized exact R05")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or not all(safe_name(n) for n in names):
            raise Refusal("ZIP_NAMES", "duplicate or unsafe member")
        data = {name: archive.read(name) for name in names}
    manifest = json_load(data["MANIFEST.json"])
    declared = manifest["members"]
    if set(declared) != set(data) - {"MANIFEST.json"}:
        raise Refusal("MANIFEST_MEMBERS", "undeclared or missing input")
    for name, expected in declared.items():
        actual = {"bytes": len(data[name]), "sha256": sha(data[name])}
        if actual != expected:
            raise Refusal("MANIFEST_SHA", name)
    if sha(data["inputs/tb_m2_m1td_real_chain.sv"]) != TB_SHA:
        raise Refusal("TB_SHA", "frozen XSAFE TB differs")
    compile_units = data["inputs/compile.f"].decode("utf-8").splitlines()
    if len(compile_units) != 69 or len(set(compile_units)) != 69:
        raise Refusal("COMPILE_UNITS", "expected 69 unique ordered units")
    if not all(safe_name(n) and ("inputs/" + n) in data for n in compile_units):
        raise Refusal("COMPILE_DEPENDENCY", "missing or unsafe compilation unit")
    prep = json_load(data["PREPARATION_RECEIPT.json"])
    if prep["compile_units"] != 69:
        raise Refusal("PREPARATION_IDENTITY", "compile count mismatch")
    for name, expected in prep["output_identities"].items():
        if name not in data or expected != {"bytes": len(data[name]), "sha256": sha(data[name])}:
            raise Refusal("PREPARATION_OUTPUT", name)
    mapping = []
    physical_raw = PHYSICAL.read_bytes()
    if sha(physical_raw) != PHYSICAL_SHA:
        raise Refusal("PHYSICAL_SHA", "frozen physical original differs")
    with zipfile.ZipFile(PHYSICAL) as archive:
        physical = json_load(archive.read("RUN_RECEIPT.json"))["input_before"]
    by_suffix = {}
    for key, item in physical.items():
        normalized = key.replace("\\", "/")
        marker = "/inputs/"
        if marker in normalized:
            by_suffix["inputs/" + normalized.rsplit(marker, 1)[1]] = item
    for name in sorted(n for n in data if n.startswith("inputs/")):
        current = {"bytes": len(data[name]), "sha256": sha(data[name])}
        original = by_suffix.get(name)
        normalized = data[name]
        for change in reversed(prep.get("path_adaptations", {}).get(name, [])):
            old, new = change["old"].encode(), change["new"].encode()
            # An adaptation may be listed once per literal occurrence. Undo
            # each once rather than global replace, preserving original bytes.
            normalized = normalized.replace(new, old, 1)
            dependency = change["new"].strip('"')
            dependency_name = "inputs/" + dependency
            if dependency_name not in data or sha(data[dependency_name]) != change["dependency_sha256"]:
                raise Refusal("ROM_DEPENDENCY", dependency_name)
        restored = {"bytes": len(normalized), "sha256": sha(normalized)}
        if original == current:
            classification = "SAME_RAW_BYTES"
        elif original == restored:
            classification = "ROM_PATH_RELOCATION_ONLY_REVERSED_TO_PHYSICAL_SHA"
        elif original is None:
            classification = "SIMULATION_OR_PREPARATION_ONLY_NOT_IN_PHYSICAL_INPUT_LIST"
        else:
            classification = "DIFFERENT_REQUIRES_EXPLICIT_REVIEW_NOT_SAME_BYTE"
        mapping.append({
            "member": name, "r05": current, "physical": original,
            "relocation_restored": restored, "classification": classification,
        })
    result = {
        "status": "EXACT_R05_STATIC_INPUT_BOUND_NOT_EXECUTED",
        "zip_sha256": R05_SHA, "zip_bytes": len(raw),
        "manifest_sha256": sha(data["MANIFEST.json"]), "tb_sha256": TB_SHA,
        "members": len(data), "declared_members": len(declared),
        "compile_units": [
            {"order": i, "member": "inputs/" + name, **declared["inputs/" + name]}
            for i, name in enumerate(compile_units)
        ],
        "rom_members": {
            n: declared[n] for n in declared if n.startswith("inputs/rom/")
        },
        "same_version_mapping": mapping,
        "same_version_counts": dict(Counter(r["classification"] for r in mapping)),
        "board_release_allowed": False, "functional_simulation": "NOT_EXECUTED",
        "per_request_deadline": "UNKNOWN_NO_PUBLIC_TRACE",
        "analog_input_to_audio_latency": "UNKNOWN_NOT_MEASURED",
    }
    return data, result


def stage_exact(data, stage):
    """Only byte-for-byte inputs, new exclusive stage, no old TB modification."""
    stage = Path(stage)
    stage.mkdir(parents=True, exist_ok=False)
    for name, contents in data.items():
        if name.startswith("inputs/"):
            relative = name.removeprefix("inputs/")
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(contents)
    return {
        p.relative_to(stage).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
        for p in stage.rglob("*") if p.is_file()
    }
