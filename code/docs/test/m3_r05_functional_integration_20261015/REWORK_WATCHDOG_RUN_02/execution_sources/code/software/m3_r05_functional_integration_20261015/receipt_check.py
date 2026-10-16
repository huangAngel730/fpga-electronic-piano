"""Exact R05 log/exit policy; SYNTHETIC is never a real functional receipt."""
import re

from common import PASS_MARKER, Refusal

BAD = re.compile(
    r"\b(?:fatal|failure|failed|fail)\b|\*\*\s*error\b|\berror\s*:"
    r"|\berrors\s*:\s*0*[1-9][0-9]*\b|\b(?:timeout|timed\s+out)\b"
    r"|\bassertion\s+(?:failed|failure)\b",
    re.IGNORECASE,
)
EXACT_PASS = re.compile(r"^(?:#\s*)?" + re.escape(PASS_MARKER) + r"\s*$", re.MULTILINE)
SUMMARY = re.compile(
    r"^(?:#\s*)?END REAL_M1 accepted=([0-9]+) active=([0-9]+) "
    r"commits=([0-9]+) nonzero=([0-9]+) frames=([0-9]+) "
    r"serial=([0-9]+) max_cycles=([0-9]+)\s*$", re.MULTILINE,
)


def check_step(name, stdout, stderr, exit_code, timeout, *, synthetic=False):
    if type(exit_code) is not int or exit_code != 0:
        raise Refusal("NONZERO_OR_INVALID_EXIT", name)
    if type(timeout) is not bool or timeout:
        raise Refusal("TIMEOUT_OR_INVALID_FLAG", name)
    try:
        text = (stdout + b"\n" + stderr).decode("utf-8", errors="strict")
    except UnicodeError:
        raise Refusal("LOG_ENCODING", name)
    if BAD.search(text):
        raise Refusal("TOOL_DIAGNOSTIC", name)
    if not synthetic and re.search(r"\bSYNTHETIC\b", text, re.I):
        raise Refusal("SYNTHETIC_RECEIPT", name)
    result = {"step": name, "status": "STEP_LOG_POLICY_PASS"}
    if name == "vsim":
        # PASS/END must each come from a single original stdout stream. Do
        # not concatenate fragments or borrow a marker from another step.
        primary = stdout.decode("utf-8", errors="strict")
        passes = EXACT_PASS.findall(primary)
        summaries = SUMMARY.findall(primary)
        if len(passes) != 1:
            raise Refusal("EXACT_PASS_MISSING_OR_DUPLICATE", name)
        if len(summaries) != 1:
            # X/Z in any numeric field fail this full exact match too.
            raise Refusal("SUMMARY_MISSING_OR_X", name)
        values = list(map(int, summaries[0]))
        accepted, active, commits, nonzero, frames, serial, cycles = values
        if not (accepted >= 6 and active == 4 and commits >= 20 and nonzero >= 20
                and frames > 2 and serial >= 5 and 0 < cycles < 834):
            raise Refusal("R05_SUMMARY_PREDICATE", str(values))
        result["dut_self_reported_summary"] = dict(zip(
            ("accepted", "active", "commits", "nonzero", "frames", "serial", "max_cycles"), values,
        ))
        result["per_request_deadline"] = "UNKNOWN_NO_PUBLIC_TRACE"
        result["serial_pcm_decode"] = "UNKNOWN_RAW_PINS_NOT_RECORDED"
    result["evidence_kind"] = "SYNTHETIC_SOFTWARE_TEST" if synthetic else "TOOL_LOG_POLICY_ONLY"
    result["board_release_allowed"] = False
    return result
