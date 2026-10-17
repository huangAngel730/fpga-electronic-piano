"""One new, bounded software group for the R06 M2 capture contract."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017"
FILES = ("CAPTURE_CONTRACT.json", "FRAME_PLAN_RULES.json", "ROUTING_PLAN.json", "NORMALIZED_ROW_SCHEMA.json", "SOURCE_BINDINGS.json")
TASK_ROOT = Path("D:/17/project_17/fpga_gowin/code/output/m2_public_contract_r06_20261017")
LEDGER = TASK_ROOT / "CONSUMPTION_M2_R6_1.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    # This one-shot execution is bound to the actual task root on this host.
    # Changing --output, checkout or date does not create another permission.
    assert output.is_relative_to(TASK_ROOT)
    marker = LEDGER
    archive = DOC.parent / "same_version_binding_20261017/M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip"
    inputs = {str(path): sha(path) for path in [HERE / "validate_capture_contract.py", Path(__file__), *[DOC / name for name in FILES], archive, Path(sys.executable)]}
    try:
        with marker.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"package": "M2-R6-1", "group": "INITIAL_SOFTWARE_ONCE", "bound_seconds": 90, "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "inputs": inputs}, stream, indent=2)
    except FileExistsError:
        print(json.dumps({"status": "BLOCKED_ALREADY_CONSUMED", "ledger": str(marker)}))
        return 2
    output.mkdir(exist_ok=False, parents=True)
    start = time.monotonic()
    cases = [
        ("positive_source_bound", None, None, None),
        ("reject_post_nba", "CAPTURE_CONTRACT.json", "sampling_phase", "POST_NBA"),
        ("reject_accept_as_budget_origin", "CAPTURE_CONTRACT.json", "deadline.budget_origin", "accept_cycle"),
        ("reject_shifted_frame_phase", "FRAME_PLAN_RULES.json", "first_edge_indices", [833, 1666, 2499, 3333, 4166, 4999]),
        ("reject_missing_existing_port_route", "ROUTING_PLAN.json", "existing16", []),
        ("reject_real_claim_from_schema", "CAPTURE_CONTRACT.json", "pro_dut_pass", True),
        ("reject_swapped_clip_channels", "CAPTURE_CONTRACT.json", "fields.clip", {"bit0": "clip_right", "bit1": "clip_left"}),
        ("reject_made_up_config_width", "CAPTURE_CONTRACT.json", "fields.config", 62),
    ]
    expected = [None, "SAMPLING_PHASE", "FRAME_BUDGET_ORIGIN", "FRAME_FORMULA_PHASE", "ROUTES_EXISTING16", "UNSUPPORTED_IMPLEMENTATION_OR_REAL_CLAIM", "CLIP_CHANNEL_PACKING", "SOURCE_FIELD_METADATA_config_payload"]
    results = []
    try:
        for index, (name, filename, key, value) in enumerate(cases):
            case = output / name
            case.mkdir()
            for item in FILES:
                shutil.copyfile(DOC / item, case / item)
            if filename:
                data = json.loads((case / filename).read_text(encoding="utf-8"))
                if key == "fields.clip":
                    next(field for field in data["fields"] if field["name"] == "result_clip_mask")["normalized_packing"] = value
                elif key == "fields.config":
                    next(field for field in data["fields"] if field["name"] == "config_payload")["width"] = value
                elif "." in key:
                    parent, child = key.split(".")
                    data[parent][child] = value
                else:
                    data[key] = value
                write(case / filename, data)
            argv = [sys.executable, "-X", "utf8", str(HERE / "validate_capture_contract.py"), str(case)]
            remaining = 90 - (time.monotonic() - start)
            assert remaining > 0, "GROUP_BUDGET_EXHAUSTED"
            before = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with (case / "stdout.raw").open("xb") as stdout, (case / "stderr.raw").open("xb") as stderr:
                process = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=remaining)
            stdout = (case / "stdout.raw").read_bytes()
            parsed = json.loads(stdout)
            passed = process.returncode == (0 if index == 0 else 1)
            passed = passed and (parsed["status"] == "SOURCE_BOUND_CONTRACT_CANDIDATE_VALID" if index == 0 else parsed.get("first_failure") == expected[index])
            item = {"case": name, "argv": argv, "cwd": str(ROOT), "start_utc": before, "end_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "exit_code": process.returncode, "expected_first_failure": expected[index], "passed": passed, "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": sha(case / "stderr.raw")}
            write(case / "RECEIPT.json", item)
            results.append(item)
            assert passed, name
        stable = all(sha(Path(name)) == value for name, value in inputs.items())
        assert stable and time.monotonic() - start <= 90
        receipt = {"status": "PASS", "level": "L1_NEW_SOFTWARE_CONTRACT_ONLY", "group": "M2-R6-1_INITIAL_ONCE", "bound_seconds": 90, "elapsed_seconds": time.monotonic() - start, "cases": results, "positive": 1, "negative": 7, "inputs_stable": stable, "inputs": inputs, "old_tests_rerun": 0, "HDL_EDA_hardware_runs": 0, "external_review_delivered": False, "pro_dut_pass": False, "board_release_allowed": False}
        write(output / "RECEIPT.json", receipt)
        print(json.dumps({key: receipt[key] for key in ("status", "level", "elapsed_seconds", "positive", "negative", "inputs_stable")}))
        return 0
    except (AssertionError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        write(output / "RECEIPT.json", {"status": "FAIL", "error": str(error), "elapsed_seconds": time.monotonic() - start, "completed_cases": results})
        print(json.dumps({"status": "FAIL", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
