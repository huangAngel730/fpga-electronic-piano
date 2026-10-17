"""Local package entry to the coordinator-only, frozen new seam cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
COMMON_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py")
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
CASE_PATH = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/c9_completion_r01/selftest.py"
CASE_SHA = "c89a12d7386d7bc3972d0db84c0022cb2e2123efbf54113be983d5fdd6b87859"
ALLOWED = ["C9_INTAKE_UNIQUE_CALENDAR_SEAM","C9_INTAKE_UNPROVEN_SEQ_REJECT"]


def run_case(case_id, output_dir):
    if case_id not in ALLOWED:
        raise ValueError("WRONG_PACKAGE_CASE")
    raw = COMMON_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
        raise ValueError("COMMON_SOURCE_CHANGED")
    common = ModuleType("_d4_b_package_common")
    common.__file__ = str(COMMON_PATH)
    exec(compile(raw, str(COMMON_PATH), "exec"), common.__dict__)
    module = common.load_source(CASE_PATH, CASE_SHA)
    return module.run_case(case_id, output_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=ALLOWED)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run_case(args.case, args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
