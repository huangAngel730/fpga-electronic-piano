"""Read-only Gowin score resource screen; never a BSRAM/STA release proof.

The XML digest must be independently supplied by the caller. A small resource
summary does not prove that the score body, rather than another RAM, is BSRAM.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET

LIMIT_BYTES = 2 * 1024 * 1024
COUNT = re.compile(r"(0|[1-9][0-9]*)(?:\((0|[1-9][0-9]*)\))?")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def count(node, field, required=False):
    value = node.get(field)
    if value is None:
        if required:
            raise ValueError("MISSING_RESOURCE:" + field)
        return 0
    match = COUNT.fullmatch(value)
    if not match or (match[2] and int(match[2]) > int(match[1])):
        raise ValueError("INVALID_RESOURCE:" + field)
    return int(match[1])


def assess(raw, expected_sha256, module, max_registers=8192, max_luts=8192):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("INVALID_EXPECTED_SHA256")
    if digest(raw) != expected_sha256:
        raise ValueError("REPORT_SHA256_MISMATCH")
    if not raw or len(raw) > LIMIT_BYTES or b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("INVALID_XML_SIZE_OR_DECLARATION")
    if not module or any(type(v) is not int or v <= 0 for v in (max_registers, max_luts)):
        raise ValueError("INVALID_POLICY_OR_MODULE")
    root = ET.fromstring(raw)
    if root.tag != "Module":
        raise ValueError("INVALID_GOWIN_ROOT")
    nodes = [n for n in root.iter() if n.get("name") == module]
    if len(nodes) != 1 or nodes[0].tag not in ("Module", "SubModule"):
        raise ValueError("MISSING_OR_DUPLICATE_MODULE")
    node = nodes[0]
    resources = {name: count(node, field, name in ("registers", "luts"))
                 for name, field in (("registers", "T_Register"), ("luts", "T_Lut"),
                                     ("bsram", "T_Bsram"), ("ssram", "T_Ssram"))}
    for name, field in (("registers", "T_Register"), ("luts", "T_Lut"),
                        ("bsram", "T_Bsram"), ("ssram", "T_Ssram")):
        if resources[name] > count(root, field, name in ("registers", "luts")):
            raise ValueError("RESOURCE_EXCEEDS_ROOT:" + name)
    multipliers = {k: count(node, k) for k in node.attrib
                   if k.startswith("T_MULT") or k.startswith("T_DSP")}
    errors = []
    if resources["bsram"] == 0:
        errors.append("NO_SCORE_BSRAM_IN_HIERARCHY")
    if resources["registers"] > max_registers:
        errors.append("SCORE_REGISTER_BUDGET")
    if resources["luts"] > max_luts:
        errors.append("SCORE_LUT_BUDGET")
    if any(multipliers.values()):
        errors.append("UNEXPECTED_SCORE_DSP")
    return {"status": "RESOURCE_SCREEN_PASS" if not errors else "RESOURCE_SCREEN_REJECT",
            "resource_screen_passed": not errors, "errors": errors,
            "report_sha256": digest(raw), "module": module, "resources": resources,
            "multiplier_primitives": multipliers,
            "policy": {"max_registers": max_registers, "max_luts": max_luts,
                       "origin": "M2 preliminary integration budget; not device capacity"},
            "score_body_bsram_proven": False, "ready_for_full_pnr": False,
            "STA_passed": False, "board_release_allowed": False,
            "still_required": ["Exact body-RAM primitive/address/port mapping evidence",
                               "Candidate source and actual synthesis provenance",
                               "Qualified fulltop positive and behavior negatives",
                               "Fresh complete PnR/STA/pin/CDC/reset/resource gate"]}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--expected-sha256", required=True)
    cli.add_argument("--module", required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--max-registers", type=int, default=8192)
    cli.add_argument("--max-luts", type=int, default=8192)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.exists():
        cli.error("REFUSE_OVERWRITE")
    try:
        raw = args.report.read_bytes()
        result = assess(raw, args.expected_sha256, args.module,
                        args.max_registers, args.max_luts)
        if args.report.read_bytes() != raw:
            raise ValueError("REPORT_CHANGED_DURING_REVIEW")
        code = 0 if result["resource_screen_passed"] else 1
    except (OSError, ValueError, ET.ParseError) as error:
        result = {"status": "INVALID_EVIDENCE", "error": str(error),
                  "resource_screen_passed": False, "ready_for_full_pnr": False,
                  "board_release_allowed": False}
        code = 2
    result.update(exit_code=code, command=sys.argv,
                  checker_sha256=digest(Path(__file__).read_bytes()))
    output.mkdir(parents=True, exist_ok=False)
    (output / "receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)
                                        + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
