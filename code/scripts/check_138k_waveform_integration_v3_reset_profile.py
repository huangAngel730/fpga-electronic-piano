"""Post-build v3 reset-classification profile; never rewrite executed gate/receipts."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import types

import check_138k_waveform_integration_build_v3 as executed

ROOT = Path(__file__).resolve().parents[2]


def reset_profile_baseline():
    """Retain all old comparisons; extend its explicit false-path set only."""
    old = executed.baseline_gate
    original = old.visual.check
    text = inspect.getsource(original)
    anchor = '    expected_false = {"set_false_path -from [get_ports {sys_rst_n}]"}\n'
    if text.count(anchor) != 1:
        raise ValueError("parent visual gate changed; explicit review required")
    additions = json.loads((executed.prepared.SCOPE / "revision_manifest.json").read_bytes())["additional_exact_falsepaths"]
    additions = tuple(line.replace("u_visual/", "") for line in additions)
    if len(additions) != 4 or any("*" in x or "/CLEAR}" not in x for x in additions):
        raise ValueError("only four specific async CLEAR entries approved")
    text = text.replace(anchor, anchor + "    expected_false.update(APPROVED_ASYNC_RESET_INPUTS)\n", 1)
    environment = dict(original.__globals__)
    environment["APPROVED_ASYNC_RESET_INPUTS"] = additions
    environment["__name__"] = "isolated_v3_reset_profile"
    exec(compile(text, "<isolated_v3_visual_gate_exact4resetextension>", "exec"), environment)
    visual = types.SimpleNamespace(check=environment["check"],
                                   FIRST_STAGES=old.visual.FIRST_STAGES, BUSS=old.visual.BUSS)
    baseline_globals = dict(old.review.__globals__)
    baseline_globals["visual"] = visual
    review = types.FunctionType(old.review.__code__, baseline_globals)
    return types.SimpleNamespace(review=review, visual=visual, parsed=old.parsed)


def review(run):
    # Execute the same exact-input, resources, clocks, D-path, min-delay and pin
    # logic as the originally executed v3 gate, with its visual false-path set
    # now aware of the four RESET entries already declared before build.
    environment = dict(executed.review.__globals__)
    environment["baseline_gate"] = reset_profile_baseline()
    gate = types.FunctionType(executed.review.__code__, environment)
    result = gate(run)
    result["post_build_profile"] = "v3_reset_classification_1"
    result["post_build_checker_SHA256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["original_executed_checker_SHA256"] = hashlib.sha256(Path(executed.__file__).read_bytes()).hexdigest()
    result["original_assessment_retained"] = True
    result["no_new_Gowin_execution"] = True
    result["board_release_allowed"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    result = review(args.run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
