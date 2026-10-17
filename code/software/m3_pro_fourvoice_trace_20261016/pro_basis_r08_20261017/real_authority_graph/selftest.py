"""NOT_RUN case adapter for authority graph."""

from __future__ import annotations

import json
from pathlib import Path

from real_authority_graph import DEPENDENCIES, ROLES, AuthorityReject, check_graph


def _graph(origin: str = "SYNTHETIC") -> dict:
    return {"requested_mode": "SYNTHETIC", "capture_id": "cap",
            "nodes": {role: {"sha256": str(index + 1) * 64,
                             "source_id": "source-closure-1",
                             "capture_id": "cap", "origin": origin,
                             "trusted_receipt": False,
                             "depends_on": DEPENDENCIES[role]}
                      for index, role in enumerate(ROLES)}}


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    value = _graph()
    if case_id == "SYNTHETIC_STAYS_SYNTHETIC":
        report = check_graph(value)
        if report["status"] != "SYNTHETIC_ONLY" or report["real_certified"]:
            raise AssertionError(report)
    elif case_id == "REAL_WITHOUT_TRUST_PENDING":
        value = _graph("REAL_CANDIDATE")
        value["requested_mode"] = "REAL"
        report = check_graph(value)
        if report["status"] != "PENDING_TRUSTED_REAL_RECEIPTS":
            raise AssertionError(report)
    else:
        if case_id == "MODE_STRING_SPOOF_REJECT":
            value["requested_mode"] = "REAL"
            expected = "REAL_MIXED"
        elif case_id == "SAME_CAPTURE_DIFFERENT_SOURCE_REJECT":
            value["nodes"]["oracle"]["source_id"] = "other-source"
            expected = "SOURCE_ID_MISMATCH"
        elif case_id == "DEPENDENCY_REFERENCE_REJECT":
            value["nodes"]["frame"]["depends_on"] = ["capture"]
            expected = "DEPENDENCY_REFERENCE"
        else:
            raise KeyError(case_id)
        try:
            check_graph(value)
        except AuthorityReject as exc:
            if expected not in str(exc):
                raise
        else:
            raise AssertionError("BAD_AUTHORITY_ACCEPTED")
        report = {"status": "EXPECTED_REJECT", "reason": expected}
    (output_dir / "input.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"case_id": case_id, "status": "PASS"}
