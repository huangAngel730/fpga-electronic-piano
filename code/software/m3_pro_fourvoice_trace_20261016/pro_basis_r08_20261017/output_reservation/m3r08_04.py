"""Append-only reservation receipts. No process, device or permission grant."""
import importlib.util
import os
from pathlib import Path
import re
import sys

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]


def claim_path(root, capture_id, plan_sha):
    token = c.digest((capture_id + "\n" + plan_sha).encode("utf-8"))
    return root / "claims" / (token + ".claim.json")


def evaluate(request):
    c.need(request.get("schema") == "M3_R08_RESERVATION_REQUEST_V1", "RESERVATION_SCHEMA")
    c.need(set(request) == {"schema", "action", "root", "capture_id", "plan_sha256", "nonce", "guard", "outcome"}, "RESERVATION_FIELDS")
    c.need(request["action"] in ("RESERVE", "FINALIZE"), "RESERVATION_ACTION")
    capture, plan, nonce = request["capture_id"], request["plan_sha256"], request["nonce"]
    c.need(type(capture) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", capture), "CAPTURE_ID")
    c.need(type(plan) is str and re.fullmatch(r"[0-9a-f]{64}", plan), "PLAN_IDENTITY")
    c.need(type(nonce) is str and re.fullmatch(r"[0-9a-f]{32,64}", nonce), "NONCE")
    root = Path(request["root"])
    c.no_alias(root)
    root = root.resolve()
    c.need(root.is_relative_to(c.DOC / "output_reservation") or
           root.is_relative_to(c.DOC / "coordinator"), "RESERVATION_SCOPE")
    guard = request["guard"]
    c.need(type(guard) is dict and set(guard) == {"validated_plan_sha256", "permission"} and
           guard["validated_plan_sha256"] == plan and guard["permission"] == "NOT_GRANTED", "GUARD_BINDING")
    root.mkdir(parents=True, exist_ok=True)
    claims = root / "claims"
    c.no_alias(claims)
    c.need(claims.resolve().is_relative_to(root), "CLAIM_PATH_ESCAPE")
    claims.mkdir(exist_ok=True)
    claim = claim_path(root, capture, plan)
    terminal = claim.with_suffix(".terminal.json")
    output = root / "outputs" / capture
    for path in (claim, terminal, output):
        c.no_alias(path)
        c.need(path.resolve().is_relative_to(root), "CLAIM_PATH_ESCAPE")
    base = {"schema": "M3_R08_OUTPUT_CLAIM_V1", "capture_id": capture, "plan_sha256": plan,
            "nonce": nonce, "root": str(root), "output": str(output), "execution_allowed": False}
    if request["action"] == "RESERVE":
        c.need(request["outcome"] is None, "EARLY_OUTCOME")
        try:
            fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise c.CheckError("ALREADY_CLAIMED_OR_CONSUMED") from error
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(c.canonical({**base, "state": "CLAIMED"}) + "\n")
        try:
            output.parent.mkdir(exist_ok=True)
            c.no_alias(output)
            output.mkdir(exist_ok=False)
        except (FileExistsError, c.CheckError) as error:
            c.write_json(terminal, {**base, "state": "FAILED_CONSUMED", "reason": "OUTPUT_EXISTS_OR_ALIAS"})
            raise c.CheckError("OUTPUT_EXISTS_OR_ALIAS") from error
        return c.result("M3_R08_OUTPUT_RESERVATION_V1", claim=c.identity(claim), state="RESERVED",
                        output=str(output), execution_allowed=False)
    c.need(request["outcome"] in ("SUCCESS", "FAILURE"), "FINAL_OUTCOME_REQUIRED")
    c.need(claim.is_file(), "CLAIM_MISSING")
    c.no_alias(claim)
    stored = c.parse(claim.read_bytes())
    c.need(stored == {**base, "state": "CLAIMED"}, "CLAIM_IDENTITY_MISMATCH")
    final = {**base, "state": "SUCCEEDED_CONSUMED" if request["outcome"] == "SUCCESS" else "FAILED_CONSUMED"}
    try:
        c.write_json(terminal, final)
    except FileExistsError as error:
        raise c.CheckError("ALREADY_FINALIZED_CONSUMED") from error
    return c.result("M3_R08_OUTPUT_RESERVATION_V1", state=final["state"], claim=c.identity(claim),
                    terminal=c.identity(terminal), execution_allowed=False)


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
