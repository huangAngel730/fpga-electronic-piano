"""Seal the B0 review repair, without altering the original B0 evidence.

Raw logs and each member's SHA are retained. --verify is read-only/in-memory.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
import zipfile

from seal_b0 import verify


ROOT = Path(__file__).resolve().parents[4]
DOCS = Path(__file__).resolve().parent
SOFTWARE = ROOT / "code/software/polyphony_scaling_candidate"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def deadline_probe(package):
    """A real exit0 child plus a controlled elapsed-clock overrun must FAIL."""
    path = ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py"
    spec = importlib.util.spec_from_file_location("repair_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    run = module.Run(package)
    with patch.object(module.time, "monotonic", side_effect=[run.start, run.start, run.start + 901]):
        try:
            run.command("deadline_counterexample", [sys.executable, "-B", "-c", "print('exit0 child')"])
        except RuntimeError as error:
            if not str(error).startswith("ELAPSED_LIMIT_EXCEEDED:"):
                raise
        else:
            raise ValueError("DEADLINE_FALSE_PASS")
    step = run.steps[0]
    if not (step["exit_code"] == 0 and step["elapsed_limit_exceeded"] is True
            and step["elapsed_seconds"] == 901 and step["timeout_seconds"] == 900):
        raise ValueError("DEADLINE_PROBE_NOT_DESIGNATED")
    return {"status": "EXIT0_OVERRUN_DESIGNATED_REJECT", "step": step,
            "clock_scope": "Injected elapsed clock only; real child exits0, no 901-second wait"}


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path)
    parser.add_argument("--prior-run", type=Path, required=False)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    package = args.package.resolve()
    if args.verify:
        print(json.dumps(verify(package)))
        return
    package.relative_to(DOCS)
    run = args.run.resolve()
    run.relative_to(ROOT / "code/output")
    if args.prior_run:
        args.prior_run = args.prior_run.resolve()
        args.prior_run.relative_to(ROOT / "code/output")
    receipt = load_json(run / "receipt.json")
    if (receipt["status"] != "B0_REPAIR_SCOPE_PASS_T061_PARTIAL"
            or receipt["exit_code"] != 0 or receipt.get("repo_gates_passed") is not True
            or receipt["elapsed_seconds"] > 1800):
        raise ValueError("NO_QUALIFIED_REPAIR_RECEIPT")
    for step in receipt["steps"]:
        if (step["exit_code"] != step["expected_exit"] or step["timed_out"]
                or step["elapsed_seconds"] > step["timeout_seconds"]):
            raise ValueError("UNQUALIFIED_COMMAND:" + step["label"])
    for key in ("candidate_sources_after", "frozen_inputs_after", "old_seal_and_shared_after", "outputs"):
        for item in receipt[key]:
            raw = (ROOT / item["path"]).read_bytes()
            if len(raw) != item["bytes"] or sha(raw) != item["sha256"]:
                raise ValueError("RECEIPT_BOUND_FILE_CHANGED:" + item["path"])
    old_seal = verify(DOCS / "B0_20261009")
    if old_seal["zip_sha256"] != "3c7d63eddfed73423faf6cd39c9504af75eb73a846b2698566fa6b64bda0bc6e":
        raise ValueError("OLD_B0_CARRIER_CHANGED")
    old_budget = load_json(ROOT / "code/output/m3_t061_b0_20261009_03/budget/budget.json")
    new_budget = load_json(run / "budget/budget.json")
    if old_budget != new_budget:
        raise ValueError("BUDGET_CHANGED")
    package.mkdir(parents=True, exist_ok=False)
    timing = deadline_probe(package)
    prior = None
    if args.prior_run:
        first = load_json(args.prior_run / "receipt.json")
        overruns = [step for step in first["steps"] if step["elapsed_seconds"] > step["timeout_seconds"]]
        if not overruns:
            raise ValueError("PRIOR_RUN_NOT_THE_OVERRUN")
        prior = {"receipt_path": (args.prior_run / "receipt.json").relative_to(ROOT).as_posix(),
                 "receipt_sha256": sha((args.prior_run / "receipt.json").read_bytes()),
                 "original_status": first["status"], "qualified_final_evidence": False,
                 "reason": "Original source missed post-wait elapsed limit; overrun invalidates this receipt",
                 "overruns": overruns}
    verification = {"old_B0": old_seal, "budget_exactly_unchanged": True,
                    "deadline_counterexample": timing, "prior_run_disposition": prior,
                    "new_run_receipt_sha256": sha((run / "receipt.json").read_bytes()),
                    "git_state": "No commit/push/fetch/merge; HEAD in run receipt is pre-repair",
                    "scope": "Software L0/L1 repair only; drain environmental assumption; T060/T061 incomplete"}
    (package / "repair_checks.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    paths = list(SOFTWARE.glob("*.py")) + [SOFTWARE / "README.md"]
    paths += [ROOT / "code/scripts/run_m3_polyphony_scaling_acceptance.py",
              DOCS / "B1_CONTRACT.md", DOCS / "DELIVERY_REPAIR_20261009.md",
              DOCS / "M2_HANDOFF_REPAIR_20261009.md", DOCS / "SEAL_FAILURE_20261009.md",
              DOCS / "seal_b0.py", Path(__file__).resolve()]
    paths += [path for path in (DOCS / "REPAIR_20261009").iterdir() if path.is_file()]
    paths += [path for path in run.rglob("*") if path.is_file()]
    if args.prior_run:
        paths += [path for path in args.prior_run.rglob("*") if path.is_file()]
    paths += [path for path in package.iterdir() if path.is_file()]
    payload = io.BytesIO()
    members = []
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(path.resolve() for path in paths)):
            raw = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            archive.writestr(name, raw)
            members.append({"member": name, "bytes": len(raw), "sha256": sha(raw)})
        for name in ("M2_B0_REVIEW.md", "M2_A2_REVIEW.md", "M2_REPLY_TO_M3.md",
                     "M2_REPLY_TO_M3 (1).md", "M2_REPLY_TO_M3 (2).md"):
            raw = (Path("E:/FPGA/GAOYUNFPGA/CallBack") / name).read_bytes()
            member = "review_input/" + name
            archive.writestr(member, raw)
            members.append({"member": member, "bytes": len(raw), "sha256": sha(raw)})
    raw = payload.getvalue()
    carrier = base64.b64encode(raw)
    (package / "evidence.zip").write_bytes(raw)
    (package / "evidence.zip.b64").write_bytes(carrier)
    manifest = {"schema": 1, "scope": verification["scope"], "zip_bytes": len(raw),
                "zip_sha256": sha(raw), "carrier_sha256": sha(carrier), "members": members}
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = verify(package)
    sealed = {"command": [sys.executable, *sys.argv], "cwd": str(ROOT),
              "utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "python_exe_sha256": sha(Path(sys.executable).read_bytes()),
              "exit_code": 0, "elapsed_seconds": round(time.monotonic() - started, 6),
              "sealer_sha256": sha(Path(__file__).read_bytes()),
              "manifest_sha256": sha((package / "manifest.json").read_bytes()),
              "repair_checks_sha256": sha((package / "repair_checks.json").read_bytes()),
              "result": result}
    (package / "seal_receipt.json").write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    forward = DOCS / "M3_T061_B0_REPAIR_20261009.zip"
    with zipfile.ZipFile(forward, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.iterdir()):
            if path.is_file() and path.name != "evidence.zip":
                archive.write(path, package.name + "/" + path.name)
    with zipfile.ZipFile(forward) as archive:
        if archive.testzip() is not None:
            raise ValueError("FORWARD_ZIP_CRC")
    print(json.dumps({**result, "forward_zip": str(forward),
                      "forward_sha256": sha(forward.read_bytes()), "forward_bytes": forward.stat().st_size}))


if __name__ == "__main__":
    main()
