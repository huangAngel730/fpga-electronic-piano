"""Move the new simulation-only copied board to its authorized E TB directory."""
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016"
OLD = ROOT / "code/rtl/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016"
NEW = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016"

backup = OUT / "STATIC_PRE_R04"
backup.mkdir(exist_ok=False)
for p in HERE.glob("*.py"):
    shutil.copyfile(p, backup / p.name)
for p in OLD.glob("*.sv"):
    shutil.copyfile(p, backup / p.name)
NEW.mkdir(parents=True, exist_ok=True)
for p in OLD.glob("*.sv"):
    target = NEW / p.name
    assert not target.exists()
    assert ROOT.resolve() in p.resolve().parents and ROOT.resolve() in target.resolve().parents
    p.rename(target)
for name in ("prepare_capture.py", "run_capture.py", "test_static.py", "seal_partial.py", "repair_static.py"):
    p = HERE / name
    s = p.read_text(encoding="utf-8").replace("code/rtl/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016", "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016")
    s = s.replace("CANDIDATE_CHANGES_R03.json", "CANDIDATE_CHANGES_R04.json")
    if name == "seal_partial.py":
        s = s.replace("SOFTWARE_R03", "SOFTWARE_R04")
    p.write_text(s, encoding="utf-8", newline="\n")
p = HERE / "run_static_tests.py"
p.write_text(p.read_text(encoding="utf-8").replace("SOFTWARE_R03", "SOFTWARE_R04"), encoding="utf-8", newline="\n")
(OUT / "SIMULATION_ONLY_RELOCATION.json").write_text(json.dumps({
    "reason": "All fopen/fdisplay/final observers belong in TB, not synthesizable rtl/board",
    "old_path": str(OLD), "new_path": str(NEW), "scope": "new observation candidate only",
    "old_originals_modified": False, "rtl_run": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print("RELOCATED_NEW_OBSERVATION_BOARD_TO_E_TB")
