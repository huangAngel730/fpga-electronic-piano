"""Reproduce isolated X4 III momentary controls; no hardware/source mutation.

--quick omits the full disabled-parser equivalence check; it is NOT the final gate.
The volume block is a mathematical proposal, not an approved audio algorithm.
"""
from pathlib import Path
import argparse, hashlib, json, os, subprocess
ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "code/tb/input/panel_verified_candidate"
CONTROL = ROOT / "code/tb/board/panel_verified_control_candidate"
CAD = Path("D:/Gowin/oss-cad-suite")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--quick", action="store_true")
    cli.add_argument("--resume-score-boundary", action="store_true", help="recheck changed score files; hash-verify and reuse all other measured runs")
    args = cli.parse_args()
    out = args.output.resolve()
    out.relative_to(ROOT / "code/output")
    old = None
    if args.resume_score_boundary:
        old = json.loads((out / "evidence.json").read_text(encoding="utf-8"))
        if not old["passed"] or not old["full_gate"] or args.quick:
            raise ValueError("cannot resume incomplete input evidence")
        allowed = {"code/tb/board/panel_verified_control_candidate/panel_score_transport.sv",
                   "code/tb/board/panel_verified_control_candidate/tb_panel_score_transport.sv"}
        for name, value in old["sources_sha"].items():
            if Path(name).as_posix() not in allowed and sha(ROOT / name) != value:
                raise ValueError("unrelated source changed " + name)
        backup = out / "evidence_before_score_boundary.json"
        if backup.exists():
            raise ValueError("do not repeat boundary recovery")
        backup.write_bytes((out / "evidence.json").read_bytes())
    else:
        out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["PATH"] = str(CAD / "lib") + ";" + str(CAD / "bin") + ";" + env["PATH"]
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    runs = {}
    defs = ROOT / "code/rtl/common/audio_defs_pkg.sv"
    record = {"scope": "isolated verified panel input and transport tests; no formal top/PnR", "full_gate": not args.quick, "passed": False, "volume_math_signed_off": False}
    def run(name, command, cwd, success=True, marker=None, timeout=220):
        log = cwd / (name + ".log")
        if old is not None and not name.startswith("score_"):
            prior = old["runs"].get(name)
            if not prior or sha(log) != prior["log_sha"] or (prior["exit"] == 0) != success:
                raise ValueError("cannot reuse tested prefix " + name)
            if marker and marker not in log.read_text(encoding="utf-8", errors="replace"):
                raise ValueError("old behavior marker missing " + name)
            runs[name] = {**prior, "reused_source_and_log_identity": True}
            print("REUSE measured unchanged run", name, flush=True)
            return
        with log.open("wb") as stream:
            result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        text = log.read_text(encoding="utf-8", errors="replace")
        runs[name] = {"exit": result.returncode, "expected_success": success,
                      "log_sha": sha(log), "command": list(map(str, command))}
        print(name, result.returncode, text[-700:], flush=True)
        if (result.returncode == 0) != success or marker and marker not in text:
            raise RuntimeError("unexpected behavioral result " + name)
    def test(name, top, files, marker, params=(), success=True):
        folder = out / ("score_boundary_verified" if old is not None and name == "score" else name)
        if old is None or name == "score":
            folder.mkdir()
        image = folder / "test.vvp"
        run(name + "_compile", [CAD / "bin/iverilog.exe", "-g2012", "-s", top,
                               *params, "-o", image, defs, *files], folder)
        run(name + "_run", [CAD / "bin/vvp.exe", image], folder, success, marker)
        return folder
    parser = INPUT / "midi_event_parser.sv"
    try:
        for hz in (64000, 50000000):
            test("input" + str(hz), "tb_panel_verified_input",
                 [parser, INPUT / "tb_panel_verified_input.sv"], "PASS verified panel input",
                 ["-Ptb_panel_verified_input.HZ=" + str(hz)])
        test("UART", "tb_panel_uart", [ROOT / "code/rtl/common/uart_rx.sv", parser,
             INPUT / "midi_input_panel_candidate.sv", INPUT / "tb_panel_uart.sv"], "PASS realUART panel")
        test("mod_volume", "tb_panel_mod_volume_isolation", [parser,
             INPUT / "tb_panel_mod_volume_isolation.sv"], "PASS volume/CC1 isolation")
        test("score", "tb_panel_score_transport", [CONTROL / "panel_score_transport.sv",
             CONTROL / "panel_demo_score.sv", CONTROL / "visual_score_tracker_transport.sv",
             CONTROL / "tb_panel_score_transport.sv"], "PASS score transport")
        test("CDC", "tb_panel_visual_command_bridge", [ROOT / "code/rtl/common/reset_sync.sv",
             ROOT / "code/rtl/common/visual_mailbox_cdc.sv", CONTROL / "panel_visual_command_bridge.sv",
             CONTROL / "tb_panel_visual_command_bridge.sv"], "PASS panel CDC")
        test("volume_proposal", "tb_panel_master_volume", [CONTROL / "panel_master_volume_proposal.sv",
             CONTROL / "tb_panel_master_volume.sv"], "PASS volume proposal")
        # Failure must occur AFTER successful elaboration, for the intended reason.
        text = parser.read_text(encoding="utf-8")
        faults = [
          ("duplicate_press", "25:if(high&&!high_b1[channel])", "25:if(high)", "16channel edge count"),
          ("volume_discrete", "!parsed_control && !parsed_volume", "!parsed_control", "1kHz shared"),
          ("no_rate_limit", "continuous_slot_available=!control_locked && control_cooldown==0",
           "continuous_slot_available=!control_locked && 1'b1", "1kHz shared"),
          ("false_mod_cancel", "control_locked && !locked_volume && locked_index == parsed_control_index",
           "control_locked && locked_index == parsed_control_index", "volume cannot cancel"),
        ]
        for name, before, after, reason in faults:
            if before not in text:
                raise ValueError("mutant anchor missing " + name)
            path = out / (name + ".sv")
            generated = text.replace(before, after).encode("utf-8")
            if old is not None:
                if path.read_bytes() != generated:
                    raise ValueError("mutant source identity changed " + name)
            else:
                path.write_bytes(generated)
            bench = "tb_panel_mod_volume_isolation" if name == "false_mod_cancel" else "tb_panel_verified_input"
            test(name, bench, [path, INPUT / (bench + ".sv")], reason, success=False)
        if not args.quick:
            frozen = subprocess.check_output(["git", "show", "de68038:code/rtl/input/midi_input/midi_event_parser.sv"], cwd=ROOT)
            if hashlib.sha256(frozen).hexdigest() != "834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6":
                raise ValueError("frozen parser identity mismatch")
            reference = out / "original.sv"
            reference.write_bytes(frozen.replace(b"module midi_event_parser #(", b"module midi_event_parser_frozen #(", 1))
            bench = out / "tb_miter.sv"
            original_tb = (ROOT / "code/tb/common/midi_scheduler_setup_review/tb_m2_parser_miter.sv").read_text(encoding="utf-8")
            bench.write_text(original_tb.replace("i==3?3:8", "i==3?16:8"), encoding="utf-8", newline="\n")
            test("disabled_miter", "tb_m2_parser_miter", [parser, reference, bench], "lane=3")
        record["passed"] = True
        record["score_boundary_rerun_after_two_source_changes"] = old is not None
        print("PASS isolated panel full_gate=" + str(not args.quick) + "; volume math remains proposed; no bitstream", flush=True)
        return 0
    finally:
        record["runs"] = runs
        record["sources_sha"] = {str(path.relative_to(ROOT)): sha(path)
            for folder in (INPUT, CONTROL) for path in folder.glob("*.sv")}
        (out / "evidence.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    raise SystemExit(main())
