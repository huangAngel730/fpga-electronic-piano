"""Consume exactly one frozen new software group with bounded descendant Job."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

from prepare import DOC, ROOT, identity, save

sys.path.insert(0, str(ROOT / "code/software/m3_r05_functional_integration_20261015"))
from supervised_process import invoke  # noqa: E402


def utc():
    return datetime.now(timezone.utc).isoformat()


def verify(spec):
    issues = []
    items = [ref[key] for ref in spec["sources_inputs_dependencies"] for key in ("original", "snapshot")]
    items += spec["tool_runtime"]
    for item in items:
        try:
            if identity(Path(item["path"])) != item:
                issues.append(item["path"])
        except OSError as error:
            issues.append(str(error))
    return {"checked_files": len(items), "identity_drift": issues, "pass": not issues}


def main():
    spec_path = DOC / "RUN_SPEC.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec["schema"] != "M3_R7A_RUN_SPEC_V1" or spec["budget_s"] != 90:
        raise SystemExit("RUN_SPEC_REFUSED")
    run = Path(spec["run"])
    # Claim blocks reruns even after an interrupted/failed launch.
    save(run / "ATTEMPT.json", {"start_utc": utc(), "RUN_SPEC": identity(spec_path), "argv": spec["command"]})
    pre = verify(spec)
    save(run / "PRECHECK.json", pre)
    if not pre["pass"]:
        raise SystemExit("IDENTITY_DRIFT_NO_PROCESS_LAUNCHED")
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    started_utc, started = utc(), time.monotonic()

    def created(pid):
        save(run / "CONSUMED.json", {"pid": pid, "utc": utc(), "group": "INITIAL_UNIQUE_NEW_SOFTWARE",
                                     "budget_s": 90, "HDL_rounds": 0})

    process = invoke(spec["command"], spec["cwd"], run, "selftest", started + 85,
                     step_budget=85, log_limit=8 * 1024 * 1024,
                     environment=environment, on_created=created)
    process.update(start_utc=started_utc, end_utc=utc())
    save(run / "PROCESS.json", process)
    post = verify(spec)
    save(run / "POSTCHECK.json", post)
    summary_path = run / "products/SUMMARY.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    group_elapsed = time.monotonic() - started
    passed = (group_elapsed <= spec["budget_s"] and
              process["exit_code"] == 0 and not process["timeout"] and not process["error"] and
              not process["log_limit_exceeded"] and post["pass"] and summary is not None and
              summary["status"] == "PASS_SYNTHETIC_SOFTWARE_ONLY")
    result = {"status": "PASS_SYNTHETIC_SOFTWARE_ONLY" if passed else "FAIL_OR_BLOCKED",
              "group_elapsed_s": group_elapsed, "budget_s": 90,
              "within_total_budget": group_elapsed <= spec["budget_s"],
              "initial_groups_consumed": int(process["process_created"] is True),
              "increment_groups_consumed": 0, "HDL_rounds": 0, "old_R06_groups": 0,
              "process": identity(run / "PROCESS.json"), "summary": summary,
              "board_release_allowed": False}
    save(run / "RECEIPT.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
