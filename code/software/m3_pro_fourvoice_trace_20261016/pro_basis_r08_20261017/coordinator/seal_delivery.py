"""Metadata-only combined R06/R07/R08 original-byte sealing and publication list.

Run after all owners freeze. Existing tracked files and unrelated untracked
files are never staged here. Git mutation is handled serially by the root.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[5]
REL = "m3_pro_fourvoice_trace_20261016/"
HERE = ROOT / ("code/docs/test/" + REL + "pro_basis_r08_20261017/coordinator")
R06_PACKAGES = {"normalized_intake", "tool_plan_adapter", "event_calendar", "tx_clock_reset_checker", "board_capture_acceptance"}
R07_PACKAGES = {"public_capture_tb", "public_equivalence_tb", "oracle_bundle_bridge", "capture_provenance"}
R08_PACKAGES = {"recursive_include_audit", "public_port_map", "plan_consumption_guard", "output_reservation", "tool_dependency_identity", "build_admission_bundle", "capture_csv_codec", "async_reset_events", "frame_coverage_diff", "frame_accept_provenance", "finish_protocol_recorder", "real_authority_graph", "i2s_serial_compare", "tx_hold_sequences", "clip_lineage", "midi_ingress_arrival", "midi_recovery_schedule", "public_diff_diagnostics", "physical_photo_index", "io_voltage_budget", "measurement_profile", "latency_alignment", "board_session_capture", "recovery_manifest", "coordinator"}


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def scope(name):
    for prefix in ("code/software/", "code/tb/board/", "code/docs/test/"):
        base = prefix + REL
        if not name.startswith(base):
            continue
        parts = Path(name[len(base):]).parts
        if len(parts) < 3:
            return None
        version, package = parts[:2]
        if version == "pro_basis_r06_20261017" and package in R06_PACKAGES:
            if package in {"normalized_intake", "tool_plan_adapter", "tx_clock_reset_checker"} and parts[2] not in {"r07_fix", "r08_integration"}:
                return None
        elif version == "pro_basis_r07_20261017" and package in R07_PACKAGES:
            pass
        elif version == "pro_basis_r08_20261017" and package in R08_PACKAGES:
            pass
        else:
            return None
        return prefix, parts
    return None


def publish_directly(name, parsed):
    prefix, parts = parsed
    if prefix != "code/docs/test/":
        return True
    if parts[:3] == ("pro_basis_r08_20261017", "midi_recovery_schedule", "SPEC_ORIGINALS") and parts[-1] in {"midi_event_parser.sv", "audio_defs_pkg.sv"}:
        return True
    if "coordinator" in parts:
        return parts[-1] in {"PLAN.md", "RESULT.md", "PACKAGE_STATUS.json", "CONSUMPTION.json", "C6_INTAKE_RECEIPT.json", "M2_BASELINE_ADVANCE.json", "M2_R09_PUBLICATION_ADVANCE.json", "SELF_REVIEW.md", "M2_DECISION_REQUESTS.json"}
    if len(parts) == 3 and Path(name).suffix in {".md", ".json"}:
        return True
    if len(parts) == 4 and parts[2] in {"r07_fix", "r08_integration", "dependency_audit"} and Path(name).suffix in {".md", ".json"}:
        return True
    if any(p.startswith(("c5_", "c6_")) for p in parts[2:-1]) and not any(p in {"inputs", "sources", "source_closure"} for p in parts[2:-1]) and Path(name).suffix in {".md", ".json", ".f", ".zip"}:
        return True
    return False


def main():
    baseline_path = HERE / "PUBLICATION_BASELINE.json"
    if not baseline_path.exists():
        baseline_path = HERE / "TRACKED_BASELINE.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    changed = [p for p, v in baseline.items() if not (ROOT / p).is_file() or identity((ROOT / p).read_bytes()) != v]
    assert not changed, "TRACKED_BASELINE_CHANGED:" + str(changed)
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip(), "PRESERVE_OTHER_STAGING"
    names = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    selected, direct, unrelated = [], [], []
    for name in sorted(n for n in names if n):
        parsed = scope(name)
        if parsed is None:
            unrelated.append(name)
            continue
        parts = Path(name).parts
        if any(p in {"__pycache__", "DELIVERY", "HANDOFF_FINAL"} or p.startswith("GATE_") for p in parts) or name.endswith(".pyc"):
            continue
        selected.append(name)
        if publish_directly(name, parsed):
            direct.append(name)
    assert selected
    # Fresh checkouts need actual new static dependencies, not only their
    # archived copies. Receipts list files really read by bounded groups.
    selected_set = set(selected)
    runtime_dependencies = set()
    receipts = []
    for receipt_path in (HERE / "RUNS").glob("*/*/RECEIPT.json"):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        spec_path = receipt_path.parent / "SPEC.json"
        assert identity(spec_path.read_bytes()) == receipt["spec_identity"]
        receipt["frozen_spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
        receipts.append(receipt)
    latest_reads = {}
    for receipt in sorted(receipts, key=lambda item: item["ended_utc"]):
        for name, expected in receipt.get("read_inputs", {}).items():
            if name in selected_set:
                runtime_dependencies.add(name)
                latest_reads[name] = expected
        # Successful runs need not read their own entry after the preflight.
        # A prior failing traceback may have recorded the older entry through
        # linecache; the actual later SPEC entry identity supersedes that read.
        entry_name = Path(receipt["frozen_spec"]["argv"][4]).relative_to(ROOT).as_posix()
        if entry_name in selected_set:
            latest_reads[entry_name] = receipt["frozen_spec"]["entry"]
            runtime_dependencies.add(entry_name)
    for name, expected in latest_reads.items():
        assert identity((ROOT / name).read_bytes()) == expected, "LATEST_TESTED_DEPENDENCY_CHANGED:" + name
    direct.extend(sorted(runtime_dependencies))
    output = HERE / "DELIVERY"
    output.mkdir(exist_ok=False)
    manifest = {name: identity((ROOT / name).read_bytes()) for name in selected}
    # Whole files remain independently readable ZIP members. Part boundaries
    # bound normal Git objects; no byte-fragment reconstruction is needed.
    batches, current, total = [], [], 0
    for name in selected:
        size = manifest[name]["bytes"]
        assert size < 94 * 1024 * 1024, "SINGLE_FILE_TOO_LARGE_FOR_GIT:" + name
        if current and total + size > 40 * 1024 * 1024:
            batches.append(current)
            current, total = [], 0
        current.append(name)
        total += size
    if current:
        batches.append(current)
    archives = []
    for index, batch in enumerate(batches, 1):
        path = output / f"M3_TASK_DAY2_R08_ORIGINALS_{index:02d}.zip"
        part_manifest = {name: manifest[name] for name in batch}
        with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in batch:
                archive.write(ROOT / name, name)
            archive.writestr("MANIFEST.json", json.dumps(part_manifest, ensure_ascii=False, indent=2) + "\n")
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            assert len(archive.namelist()) == len(set(archive.namelist()))
            for name, value in part_manifest.items():
                assert identity(archive.read(name)) == value
        archives.append({"path": path.relative_to(ROOT).as_posix(), "payload_count": len(batch), **identity(path.read_bytes())})
        direct.append(path.relative_to(ROOT).as_posix())
    save(output / "ORIGINALS_INDEX.json", {"schema": "M3_TASK_DAY2_R08_ORIGINALS_V1", "archives": archives, "files": manifest, "direct_runtime_dependencies": sorted(runtime_dependencies), "unrelated_untracked_preserved": unrelated, "new_functional_runs": 0})
    save(output / "RECEIPT.json", {"status": "ALL_PARTS_CRC_SIZE_SHA_PASS", "payload_count": len(manifest), "archives": archives, "prior_tracked_changed": [], "board_release_allowed": False})
    direct += [(output / name).relative_to(ROOT).as_posix() for name in ("ORIGINALS_INDEX.json", "RECEIPT.json")]
    list_path = HERE / "PUBLICATION_FILES.json"
    direct.append(list_path.relative_to(ROOT).as_posix())
    save(list_path, {"baseline": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(), "paths": sorted(set(direct))})
    print(json.dumps({"payloads": len(manifest), "archives": archives, "publication_paths": len(set(direct))}))


if __name__ == "__main__":
    main()
