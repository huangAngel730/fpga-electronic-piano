"""Recheck sealed T058 captures only; no RTL/synthesis/device execution."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
BENCH = ROOT / "code/tb/input/pcm_waveform_candidate"
DOCS = ROOT / "code/docs/hardware/pcm_waveform_v1"
RUNNER = ROOT / "code/scripts/run_m3_pcm_waveform_acceptance.py"
sys.dont_write_bytecode = True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    out = args.output.resolve()
    if (out.exists() or not out.is_relative_to((ROOT / "code/output").resolve())
            or not out.name.startswith("m3_wave_checker_repair_")):
        cli.error("require new code/output/m3_wave_checker_repair_* directory")
    out.mkdir(parents=True)
    started = time.monotonic()
    receipt = {"passed": False, "scope": "sealed capture offline checker repair only",
               "runs": {}, "cases": {}, "new_rtl_runs": 0, "new_synthesis_runs": 0}
    sources = [BENCH / "reference.py", RUNNER, Path(__file__).resolve()]
    receipt["source_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sources}

    def run(label, command):
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True,
                                timeout=min(60, max(1, 300 - (time.monotonic() - started))),
                                check=False)
        for stream, data in (("stdout", result.stdout), ("stderr", result.stderr)):
            (out / (label + "." + stream + ".log")).write_bytes(data)
        receipt["runs"][label] = {"command": list(map(str, command)), "exit": result.returncode,
                                  "stdout_sha256": sha(result.stdout), "stderr_sha256": sha(result.stderr)}
        print(label, "exit", result.returncode, flush=True)
        return result.returncode, (result.stdout + result.stderr).decode("utf-8", errors="replace")

    def check(label, content, reason=None):
        path = out / (label + ".txt")
        path.write_bytes(content.encode("ascii"))
        code, text = run(label, [sys.executable, "-B", "-X", "utf8", RUNNER, "--check-capture", path])
        if code != (1 if reason else 0) or (reason and reason not in text):
            raise ValueError("CHECK_RESULT " + label + " " + text[:300])
        receipt["cases"][label] = {"capture_sha256": sha(path.read_bytes()), "exit": code,
                                    "reason": reason, "bytes": path.stat().st_size}
        if not reason:
            receipt["summary"] = json.loads(text)

    try:
        meta = json.loads((DOCS / "evidence/raw_manifest.json").read_text(encoding="utf-8"))
        raw = {}
        for name, item in meta.items():
            data = base64.b64decode((DOCS / "evidence" / name).read_bytes())
            if sha(data) != item["raw_sha256"] or len(data) != item["raw_bytes"]:
                raise ValueError("LEGACY_RAW_IDENTITY " + name)
            raw[name.removesuffix(".b64")] = data
        original = json.loads(raw["acceptance/receipt.json"])
        receipt["original_source_sha256"] = original["source_sha256"]
        receipt["original_raw_manifest_sha256"] = sha((DOCS / "evidence/raw_manifest.json").read_bytes())
        for name, expected in original["source_sha256"].items():
            if name.endswith("/reference.py"):
                code, _ = run("legacy_reference_snapshot", ["git", "show", "4739e39:" + name])
                snapshot = (out / "legacy_reference_snapshot.stdout.log").read_bytes()
                if code or sha(snapshot) != expected:
                    raise ValueError("LEGACY_REFERENCE_SNAPSHOT")
                (out / "legacy_reference.py").write_bytes(snapshot)
            elif sha((ROOT / name).read_bytes()) != expected:
                raise ValueError("FROZEN_SOURCE_IDENTITY " + name)
        # The original receipts, captures and compiler/run logs remain original.
        for label, reason in (("positive", None), ("signed_wrong", "PIXEL_REFERENCE"),
                              ("torn_front", "STATE_REFERENCE")):
            for suffix in ("_compile", "_simulate"):
                step = original["runs"][label + suffix]
                if step["exit"] or sha(raw["acceptance/" + label + suffix + ".stdout.log"]) != step["stdout_sha256"]:
                    raise ValueError("LEGACY_RUN_IDENTITY")
            content = raw["acceptance/" + label + "/capture.txt"].decode("ascii")
            check(label, content, reason)
        positive = raw["acceptance/positive/capture.txt"].decode("ascii")
        lines = positive.splitlines()
        first_directed = next(i for i, line in enumerate(lines) if line.startswith("I ")
                              and line.split()[3] == "-8388608")
        first_restart = next(i for i, line in enumerate(lines) if line.startswith("T "))
        first_publish = next(i for i, line in enumerate(lines) if line.startswith("V "))
        first_reset = next(i for i, line in enumerate(lines) if line.startswith("R "))

        def replace_line(index, transform):
            copy = lines.copy()
            copy[index] = transform(copy[index])
            return "\n".join(copy) + "\n"

        def field(index, position, value):
            def transform(line):
                parts = line.split()
                parts[position] = str(value)
                return " ".join(parts)
            return replace_line(index, transform)

        damages = {"empty": ("", "CAPTURE_HEADER_OR_END"),
                   "truncated": ("\n".join(lines[:-1]) + "\n", "CAPTURE_HEADER_OR_END")}
        for value in (4033935, 4033937, 0, 999999999):
            damages["end_checks_" + str(value)] = (field(-1, 1, value), "EXACT_CHECK_COUNT")
        for label, position, value in (("pcm_legal", 3, 8388607), ("right_legal", 4, 1),
                                        ("seq_legal", 2, 10), ("cycle", 1, 999),
                                        ("restart_bit", 5, 1)):
            damages[label] = (field(first_directed, position, value), "STIMULUS_IDENTITY")
        for label, index in (("input", first_directed), ("restart", first_restart),
                             ("publish", first_publish), ("reset", first_reset)):
            copy = lines.copy()
            del copy[index]
            damages["missing_" + label] = ("\n".join(copy) + "\n", "STIMULUS_IDENTITY")
            copy = lines.copy()
            copy.insert(index, copy[index])
            damages["duplicate_" + label] = ("\n".join(copy) + "\n", "STIMULUS_IDENTITY")
        damages["wrong_publish"] = (field(first_publish, 2, 0), "STIMULUS_IDENTITY")
        damages["wrong_restart"] = (field(first_restart, 1, 99), "STIMULUS_IDENTITY")
        last_input = max(j for j, row in enumerate(lines) if row.startswith("I "))
        last_record = max(j for j, row in enumerate(lines) if row.startswith(("R ", "T ", "V ", "I ")))
        damages["missing_last_input"] = ("\n".join(line for i, line in enumerate(lines)
            if i != last_input) + "\n", "STIMULUS_IDENTITY")
        damages["missing_last_record"] = ("\n".join(line for i, line in enumerate(lines)
            if i != last_record and not line.startswith("L 7 "))
            + "\n", "STIMULUS_COMPLETENESS")
        row_index = next(i for i, line in enumerate(lines) if line.startswith("L "))
        damages["row_hash"] = (field(row_index, 3, 0), "PIXEL_REFERENCE")
        damages["frame_count"] = (field(-1, 5, 7), "END_COVERAGE")
        damages["counter"] = (field(-1, 6, 12345), "END_COUNTERS")
        damages["unknown"] = (positive.replace("HEADER T058 1", "HEADER T058 1\nGARBAGE"), "UNKNOWN_OR_MALFORMED_RECORD")
        for label, (content, reason) in damages.items():
            if content == positive:
                raise ValueError("DAMAGE_ANCHOR " + label)
            check("damage_" + label, content, reason)
        receipt["old_evidence_raw_files_verified"] = len(raw)
        receipt["damaged_captures_rejected"] = len(damages)
        if any(sha(p.read_bytes()) != receipt["source_sha256"][p.relative_to(ROOT).as_posix()] for p in sources):
            raise ValueError("SOURCE_CHANGED_DURING_RUN")
        receipt["passed"] = True
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
        receipt["error"] = str(error)
        print("FAIL", error, flush=True)
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PASS offline repair" if receipt["passed"] else "FAIL offline repair", flush=True)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
