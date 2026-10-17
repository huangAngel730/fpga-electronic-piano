"""SHA-verified reuse of completed actual RTL steps, never mock a build.

Used only when publication runner labels change: all compiled RTL/TB and all
mathematical/reference inputs must still equal the qualified original run.
The original receipt/compile logs/image accompany the byte-identical capture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from inventory import ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--response", type=int, required=True, choices=(1, 3, 32, 64))
    parser.add_argument("--long", type=int, required=True, choices=(0, 1))
    args = parser.parse_args()
    receipt_path = args.receipt.resolve()
    receipt_path.relative_to(ROOT / "code/output")
    output = args.output.resolve()
    output.relative_to(ROOT / "code/output")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    # A later unrelated negative-test failure never turns a completed positive
    # RTL step into a failed compilation. Qualify ONLY the selected three steps,
    # preserve the original overall FAIL, and rerun all final applicable tests.
    before = receipt["candidate_sources_before"]
    if receipt.get("candidate_sources_after", before) != before:
        raise ValueError("ORIGINAL_SOURCE_DRIFT")
    frozen = receipt["frozen_inputs_before"]
    if receipt.get("frozen_inputs_after", frozen) != frozen:
        raise ValueError("ORIGINAL_FROZEN_DRIFT")
    orchestration = {"b2d_run.py", "run_m3_polyphony_scaling_acceptance.py"}
    for item in before + frozen:
        path = ROOT / item["path"]
        if path.name not in orchestration and digest(path) != item["sha256"]:
            raise ValueError("REUSED_MATH_OR_RTL_SOURCE_CHANGED:" + item["path"])
    for item in receipt["outputs"]:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise ValueError("ORIGINAL_OUTPUT_CHANGED:" + item["path"])
    selected = {s["label"]: s for s in receipt["steps"]}
    stem = f"B2D_N16_R{args.response}_long{args.long}"
    compile_step = selected[stem + "_compile"]
    simulation = selected[stem + "_simulate"]
    for step in (compile_step, simulation, selected[stem + "_replay"]):
        if step["exit_code"] or step["timed_out"] or step["elapsed_limit_exceeded"]:
            raise ValueError("SELECTED_ORIGINAL_STEP_NOT_QUALIFIED")
    original_report = json.loads((receipt_path.parent / (stem + ".json")).read_text(encoding="utf-8"))
    if original_report["status"] != "B2D_N16_EVENT_AUDIO_PASS_T061_PARTIAL":
        raise ValueError("SELECTED_ORIGINAL_REPLAY_FAILED")
    output.mkdir(exist_ok=False)
    shutil.copyfile(receipt_path, output / "original_receipt.json")
    for item in (compile_step["stdout"], compile_step["stderr"], simulation["stderr"]):
        shutil.copyfile(ROOT / item["path"], output / Path(item["path"]).name)
    shutil.copyfile(receipt_path.parent / (stem + ".vvp"), output / "actual_original.vvp")
    if args.response == 3:
        for name in ("failure.zip", "manifest.json"):
            shutil.copyfile(ROOT / "code/output/m3_t061_b2d_failure_20261010_01" / name, output / name)
            shutil.copyfile(ROOT / "code/output/m3_t061_b2d_failure_20261010_02" / name,
                            output / ("prior_workflow_" + name))
    record = dict(status="ACTUAL_RTL_CAPTURE_SHA_VERIFIED_NOT_NEW_SIMULATION", original_receipt=str(receipt_path),
                  original_receipt_sha256=digest(receipt_path), compile=compile_step, simulation=simulation,
                  original_overall_status=receipt["status"], original_overall_error=receipt.get("error"),
                  original_scope_caption_retained_not_authoritative=True,
                  excluded_source_changes="runner/orchestration only; no RTL/TB/math/reference changes")
    (output / "reuse_receipt.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    sys.stdout.buffer.write((ROOT / simulation["stdout"]["path"]).read_bytes())


if __name__ == "__main__":
    main()
