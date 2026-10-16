"""Seal the authorized four behavioral negatives with historical originals."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
TB = ROOT / "code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/tb_slider_audio_coexist.sv"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    with p.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    run_path = HERE / "RUN_01/NIGHT_RUN_RECEIPT.json"
    run = json.loads(run_path.read_text())
    facts = json.loads((HERE / "TRACE_FACTS.json").read_text())
    prior_delivery = json.loads((HERE.parent / "DELIVERY.json").read_text())
    prior_zip = HERE.parent / "D_AUDIO_VISUAL_COEXIST_PARTIAL_20261016.zip"
    assert sha(prior_zip) == prior_delivery["sha256"]
    assert run["passed"] and run["identity_unchanged"] and len(run["results"]) == 4
    assert facts["passed"] and not run["positive_group_rerun"]
    assert len(list(HERE.glob("RUN_*/CONSUMED.json"))) == 1
    # Verify bytes independently without re-running any tool/checker.
    for label in ("iverilog_version", "vvp_version", "compile") + tuple(f"negative_{i}_{suffix}" for i in (1, 2, 3, 4) for suffix in ("simulate", "check")):
        receipt = json.loads((HERE / "RUN_01" / (label + ".receipt.json")).read_text())
        for stream in ("stdout", "stderr"):
            assert sha(HERE / "RUN_01" / (label + "." + stream)) == receipt[stream + "_sha256"]
    before = json.loads((HERE / "RUN_01/before.json").read_text())
    assert before == json.loads((HERE / "RUN_01/after.json").read_text())
    current = {str(p): sha(p) for p in (TB, HERE / "run_negatives.py", HERE / "check_coexist.py")}
    assert all(before["inputs"][p]["sha256"] == digest for p, digest in current.items())
    manifest_sha = sha(HERE.parent / "MANIFEST.json")
    assert manifest_sha == "3cedcbf46977a0750374e26ce44c57174b0cf74e63b1568df366ab14f5b2c02e"
    receipt = {
        "status": "COMPLETE_AUTHORIZED_FOUR_RTL_NEGATIVES", "scope_complete": True,
        "formal_d_hardware_or_whole_system_complete": False,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "utc": datetime.now(timezone.utc).isoformat(), "new_batch": "RESUME_R01",
        "groups_consumed": 1, "group_limit": 3, "batch_closed_on_first_pass": True,
        "old_allowance_restored": False, "per_tool_seconds": 300, "per_group_seconds": 300,
        "simulation_budget_seconds": 900, "actual_simulation_seconds": run["simulation_seconds"],
        "actual_group_seconds": run["elapsed_seconds"], "calls": run["calls"],
        "compile_starts": 1, "behavioral_simulations": 4, "positive_reruns": 0,
        "level": run["level"], "run_receipt_sha256": sha(run_path),
        "negative_results": run["results"], "trace_facts": facts,
        "tool_and_source_before_after": "IDENTICAL", "tools": before["tools"],
        "source_sha256": current,
        "prior_positive_archive": {"path": str(prior_zip), "sha256": sha(prior_zip),
                                   "historical_status": "PARTIAL_PRESERVED_UNCHANGED"},
        "prior_manifest_static_sha256": manifest_sha,
        "prior_manifest_scope": "STATIC_CHECK_NOT_IN_RUN_BEFORE_AFTER",
        "self_review": "OWN_READ_ONLY_AGENT_AND_IMPLEMENTER_NO_CONCRETE_BLOCKER_IN_SCOPE",
        "board_release_allowed": False, "r05_algorithm": "NOT_RUN",
        "formal_top": "NOT_TESTED", "gowin": "NOT_RUN", "modelsim": "NOT_RUN",
        "hardware": "NOT_RUN", "hit_flash": "KNOWN_FAIL_DEFERRED_NOT_TESTED",
        "git_write_commands": 0, "submitted": False, "pushed": False,
        "handoff_target": "01a14050-cd98-7c41-8004-5d3e25765167",
        "communication_authority": "USER_MESSAGE_READ_FROM_TARGET_THREAD_01a14237-c04d-7d41-ae9d-cd8493ff0dd9",
        "handoff_state_at_seal": "PENDING_ONE_FINAL_MESSAGE",
    }
    write(HERE / "NIGHT_RUN_RECEIPT.json", receipt)
    paths = sorted(p for p in HERE.rglob("*") if p.is_file()) + [TB, prior_zip]
    manifest = {p.relative_to(ROOT).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in paths}
    write(HERE / "MANIFEST.json", {"kind": "FOUR_NEGATIVE_SCOPE_COMPLETE_WITH_PRIOR_ORIGINALS", "files": manifest})
    archive = HERE / "D_FOUR_RTL_NEGATIVES_COMPLETE_RESUME_R01_20261016.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in paths + [HERE / "MANIFEST.json"]:
            z.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(paths)+1
        for name, entry in manifest.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == entry["sha256"]
    delivery = {"status": receipt["status"], "archive": str(archive),
                "bytes": archive.stat().st_size, "sha256": sha(archive), "member_files": len(paths)+1,
                "crc_and_member_sha": "PASS", "submitted": False, "pushed": False,
                "board_release_allowed": False}
    write(HERE / "DELIVERY.json", delivery)
    print(json.dumps(delivery))


if __name__ == "__main__":
    main()
