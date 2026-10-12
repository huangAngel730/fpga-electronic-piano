"""Bounded B-only qualification and standalone evidence sealing."""

import argparse
import base64
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope_bundle as scope  # noqa: E402


def negatives(original):
    cases = []

    def add(name, diagnostic, edit):
        bad = copy.deepcopy(original)
        edit(bad)
        cases.append((name, diagnostic, bad))

    add("wrong_input_SHA", "SCOPE_INPUT_IDENTITY", lambda s: s["input_identity"][
        "audio_observation.jsonl"].update(sha256="0" * 64))
    add("wrong_ROM_SHA", "SCOPE_ROM_IDENTITY", lambda s: next(iter(s["ROM_identity"].values())).update(
        sha256="0" * 64))
    add("wrong_dependency_SHA", "SCOPE_DEPENDENCY_IDENTITY", lambda s: next(iter(
        s["dependency_identity"].values())).update(sha256="0" * 64))
    add("window_exclusion", "SCOPE_EXCLUSION_WIDENED", lambda s: s[
        "EXCLUDED_METADATA_EXPECTATION"].update(cycle_window=[1744211, 1745045]))
    add("all_flags_exclusion", "SCOPE_EXCLUSION_WIDENED", lambda s: s[
        "EXCLUDED_METADATA_EXPECTATION"].update(all_fixture_flags=True))
    add("missing_receipt_claim", "SCOPE_RECEIPT_IDENTITY", lambda s: s["reused_receipts"].pop(
        "router_receipt.json"))
    add("false_complete", "SCOPE_FALSE_COMPLETE", lambda s: s.update(t060_complete=True))
    add("false_STA", "SCOPE_FALSE_STA", lambda s: s.update(physical_STA_passed=True))
    return cases


def run(output):
    output = scope.fresh(output)
    begin = time.monotonic()
    inputs = sorted(HERE.glob("*.py")) + [scope.ROOT / scope.REVIEW / name
                                          for name in ("ACCEPTANCE_SCOPE.json", "SUMMARY.json")]
    inputs += [scope.ROOT / scope.ROUTER,
               HERE.parent / "t060_minclosure_20261011/scope.py",
               HERE.parent / "t060_minclosure_20261011/test_scope.py"]
    before = {p.relative_to(scope.ROOT).as_posix(): scope.identity(p.read_bytes()) for p in inputs}
    steps = []

    def command(name, argv, expected=0, diagnostic=None):
        remaining = 300 - (time.monotonic() - begin)
        scope.require(remaining > 0, "SCOPE_TOTAL_TIMEOUT")
        start = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(argv, cwd=output, capture_output=True, timeout=min(90, remaining))
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b"", error.stderr or b"", -1
            timed_out = True
        (output / (name + ".stdout.txt")).write_bytes(stdout)
        (output / (name + ".stderr.txt")).write_bytes(stderr)
        steps.append({"label": name, "argv": argv, "exit_code": code, "expected_exit": expected,
                      "diagnostic": diagnostic, "timeout": timed_out,
                      "elapsed_seconds": time.monotonic() - start,
                      "stdout": scope.identity(stdout), "stderr": scope.identity(stderr)})
        (output / "progress.json").write_text(json.dumps(steps, indent=2) + "\n", encoding="utf-8")
        print(name + ": exit " + str(code), flush=True)
        scope.require(not timed_out and code == expected and (
            diagnostic is None or diagnostic.encode() in stdout + stderr), "SCOPE_STEP_FAILED:" + name)

    python = [sys.executable, "-I", "-S", "-B", "-X", "utf8"]
    failure = None
    try:
        # unittest discover imports only the new B tests, not prior audio test suites.
        command("new_scope_tests", python + ["-m", "unittest", "discover", "-s", str(HERE),
                                           "-p", "test_scope_bundle.py", "-v"])
        command("prepare", python + [str(HERE / "scope_bundle.py"), "prepare", "--repo",
                                     str(scope.ROOT), "--output", str(output / "bundle")])
        portable = output / "bundle"
        (portable / "scope_bundle.py").write_bytes((HERE / "scope_bundle.py").read_bytes())
        (output / "sources").mkdir()
        for p in HERE.glob("*.py"):
            (output / "sources" / p.name).write_bytes(p.read_bytes())
        verifier = python + [str(portable / "scope_bundle.py"), "verify", "--bundle", str(portable)]
        command("isolated_verify", verifier)
        summary = scope.load((portable / "scope.json").read_bytes())
        (output / "negatives").mkdir()
        for name, diagnostic, bad in negatives(summary):
            path = output / "negatives" / (name + ".json")
            scope.dump(path, bad)
            command("reject_" + name, verifier + ["--summary", str(path)], 1, diagnostic)
        for name in ("missing_actual_receipt", "resigned_bad_receipt"):
            folder = output / "negatives" / name
            (folder / "authority").mkdir(parents=True)
            for p in (portable / "authority").iterdir():
                if name == "missing_actual_receipt" and p.name == "router_receipt.json":
                    continue
                raw = p.read_bytes()
                if name == "resigned_bad_receipt" and p.name == "counter_review.json":
                    raw += b" "
                (folder / "authority" / p.name).write_bytes(raw)
            (folder / "scope.json").write_bytes((portable / "scope.json").read_bytes())
            # A new self-declared SHA manifest cannot replace the verifier's pinned trust roots.
            scope.dump(folder / "resigned_manifest.json", {p.name: scope.identity(p.read_bytes())
                       for p in (folder / "authority").iterdir()})
            command("reject_" + name, python + [str(portable / "scope_bundle.py"), "verify",
                    "--bundle", str(folder)], 1,
                    "SCOPE_RECEIPT_SET" if name == "missing_actual_receipt" else "SCOPE_RECEIPT_SHA")
        command("reject_output_overwrite", python + [str(HERE / "scope_bundle.py"), "prepare",
                "--repo", str(scope.ROOT), "--output", str(portable)], 1, "SCOPE_OUTPUT_EXISTS")
    except Exception as error:
        failure = str(error)
    after = {p.relative_to(scope.ROOT).as_posix(): scope.identity(p.read_bytes()) for p in inputs}
    if before != after:
        failure = "SCOPE_EXECUTION_SOURCE_DRIFT"
    receipt = {"status": "NEW_B_SCOPE_QUALIFICATION_PASS" if failure is None else "NEW_B_SCOPE_FAIL",
               "exit_code": 0 if failure is None else 1, "failure": failure, "steps": steps,
               "sources_before": before, "sources_after": after,
               "python": {"path": sys.executable, "version": sys.version,
                          **scope.identity(Path(sys.executable).read_bytes())},
               "elapsed_seconds": time.monotonic() - begin, "total_limit_seconds": 300,
               "step_limit_seconds": 90, "tests": 29, "CLI_refusals": 11,
               "new_math_replays": 0, "old_56_negative_runs": 0,
               "new_RTL_runs": 0, "EDA_runs": 0, "t060_complete": False,
               "scope": "L0/L1 new B structure/identity/refusal only; historical math REUSED"}
    scope.dump(output / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "exit_code": receipt["exit_code"], "failure": failure}))
    return receipt["exit_code"]


def seal(run_dir, output, notes):
    receipt = scope.load((run_dir / "receipt.json").read_bytes())
    scope.require(receipt["status"] == "NEW_B_SCOPE_QUALIFICATION_PASS" and receipt["exit_code"] == 0
                  and receipt["sources_before"] == receipt["sources_after"], "SCOPE_SEAL_NOT_PASS")
    for name, expected in receipt["sources_after"].items():
        scope.require(scope.identity((scope.ROOT / name).read_bytes()) == expected,
                      "SCOPE_SEAL_SOURCE_DRIFT:" + name)
    scope.verify(run_dir / "bundle")
    members = {"run/" + p.relative_to(run_dir).as_posix(): p.read_bytes()
               for p in run_dir.rglob("*") if p.is_file()}
    members["README.md"] = notes.read_bytes()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    payload = stream.getvalue()
    output = scope.fresh(output)
    (output / "SCOPE_EVIDENCE.zip.b64").write_text(base64.encodebytes(payload).decode("ascii"),
                                                 encoding="ascii", newline="\n")
    manifest = {"status": "B_SCOPE_SOFTWARE_SEALED_ONLY", "zip": scope.identity(payload),
                "members": {n: scope.identity(d) for n, d in sorted(members.items())},
                "t060_complete": False, "M2_review": "pending_user_forward_not_delivered"}
    scope.dump(output / "seal.json", manifest)
    return manifest["zip"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    execute = modes.add_parser("run")
    execute.add_argument("--output", required=True, type=Path)
    package = modes.add_parser("seal")
    package.add_argument("--run", required=True, type=Path)
    package.add_argument("--output", required=True, type=Path)
    package.add_argument("--notes", required=True, type=Path)
    args = parser.parse_args()
    if args.mode == "run":
        sys.exit(run(args.output.resolve()))
    print(json.dumps(seal(args.run.resolve(), args.output, args.notes)))
