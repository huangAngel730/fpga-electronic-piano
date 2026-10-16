"""One static-only revision. No simulator, subprocess or Git operations."""
import difflib
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOCS = ROOT / "code/docs/test/m3_r05_functional_integration_20261015/night_20261016"
TB = ROOT / "code/tb/board/m3_r05_functional_integration_20261015/night_20261016"
BOARD = ROOT / "code/rtl/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016"


def main():
    backup = DOCS / "STATIC_PRE_R03"
    backup.mkdir(exist_ok=False)
    files = list(HERE.glob("*.py")) + list(TB.glob("*.sv")) + list(BOARD.glob("*.sv")) + list(DOCS.glob("*.diff"))
    for path in files:
        shutil.copyfile(path, backup / path.name)
    original = (HERE.parent / "public_ledger.py").read_text(encoding="utf-8")
    old = '            epoch = item["epoch"]\n'
    new = '            previous_reset = 0\n' + old
    assert original.count(old) == 1
    current = original.replace(old, new)
    # The public clip counter saturates, rather than wraps, at all ones.
    current = current.replace('(last_clip + clip_pending) & 0xFFFFFFFF', 'min(last_clip + clip_pending, 0xFFFFFFFF)')
    (HERE / "public_ledger.py").write_text(current, encoding="utf-8", newline="\n")
    (DOCS / "LEDGER_R03.diff").write_text("".join(difflib.unified_diff(
        original.splitlines(True), current.splitlines(True), fromfile="old_ledger_read_only", tofile="night_ledger")), encoding="utf-8", newline="\n")
    prepare = HERE / "prepare_capture.py"
    s = prepare.read_text(encoding="utf-8")
    # Same timestamp zero, but after initial drivers settle. Header always first.
    anchor = '    end\n    always @(posedge core_clk) begin'
    addition = r'''      #0;
      $fdisplay(night_input_fd,"{\\"kind\\":\\"INITIAL_INPUTS\\",\\"time_ns\\":%0d,\\"midi_rx\\":%0d,\\"sys_rst_n\\":%0d}",$time,midi_rx,sys_rst_n);
'''
    assert s.count(anchor) == 1
    s = s.replace(anchor, addition + anchor)
    s = s.replace('shared_event_data,status_active_voice_count})', 'shared_event_data,status_active_voice_count,night_config_valid,night_config_ready})')
    s = s.replace('always @(midi_rx) $fdisplay', 'always @(midi_rx) if ($time > 0) $fdisplay')
    s = s.replace('always @(sys_rst_n) $fdisplay', 'always @(sys_rst_n) if ($time > 0) $fdisplay')
    s = s.replace('CANDIDATE_CHANGES_R02.json', 'CANDIDATE_CHANGES_R03.json')
    prepare.write_text(s, encoding="utf-8", newline="\n")
    runner = HERE / "run_capture.py"
    runner.write_text(runner.read_text(encoding="utf-8").replace('CANDIDATE_CHANGES_R02.json', 'CANDIDATE_CHANGES_R03.json'), encoding="utf-8", newline="\n")
    print("STATIC_REPAIR_R03_ONLY")


if __name__ == "__main__":
    main()
