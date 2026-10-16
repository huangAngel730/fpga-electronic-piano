"""Prepare a new authorized batch; never rewrite earlier evidence."""
import difflib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from common import ROOT, DOCS, TB_DIR, identity, write_new

old = DOCS / "night_20261016/RESUME_R01"
out = DOCS / "night_20261016/RESUME_R02"
out.mkdir(exist_ok=False)
tb = TB_DIR / "night_20261016/RESUME_R02"
tb.mkdir(exist_ok=False)
eb = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016"
board = eb / "RESUME_R02/m2_fourvoice_timbre_delay_board_observed.sv"
board.parent.mkdir(exist_ok=False)
sources = {
    board: eb / "RESUME_R01/FIX_03_PENDING" / board.name,
    tb / "m3_r05_public_observer.sv": TB_DIR / "night_20261016/RESUME_R01/FIX_02/m3_r05_public_observer.sv",
    tb / "tb_r05_observed_7ms.sv": TB_DIR / "night_20261016/RESUME_R01/tb_r05_observed_7ms.sv",
    HERE / "public_ledger.py": HERE.parent / "RESUME_R01/public_ledger.py",
    out / "INPUT_BINDING.json": old / "INPUT_BINDING.json",
}
for target, source in sources.items():
    shutil.copyfile(source, target)
    assert identity(source)["sha256"] == identity(target)["sha256"]
prior_board = eb / "RESUME_R01/FIX_02" / board.name
before = prior_board.read_text(encoding="utf-8")
after = board.read_text(encoding="utf-8")
assert before.replace("    wire night_committed_clip;\n", "") == after.replace("    wire night_committed_clip;\n", "")
assert after.index("wire night_committed_clip;") < after.index("    generate")
assert after.index("wire night_config_valid,night_config_ready;") < after.index("    generate")
diff = out / "BOARD_DECLARATION.diff"
diff.write_text("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile="R01_FIX02", tofile="R02")), encoding="utf-8", newline="\n")
changes = json.loads((old / "CANDIDATE_CHANGES_FIX02.json").read_text(encoding="utf-8"))
for row in changes["changes"]:
    row["candidate"] = identity({"BOARD": board, "TB": tb / "tb_r05_observed_7ms.sv", "OBSERVER": tb / "m3_r05_public_observer.sv"}[row["kind"]])
    if row["kind"] == "BOARD":
        row["previous_candidate"] = identity(prior_board)
        row["incremental_diff"] = identity(diff)
write_new(out / "CANDIDATE_CHANGES.json", changes)
schema_text = (old / "STARTUP_SCHEMA.json").read_text(encoding="utf-8")
new_schema = schema_text.replace("RESUME_R01/FIX_02", "RESUME_R02")
(out / "STARTUP_SCHEMA.json").write_text(new_schema, encoding="utf-8", newline="\n")
(out / "STARTUP_SCHEMA.diff").write_text("".join(difflib.unified_diff(schema_text.splitlines(True), new_schema.splitlines(True), fromfile="R01", tofile="R02")), encoding="utf-8", newline="\n")
contract = (old / "CAPTURE_INTERFACE.md").read_text(encoding="utf-8").replace("Last remaining real functional group only.", "R02 newly authorized maximum three functional groups; stop at first success. Old groups remain consumed.")
(out / "CAPTURE_INTERFACE.md").write_text(contract, encoding="utf-8", newline="\n")
runner = (HERE.parent / "RESUME_R01/run_capture_fix02.py").read_text(encoding="utf-8")
runner = runner.replace("RESUME_R01/FIX_02", "RESUME_R02").replace("RESUME_R01", "RESUME_R02").replace("CANDIDATE_CHANGES_FIX02.json", "CANDIDATE_CHANGES.json")
runner = runner.replace("1 <= index <= 9", "1 <= index <= 3")
(HERE / "run_capture.py").write_text(runner, encoding="utf-8", newline="\n")
write_new(out / "PREPARATION.json", {"status": "STATIC_CANDIDATE_READY_NOT_EXECUTED", "copies": [{"source": identity(s), "copy": identity(t)} for t, s in sources.items()], "authorization": identity(DOCS / "coordinator/night_20261016/RESUME_R02/AUTHORIZATION_AND_DISPATCH.md"), "schema": identity(out / "STARTUP_SCHEMA.json"), "schema_changes": ["producer_observer path", "producer_board path"], "new_budget": 3, "old_budget_consumed": 3, "formal_algorithm_rom_clock_changed": False})
print("R02_PREPARED")
