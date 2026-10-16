"""Seal final failed resume batch and verify all immutable inputs/snapshots."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
SOFT = HERE.parent
sys.path.insert(0, str(SOFT.parent.parent))
from common import ROOT, DOCS, TB_DIR, R05, identity, write_new

BASE = DOCS / "night_20261016/RESUME_R01"
SEAL = BASE / "SEAL_RESUME_FAILURE"


def main():
    audit = []
    for run in ("RUN_02", "RUN_03", "RUN_04"):
        p = BASE / run / "RUN_RECEIPT.json"
        r = json.loads(p.read_text(encoding="utf-8"))
        assert r["functional_attempt_consumed"] is True
        assert r["source_before"] == r["source_after"]
        assert r["tool_before"] == r["tool_after"]
        assert r["source_snapshot_layout"] == "FLAT_RELATIVE_SHA_MAP_V1"
        assert set(r["source_snapshot_files"]) == set(r["source_before"])
        for key, original in r["source_before"].items():
            copied = identity(r["source_snapshot_files"][key]["path"])
            assert copied == r["source_snapshot_files"][key]
            assert copied["sha256"] == original["sha256"] and copied["bytes"] == original["bytes"]
        for relative, original in r["stage_before"].items():
            now = identity(Path(r["stage"]) / relative)
            assert now["sha256"] == original["sha256"] and now["bytes"] == original["bytes"]
        for call in r["version_calls"] + r["functional_calls"]:
            for stream in ("stdout", "stderr"):
                assert identity(call[stream]["path"]) == call[stream]
        audit.append({"run": run, "receipt": identity(p), "executed_snapshots_verified": len(r["source_before"]),
            "staged_inputs_verified": len(r["stage_before"]), "raw_streams_verified": 2*(len(r["version_calls"])+len(r["functional_calls"])),
            "total_elapsed_s": r["elapsed_s"], "functional_calls": [{"tool": Path(c["argv"][0]).name,"exit_code":c["exit_code"],"elapsed_s":c["elapsed_s"]} for c in r["functional_calls"]]})
    write_new(BASE / "FINAL_AUDIT.json", {"status": "IMMUTABLE_FAILED_ORIGINALS_VERIFIED", "runs": audit,
        "no_successful_business_capture": True, "functional_groups": 3, "remaining": 0})
    SEAL.mkdir(exist_ok=False)
    paths = [R05]
    for folder in (SOFT, TB_DIR / "night_20261016/RESUME_R01", ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016/RESUME_R01", BASE):
        for path in folder.rglob("*"):
            if not path.is_file() or SEAL in path.parents or "__pycache__" in path.parts:
                continue
            # Keep exact HDL/ROM input/source bodies and logs, omit rebuildable
            # compiled simulator databases, wave files, and incidental transcripts.
            if "work" in path.parts or path.suffix in (".wlf", ".qdb", ".mdb") or path.name == "transcript":
                continue
            paths.append(path)
    paths = sorted(set(paths))
    members = {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}
    write_new(SEAL / "MANIFEST.json", {"schema":"M3_A_RESUME_FAILURE_MANIFEST_V1","members":members})
    target = SEAL / "M3_NIGHT_A_RESUME_R01_FAILED_ORIGINALS.zip"
    with zipfile.ZipFile(target,"x",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths:
            z.write(p,p.relative_to(ROOT).as_posix())
        z.write(SEAL / "MANIFEST.json","MANIFEST.json")
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,item in members.items():
            raw=z.read(name)
            assert len(raw)==item["bytes"] and hashlib.sha256(raw).hexdigest()==item["sha256"]
    write_new(SEAL / "SEAL_RECEIPT.json", {"package":identity(target),"manifest":identity(SEAL/"MANIFEST.json"),"members_verified":len(members),
        "real_rtl_status":"FAILED_ALL_THREE_FUNCTIONAL_GROUPS","successful_capture":False,"board_release_allowed":False})
    print(json.dumps({"package":identity(target),"members_verified":len(members)},ensure_ascii=False))


if __name__ == "__main__":
    main()
