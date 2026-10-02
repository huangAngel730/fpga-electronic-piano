"""Report gate sensitivity against real STA files, not synthetic pass labels."""
from pathlib import Path
import argparse
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code/scripts"))
from check_control_snapshot_timing import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    cfg = parser.parse_args()
    source = cfg.folder.resolve()
    errors, _ = check(source)
    if errors:
        raise RuntimeError("baseline report not PASS: " + str(errors))
    name = "control_snapshot_timing_probe"
    timing = Path("impl/pnr") / (name + "_tr_content.html")
    needed = [timing, Path("impl/pnr") / (name + ".rpt.txt"),
              Path("impl/gwsynthesis") / (name + "_syn_rsc.xml"), Path("build.log")]
    edits = [
        (r"(Numbers of Hold Violated Endpoints</td>\s*<td>)0", r"\g<1>1", "Hold Violated"),
        (r"(Numbers of Setup Violated Endpoints</td>\s*<td>)0", r"\g<1>1", "Setup Violated"),
        (r"set_clock_uncertainty -hold 0\.500", "set_clock_uncertainty -hold 0.000", "uncertainty"),
        (r"(<td>sys_clk</td>\s*<td>Base</td>\s*<td>)20\.000", r"\g<1>40.000", "50MHz"),
    ]
    for pattern, replacement, reason in edits:
        with tempfile.TemporaryDirectory(prefix="control_report_negative_") as directory:
            dest = Path(directory)
            for rel in needed:
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / rel, target)
            original = (dest / timing).read_text(encoding="utf-8")
            mutated, count = re.subn(pattern, replacement, original, count=1)
            if count != 1:
                raise RuntimeError("corruption anchor missing: " + reason)
            (dest / timing).write_text(mutated, encoding="utf-8", newline="\n")
            errors, _ = check(dest)
            if not errors or not any(reason in error for error in errors):
                raise RuntimeError("bad report accepted: " + reason + str(errors))
            print("PASS reject", reason)
    print("PASS real report +4 fail-closed corruptions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
