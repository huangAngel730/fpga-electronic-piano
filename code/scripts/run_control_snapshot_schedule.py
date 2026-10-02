"""Actual M3 parser + M2 serialized snapshot + original reference at50MHz.
No audio algorithm or formal top edits. Audio request cadence is a TB source.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def main():
    stage = ROOT / "code/output/control_snapshot_optimization_20261002/schedule"
    stage.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + os.environ["PATH"]
    sources = [ROOT / rel for rel in ["code/rtl/common/audio_defs_pkg.sv",
        "code/rtl/input/midi_input/midi_event_parser.sv", "code/rtl/board/performance_control_state.sv",
        "code/rtl/board/performance_control_snapshot.sv", "code/tb/board/tb_control_snapshot_schedule.sv"]]
    compile_cmd = [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_control_snapshot_schedule",
                   "-o", str(stage / "tb.vvp")] + list(map(str, sources))
    results = []
    for label, command in [("compile", compile_cmd), ("RTL", [str(CAD / "bin/vvp.exe"), str(stage / "tb.vvp")])]:
        with (stage / (label + ".log")).open("w", encoding="utf-8", newline="\n") as stream:
            process = subprocess.run(command, cwd=stage, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
        text = (stage / (label + ".log")).read_text(encoding="utf-8", errors="replace")
        if process.returncode:
            print(text[-3000:]);return process.returncode
        if label == "RTL":
            results = [line for line in text.splitlines() if line.startswith("PASS control_snapshot_schedule")]
            print(text.strip())
            if len(results) != 1 or "FATAL" in text:
                return 1
    (stage / "evidence.json").write_text(json.dumps({"scope": "50MHz real-rate M3-parser scheduling TB, not official PCM algorithm or latency measurement",
        "result": results, "sources_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "logs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.glob("*.log")}}, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
