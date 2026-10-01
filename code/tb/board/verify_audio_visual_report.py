"""Exercise the coexistence gate against actual reports and corruptions."""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code/scripts"))
from check_audio_visual_probe import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    source = parser.parse_args().prepared.resolve()
    errors, _ = check(source)
    if errors:
        raise AssertionError("baseline gate not PASS: " + str(errors))
    name = "audio_visual_coexistence_top"
    timing = Path("impl/pnr") / (name + "_tr_content.html")
    usage = Path("impl/pnr") / (name + ".rpt.txt")
    pin = Path("impl/pnr") / (name + ".pin.html")
    hierarchy = Path("impl/gwsynthesis") / (name + "_syn_rsc.xml")
    edits = [
        (timing, "Numbers of Setup Violated Endpoints</td>\n<td>0", "Numbers of Setup Violated Endpoints</td>\n<td>1", "Setup"),
        (timing, "set_output_delay -clock sys_clk -max 5.000 [get_ports {i2s_din}]", "set_output_delay -clock sys_clk -max 5.000 [get_ports {unused}]", "output delay"),
        (timing, "set_max_delay -from [get_regs {u_visual/u_event_bridge/payload_hold*}]", "set_max_delay -from [get_regs {missing/payload_hold*}]", "payload"),
        (hierarchy, 'name="u_latency" Register="65"', 'name="u_latency" Register="0"', "latency"),
    ]
    for index, (file, before, after, expected) in enumerate(edits):
        with tempfile.TemporaryDirectory(prefix="av_gate_") as tmp:
            dest = Path(tmp)
            for entry in (timing, usage, pin, hierarchy):
                target = dest / entry
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / entry, target)
            text = (dest / file).read_text(encoding="utf-8")
            if before not in text:
                raise AssertionError("corruption anchor unavailable: " + before)
            (dest / file).write_text(text.replace(before, after), encoding="utf-8")
            errors, _ = check(dest)
            if not errors or not any(expected.lower() in msg.lower() for msg in errors):
                raise AssertionError("corruption accepted: " + expected + str(errors))
            print("PASS reject corruption", expected)
    print("PASS coexistence report baseline + 4 independent corruptions")


if __name__ == "__main__":
    main()
