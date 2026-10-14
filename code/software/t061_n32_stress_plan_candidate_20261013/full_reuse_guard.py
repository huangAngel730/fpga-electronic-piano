"""Qualify only this known FULL checker-only failure for software recheck."""
import ast

OLD_CHECKER_SHA = "befaa7e7c0ac1e0dbe8bc0ae8368e93017526471fdf967d2375f71d3319d4262"
SOFTWARE = "code/software/t061_n32_stress_plan_candidate_20261013/"
TB = "code/tb/audio/t061_n32_allocator_candidate_20261013/C/"
ALLOWED = {SOFTWARE + name for name in ("check_full_v6.py", "full_steal_successor.py",
           "full_reuse_guard.py")} | {TB + name for name in ("c_assets.py", "c_capsule.py",
           "c_delivery.py", "test_full_closure.py", "test_full_steal_successor.py",
           "test_full_reuse_guard.py", "full_transfer.py")}


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def unchanged_normal_functions(old, new):
    def functions(raw):
        return {node.name: ast.dump(node, include_attributes=False)
                for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef)}
    a, b = functions(old), functions(new)
    require(all(a.get(name) == b.get(name) and name in a for name in ("input_identity", "check", "main")),
            "C_FULL_REUSE_NORMAL_CHECKER_CHANGED")


def qualify(plan, receipt, normal, rejected, old_sources, new_sources, tool_files):
    require(plan.get("profile") == "full-v6" and "reused_simulation" not in plan,
            "C_FULL_REUSE_FRESH_FULL_ORIGIN_REQUIRED")
    require(receipt.get("status") == "FAIL_PARTIAL" and receipt.get("exit_code") == 1
            and receipt.get("failure") == "ValueError:C_STEP_FAILED:mutations",
            "C_FULL_REUSE_KNOWN_FAILURE_ONLY")
    steps = receipt.get("steps", [])
    require([row.get("name") for row in steps] == ["compile", "simulate", "check", "mutations"],
            "C_FULL_REUSE_ORIGINAL_STEP_SET")
    require(all(row.get("exit_code") == (1 if row["name"] == "mutations" else 0)
                and row.get("timeout") is False and row.get("failure") is None for row in steps),
            "C_FULL_REUSE_COMPLETED_SIM_AND_CHECK_REQUIRED")
    require(normal.get("status") == "N32_C_STRESS_PASS_T061_PARTIAL"
            and normal.get("complete_C_capture") is True
            and normal.get("single_continuous_full_C_run") is True
            and normal.get("capture_composition") is False
            and normal.get("independent_clocked_math", {}).get("lifecycle", {}).get("retirements", 0) >= 4,
            "C_FULL_REUSE_NORMAL_FULL_PROOF_REQUIRED")
    require(rejected == {"status": "REJECT", "reason": ""}, "C_FULL_REUSE_KNOWN_STOPITERATION_ONLY")
    require(old_sources.get(SOFTWARE + "check_full_v6.py", {}).get("sha256") == OLD_CHECKER_SHA,
            "C_FULL_REUSE_KNOWN_CHECKER_PIN")
    require(receipt.get("inputs_after") == old_sources, "C_FULL_REUSE_OLD_INPUTS_AFTER")
    require(plan.get("tool_files") == tool_files == receipt.get("tools_after"),
            "C_FULL_REUSE_TOOL_IDENTITY")
    for name in set(old_sources) | set(new_sources):
        if name in ALLOWED or (name.startswith("assets/") and
                (name.startswith("assets/build_evidence/") or name == "assets/asset_build_receipt.json")):
            continue
        if name.startswith(TB) and name.endswith(".md"):
            continue
        require(name in old_sources and name in new_sources and old_sources[name] == new_sources[name],
                "C_FULL_REUSE_INPUT_DRIFT:" + name)
    return {"status": "KNOWN_CHECKER_ONLY_FAILURE_FULL_CAPTURE_QUALIFIED",
            "execution_mode": "RTL_REUSED_NO_NEW_SIMULATION",
            "original_status": receipt["status"], "original_failure": receipt["failure"],
            "changed_scope": "FULL_SOFTWARE_RECHECK_AND_EXACT_STEAL_MUTATION_ONLY"}
