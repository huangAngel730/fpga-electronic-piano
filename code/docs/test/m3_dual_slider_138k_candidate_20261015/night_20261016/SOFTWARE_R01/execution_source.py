"""Software-only audit of existing RUN_03 capture; never starts an RTL tool."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
OUT = HERE / "SOFTWARE_R01"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, value):
    with p.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    start = time.monotonic()
    OUT.mkdir(exist_ok=False)
    capture = HERE / "RUN_03/positive/capture.csv"
    visual = HERE / "RUN_03/positive/visual.csv"
    checker = HERE / "check_coexist.py"
    before = {str(p): sha(p) for p in (capture, visual, checker, Path(__file__).resolve(), Path(sys.executable))}
    shutil.copyfile(checker, OUT / checker.name)
    shutil.copyfile(Path(__file__).resolve(), OUT / "execution_source.py")
    spec = importlib.util.spec_from_file_location("owned_coexist_checker", checker)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.check(capture, visual)
    write(OUT / "POSITIVE_CHECK.json", result)
    original = capture.read_text(encoding="ascii").splitlines()
    original_visual = visual.read_text(encoding="ascii").splitlines()
    cases = []
    # All bad inputs below are explicit software waveform mutations. They do
    # not replace the four unexecuted TB fault injection simulations.
    for name, expected in (("swap_serial_ws", "SERIAL_PCM_LSBJ_OR_STEREO"),
                           ("flip_payload_bit", "SERIAL_PCM_LSBJ_OR_STEREO"),
                           ("drop_sys_cycle", "MISSING_OR_DUPLICATE_CYCLE"),
                           ("unknown_pin", "UNKNOWN_OR_NONINTEGER"),
                           ("drop_visual_frame", "D_VISUAL_FRAME_COMPLETENESS")):
        rows = original.copy()
        display = original_visual.copy()
        if name == "swap_serial_ws":
            for i in range(1, len(rows)-1):
                values = rows[i].split(",")
                if values[2] == "1":
                    values[21] = str(1-int(values[21]))
                    rows[i] = ",".join(values)
        elif name in ("flip_payload_bit", "unknown_pin"):
            for i in range(2, len(rows)-1):
                prev = rows[i-1].split(",")
                values = rows[i].split(",")
                if int(values[0]) > 5000 and values[20] == "1" and prev[20] == "0" and values[22] == "1":
                    values[22] = "0" if name == "flip_payload_bit" else "x"
                    rows[i] = ",".join(values)
                    break
        elif name == "drop_sys_cycle":
            del rows[5000]
        else:
            for i, line in enumerate(display):
                if line.startswith("FRAME,"):
                    del display[i]
                    break
        bad_audio = OUT / (name + ".csv")
        bad_visual = OUT / (name + ".visual.csv")
        bad_audio.write_text("\n".join(rows)+"\n", encoding="ascii")
        bad_visual.write_text("\n".join(display)+"\n", encoding="ascii")
        try:
            module.check(bad_audio, bad_visual)
            raise RuntimeError("MUTATION_NOT_REJECTED:" + name)
        except ValueError as exc:
            diagnostic = str(exc)
            if not diagnostic.startswith(expected):
                raise RuntimeError("WRONG_DIAGNOSTIC:" + name + ":" + diagnostic) from exc
            cases.append({"name": name, "evidence_kind": "SYNTHETIC_WAVEFORM_MUTATION",
                          "expected": expected, "actual": diagnostic, "rejected": True,
                          "audio_sha256": sha(bad_audio), "visual_sha256": sha(bad_visual)})
    after = {str(p): sha(p) for p in (capture, visual, checker, Path(__file__).resolve(), Path(sys.executable))}
    write(OUT / "RECEIPT.json", {"passed": before == after, "before": before, "after": after,
        "cases": cases, "elapsed_seconds": time.monotonic()-start,
        "utc": datetime.now(timezone.utc).isoformat(), "rtl_invocations": 0,
        "tb_behavioral_negatives": "UNKNOWN_NOT_EXECUTED_AFTER_THIRD_GROUP_STOP",
        "board_release_allowed": False})
    print(json.dumps({"passed": before == after, "software_bad_cases": len(cases),
        "decoded_stereo_frames": result["decoded_stereo_frames"],
        "visual_audio_coverage": result["visual_audio_coverage"], "rtl_invocations": 0}))


if __name__ == "__main__":
    main()
