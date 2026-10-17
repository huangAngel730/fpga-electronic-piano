"""Record bounded static seal command and original streams; not a test round."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time

from run_binding_selftest import DOC, HERE, ROOT, HELPERS, identity, invoke
from metadata_cases import save


def main():
    sources = sorted(list(HERE.glob("*.py")) + [HELPERS / n for n in
                     ("common.py", "supervised_process.py", "windows_job.py")])
    before = [identity(p) for p in sources]
    argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "seal_binding.py")]
    start = datetime.now(timezone.utc).isoformat()
    save(DOC / "SEAL_EXECUTION_LAUNCH.json", {"argv": argv, "cwd": str(ROOT), "started_utc": start,
         "single_static_seal_budget_s": 90, "source_before": before, "functional_round_consumption": 0})
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    rec = invoke(argv, ROOT, DOC, "SEAL_EXECUTION", time.monotonic() + 85,
                 step_budget=85, environment=env)
    rec.update(started_utc=start, ended_utc=datetime.now(timezone.utc).isoformat(),
               source_before=before, source_after=[identity(p) for p in sources],
               functional_round_consumption=0)
    save(DOC / "SEAL_EXECUTION_RECEIPT.json", rec)
    assert rec["exit_code"] == 0 and not rec["error"] and not rec["timeout"]
    assert rec["source_before"] == rec["source_after"]
    print(identity(DOC / "DELIVERY_RECEIPT.json"))


if __name__ == "__main__":
    main()
