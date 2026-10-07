"""Run the unmodified M1 v5 package, real captures and nontruncated negatives."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

from review_m1_138k40_audio_delivery import (
    mutation_rows, output_path, run_case, safe_extract,
)
from run_platform_audio_capture import audit_pair

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extended_mutations(rows):
    cases = mutation_rows(rows)
    active = next(i for i, row in enumerate(rows)
                  if row["tag"] == "STATE" and row["occupied"] == 1
                  and int(row["level_q16"], 16) > 0)

    def changed(fn):
        data = copy.deepcopy(rows)
        fn(data)
        return data

    for name, field, change in (
        ("legal_wrong_fcw", "dds_fcw", lambda v: f"{int(v, 16) ^ 1:08x}"),
        ("legal_wrong_phase", "phase_acc", lambda v: f"{int(v, 16) ^ 1:08x}"),
        ("legal_wrong_table", "table", lambda v: (v + 1) % 4),
        ("legal_wrong_envelope", "envelope", lambda v: v + 1 if v < 32767 else v - 1),
        ("wrong_raw_state", "raw_state", lambda v: 0),
    ):
        cases[name] = changed(lambda d, key=field, fn=change:
                              d[active].update({key: fn(d[active][key])}))

    def duplicate_state(data):
        i = next(i for i, row in enumerate(data) if row["tag"] == "STATE")
        data.insert(i + 1, copy.deepcopy(data[i]))
        data[-1]["counts"]["STATE"] += 1

    def missing_state(data):
        i = next(i for i, row in enumerate(data) if row["tag"] == "STATE")
        data.pop(i)
        data[-1]["counts"]["STATE"] -= 1

    cases["duplicate_state_adjusted_end"] = changed(duplicate_state)
    cases["missing_lane_state_adjusted_end"] = changed(missing_state)
    cases["missing_end_counts"] = changed(lambda d: d[-1].update(counts={}))
    cases["wrong_schema"] = changed(lambda d: d[0].update(schema=99))
    return cases


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--package", type=Path, required=True)
    cli.add_argument("--observation", type=Path, required=True)
    cli.add_argument("--capture", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    out = output_path(args.output)
    out.mkdir(parents=True)
    package = safe_extract(args.package.resolve(), out / "package")
    bench = out / "package/code/model/acceptance_138k40"
    main_script = bench / "audio_acceptance_138k40.py"
    obs, raw = args.observation.resolve(), args.capture.resolve()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    python = [sys.executable, "-B", "-X", "utf8"]
    generated = out / "generated"
    generated.mkdir()
    runs = {}

    def execute(name, arguments, cwd=out):
        result = run_case(name, python + arguments, cwd, out, env)
        print(name, "exit", result["exit_code"], flush=True)
        return result

    for name in ("capture_contract", "adsr_acceptance", "dds_consistency"):
        runs[name] = execute(name, [bench / (name + ".py")])
    runs["builtin_before_generation"] = execute(
        "builtin_before_generation", [main_script, "--test-counterexamples"], generated)
    runs["real_both_capture"] = execute(
        "real_both_capture", [main_script, "--jsonl", obs, "--capture", raw])
    runs["real_json_only_diagnostic"] = execute(
        "real_json_only_diagnostic", [main_script, "--jsonl", obs])
    runs["generation"] = execute(
        "generation", [main_script, "--create-counterexamples", obs], generated)
    runs["builtin_after_generation"] = execute(
        "builtin_after_generation", [main_script, "--test-counterexamples"], generated)
    generated_records = {}
    for path in sorted(generated.glob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        run = execute("generated_" + path.stem, [main_script, "--jsonl", path])
        generated_records[path.name] = {
            "sha256": sha(path), "records": len(records),
            "end_present": bool(records and records[-1]["tag"] == "END"), "run": run,
        }
    rows = [json.loads(line) for line in obs.read_text(encoding="ascii").splitlines()]
    mutants = out / "complete_mutants"
    mutants.mkdir()
    negatives = {}
    for name, records in extended_mutations(rows).items():
        path = mutants / (name + ".jsonl")
        path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n"
                                for row in records), encoding="ascii", newline="\n")
        run = execute("negative_" + name, [main_script, "--jsonl", path])
        negatives[name] = {"sha256": sha(path), "run": run}
    f_negatives = {}
    for name, data in (("empty", b""), ("no_m_records", b"R 1 1\nEND 2487\n"),
                       ("unrecognized_garbage", b"CORRUPT\n")):
        path = out / (name + ".capture")
        path.write_bytes(data)
        run = execute("f_negative_" + name,
                      [main_script, "--jsonl", obs, "--capture", path])
        f_negatives[name] = {"sha256": sha(path), "run": run}
    runs["missing_jsonl"] = execute(
        "missing_jsonl", [main_script, "--jsonl", out / "not_found.jsonl"])
    runs["missing_capture"] = execute(
        "missing_capture", [main_script, "--jsonl", obs, "--capture", out / "not_found.capture"])
    accepted = [name for name, result in negatives.items() if result["run"]["exit_code"] == 0]
    f_accepted = [name for name, result in f_negatives.items() if result["run"]["exit_code"] == 0]
    sources = {path.name: {"bytes": path.stat().st_size, "sha256": sha(path),
                          "listed_in_package_manifest":
                          "code/model/acceptance_138k40/" + path.name in package["manifest"]["files"]}
               for path in sorted(bench.glob("*.py"))}
    errors = []
    if runs["real_both_capture"]["exit_code"] != 0:
        errors.append("original dual-capture positive failed")
    if accepted:
        errors.append("accepted complete JSONL corruption: " + ",".join(accepted))
    if f_accepted:
        errors.append("accepted invalid F capture: " + ",".join(f_accepted))
    if len(generated_records) != 8 or any(not v["end_present"] for v in generated_records.values()):
        errors.append("generated negatives missing/full EOF coverage invalid")
    if runs["missing_jsonl"]["exit_code"] == 0 or runs["missing_capture"]["exit_code"] == 0:
        errors.append("missing-file CLI false pass")
    result = {
        "date": "2026-10-07", "package_sha256": package["archive_sha256"],
        "package_reference_manifest_files": package["manifest_file_count"],
        "acceptance_sources": sources, "observation_sha256": sha(obs), "raw_capture_sha256": sha(raw),
        "independent_transport": audit_pair(obs, raw, 40_000_000), "runs": runs,
        "generated": generated_records, "negative_results": negatives,
        "negative_count": len(negatives), "accepted_jsonl_corruption": accepted,
        "f_negatives": f_negatives, "accepted_invalid_f": f_accepted,
        "errors": errors, "passed": not errors,
        "sources_modified": False, "simulation_rerun": False, "gowin_rerun": False,
    }
    (out / "review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    print(json.dumps({"passed": result["passed"], "errors": errors,
                      "negative_count": len(negatives), "accepted": accepted}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
