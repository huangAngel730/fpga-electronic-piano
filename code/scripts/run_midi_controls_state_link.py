"""M2 standalone M3-parser accepted tap to control-state snapshot test.
No formal router/FCW/LFO edit, no new bitstream; sample cadence1041/1042 cycles.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def main():
    stage = ROOT / "code/output/midi_controls_M2_review_20261001/link"
    stage.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + os.environ["PATH"]
    sources = [ROOT / rel for rel in ["code/rtl/common/audio_defs_pkg.sv",
               "code/rtl/input/midi_input/midi_event_parser.sv",
               "code/rtl/board/performance_control_state.sv",
               "code/tb/board/tb_midi_controls_state_link.sv"]]
    command = [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_midi_controls_state_link",
               "-o", str(stage / "link.vvp")] + list(map(str, sources))
    results = []
    for label, command in [("compile", command), ("run", [str(CAD / "bin/vvp.exe"), str(stage / "link.vvp")])]:
        result = subprocess.run(command, cwd=stage, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=180)
        text = result.stdout + result.stderr
        (stage / (label + ".log")).write_text(text, encoding="utf-8", newline="\n")
        if result.returncode:
            print(text[-3000:])
            return result.returncode
        if label == "run":
            results = [line for line in text.splitlines() if line.startswith("PASS midi_controls_state_link")]
            print(text.strip())
            if len(results) != 1:
                return 1
    # A hookup mutation must fail: using valid alone instead of valid&&ready
    # writes controls during backpressure. Mutate only a scratch TB connection.
    broken_tb = stage / "wrong_tap_tb.sv"
    original_tb = sources[-1].read_text(encoding="utf-8")
    anchor = ".accepted_valid(accepted_valid),.accepted_data(event_data)"
    if original_tb.count(anchor) != 1:
        raise RuntimeError("wrong-tap mutation anchor missing")
    broken_tb.write_text(original_tb.replace(anchor, ".accepted_valid(event_valid),.accepted_data(event_data)"),
                         encoding="utf-8", newline="\n")
    negative_compile = [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_midi_controls_state_link",
                        "-o", str(stage / "wrong_tap.vvp")] + list(map(str, sources[:-1])) + [str(broken_tb)]
    result = subprocess.run(negative_compile, cwd=stage, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    (stage / "wrong_tap_compile.log").write_text(result.stdout + result.stderr, encoding="utf-8", newline="\n")
    if result.returncode:
        raise RuntimeError("negative tap fixture did not compile")
    result = subprocess.run([str(CAD / "bin/vvp.exe"), str(stage / "wrong_tap.vvp")],
                            cwd=stage, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    negative_text = result.stdout + result.stderr
    (stage / "wrong_tap.log").write_text(negative_text, encoding="utf-8", newline="\n")
    rejected = result.returncode != 0 and "live pitch query by identity" in negative_text
    if not rejected:
        raise RuntimeError("incorrect valid-only accepted-event tap was not rejected: " + negative_text)
    print("PASS wrong valid-only control-state tap rejected")
    (stage / "evidence.json").write_text(json.dumps({"scope": "M3 parser to independent M2 state TB-only; no formal audio or hardware claim",
         "result": results, "wrong_valid_only_tap_rejected": rejected, "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
         "logs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.glob("*.log")}}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
