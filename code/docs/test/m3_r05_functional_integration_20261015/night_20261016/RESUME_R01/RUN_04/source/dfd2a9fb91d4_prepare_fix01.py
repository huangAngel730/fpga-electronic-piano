"""Minimal fix of observation-only declarations; prior failure is immutable."""
import difflib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from common import ROOT, DOCS, identity, write_new

OUT = DOCS / "night_20261016/RESUME_R01"
old = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016/RESUME_R01/m2_fourvoice_timbre_delay_board_observed.sv"
new = old.parent / "FIX_01" / old.name
new.parent.mkdir(exist_ok=False)
raw = old.read_bytes()
declaration = b"    wire night_config_valid,night_config_ready;\n"
assert raw.count(declaration) == 1 and raw.count(b"    logic rst_sync_n;") == 1
fixed = raw.replace(declaration, b"").replace(b"    logic rst_sync_n;", b"    logic rst_sync_n;\n" + declaration.rstrip(b"\n"))
new.write_bytes(fixed)
diff = OUT / "BOARD_FIX01.diff"
diff.write_text("".join(difflib.unified_diff(raw.decode().splitlines(True), fixed.decode().splitlines(True),
    fromfile="resume_first_compile_failure_source", tofile="observation_declaration_order_fix")), encoding="utf-8", newline="\n")
changes = json.loads((OUT / "CANDIDATE_CHANGES.json").read_text(encoding="utf-8"))
for row in changes["changes"]:
    if row["kind"] == "BOARD":
        original = (OUT / "RUN_02/stage/inputs/sources/m2_fourvoice_timbre_delay_board_top.sv").read_bytes()
        # Original baseline diff plus this exact observation-only declaration move.
        base_diff = (OUT / "BOARD.diff").read_text(encoding="utf-8")
        (OUT / "BOARD_WITH_FIX01.diff").write_text(base_diff + "\n# Incremental declaration-order repair\n" + diff.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        row["candidate"] = identity(new)
        row["diff"] = identity(OUT / "BOARD_WITH_FIX01.diff")
write_new(OUT / "CANDIDATE_CHANGES_FIX01.json", changes)
runner = (HERE / "run_capture.py").read_text(encoding="utf-8")
runner = runner.replace("RESUME_R01/m2_fourvoice_timbre_delay_board_observed.sv", "RESUME_R01/FIX_01/m2_fourvoice_timbre_delay_board_observed.sv")
runner = runner.replace('CANDIDATE_CHANGES.json', 'CANDIDATE_CHANGES_FIX01.json')
# Run numbers also include preparation failures; actual starts are capped by markers.
runner = runner.replace('if not 1 <= index <= 3:', 'if not 1 <= index <= 9:')
runner = runner.replace('raise ValueError("three candidate maximum")', 'raise ValueError("numbered output range exceeded")')
(HERE / "run_capture_fix01.py").write_text(runner, encoding="utf-8", newline="\n")
write_new(OUT / "FIX01_RECEIPT.json", {"reason": "ModelSim vlog-2730: observation config wires declared after procedural usage",
    "before": identity(old), "after": identity(new), "diff": identity(diff),
    "algorithm_rom_changed": False, "functional_groups_before": len(list(OUT.glob("RUN_*_CONSUMED.json"))),
    "raw_failure": identity(OUT / "RUN_02/logs/vlog.stdout.log"), "old_sources_unchanged": True})
print("FIX01_PREPARED_DECLARATION_MOVE_ONLY")
