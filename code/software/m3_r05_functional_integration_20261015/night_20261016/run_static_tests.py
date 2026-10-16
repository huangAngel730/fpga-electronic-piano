"""Run only the Python regression under original Job/NUL supervision."""
import sys
import time
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import ROOT, DOCS, identity, write_new
from supervised_process import invoke

out = DOCS / "night_20261016/SOFTWARE_R04"
out.mkdir(exist_ok=False)
source = {p.name: identity(p) for p in HERE.glob("*.py")}
copied = out / "source"
copied.mkdir()
for name in source:
    shutil.copyfile(HERE / name, copied / name)
call = invoke([sys.executable, "-X", "utf8", str(HERE / "test_static.py"), str(out / "cases")],
    ROOT, out, "static_tests", time.monotonic() + 300, step_budget=300)
write_new(out / "RUN_RECEIPT.json", {"kind": "SOFTWARE_ONLY", "call": call,
    "source_before": source, "source_after": {p.name: identity(p) for p in HERE.glob("*.py")},
    "python": identity(sys.executable), "rtl_execution": False})
print(call["exit_code"], call["error"])
sys.exit(0 if call["exit_code"] == 0 and not call["error"] and not call["timeout"] else 1)
