"""Persist labelled synthetic counterexamples; never executes ModelSim."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import test_receipt_check as legacy_cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("r04_core_under_test", args.core)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    shutil.copyfile(args.core, args.output / "SOURCE_UNDER_TEST.txt")
    diagnostics = ["Error: synthetic diagnostic"] if args.baseline else [
        "Error: synthetic diagnostic", "Errors: 1", "** Error: diagnostic",
        "FAIL: diagnostic", "FAILED: diagnostic", "Failure: diagnostic",
    ]
    positions = ["after"] if args.baseline else ["before", "after"]
    results = []
    for tool in ("vlog", "vsim"):
        for position in positions:
            for diagnostic in diagnostics:
                fixture = legacy_cases.ReceiptCheckTests("test_valid_synthetic_receipt_is_accepted")
                fixture.setUp()
                try:
                    for path in (fixture.vlog, fixture.vsim):
                        path.write_text("# SYNTHETIC ONLY; NO TOOL RUN\n" + path.read_text(
                            encoding="utf-8"), encoding="utf-8")
                    path = getattr(fixture, tool)
                    text = path.read_text(encoding="utf-8")
                    marker = "# " + module.R04_PASS_MARKER
                    if tool == "vlog":
                        text += marker + "\n"
                    extra = "# " + diagnostic
                    replacement = (extra + "\n" + marker if position == "before"
                                   else marker + "\n" + extra)
                    path.write_text(text.replace(marker, replacement), encoding="utf-8")
                    result = module.check_receipt(
                        package_path=fixture.package, vlog_log_path=fixture.vlog,
                        vsim_log_path=fixture.vsim, run_status_path=fixture.status,
                        inputs_before_path=fixture.before, inputs_after_path=fixture.after,
                        expected_archive_sha256=fixture.archive_sha,
                        expected_manifest_sha256=fixture.manifest_sha,
                    )
                    case_dir = args.output / f"SYNTHETIC_{len(results):02}_{tool}_{position}"
                    case_dir.mkdir()
                    for original in (fixture.package, fixture.vlog, fixture.vsim,
                                     fixture.status, fixture.before, fixture.after):
                        # .txt retains original log bytes while avoiding ignored .log files.
                        name = original.name + (".txt" if original.suffix == ".log" else "")
                        shutil.copyfile(original, case_dir / name)
                    (case_dir / "result.json").write_text(
                        json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
                    results.append({"tool": tool, "position": position,
                                    "diagnostic": diagnostic, "expected_rejected": True,
                                    "actual_rejected": not result.accepted,
                                    "case": case_dir.name})
                finally:
                    fixture.tearDown()
    summary = {"evidence_kind": "SYNTHETIC", "baseline": args.baseline,
               "actual_modelsim_calls": 0, "cases": results}
    print(json.dumps(summary, indent=2))
    (args.output / "SYNTHETIC_CASES.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if all(case["actual_rejected"] for case in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
