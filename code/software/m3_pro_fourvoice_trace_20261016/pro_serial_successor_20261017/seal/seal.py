"""Static B2 seal: existing artifacts only; no functional/tool suite launches."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import zipfile

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[3]
DOCS = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016" / HERE.name
OUT = DOCS / "SEAL_01"


def identity(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def verify(item):
    actual = identity(item["path"])
    assert actual["bytes"] == item["bytes"], ("SIZE_DRIFT", item)
    assert actual["sha256"] == item["sha256"], ("SHA_DRIFT", item)


def main():
    OUT.mkdir(exist_ok=False)
    launch = {"argv": sys.argv, "cwd": str(Path.cwd()),
              "machine": platform.node(), "python": identity(sys.executable),
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "functional_rounds_consumed": 0,
              "operation": "EXISTING_ARTIFACT_IDENTITY_AND_ZIP_INTEGRITY_ONLY"}
    save(OUT / "LAUNCH.json", launch)
    preflight = load(DOCS / "PREFLIGHT/PREFLIGHT.json")
    for item in preflight["inputs"]:
        verify(item)
    rounds = [load(DOCS / f"ROUND_{n:02}/RUN_RECEIPT.json") for n in (1, 2)]
    cases = []
    for run in rounds:
        assert run["exit_code"] == run["child_exit_code"] == 0
        assert run["source_before"] == run["source_after"]
        assert run["runtime_after_same"] and not run["timeout"]
        for key in ("stdout", "stderr"):
            verify(run[key])
        for item in run["source_before"]:
            original = Path(item["path"])
            snapshot = DOCS / f"ROUND_{run['round']:02}" / "sources" / original.relative_to(ROOT)
            copy = identity(snapshot)
            assert (copy["bytes"], copy["sha256"]) == (item["bytes"], item["sha256"])
        for path in sorted((DOCS / f"ROUND_{run['round']:02}/cases").glob("*/CASE_RECEIPT.json")):
            case = load(path)
            assert case["passed"]
            for item in case["inputs"].values():
                verify(item)
            for key in ("binding", "result", "stdout", "stderr"):
                verify(case[key])
            cases.append({"round": run["round"], "case": case["case"],
                          "exit_code": case["exit_code"],
                          "diagnostic": case["actual_diagnostic"],
                          "receipt": identity(path)})
    assert len(cases) == 22
    for item in rounds[-1]["source_after"]:
        verify(item)
    assert len(list(HERE.glob("*.py"))) == 5
    upstream = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017"
    links = [identity(upstream / name) for name in (
        "OBSERVATION_CONTRACT.json", "OBSERVATION_CONTRACT.md", "FINAL_ENTRY.json",
        "RECEIPT.json", "RESULT.md", "intake_20261017/MISSING_ITEMS.json")]
    assert links[0]["sha256"] == "d89076836f8c60dd6544bbf2d9a5e8fa2f645ef49c8860458210562adf12d716"
    final = load(upstream / "FINAL_ENTRY.json")
    for key in ("receipt", "result", "archive", "manifest"):
        verify(final[key])
    save(DOCS / "SOURCE_LINK.json", {
        "mode": "READ_ONLY_ORIGINAL_LOCATION_AND_SHA_NO_OLD_BODY_REPACK",
        "baseline_head": preflight.get("head", "414e1a9d3ee0617c5e8ba72dd4b22c36122c9926"),
        "upstream": links, "B1_final_artifacts": final,
        "preflight_inputs": preflight["inputs"],
        "readonly_dependencies": [i for i in rounds[-1]["source_after"]
                                  if not Path(i["path"]).is_relative_to(HERE)],
        "real_B1_B2_admission": "PENDING", "board_release_allowed": False})
    save(DOCS / "NIGHT_RUN_RECEIPT.json", {
        "schema": "M3_B2_TASK_DAY_RECEIPT_V1",
        "status": "DONE_LIMITED_ADAPTER_PREPARATION__PENDING_PRO_SOURCE_OR_TRACE",
        "level": "L1_NEW_ADAPTER_SELFTEST_ONLY", "rounds_consumed": 2,
        "rounds_maximum": 6, "seconds": sum(r["seconds"] for r in rounds),
        "round_receipts": [identity(DOCS / f"ROUND_{n:02}/RUN_RECEIPT.json") for n in (1, 2)],
        "cases": cases, "final_source": rounds[-1]["source_after"],
        "runtime_enumeration": {"count": len(preflight["runtime"]),
                                "preflight": identity(DOCS / "PREFLIGHT/PREFLIGHT.json"),
                                "dynamic_load_closure_independently_verified": False},
        "coverage_note": "R1_19_OLD_VERSION_PLUS_R2_3_TARGETED_ONLY_NOT_FINAL_22_FULL_RERUN",
        "first_static_gap": "UNEXPECTED_CANCEL_DID_NOT_CLEAR_ACTIVE_KEY_FIXED_IN_R2",
        "unexpected_functional_process_failures": 0,
        "old_suites_eda_native_hardware_executed": 0,
        "formal_auditor_system_enabled": False,
        "self_review": "OWN_READONLY_AGENT_FINAL_INCREMENT_NO_CONCRETE_BLOCKER_NO_EXECUTION",
        "pro_dut_pass": False, "PCM_algorithm_pass": False,
        "physical_48k_PT8211_pass": False, "board_release_allowed": False,
        "real_finish_END_MONITOR_END_validated": False,
        "source_admission_owner": "B1", "publication_owner": "night_task1",
        "committed": False, "pushed": False,
        "final_return": "NO_SEND_TOOL_COORDINATOR_READONLY_PICKUP",
        "result": identity(DOCS / "RESULT.md")})
    candidates = sorted(p for folder in (HERE, DOCS) for p in folder.rglob("*") if p.is_file())
    included, excluded = [], []
    for path in candidates:
        if "__pycache__" in path.parts or path.is_relative_to(OUT):
            continue
        relative = path.relative_to(ROOT).as_posix()
        # Preserve old dependency snapshots locally, but obey the final instruction
        # to reference old sources rather than placing their bodies in this ZIP.
        if "sources" in path.parts:
            index = path.parts.index("sources")
            original = ROOT.joinpath(*path.parts[index + 1:])
            if not original.is_relative_to(HERE):
                excluded.append({"snapshot": identity(path), "original": str(original),
                                 "reason": "OLD_DEPENDENCY_BODY_REFERENCE_ONLY"})
                continue
        included.append((path, relative))
    save(DOCS / "FILE_LIST.json", {
        "included_existing_new_files": [identity(p) for p, _ in included],
        "excluded_old_snapshots_preserved_locally": excluded,
        "new_static_seal_metadata": ["FILE_LIST.json", "SEAL_01/LAUNCH.json",
                                     "SEAL_01/MANIFEST.json", "SEAL_01/VERIFICATION.json",
                                     "LATEST_RECEIPT.json"],
        "all_old_cases_and_archives": "READ_ONLY_ORIGINAL_LOCATIONS_NOT_REPACKED"})
    included += [(DOCS / "FILE_LIST.json", (DOCS / "FILE_LIST.json").relative_to(ROOT).as_posix()),
                 (OUT / "LAUNCH.json", (OUT / "LAUNCH.json").relative_to(ROOT).as_posix())]
    manifest = [{"member": member, **identity(path)} for path, member in included]
    save(OUT / "MANIFEST.json", {"payloads": manifest, "old_bodies_included": False})
    archive = OUT / "M3_B2_PUBLIC_CSV_SERIAL_ADAPTER_PREPARATION_20261017.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for path, member in included:
            z.write(path, member)
        z.write(OUT / "MANIFEST.json", "MANIFEST.json")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(manifest) + 1 == len(set(z.namelist()))
        for item in manifest:
            data = z.read(item["member"])
            assert len(data) == item["bytes"]
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
        assert z.read("MANIFEST.json") == (OUT / "MANIFEST.json").read_bytes()
    verification = {"exit_code": 0, "CRC_and_member_SHA_pass": True,
                    "payload_count": len(manifest), "zip_members": len(manifest) + 1,
                    "archive": identity(archive), "manifest": identity(OUT / "MANIFEST.json"),
                    "ended_utc": datetime.now(timezone.utc).isoformat(),
                    "functional_rounds_consumed": 0, "launch": identity(OUT / "LAUNCH.json")}
    save(OUT / "VERIFICATION.json", verification)
    save(DOCS / "LATEST_RECEIPT.json", {
        "status": "DONE_LIMITED_ADAPTER_PREPARATION__PENDING_PRO_SOURCE_OR_TRACE",
        "archive": identity(archive), "verification": identity(OUT / "VERIFICATION.json"),
        "receipt": identity(DOCS / "NIGHT_RUN_RECEIPT.json"),
        "result": identity(DOCS / "RESULT.md"),
        "file_list": identity(DOCS / "FILE_LIST.json"),
        "source_link": identity(DOCS / "SOURCE_LINK.json"),
        "publication_owner": "night_task1", "committed": False, "pushed": False,
        "board_release_allowed": False})
    print(json.dumps(verification, ensure_ascii=False))


if __name__ == "__main__":
    main()
