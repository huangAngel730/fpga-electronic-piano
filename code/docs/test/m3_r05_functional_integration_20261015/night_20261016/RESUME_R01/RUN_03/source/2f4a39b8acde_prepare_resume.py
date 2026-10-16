"""Copy the frozen observation candidate into the authorized resume batch."""
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
OLD = HERE.parent
sys.path.insert(0, str(OLD.parent))
from common import ROOT, DOCS, TB_DIR, identity, write_new

OUT = DOCS / "night_20261016/RESUME_R01"
TBO = TB_DIR / "night_20261016"
TBN = TBO / "RESUME_R01"
BO = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016"
BN = BO / "RESUME_R01"


def main():
    OUT.mkdir(exist_ok=False)
    TBN.mkdir(exist_ok=False)
    BN.mkdir(exist_ok=False)
    pairs = [(TBO / name, TBN / name) for name in ("m3_r05_public_observer.sv", "tb_r05_observed_7ms.sv")]
    pairs += [(BO / "m2_fourvoice_timbre_delay_board_observed.sv", BN / "m2_fourvoice_timbre_delay_board_observed.sv")]
    pairs += [(OLD / "public_ledger.py", HERE / "public_ledger.py")]
    pairs += [(OUT.parent / name, OUT / name) for name in ("INPUT_BINDING.json", "BOARD.diff", "TB.diff", "OBSERVER.diff", "CAPTURE_INTERFACE.md")]
    mapping = []
    for old, new in pairs:
        assert not new.exists()
        shutil.copyfile(old, new)
        assert old.read_bytes() == new.read_bytes()
        mapping.append({"old": identity(old), "new": identity(new), "same_bytes": True})
    changes = json.loads((OUT.parent / "CANDIDATE_CHANGES_R04.json").read_text(encoding="utf-8"))
    candidates = {"BOARD": BN / "m2_fourvoice_timbre_delay_board_observed.sv", "TB": TBN / "tb_r05_observed_7ms.sv", "OBSERVER": TBN / "m3_r05_public_observer.sv"}
    for row in changes["changes"]:
        row["candidate"] = identity(candidates[row["kind"]])
        row["diff"] = identity(OUT / (row["kind"] + ".diff"))
    write_new(OUT / "CANDIDATE_CHANGES.json", changes)
    s = (OLD / "run_capture.py").read_text(encoding="utf-8")
    s = s.replace('sys.path.insert(0, str(HERE.parent))', 'sys.path.insert(0, str(HERE.parent.parent))')
    s = s.replace('BASE = DOCS / "night_20261016"', 'BASE = DOCS / "night_20261016/RESUME_R01"')
    s = s.replace('night_20261016/m2_fourvoice_timbre_delay_board_observed.sv', 'night_20261016/RESUME_R01/m2_fourvoice_timbre_delay_board_observed.sv')
    s = s.replace('night_20261016/tb_r05_observed_7ms.sv', 'night_20261016/RESUME_R01/tb_r05_observed_7ms.sv')
    s = s.replace('night_20261016/m3_r05_public_observer.sv', 'night_20261016/RESUME_R01/m3_r05_public_observer.sv')
    s = s.replace('list((TB_DIR / "night_20261016").glob', 'list((TB_DIR / "night_20261016/RESUME_R01").glob')
    s = s.replace('HERE.parent / n for n in', 'HERE.parent.parent / n for n in')
    # Freeze all imported source bodies, including runner transitive imports.
    begin = s.index('    # Imported supervision/parser originals')
    end = s.index('    return {p.relative_to(ROOT)', begin)
    s = s[:begin] + '    paths += list(HERE.parent.parent.glob("*.py"))\n' + s[end:]
    s = s.replace('coordinator/night_20261016/DISPATCH.md', 'coordinator/night_20261016/RESUME_R01/AUTHORIZATION_AND_DISPATCH.md')
    s = s.replace('CANDIDATE_CHANGES_R04.json', 'CANDIDATE_CHANGES.json')
    s = s.replace('    out = BASE / name\n', '''    if (BASE / (name + "_CONSUMED.json")).exists():
        raise ValueError("RESUME_FUNCTIONAL_GROUP_ALREADY_CONSUMED")
    if len(list(BASE.glob("RUN_*_CONSUMED.json"))) >= 3:
        raise ValueError("RESUME_THREE_GROUP_BUDGET_EXHAUSTED")
    out = BASE / name
''')
    (HERE / "run_capture.py").write_text(s, encoding="utf-8", newline="\n")
    for p in HERE.glob("*.py"):
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
    write_new(OUT / "PREPARATION_RECEIPT.json", {"status": "STATIC_RESUME_PREPARED_NOT_EXECUTED", "copies": mapping,
        "runner": identity(HERE / "run_capture.py"), "baseline_head": "c12636c034be62e10c564217298564422a533b9c",
        "old_staged_files": "READ_ONLY", "authority": identity(DOCS / "coordinator/night_20261016/RESUME_R01/AUTHORIZATION_AND_DISPATCH.md"),
        "user_source_thread": "01a14050-cd98-7c41-8004-5d3e25765167", "user_message": "01a14237-c04d-7d41-ae9d-cd8493ff0dd9"})
    print("RESUME_PREPARED_SAME_CANDIDATE_BYTES_NO_TOOL_RUN")


if __name__ == "__main__":
    main()
