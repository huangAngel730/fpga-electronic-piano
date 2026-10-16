"""One Python-only diagnostic for R01 mismatch; never starts HDL or checker."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from collect_readiness import HERE, ROOT, env_sha, old_runner, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = ROOT / "code/docs/test/t052_publication_acceptance_20261012/long_window_preparation_20261015/chat8_readiness_20261016"
    if not output.is_relative_to(allowed.resolve()):
        raise SystemExit("OUTPUT_OUTSIDE_DISPATCH")
    output.mkdir()
    ambient = dict(os.environ)
    explicit = dict(ambient)
    suite = Path("D:/Gowin/oss-cad-suite").resolve()
    explicit["PATH"] = os.pathsep.join((str(suite / "bin"), str(suite / "lib"), ambient.get("PATH", "")))
    explicit["IVERILOG_ROOT"] = str(suite / "lib/ivl")
    expected = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in explicit.items()}
    try:
        os.environ.clear()
        os.environ.update(explicit)
        step = old_runner.supervise([sys.executable, "-B", "-X", "utf8",
                                    str(HERE / "environment_probe.py")], output, "debug_job",
                                    10, time.monotonic()+10, dict(old_runner.MAXIMA))
    finally:
        os.environ.clear()
        os.environ.update(ambient)
    observed = json.loads((output / "debug_job.stdout.bin").read_text(encoding="utf-8"))
    actual = observed["environment_item_sha256"]
    differing = {k: {"parent": expected.get(k), "child": actual.get(k)}
                 for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k)}
    receipt = {"scope": "PYTHON_ONLY_ENVIRONMENT_DIAGNOSIS", "actual_argv": sys.orig_argv,
               "parent_sha": env_sha(explicit), "child_sha": observed["environment_sha256"],
               "differing_keys": differing, "step": step, "HDL_calls": 0,
               "raw_child_observation": observed, "execute_calls": 0}
    write(output / "DIAGNOSIS.json", receipt)
    print(json.dumps({"scope": receipt["scope"], "differing_keys": differing}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
