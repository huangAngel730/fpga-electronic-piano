"""Bounded real router/audio positive, targeted negatives and Python mutants.

Generates only isolated new test artifacts; original captures and source stay
read-only. Negative success requires exit1 AND the specified diagnostic.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from strict_capture import require

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=sha(raw))


def run(command, output, label):
    begin = time.monotonic()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with (output / (label + ".stdout.bin")).open("xb") as out, (output / (label + ".stderr.bin")).open("xb") as err:
        process = subprocess.run(command, cwd=ROOT, env=env, stdout=out, stderr=err,
                                 timeout=30, check=False)
    elapsed = time.monotonic() - begin
    require(elapsed <= 30, "ROUTER_SUBPROCESS_ELAPSED_LIMIT")
    raw = (output / (label + ".stdout.bin")).read_bytes()
    return dict(command=command, cwd=str(ROOT), exit_code=process.returncode,
                elapsed_seconds=round(elapsed, 6), timeout_seconds=30,
                stdout=identity(output / (label + ".stdout.bin")),
                stderr=identity(output / (label + ".stderr.bin")),
                result=json.loads(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(ROOT / "code/output") and output != ROOT / "code/output", "ROUTER_OUTPUT_SCOPE")
    output.mkdir(parents=True, exist_ok=False)
    begin = time.monotonic()
    report = dict(status="FAIL", t060_complete=False, cases=[])
    code = 1
    try:
        original = args.bundle_root.resolve() / "original_Golden"
        jpath, fpath = original / "audio_observation.jsonl", original / "midi_pcm.capture"
        sources = [identity(p) for p in sorted(HERE.glob("*.py"))]
        report["sources"], report["original_inputs"] = sources, [identity(jpath), identity(fpath)]
        jrows = [json.loads(line) for line in jpath.read_text(encoding="utf-8").splitlines()]
        frows = fpath.read_text(encoding="utf-8").splitlines()
        rom = ROOT / "code/rtl/138K_try/clock_trials_20261005/H_pll_core40_route2/rom"

        def command(j, f, checker=HERE / "router_check.py"):
            return [sys.executable, "-B", "-X", "utf8", str(checker), str(j), str(f), "--rom-root", str(rom)]

        positive = run(command(jpath, fpath), output, "positive")
        report["positive"] = positive
        require(positive["exit_code"] == 0 and positive["result"]["status"] == "ROUTER_AND_AUDIO_MATCH_AWAITING_M2", "ROUTER_POSITIVE_FAILED")

        def negative(name, js, fs, expected):
            require(time.monotonic() - begin < 300, "ROUTER_REGRESSION_TOTAL_LIMIT")
            jp, fp = output / (name + ".jsonl"), output / (name + ".capture")
            jp.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in js) + "\n", encoding="utf-8", newline="\n")
            fp.write_text("\n".join(fs) + "\n", encoding="utf-8", newline="\n")
            require(js[-1] == jrows[-1] and fs[-1] == frows[-1], "ROUTER_NEGATIVE_END_CHANGED")
            result = run(command(jp, fp), output, name)
            result.update(case=name, expected_diagnostic=expected, inputs=[identity(jp), identity(fp)])
            report["cases"].append(result)
            require(result["exit_code"] == 1 and result["result"]["status"] == "REJECTED_ROUTER" and result["result"]["diagnostic"].startswith(expected), "ROUTER_NEGATIVE_WRONG_DIAGNOSTIC:" + name)

        fs = list(frows)
        n = next(i for i, line in enumerate(fs) if line.startswith("N "))
        parts = fs[n].split()
        parts[2] = "2" if parts[2] != "2" else "1"
        fs[n] = " ".join(parts)
        negative("wrong_allocation_lane", jrows, fs, "ROUTER_N_LANE_OR_EDGE")
        for field, token, diagnostic in (("occupancy", 3, "ROUTER_Q_OCCUPANCY_IDENTITY_OR_EDGE"),
                                          ("generation", 6, "ROUTER_Q_OCCUPANCY_IDENTITY_OR_EDGE")):
            fs = list(frows)
            q = next(i for i, line in enumerate(fs) if line.startswith("Q ") and int(line.split()[3], 16))
            parts = fs[q].split()
            parts[token] = f"{int(parts[token], 16) ^ 1:0{len(parts[token])}x}"
            fs[q] = " ".join(parts)
            negative("wrong_q_" + field, jrows, fs, diagnostic)
        js = deepcopy(jrows)
        off = next(r for r in js if r["tag"] == "STATE" and r["note_off"])
        off.update(note_off=0, note_on=1)
        negative("off_changed_to_on", js, frows, "ROUTER_STATE_note_on")
        js = deepcopy(jrows)
        next(r for r in js if r["tag"] == "STATE" and r["note_off"])["cycle"] += 2
        negative("off_wrong_physical_edge", js, frows, "ROUTER_STATE_COUNTER_LABEL")
        js, fs = deepcopy(jrows), list(frows)
        commit = next(r for r in js if r["tag"] == "COMMIT" and r["pcm_left"] == 768)
        commit["pcm_left"] = 769
        for i, line in enumerate(fs):
            parts = line.split()
            if parts[0] == "M" and int(parts[1]) == commit["cycle"]:
                parts[3] = "000301"
                fs[i] = " ".join(parts)
                break
        negative("coherent_pcm_768_to_769", js, fs, "M_PCM_MATH")

        report["mutants"] = []
        for name, old, new, diagnostic in (
                ("newest_instead_of_oldest", "lane = min(range(4), key=lambda i: self.slots[i][\"age\"])",
                 "lane = max(range(4), key=lambda i: self.slots[i][\"age\"])", "ROUTER_N_LANE_OR_EDGE"),
                ("ignore_pedal", "if (s[\"source\"], s[\"channel\"]) in self.pedals:",
                 "if False:  # isolated executable mutant: pedal ignored", "ROUTER_STATE_COUNT")):
            folder = output / name
            folder.mkdir()
            for p in HERE.glob("*.py"):
                raw = p.read_bytes()
                if p.name == "router_model.py":
                    text = raw.decode("utf-8")
                    require(text.count(old) == 1, "ROUTER_MUTATION_ANCHOR")
                    raw = text.replace(old, new).encode("utf-8")
                (folder / p.name).write_bytes(raw)
            result = run(command(jpath, fpath, folder / "router_check.py"), output, name)
            result.update(case=name, expected_diagnostic=diagnostic, mutant_source=identity(folder / "router_model.py"), original_source=identity(HERE / "router_model.py"))
            report["mutants"].append(result)
            require(result["exit_code"] == 1 and result["result"]["status"] == "REJECTED_ROUTER" and result["result"]["diagnostic"].startswith(diagnostic), "ROUTER_MUTANT_WRONG_REJECTION:" + name)
        for item in sources + report["original_inputs"]:
            require(identity(Path(item["path"])) == item, "ROUTER_INPUT_DRIFT")
        require(time.monotonic() - begin <= 300, "ROUTER_REGRESSION_TOTAL_LIMIT")
        report.update(status="ROUTER_REGRESSION_MATCH_AWAITING_M2", negative_cases=6, executable_mutants=2)
        code = 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    report.update(exit_code=code, elapsed_seconds=round(time.monotonic()-begin, 6))
    (output / "receipt.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
