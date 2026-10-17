"""Consume the existing R6-4 one-shot repair allocation, not an R7 allocation."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

import consumer as c

sys.path.insert(0, str(c.ROOT / "code/software/m3_r05_functional_integration_20261015"))
from supervised_process import invoke  # noqa: E402


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def verify(spec):
    items = [ref[key] for ref in spec["sources_inputs_dependencies"] for key in ("original", "snapshot")]
    items += spec["tool_runtime"]
    drift = []
    for item in items:
        try:
            if c.identity(item["path"]) != item:
                drift.append(item["path"])
        except OSError as error:
            drift.append(str(error))
    return {"checked_files": len(items), "identity_drift": drift, "pass": not drift}


def main():
    path = c.DOC / "RUN_SPEC.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec["schema"] != "M3_R6_4_R07_FIX_RUN_SPEC_V1" or spec["budget_s"] != 60:
        raise SystemExit("FIX_SPEC_REFUSED")
    run = Path(spec["run"])
    save(run / "ATTEMPT.json", {"utc": utc(), "RUN_SPEC": c.identity(path), "argv": spec["command"]})
    before = verify(spec)
    save(run / "PRECHECK.json", before)
    if not before["pass"]:
        raise SystemExit("IDENTITY_DRIFT_NO_PROCESS")
    environment = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH"):
        environment.pop(key, None)
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    start_utc, started = utc(), time.monotonic()

    def created(pid):
        save(run / "CONSUMED.json", {"pid": pid, "utc": utc(), "budget_s": 60,
                                     "original_R06_repair_groups_consumed": 1, "R7_A_groups_added": 0})

    process = invoke(spec["command"], spec["cwd"], run, "targeted", started + 55,
                     step_budget=55, log_limit=8 * 1024 * 1024, environment=environment, on_created=created)
    process.update(start_utc=start_utc, end_utc=utc())
    save(run / "PROCESS.json", process)
    after = verify(spec)
    save(run / "POSTCHECK.json", after)
    summary_path = run / "products/SUMMARY.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    elapsed = time.monotonic() - started
    passed = (elapsed <= 60 and process["exit_code"] == 0 and not process["timeout"] and
              not process["error"] and not process["log_limit_exceeded"] and after["pass"] and
              summary is not None and summary["status"] == "PASS_TARGETED_CONSUMER_REPAIR_ONLY")
    result = {"status": "PASS_TARGETED_CONSUMER_REPAIR_ONLY" if passed else "FAIL_PARTIAL_STOP_NO_RETRY",
              "group_elapsed_s": elapsed, "limit_s": 60, "within_budget": elapsed <= 60,
              "original_R06_initial_groups_already_consumed": 1,
              "original_R06_repair_groups_consumed": int(process["process_created"] is True),
              "repair_groups_remaining": 0, "R7_A_groups_added": 0, "HDL_EDA_hardware": 0,
              "process": c.identity(run / "PROCESS.json"), "summary": summary, "board_release_allowed": False}
    save(run / "RECEIPT.json", result)
    print(json.dumps(result))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
