"""Seven small designated semantic corruptions of a complete REAL B1 capture."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from b1_check import replay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    replay(raw)
    lines = raw.decode("ascii").splitlines()
    cases = []
    for name, event, column, reason in (
        ("issue_context", "ISSUE", 4, "ISSUE_CONTEXT"),
        ("rom_data", "ROM", 4, "ROM_DATA"),
        ("accept_wrong_generation", "RESULT", 5, "RESULT_ACCEPTANCE"),
        ("returned_payload", "RESULT", 4, "RESULT_OPAQUE_PAYLOAD"),
        ("readback", "READ", 4, "ATOMIC_BANK_READBACK"),
    ):
        copy = list(lines)
        for index, line in enumerate(copy):
            parts = line.split()
            if len(parts) > 2 and parts[0] == "B1" and parts[2] == event:
                if name == "returned_payload" and parts[5] != "1":
                    continue
                parts[column] = format(int(parts[column], 16) ^ 1, "x")
                copy[index] = " ".join(parts)
                break
        else:
            raise ValueError("MISSING_MUTATION_TARGET:" + name)
        cases.append((name, copy, reason))
    missing_rom = [line for line in lines if " ROM_VISIBLE " not in line]
    cases.append(("missing_rom_valid", missing_rom, "ROM_DUPLICATE_OR_EARLY"))
    truncated = [line for line in lines if not line.startswith("B1_END ") and "$finish called" not in line]
    cases.append(("missing_end", truncated, "INCOMPLETE_CAPTURE"))
    args.output.mkdir(exist_ok=False)
    results = []
    checker = Path(__file__).with_name("b1_check.py")
    for name, changed, reason in cases:
        path = args.output / (name + ".capture")
        payload = ("\n".join(changed) + "\n").encode("ascii")
        if payload == raw:
            raise ValueError("UNCHANGED_NEGATIVE")
        path.write_bytes(payload)
        command = [sys.executable, "-B", "-X", "utf8", str(checker), "--input", str(path)]
        result = subprocess.run(command, capture_output=True, timeout=60, check=False)
        (args.output / (name + ".stdout.bin")).write_bytes(result.stdout)
        (args.output / (name + ".stderr.bin")).write_bytes(result.stderr)
        parsed = json.loads(result.stdout)
        if result.returncode != 1 or parsed != {"status": "REJECT", "reason": reason}:
            raise ValueError(f"WRONG_REJECTION:{name}:{result.returncode}:{parsed}")
        results.append({"case": name, "command": command, "exit_code": result.returncode,
                        "reason": reason, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    report = {"positive_input_sha256": hashlib.sha256(raw).hexdigest(), "negative_results": results}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
