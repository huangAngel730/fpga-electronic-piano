"""One bounded audit group; exclusive outputs preserve unsuccessful originals."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OUT = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/intake_20261017"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    if ROOT.name != "fpga-electronic-piano":
        raise RuntimeError("Wrong repository root")
    group = OUT / "ROUND_01"
    group.mkdir(exist_ok=False)
    write(group / "CONSUMED.json", {"round": 1, "window_limit": 2,
          "shared_B1_limit": 6, "night_task2_reserved": 4,
          "utc": datetime.now(timezone.utc).isoformat(), "state": "CONSUMED_BEFORE_LAUNCH",
          "ModelSim_Gowin_Icarus_device_calls": 0})
    for label, args in (("head", ["rev-parse", "HEAD"]),
                        ("origin", ["rev-parse", "origin/develop"]),
                        ("tracked_status", ["status", "--porcelain=v1", "--untracked-files=no"])):
        process = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True)
        (group / f"{label}.stdout").write_bytes(process.stdout)
        (group / f"{label}.stderr").write_bytes(process.stderr)
    argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "audit_intake.py")]
    sources = {str(p): sha(p) for p in HERE.glob("*.py")}
    launch = {"argv": argv, "cwd": str(ROOT), "timeout_seconds": 90,
              "machine": platform.node(), "python": {"path": sys.executable,
              "version": sys.version, "sha256": sha(sys.executable)},
              "source_sha256_before": sources, "start_utc": datetime.now(timezone.utc).isoformat()}
    write(group / "LAUNCH.json", launch)
    started = time.monotonic()
    timeout = False
    with (group / "audit.stdout").open("xb") as stdout, (group / "audit.stderr").open("xb") as stderr:
        process = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr)
        try:
            code = process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            timeout = True
            process.kill()
            code = process.wait()
    receipt = dict(launch, pid=process.pid, exit_code=code, timeout=timeout,
                   end_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic() - started,
                   source_sha256_after={str(p): sha(p) for p in HERE.glob("*.py")},
                   stdout_sha256=sha(group / "audit.stdout"), stderr_sha256=sha(group / "audit.stderr"),
                   source_identity_stable=all(sha(p) == digest for p, digest in sources.items()))
    write(group / "RECEIPT.json", receipt)
    print(json.dumps({"exit_code": code, "timeout": timeout,
                      "elapsed_seconds": receipt["elapsed_seconds"],
                      "source_identity_stable": receipt["source_identity_stable"]}))
    return 1 if timeout else code


if __name__ == "__main__":
    sys.exit(main())
