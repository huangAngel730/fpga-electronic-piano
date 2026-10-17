"""One bounded R6-1 software group; exclusive output and pre-call identity log."""
import datetime
import argparse
import hashlib
import json
import re
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    start = time.monotonic()
    repo, output, config = map(Path, sys.argv[1:4])
    repair = sys.argv[4:] == ["--repair"]
    if sys.argv[4:] and not repair:
        raise ValueError("unknown mode")
    budget = 60 if repair else 90
    output.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    cfg = json.loads(config.read_text(encoding="utf-8"))
    inputs = [config, repo / cfg["archive"]["path"], *sorted(here.glob("*.py"))]
    inputs += [Path(sys.executable)]
    inputs += sorted({Path(m.__file__).resolve() for m in list(sys.modules.values())
                      if getattr(m, "__file__", None) and Path(m.__file__).is_file()
                      and Path(m.__file__).resolve().is_relative_to(Path(sys.base_prefix).resolve())})
    inputs += sorted(Path(sys.executable).parent.glob("python*.dll"))
    inputs = list(dict.fromkeys(inputs))
    before = [{"path": str(p.resolve()), "bytes": p.stat().st_size, "sha256": digest(p)} for p in inputs]
    frozen = output / "frozen"
    frozen.mkdir()
    for p in sorted(here.glob("*.py")):
        (frozen / p.name).write_bytes(p.read_bytes())
    (frozen / config.name).write_bytes(config.read_bytes())
    test_name = "test_repair.py" if repair else "test_audit.py"
    command = [sys.executable, "-B", "-X", "utf8", str(frozen / test_name),
               str(repo), str(output / "cases"), str(config)]
    dump(output / "PLAN.json", {"machine": platform.node(), "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "argv": command, "cwd": str(repo), "budget_seconds": budget, "inputs": before,
         "dependency": "Python standard library only; no HDL or EDA", "python": sys.version,
         "case_definition": "test_audit.py frozen SHA; generated synthetic case manifests before calls",
         "consumption": "exclusive RUN_01 output; no automatic retry"})
    timed_out = False
    with (output / "stdout.txt").open("wb") as stdout, (output / "stderr.txt").open("wb") as stderr:
        try:
            proc = subprocess.run(command, cwd=repo, stdout=stdout, stderr=stderr,
                                  timeout=max(0.01, budget - 5 - (time.monotonic() - start)))
            code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out, code = True, 124
    unchanged = all(digest(Path(row["path"])) == row["sha256"] for row in before)
    artifacts = [{"path": str(p.relative_to(output)), "sha256": digest(p), "bytes": p.stat().st_size}
                 for p in sorted(output.rglob("*")) if p.is_file()]
    elapsed = time.monotonic() - start
    final = code if unchanged and elapsed <= budget else 125
    dump(output / "RECEIPT.json", {"exit_code": final, "child_exit_code": code, "timeout": timed_out,
         "elapsed_seconds_including_artifact_hashes": elapsed, "inputs_unchanged": unchanged,
         "child_calls": 1, "hdl_calls": 0, "artifacts": artifacts,
         "receipt_self_excluded": True, "board_release_allowed": False})
    print(json.dumps({"exit_code": final, "elapsed": elapsed, "timeout": timed_out}))
    return final


if __name__ == "__main__":
    raise SystemExit(main())
