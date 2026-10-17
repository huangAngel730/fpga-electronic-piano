"""New D/D2 positive and actual rejected fixture derivatives, never Pro DUT."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from fixture import build_plan, emit
from preflight import identity


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = build_plan()
    plan_path = args.output / "INPUT_PLAN.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    cases = [("positive", None, 0, None),
             ("left_right_swap", "left_right_swap", 1, "SERIAL_SAMPLE"),
             ("shift_one_bit", "shift_one_bit", 1, "LSBJ_PADDING_NONZERO"),
             ("ws_boundary", "ws_boundary", 1, "WS_SLOT_COUNT"),
             ("sign_extension", "sign_extension", 1, "SERIAL_SAMPLE"),
             ("missing_frame", "missing_frame", 1, "FRAME_CALENDAR"),
             ("miss_deadline", "miss_deadline", 1, "REQUEST_DEADLINE_MISSED"),
             ("old_epoch", "old_epoch", 1, "OLD_EPOCH_PCM"),
             ("pa_wrong_active_polarity", "pa_wrong_active_polarity", 1, "PA_EN_ACTIVE_HIGH"),
             ("pa_early", "pa_early", 1, "PA_EN_BEFORE_STABLE"),
             ("pa_reset", "pa_reset", 1, "PA_EN_DURING_RESET"),
             ("reset_not_silent", "reset_not_silent", 1, "RESET_NOT_SILENT"),
             ("x_pin", "x_pin", 1, "UNKNOWN_OR_NONINTEGER")]
    results = []
    for name, fault, expected_exit, expected_code in cases:
        folder = args.output / name
        folder.mkdir()
        capture = folder / "FIXTURE_CAPTURE.jsonl"
        emit(capture, plan, fault)
        (folder / "EXPECTED.json").write_text(json.dumps({"exit": expected_exit, "first_difference": expected_code,
           "fault": fault, "scope": "ISOLATED_PYTHON_FIXTURE_NOT_PRO_DUT"}) + "\n", encoding="utf-8")
        argv = [sys.executable, "-X", "utf8", str(Path(__file__).parent / "check_fixture.py"),
                "--capture", str(capture), "--plan", str(plan_path), "--output", str(folder / "RESULT.json")]
        started = time.monotonic()
        with (folder / "stdout.txt").open("xb") as out, (folder / "stderr.txt").open("xb") as err:
            call = subprocess.run(argv, stdout=out, stderr=err, timeout=90, check=False)
        result_path = folder / "RESULT.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
        actual = result.get("first_difference", {}).get("code")
        passed = call.returncode == expected_exit and actual == expected_code
        data = {"name": name, "argv": argv, "cwd": str(Path.cwd()), "seconds": time.monotonic() - started,
                "exit_code": call.returncode, "expected_exit": expected_exit, "expected_code": expected_code,
                "actual_code": actual, "first_difference": result.get("first_difference"), "passed": passed,
                "input_plan": identity(plan_path), "capture": identity(capture),
                "stdout": identity(folder / "stdout.txt"), "stderr": identity(folder / "stderr.txt")}
        (folder / "CASE_RECEIPT.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        results.append(data)
        if not passed:
            break
    (args.output / "RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(results), "passed": sum(r["passed"] for r in results),
                      "first_failure": next((r for r in results if not r["passed"]), None),
                      "Pro_DUT": "UNKNOWN_NOT_TESTED"}))
    return int(len(results) != len(cases) or not all(r["passed"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
