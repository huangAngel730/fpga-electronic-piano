"""Few distinct complete-capture math/identity counterexamples, actual CLI exit1."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from b2_check import check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    check(raw)
    lines = raw.decode("ascii").splitlines()
    if lines[-2].startswith("END ") and "$finish called at " in lines[-1]:
        lines = lines[:-1]
    lane = next(i for i, line in enumerate(lines) if line.startswith("L ") and
                int(line.split()[9]) != 0 and int(line.split()[8]) not in (0, 32767))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = [("phase", lane, 4, "MATH_PHASE"), ("table", lane, 5, "MATH_TABLE"),
             ("FCW", lane, 6, "MATH_FCW"), ("wave", lane, 7, "MATH_WAVE"),
             ("envelope", lane, 8, "MATH_ENVELOPE"), ("gain_pcm", lane, 9, "MATH_GAIN_PCM")]
    result_row = next(i for i in range(lane + 1, len(lines)) if lines[i].startswith("O "))
    cases += [("stereo", result_row, 3, "MATH_STEREO_SATURATION"),
              ("identity", result_row, 10, "FULL_SNAPSHOT_IDENTITY"),
              ("END_count", len(lines)-1, 2, "END_COUNTS_OR_INCOMPLETE_FRAME")]
    reports = []
    checker = Path(__file__).with_name("b2_check.py")
    for name, row, column, reason in cases:
        changed = lines.copy()
        values = changed[row].split()
        hexadecimal = column in (4, 6) and row == lane or name == "identity"
        old = int(values[column], 16 if hexadecimal else 10)
        value = old ^ 1 if name not in ("gain_pcm", "stereo") else old + 256
        values[column] = format(value, "x") if hexadecimal else str(value)
        changed[row] = " ".join(values)
        bad = ("\n".join(changed) + "\n").encode("ascii")
        capture = output / (name + ".capture")
        capture.write_bytes(bad)
        report = output / (name + ".json")
        command = [sys.executable, "-B", "-X", "utf8", str(checker),
                   "--input", str(capture), "--output", str(report)]
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=90, check=False)
        (output / (name + ".stdout.bin")).write_bytes(process.stdout)
        (output / (name + ".stderr.bin")).write_bytes(process.stderr)
        result = json.loads(report.read_text(encoding="utf-8"))
        if process.returncode != 1 or not result.get("reason", "").startswith(reason):
            raise ValueError("NEGATIVE_WRONG_REJECTION:" + name + ":" + str(result))
        reports.append({"name": name, "command": command, "exit_code": process.returncode,
                        "reason": result["reason"], "complete_END_preserved": True,
                        "sha256": hashlib.sha256(bad).hexdigest()})
    summary = {"status": "B2A_NINE_DISTINCT_COUNTEREXAMPLES_PASS", "cases": reports,
               "input_sha256": hashlib.sha256(raw).hexdigest()}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
