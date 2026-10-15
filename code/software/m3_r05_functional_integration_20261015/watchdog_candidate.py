"""One exact user-authorized TB copy; original ZIP remains immutable."""
from common import TB_DIR, TB_SHA, DOCS, HERE, Refusal, sha, identity, json_load

MEMBER = "inputs/tb_m2_m1td_real_chain.sv"
OLD = b"#6000000;$fatal"
NEW = b"#7000000;$fatal"
CANDIDATE = TB_DIR / "tb_r05_watchdog_7ms.sv"
USER_SCOPE = HERE / "USER_REWORK_SCOPE_20261016.md"
SECOND_MARKER = DOCS / "R05_WATCHDOG_USER_REPAIR_ATTEMPT_CONSUMED.json"


def overlay(data):
    original = data[MEMBER]
    candidate = CANDIDATE.read_bytes()
    if sha(original) != TB_SHA or original.count(OLD) != 1:
        raise Refusal("FROZEN_TB_IDENTITY", "unexpected original")
    if candidate != original.replace(OLD, NEW, 1):
        raise Refusal("CANDIDATE_DIFF", "only one watchdog literal may differ")
    copied = dict(data)
    copied[MEMBER] = candidate
    return copied, {"kind": "USER_AUTHORIZED_WATCHDOG_ONLY_OVERLAY",
                    "original_tb_sha256": TB_SHA,
                    "candidate": identity(CANDIDATE),
                    "user_scope": identity(USER_SCOPE),
                    "changed_member": MEMBER, "old_watchdog_ns": 6000000,
                    "new_watchdog_ns": 7000000,
                    "reverse_restores_original": candidate.replace(NEW, OLD, 1) == original}


def prerequisite():
    if SECOND_MARKER.exists():
        raise Refusal("ATTEMPT_ALREADY_CONSUMED", str(SECOND_MARKER))
    marker = DOCS / "R05_FUNCTIONAL_ATTEMPT_CONSUMED.json"
    first = DOCS / "REWORK_AUTHORIZED_RUN_01/RUN_RECEIPT.json"
    prior = json_load(first.read_bytes())
    consumed = json_load(marker.read_bytes())
    if (prior.get("functional_attempt_consumed") is not True
            or prior.get("functional_tool_count") != 3
            or prior.get("status") != "FAILED_STOP_NO_RETRY"
            or consumed.get("output") != str(first.parent.resolve())):
        raise Refusal("FIRST_ROUND_IDENTITY", "exact consumed first failure required")
    call = prior["functional_calls"][-1]
    raw = __import__("pathlib").Path(call["stdout"]["path"]).read_bytes()
    if sha(raw) != call["stdout"]["sha256"] or b"Fatal: M1TD_REAL_CHAIN_TIMEOUT" not in raw:
        raise Refusal("FIRST_FAILURE_IDENTITY", "original fatal missing/changed")
    return {"first_round": identity(first), "first_consumption": identity(marker)}
