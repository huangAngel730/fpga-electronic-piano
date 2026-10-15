"""Fixed Python-only runner; records raw streams and immutable source snapshots."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from static_bundle import BASE, ROOT, SOURCE_MANIFEST, TB, identity


HERE = Path(__file__).resolve().parent


def source_paths():
    return sorted([*HERE.glob("*.py"), *HERE.glob("*.md"),
                   *(ROOT / BASE).glob("*.py"), *(ROOT / TB).glob("*.sv"),
                   ROOT / SOURCE_MANIFEST])


def snapshot(paths):
    return {str(p.resolve()): identity(p) for p in paths}


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def run(output, prepared=None):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / "code/output").resolve()):
        raise ValueError("OUTPUT_MUST_BE_IN_CODE_OUTPUT")
    # mkdir is the exclusive claim; no existing directory is ever reused.
    output.mkdir(parents=True, exist_ok=False)
    paths = source_paths()
    before = snapshot(paths)
    with zipfile.ZipFile(output / "source_before.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
    commands = [("new_software_negatives", [sys.executable, "-B", "-X", "utf8",
                 str(HERE / "test_static_bundle.py")], 60)]
    if prepared is not None:
        commands.append(("existing_preparation_identity", [sys.executable, "-B", "-X", "utf8",
                         str(HERE / "static_bundle.py"), "--prepared", str(Path(prepared).resolve()),
                         "--report", str(output / "static_identity.json")], 60))
    steps = []
    for name, argv, limit in commands:
        start = time.monotonic()
        out, err = output / (name + ".stdout.bin"), output / (name + ".stderr.bin")
        with out.open("xb") as stdout, err.open("xb") as stderr:
            try:
                completed = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr,
                                           timeout=limit, check=False)
                code, timeout = completed.returncode, False
            except subprocess.TimeoutExpired:
                code, timeout = 124, True
        steps.append(dict(name=name, argv=argv, cwd=str(ROOT), exit_code=code, timeout=timeout,
                          limit_seconds=limit, elapsed_seconds=time.monotonic() - start,
                          stdout=identity(out), stderr=identity(err)))
        if code != 0:
            break
    after = snapshot(paths)
    passed = len(steps) == len(commands) and all(s["exit_code"] == 0 for s in steps) and before == after
    receipt = dict(schema="T052_STATIC_BINDING_SOFTWARE_R01", status="PASS" if passed else "FAIL",
                   scope="NEW_SOFTWARE_NEGATIVES_AND_STATIC_IDENTITIES_ONLY",
                   utc=datetime.now(timezone.utc).isoformat(), source_before=before, source_after=after,
                   source_snapshot=identity(output / "source_before.zip"), steps=steps,
                   python=identity(Path(sys.executable)), python_version=sys.version,
                   execution_authorized=False, HDL_compiles=0, RTL_runs=0, EDA_runs=0,
                   complete_T052=False, old_4207_completeness="UNKNOWN")
    write_json(output / "receipt.json", receipt)
    print(json.dumps(dict(status=receipt["status"], output=str(output), steps=len(steps),
                          HDL_compiles=0, RTL_runs=0)))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prepared", type=Path)
    args = parser.parse_args()
    try:
        return run(args.output, args.prepared)
    except (OSError, ValueError) as exc:
        print(json.dumps(dict(status="RUNNER_REJECTED", diagnostic=str(exc))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
