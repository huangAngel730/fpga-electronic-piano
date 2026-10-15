"""Build a hash-bound LOCKED proposal; never executes compile/run/check."""
import argparse
import json
import os
from pathlib import Path
import sys

from bounded_runner import MAXIMA, environment_sha, identity, sha, write_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TB = ROOT / "code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"


def propose(prepared, destination, target, allowance):
    old = json.loads((prepared / "proposal.json").read_text(encoding="utf-8"))
    if old["input"]["sha256"] != "fd220e83da98c03f0181c0a45e4edfa2ddc77adda055911508e7f7469131d4d0":
        raise ValueError("FROZEN_CONTROLS")
    files = {}
    copies = {}
    for name in ("controls.hex", "M1_INPUT_CONFIRMATION.md"):
        src = (prepared / name).resolve()
        files[str(src)] = identity(src)
        copies[str(src)] = name
    for name, spec in old["frozen_sources"].items():
        src = (prepared / "readonly" / name).resolve()
        current = identity(src)
        if current != {k: spec[k] for k in ("bytes", "sha256")}:
            raise ValueError("FROZEN_SOURCE:" + name)
        files[str(src)] = current
        copies[str(src)] = "readonly/" + name
    for src in TB.glob("*.sv"):
        src = src.resolve()
        files[str(src)] = identity(src)
        copies[str(src)] = src.name
    for src in HERE.glob("*.py"):
        files[str(src)] = identity(src)
    for tool in old["tools"]["files"]:
        src = Path(tool["path"])
        current = identity(src)
        if current != {k: tool[k] for k in ("bytes", "sha256")}:
            raise ValueError("TOOL_DRIFT:" + str(src))
        files[str(src.resolve())] = current
    python = Path(sys.executable).resolve()
    files[str(python)] = identity(python)
    commands = {"compile": old["compile_argv"], "run": old["run_argv"],
                "check": [str(python), "-B", "-X", "utf8", str(HERE / "check_capture.py"),
                          "--capture", str(target), "--report", str(target / "capture_review.json")]}
    proposal = {"schema": "T052_LONG_ONE_SHOT_M2_V1", "approved": False,
                "approval_id": "PENDING_M2_EXACT_COMBINATION",
                "decision_reference": "V0357 permits FORMAT ONLY, NOT EXECUTION",
                "machine": os.environ.get("COMPUTERNAME", "UNKNOWN"),
                "environment_sha256": environment_sha(),
                "format": "T052_LONG_PUBLIC_HEX_V1", "output": str(target),
                "allowance_directory": str(allowance), "limits": MAXIMA,
                "identities": files, "copies": copies, "commands": commands,
                "tool_versions": old["tool_versions"],
                "dynamic_loaded_dependencies": "UNKNOWN",
                "supervisor_source_sha256": sha(HERE / "bounded_runner.py"),
                "file_limit_semantics": "50ms polling + Job kill; overshoot possible; NOT NTFS quota",
                "new_RTL_compiles": 0, "new_RTL_runs": 0}
    write_json(destination, proposal)
    return proposal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--allowance", type=Path, required=True)
    args = parser.parse_args()
    result = propose(args.prepared.resolve(), args.proposal.resolve(),
                     args.target.resolve(), args.allowance.resolve())
    print(json.dumps({"status": "LOCKED_PROPOSAL_ONLY", "approved": result["approved"],
                      "identity_files": len(result["identities"]),
                      "proposal": identity(args.proposal)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
