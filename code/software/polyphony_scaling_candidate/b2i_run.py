"""Software-only actual hybrid ledger, no fresh RTL or EDA execution."""
import json
import sys

from inventory import ROOT


def run_b2i(run, args):
    candidate = ROOT / "code/software/polyphony_scaling_candidate"
    run.command("actual_hybrid_budget", [sys.executable, "-B", "-X", "utf8",
                str(candidate / "b2i_audit.py"), "--output", str(run.output / "actual_budget")])
    run.command("actual_hybrid_budget_tests", [sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover",
                "-s", str(candidate), "-p", "test_b2i.py", "-v"])
    audit = json.loads((run.output / "actual_budget/audit.json").read_text(encoding="utf-8"))
    return dict(status=audit["status"], configurations=len(audit["configurations"]),
                historical_reports=len(audit["historical_reports"]), new_RTL_simulation=False,
                new_synthesis=False, new_PnR=False, task_complete=False,
                validation="L0 source audit / L1 software tests only")
