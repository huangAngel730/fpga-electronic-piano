"""Exact frozen delivery binding. No import-time I/O except path constants.

The spec descriptor must be pinned by the independently frozen caller. It is
an identity contract, never a substitute for execution permission or Git proof.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[8]
MAX_JSON = 8 * 1024 * 1024


class Reject(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Reject(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def safe_path(path):
    path = Path(path)
    need(not str(path).startswith(("\\\\", "\\??\\")), "ALIAS_OR_DEVICE")
    for part in path.parts:
        need(part.rstrip(" .") == part and not re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part), "ALIAS_OR_DEVICE")
    for item in (path, *path.parents):
        need(not item.is_symlink() and not item.is_junction(), "ALIAS_OR_DEVICE")
    return path.resolve()


def relative(value):
    need(type(value) is str and value and "\\" not in value and ":" not in value, "RELATIVE_PATH")
    item = PurePosixPath(value)
    need(not item.is_absolute() and item.as_posix() == value and value != "." and
         not any(part in ("..", ".git", ".aws", ".codex") for part in item.parts), "RELATIVE_PATH")
    return value


def identity(path):
    sha, size = hashlib.sha256(), 0
    with safe_path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            sha.update(block)
    return {"bytes": size, "sha256": sha.hexdigest()}


def checked(ref, root=ROOT):
    need(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "DESCRIPTOR")
    need(type(ref["bytes"]) is int and ref["bytes"] >= 0 and type(ref["sha256"]) is str and
         re.fullmatch("[0-9a-f]{64}", ref["sha256"]), "DESCRIPTOR_IDENTITY")
    root = safe_path(root)
    path = safe_path(root / relative(ref["path"]))
    need(path.is_relative_to(root) and path.is_file(), "DESCRIPTOR_SCOPE")
    need(identity(path) == {key: ref[key] for key in ("bytes", "sha256")}, "FILE_CHANGED:" + ref["path"])
    return path


def _pairs(items):
    value = {}
    for key, entry in items:
        need(key not in value, "DUPLICATE_JSON_KEY")
        value[key] = entry
    return value


def read(path):
    with safe_path(path).open("rb") as stream:
        raw = stream.read(MAX_JSON + 1)
    need(len(raw) <= MAX_JSON, "JSON_BOUND")
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Reject("NONFINITE_JSON")))


def pointer(value, path):
    need(type(path) is str and path.startswith("/"), "JSON_POINTER")
    for key in path[1:].split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            need(key.isdecimal() and int(key) < len(value), "POINTER_MISSING:" + path)
            value = value[int(key)]
        else:
            need(type(value) is dict and key in value, "POINTER_MISSING:" + path)
            value = value[key]
    return value


def verify(spec_ref, snapshot_root=ROOT):
    """Reconstruct identities from bytes, not approval/status strings or sample IDs."""
    spec_path = checked(spec_ref)
    spec = read(spec_path)
    need(spec["schema"] == "M3_R11_FROZEN_DELIVERY_SPEC_V1" and
         spec["direction"] in ("RECEIVE", "SEND"), "SPEC_SCHEMA")
    handoff_path = checked(spec["handoff"])
    handoff = read(handoff_path)
    need(handoff.get("schema") == "NIGHT_HANDOFF_V1", "HANDOFF_SCHEMA")
    keys = ("handoff_id", "task_id", "plan_version", "producer", "consumer", "base_commit", "result_commit")
    need(set(spec["expected_identity"]) == set(keys), "EXPECTED_IDENTITY_FIELDS")
    need({key: handoff.get(key) for key in keys} == spec["expected_identity"], "HANDOFF_IDENTITY_MISMATCH")
    for key in ("base_commit", "result_commit"):
        need(type(handoff[key]) is str and re.fullmatch("[0-9a-f]{40}", handoff[key]), "FULL_COMMIT_REQUIRED")
    need(handoff["producer"] in ("M1", "M2", "M3") and handoff["consumer"] in ("M1", "M2", "M3"), "ACTOR")
    need(type(handoff["manifest"]) is list and handoff["manifest"] and
         canonical(handoff["manifest"]) == canonical(spec["expected_manifest"]), "HANDOFF_MANIFEST_MISMATCH")
    names = [relative(item["path"]) for item in handoff["manifest"]]
    need(len(set(name.casefold() for name in names)) == len(names), "MANIFEST_DUPLICATE")
    for entry in handoff["manifest"]:
        checked(entry, snapshot_root)
    contract = read(checked(spec["run_contract"]))
    need(canonical(contract["inputs"]) == canonical(spec["frozen_inputs"]), "FROZEN_INPUT_SET_MISMATCH")
    need(canonical(contract["source_frozen"]) == canonical(spec["frozen_sources"]), "FROZEN_SOURCE_SET_MISMATCH")
    for ref in [*spec["frozen_inputs"], *spec["frozen_sources"]]:
        checked(ref, snapshot_root)
    if spec["direction"] == "RECEIVE":
        need(spec["handoff"] in spec["frozen_inputs"], "HANDOFF_NOT_FROZEN_INPUT")
    need(bool(spec["result_relations"]), "RESULT_BINDING_REQUIRED")
    for binding in spec["result_relations"]:
        result = read(checked(binding["file"]))
        for relation in binding["equalities"]:
            need(canonical(pointer(result, relation["pointer"])) == canonical(relation["equals"]),
                 "RESULT_RELATION_MISMATCH:" + relation["pointer"])
        if "manifest_check" in binding:
            rule = binding["manifest_check"]
            rows = pointer(result, rule["pointer"])
            observed = [{"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}
                        for row in rows if row[rule["filter_key"]] == rule["filter_value"]]
            commits = [row["commit"] for row in rows if row[rule["filter_key"]] == rule["filter_value"]]
            need(canonical(observed) == canonical(handoff["manifest"]) and
                 commits and all(commit == handoff["result_commit"] for commit in commits), "RESULT_MANIFEST_IDENTITY_MISMATCH")
    commit_binding = spec["commit_binding"]
    need(pointer(read(checked(commit_binding["file"])), commit_binding["pointer"]) == handoff["result_commit"],
         "RESULT_COMMIT_MISMATCH")
    need(spec["direction"] != "RECEIVE" or any("manifest_check" in entry for entry in spec["result_relations"]),
         "INPUT_RESULT_MANIFEST_BINDING_REQUIRED")
    # A historical SPEC only froze sources; it did NOT record the raw contract
    # SHA. Never manufacture that missing edge with a new historical sidecar.
    historical = spec["purpose"] == "HISTORICAL_BINDING_EXAMPLE"
    result_refs = [entry["file"] for entry in spec["result_relations"]]
    required = [spec["run_contract"], *result_refs]
    if not historical:
        need(spec["purpose"] in ("NEW_UNPUBLISHED_DELIVERY", "NEW_RECEIVED_DELIVERY"), "SPEC_PURPOSE")
        provenance = read(checked(spec["execution_provenance"]))
        need(provenance["schema"] == "M3_R11_RESULT_PROVENANCE_V1", "RESULT_PROVENANCE_SCHEMA")
        # Execution evidence precedes publication. Putting the future Git SHA
        # inside its own archived payload would create an impossible hash cycle.
        delivery_identity = {key: spec["expected_identity"][key] for key in keys if key != "result_commit"}
        need(provenance["run_contract"] == spec["run_contract"] and
             provenance["delivery_identity"] == delivery_identity and
             provenance["frozen_inputs"] == spec["frozen_inputs"] and
             provenance["frozen_sources"] == spec["frozen_sources"], "RESULT_CONTRACT_BINDING_MISMATCH")
        input_ref = provenance["input_handoff"]
        need(input_ref in spec["frozen_inputs"], "RESULT_HANDOFF_NOT_FROZEN")
        checked(input_ref, snapshot_root)
        need(spec["direction"] != "RECEIVE" or input_ref == spec["handoff"], "RESULT_HANDOFF_BINDING_MISMATCH")
        need(type(provenance["result_refs"]) is list and provenance["result_refs"], "ACTUAL_RESULTS_REQUIRED")
        for ref in provenance["result_refs"]:
            checked(ref)
        need(all(ref in provenance["result_refs"] for ref in result_refs),
             "RESULT_PROVENANCE_INCOMPLETE")
        # The separately pinned publication commit proof is not falsely archived
        # as pre-publication run output; admission checks actual Git blob bytes.
        required += [spec["execution_provenance"], input_ref, *provenance["result_refs"]]
    if spec["direction"] == "SEND":
        archived = [entry["file"] for entry in spec["archive_bindings"]]
        need(all(ref in archived for ref in required), "OUTPUT_RESULTS_ARCHIVE_BINDING_REQUIRED")
    for binding in spec["archive_bindings"]:
        need(binding["archive"] in handoff["manifest"], "RESULT_ARCHIVE_NOT_IN_HANDOFF")
        archive = checked(binding["archive"], snapshot_root)
        original = checked(binding["file"])
        with zipfile.ZipFile(archive) as z:
            entries = [entry for entry in z.infolist() if entry.filename == relative(binding["member"])]
            need(len(entries) == 1 and entries[0].file_size <= MAX_JSON, "ARCHIVE_MEMBER_IDENTITY")
            raw = z.read(entries[0])
        need({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} == identity(original), "ARCHIVE_RESULT_SPLICE")
    # Recheck the raw spec/HANDOFF after all dependent reads, before any state advance.
    checked(spec_ref)
    checked(spec["handoff"])
    return {"schema": "M3_R11_VERIFIED_DELIVERY_BINDING_V1", "spec": spec_ref,
            "handoff": handoff, "handoff_ref": spec["handoff"], "direction": spec["direction"],
            "key": hashlib.sha256(canonical([handoff["handoff_id"], handoff["result_commit"], handoff["consumer"]])).hexdigest(),
            "spec_body": spec, "identity_bound_only": True, "remote_verified": False,
            "historical_evidence_only": historical,
            "direct_result_contract_binding": "MISSING" if historical else "DECLARED_AND_BYTES_BOUND",
            "queue_allowed": not historical, "execution_allowed": False}
