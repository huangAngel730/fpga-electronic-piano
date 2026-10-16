"""No tool launch: diagnose immutable snapshot preparation failure."""
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from common import DOCS, identity, write_new

base = DOCS / "night_20261016/RESUME_R01"
old = json.loads((base / "RUN_01/RUN_RECEIPT.json").read_text(encoding="utf-8"))
out = base / "DIAGNOSTIC_01"
out.mkdir(exist_ok=False)
results = []
for relative, item in old["source_before"].items():
    target = out / "execution_sources" / relative
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item["path"], target)
        results.append({"relative": relative, "copied": True})
    except Exception as exc:
        results.append({"relative": relative, "copied": False, "error": repr(exc), "path_length": len(str(target))})
        break
write_new(out / "RESULT.json", {"no_tool_launched": True, "results": results})
print(json.dumps(results[-1], ensure_ascii=False))
