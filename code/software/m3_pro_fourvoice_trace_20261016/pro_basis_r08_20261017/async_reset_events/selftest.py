"""NOT_RUN case adapter for async reset events."""

from __future__ import annotations

import json
from pathlib import Path

from async_reset_events import ResetReject, record_edges


def _samples() -> list[dict]:
    return [
        {"time_ps": 10, "core_posedge": False, "rst_n": 0,
         "pll_locked": 0, "source_line": 1},
        {"time_ps": 20, "core_posedge": True, "rst_n": 0,
         "pll_locked": 1, "source_line": 2},
        {"time_ps": 30, "core_posedge": True, "rst_n": 1,
         "pll_locked": 1, "source_line": 3},
        {"time_ps": 35, "core_posedge": False, "rst_n": 0,
         "pll_locked": 1, "source_line": 4},
        {"time_ps": 40, "core_posedge": True, "rst_n": 1,
         "pll_locked": None, "source_line": 5},
    ]


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    samples = _samples()
    actual_samples = samples
    if case_id == "ASYNC_ASSERT_TWO_EPOCHS":
        report = record_edges(actual_samples)
        if [e["epoch"] for e in report["edges"] if e["kind"] == "ASYNC_ASSERT"] != [0, 1]:
            raise AssertionError("EPOCHS")
    elif case_id == "MISSING_RELEASE_PENDING":
        actual_samples = samples[:2]
        report = record_edges(actual_samples)
        if report["status"] != "PENDING_RELEASE":
            raise AssertionError("NOT_PENDING")
    elif case_id == "UNKNOWN_LOCK_PRESERVED":
        report = record_edges(samples)
        pending = [e for e in report["edges"]
                   if e["kind"] == "SYNC_RELEASE_PENDING_AUTHORITY"]
        functional = [e for e in report["edges"]
                      if e["kind"] == "FIRST_FUNCTIONAL_PRE_NBA"
                      and e["epoch"] == 1]
        if (report["status"] != "PENDING_LOCK_AUTHORITY"
                or pending[-1]["release_source"] != "UNKNOWN_LOCK_SOURCE"
                or functional):
            raise AssertionError("LOCK_INVENTED")
    elif case_id == "LOCK_LOW_PENDING":
        samples[-1]["pll_locked"] = 0
        report = record_edges(samples)
        functional = [e for e in report["edges"]
                      if e["kind"] == "FIRST_FUNCTIONAL_PRE_NBA"
                      and e["epoch"] == 1]
        if report["status"] != "PENDING_LOCK_AUTHORITY" or functional:
            raise AssertionError("UNLOCKED_RELEASE_ACCEPTED")
    elif case_id == "OUT_OF_ORDER_REJECT":
        samples[2]["time_ps"] = 19
        actual_samples = samples
        exception_text = None
        try:
            record_edges(actual_samples)
        except ResetReject as exc:
            if "TIME_ORDER" not in str(exc):
                raise
            exception_text = str(exc)
        else:
            raise AssertionError("ORDER_ACCEPTED")
        report = {"status": "EXPECTED_REJECT", "exception": exception_text}
    elif case_id == "UNKNOWN_POSEDGE_REJECT":
        samples[2]["core_posedge"] = "x"
        actual_samples = samples
        try:
            record_edges(actual_samples)
        except ResetReject as exc:
            if "CORE_POSEDGE_VALUE" not in str(exc):
                raise
            report = {"status": "EXPECTED_REJECT", "exception": str(exc)}
        else:
            raise AssertionError("UNKNOWN_POSEDGE_ACCEPTED")
    elif case_id == "UNKNOWN_RESET_REJECT":
        samples[2]["rst_n"] = None
        actual_samples = samples
        try:
            record_edges(actual_samples)
        except ResetReject as exc:
            if "RESET_VALUE" not in str(exc):
                raise
            report = {"status": "EXPECTED_REJECT", "exception": str(exc)}
        else:
            raise AssertionError("UNKNOWN_RESET_ACCEPTED")
    else:
        raise KeyError(case_id)
    result = {"case_id": case_id, "status": "PASS"}
    (output_dir / "input.json").write_text(json.dumps(actual_samples, indent=2) + "\n", encoding="utf-8")
    (output_dir / "component_output.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
