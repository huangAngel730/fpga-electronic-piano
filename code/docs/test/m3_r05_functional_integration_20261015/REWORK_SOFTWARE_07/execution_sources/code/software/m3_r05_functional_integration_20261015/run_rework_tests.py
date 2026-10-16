"""Bounded A-only Python tests; immutable raw streams and execution sources."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time

from common import HERE, DOCS, ROOT, identity, snapshot_sources, write_new
from supervised_process import invoke


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    if output.parent != DOCS.resolve():
        raise ValueError("owned direct child required")
    output.mkdir(exist_ok=False)
    start = time.monotonic()
    before = snapshot_sources()
    sources = output / "execution_sources"
    for relative, item in before.items():
        dest = sources / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item["path"], dest)
    environment = dict(os.environ)
    environment["A_REWORK_TEST_OUTPUT"] = str(output)
    calls = []
    for name in ("test_rework", "test_software"):
        result = invoke([sys.executable, "-B", "-X", "utf8", "-m", "unittest", "-v", name],
                        HERE, output, name, start + 300, step_budget=90,
                        environment=environment)
        calls.append(result)
        if result["exit_code"] != 0 or result["timeout"] or result["error"]:
            break
    after = snapshot_sources()
    passed = (len(calls) == 2 and all(c["exit_code"] == 0 and not c["timeout"]
                                    and not c["error"] for c in calls)
              and before == after)
    elapsed = time.monotonic() - start
    passed = passed and elapsed < 300
    receipt = {"status": "SOFTWARE_PASS" if passed else "FAILED",
               "evidence_kind": "PYTHON_SYNTHETIC_ONLY", "calls": calls,
               "python": identity(sys.executable), "source_before": before,
               "source_after": after, "elapsed_s": elapsed,
               "ModelSim_calls": 0, "exit_code": 0 if passed else 1}
    write_new(output / "RUN_RECEIPT.json", receipt)
    print(receipt["status"])
    return receipt["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
