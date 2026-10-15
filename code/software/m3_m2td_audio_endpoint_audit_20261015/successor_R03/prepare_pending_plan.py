"""Prepare precise, non-executable B follow-up plan and byte-only relocation proposal."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOC = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03"
OLD_PREFIX = "C:/Users/Angel17/.codex/worktrees/m2-138k-migration/fpga_gowin/code/output/m2_m1td_whole_prepare_20261015_06/"
PROPOSED_PREFIX = (REPO / "code/output/m3_m2td_endpoint_probe_20261015_PROPOSED_NOT_CREATED").as_posix() + "/"


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    output = DOC / "pending_plan_r02"
    output.mkdir(exist_ok=False)
    audit_blob = (DOC / "input_audit_verify_r02/AUDIT.json").read_bytes()
    audit = json.loads(audit_blob)
    old_targets_blob = (DOC.parent / "targets.json").read_bytes()
    old_targets = json.loads(old_targets_blob)
    if not (audit["matched_count"] == 84 and audit["missing"] == [] and audit["unchanged"]):
        raise ValueError("complete frozen identity required even for proposal")
    relocation = []
    for record in audit["matched"]:
        path = DOC / "input_audit_r01/derived_original_bytes" / record["path"]
        raw = path.read_bytes()
        changed = raw.replace(OLD_PREFIX.encode(), PROPOSED_PREFIX.encode())
        if raw != changed:
            relocation.append({"path": record["path"], "before_sha256": sha(raw), "proposed_after_sha256": sha(changed),
                               "literal_prefix_replacements": raw.count(OLD_PREFIX.encode()),
                               "exact_inverse_matches": changed.replace(PROPOSED_PREFIX.encode(), OLD_PREFIX.encode()) == raw,
                               "classification": "UNAPPROVED_BYTE_CHANGE_PROPOSAL_ONLY_NOT_WRITTEN_OR_EXECUTED"})
    plan = {
        "schema": "M3_M2TD_SUCCESSOR_R03_PENDING_PLAN_V1", "status": "BLOCKED_INPUT",
        "user_one_round_authorized": True, "execution_prerequisites_met": False,
        "physical_allowance_consumed": False, "physical_tool_starts": 0,
        "frozen_original_input_count": 84, "frozen_audit_sha256": sha(audit_blob),
        "reused_target_list_sha256": sha(old_targets_blob), "reused_old_software_tests": "32+13; NOT_RERUN",
        "targets": [{"id": t["id"], "from_node": t["from_node"], "to_node": t["to_node"],
                     "clock": t["clock"], "required_analyses": ["Setup", "Hold"], "slack_min_ns": "0.000"}
                    for t in old_targets["targets"]],
        "source_register_pair": old_targets["requested_register_pair"],
        "proposed_stage_prefix": PROPOSED_PREFIX, "proposed_stage_created": False,
        "required_new_physical_marker": "EXCLUSIVE_CREATE_ONLY_AFTER_ALL_PREREQUISITES_VERIFIED",
        "physical_budget_seconds_max": 1800, "failure_policy": "STOP_ON_FIRST_PHYSICAL_FAILURE_NO_RETRY",
        "unresolved": [
            "Frozen source absolute ROM/include paths refer to absent original-machine C:/ prefix.",
            "Historical .vg/database absent, so base_s1/base_s2 pair UNKNOWN; this absence alone does not prevent a permitted same-source new build.",
            "Exact get_regs/get_pins query collection semantics and active returned names not executed/verified.",
            "Launcher SHA matches signed original; loaded dependency identity/runtime version has not been observed."],
        "next_responsibility": {
            "M2": "Provide same-run database if available; otherwise decide controlled reversible literal relocation and verify same-source rebuild/object fallback.",
            "implementation": "Only after identity/query prerequisites hold, use fresh stage/marker and bounded one round; never reuse old artifacts."},
        "relocation": {"from_prefix": OLD_PREFIX, "to_prefix": PROPOSED_PREFIX, "files": relocation,
                       "all_inverse_matches": all(x["exact_inverse_matches"] for x in relocation),
                       "applied": False},
        "board_release_allowed": False, "new_sta_executed": False}
    (output / "PENDING_PLAN.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    proposal = (DOC.parent / "STA_PROPOSAL_NOT_EXECUTABLE.tcl.txt").read_bytes()
    (output / "DIRECTED_REPORTS_PROPOSAL_ONLY.sdc.txt").write_bytes(proposal)
    print(json.dumps({"status": "BLOCKED_INPUT", "reused_pairs": len(plan["targets"]),
                      "proposed_literal_only_changed_files": len(relocation), "inverse_all_match": plan["relocation"]["all_inverse_matches"],
                      "physical_tool_starts": 0, "marker_consumed": False}))


if __name__ == "__main__":
    main()
