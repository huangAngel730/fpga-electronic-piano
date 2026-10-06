"""Review an M1 138K/40MHz audio-acceptance ZIP against real captures."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def output_path(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to((ROOT / "code/output").resolve())
    if resolved.exists():
        raise FileExistsError("REFUSE_OVERWRITE " + str(resolved))
    return resolved


def safe_extract(archive_path: Path, destination: Path) -> dict[str, object]:
    archive_sha = sha256(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP_CRC")
        files = [item for item in archive.infolist() if not item.is_dir()]
        roots = {PurePosixPath(item.filename).parts[0] for item in files}
        if len(roots) != 1:
            raise ValueError("ZIP_ROOT")
        root = next(iter(roots)) + "/"
        manifest = json.loads(archive.read(root + "PACKAGE_MANIFEST.json"))
        for relative, record in manifest["files"].items():
            data = archive.read(root + relative)
            if (
                len(data) != record["bytes"]
                or hashlib.sha256(data).hexdigest() != record["sha256"]
            ):
                raise ValueError("PACKAGE_MANIFEST " + relative)
        for item in files:
            relative = PurePosixPath(item.filename.removeprefix(root))
            if relative.is_absolute() or ".." in relative.parts or ":" in str(relative):
                raise ValueError("ZIP_PATH " + item.filename)
            target = (destination / Path(*relative.parts)).resolve()
            target.relative_to(destination.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item.filename))
    return {
        "archive_sha256": archive_sha,
        "member_count": len(files),
        "manifest_file_count": len(manifest["files"]),
        "manifest": manifest,
    }


def run_case(
    name: str,
    command: list[object],
    cwd: Path,
    output: Path,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    result = subprocess.run(
        list(map(str, command)),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
        check=False,
    )
    log = output / "logs" / (name + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(result.stdout)
    return {
        "exit_code": result.returncode,
        "command": list(map(str, command)),
        "log": log.relative_to(output).as_posix(),
        "log_sha256": sha256(log),
    }


def mutation_rows(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    def changed(function):
        data = copy.deepcopy(rows)
        function(data)
        return data

    def first(data, tag):
        return next(index for index, row in enumerate(data) if row["tag"] == tag)

    def duplicate(tag):
        def apply(data):
            index = first(data, tag)
            data.insert(index + 1, copy.deepcopy(data[index]))

        return apply

    cases: dict[str, list[dict[str, object]]] = {
        "empty": [],
        "meta_only": [copy.deepcopy(rows[0])],
        "missing_end": copy.deepcopy(rows[:-1]),
        "wrong_sys_hz": changed(lambda data: data[0].update(sys_hz=50_000_000)),
        "wrong_sample_hz": changed(lambda data: data[0].update(sample_hz=44_100)),
        "duplicate_request": changed(duplicate("REQUEST")),
        "duplicate_commit": changed(duplicate("COMMIT")),
    }
    cases["orphan_commit"] = changed(
        lambda data: data[first(data, "COMMIT")].update(request_id=1_000_000)
    )
    for tag in ("REQUEST", "COMMIT", "STATE", "RESET"):
        cases["wrong_end_" + tag.lower()] = changed(
            lambda data, key=tag: data[-1]["counts"].update(
                {key: data[-1]["counts"][key] + 1}
            )
        )
    cases["pcm_out_of_range"] = changed(
        lambda data: data[first(data, "COMMIT")].update(pcm_left=1 << 23)
    )

    def corrupt_level(data):
        index = next(
            index
            for index, row in enumerate(data)
            if row["tag"] == "STATE" and int(row["level_q16"], 16) > 0
        )
        value = (int(data[index]["level_q16"], 16) + (3 << 16)) & 0xFFFFFFFF
        data[index]["level_q16"] = f"{value:08x}"

    cases["adsr_level_plus3"] = changed(corrupt_level)

    def no_states(data):
        data[:] = [row for row in data if row["tag"] != "STATE"]
        data[-1]["counts"]["STATE"] = 0

    cases["no_states_with_matching_end"] = changed(no_states)

    def remove_first_reset(data):
        data.pop(first(data, "RESET"))
        data[-1]["counts"]["RESET"] -= 1

    cases["missing_first_reset_adjusted_end"] = changed(remove_first_reset)
    cases["wrong_reset_epoch"] = changed(
        lambda data: data[first(data, "RESET")].update(epoch=99)
    )

    def corrupt_state(field, value):
        return lambda data: data[first(data, "STATE")].update({field: value})

    cases["wrong_pending_request_id"] = changed(
        corrupt_state("pending_request_id", 999_999)
    )
    cases["wrong_dds_fcw"] = changed(corrupt_state("dds_fcw", "deadbeef"))
    cases["wrong_phase_acc"] = changed(corrupt_state("phase_acc", "12345678"))
    cases["wrong_table"] = changed(corrupt_state("table", 99))
    cases["wrong_envelope_field"] = changed(corrupt_state("envelope", 32767))

    def unknown_record(data):
        data.insert(-1, {"tag": "CORRUPT", "value": 1})

    cases["unknown_record"] = changed(unknown_record)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = output_path(args.output)
    output.mkdir(parents=True)
    package_dir = output / "package"
    package = safe_extract(args.package.resolve(), package_dir)
    acceptance = package_dir / "code/model/acceptance_138k40"
    model = package_dir / "code/model"
    observation = args.observation.resolve()
    capture = args.capture.resolve()
    if not observation.is_file() or not capture.is_file():
        raise FileNotFoundError("REAL_CAPTURE_MISSING")

    normal_env = os.environ.copy()
    normal_env["PYTHONDONTWRITEBYTECODE"] = "1"
    restored_env = normal_env.copy()
    restored_env["PYTHONPATH"] = str(model)
    python = [sys.executable, "-B", "-X", "utf8"]
    runs = {
        "capture_contract_direct": run_case(
            "capture_contract_direct",
            python + ["capture_contract.py"],
            acceptance,
            output,
            normal_env,
        ),
        "adsr_direct": run_case(
            "adsr_direct", python + ["adsr_acceptance.py"], acceptance, output, normal_env
        ),
        "adsr_with_model_path": run_case(
            "adsr_with_model_path",
            python + ["adsr_acceptance.py"],
            acceptance,
            output,
            restored_env,
        ),
        "builtin_counterexamples": run_case(
            "builtin_counterexamples",
            python + ["audio_acceptance_138k40.py", "--test-counterexamples"],
            acceptance,
            output,
            restored_env,
        ),
        "real_observation": run_case(
            "real_observation",
            python + ["audio_acceptance_138k40.py", "--jsonl", observation],
            acceptance,
            output,
            restored_env,
        ),
        "missing_file_cli": run_case(
            "missing_file_cli",
            python
            + ["audio_acceptance_138k40.py", "--jsonl", output / "missing.jsonl"],
            acceptance,
            output,
            restored_env,
        ),
    }

    sys.path.insert(0, str(ROOT / "code/scripts"))
    from run_platform_audio_capture import audit_pair

    transport_positive = audit_pair(observation, capture, 40_000_000)
    rows = [json.loads(line) for line in observation.read_text(encoding="ascii").splitlines()]
    mutants = output / "mutants"
    mutants.mkdir()
    negative_results = {}
    for name, data in mutation_rows(rows).items():
        path = mutants / (name + ".jsonl")
        path.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in data),
            encoding="ascii",
            newline="\n",
        )
        run = run_case(
            "mutant_" + name,
            python + ["audio_acceptance_138k40.py", "--jsonl", path],
            acceptance,
            output,
            restored_env,
        )
        try:
            audit_pair(path, capture, 40_000_000)
        except (OSError, ValueError, KeyError, IndexError) as error:
            transport = {"rejected": True, "reason": str(error)}
        else:
            transport = {"rejected": False, "reason": "accepted"}
        negative_results[name] = {
            "m1_rejected": run["exit_code"] != 0,
            "m1_run": run,
            "transport": transport,
            "jsonl_sha256": sha256(path),
        }

    m1_accepted_invalid = sorted(
        name for name, result in negative_results.items() if not result["m1_rejected"]
    )
    required_failures = []
    if runs["adsr_direct"]["exit_code"] == 0:
        required_failures.append("direct package import unexpectedly passed")
    if runs["adsr_with_model_path"]["exit_code"] != 0:
        required_failures.append("ADSR selftest failed after model path restore")
    if runs["builtin_counterexamples"]["exit_code"] == 0:
        required_failures.append("built-in counterexample unexpectedly passed")
    if runs["real_observation"]["exit_code"] != 0:
        required_failures.append("real observation failed")
    if runs["missing_file_cli"]["exit_code"] == 0:
        required_failures.append("missing file CLI returned zero")
    if m1_accepted_invalid:
        required_failures.append(
            "M1 checker accepted invalid captures: " + ",".join(m1_accepted_invalid)
        )
    result = {
        "date": "2026-10-06",
        "package": package,
        "observation_sha256": sha256(observation),
        "capture_sha256": sha256(capture),
        "transport_positive": transport_positive,
        "runs": runs,
        "negative_case_count": len(negative_results),
        "negative_results": negative_results,
        "m1_rejected_count": sum(
            result["m1_rejected"] for result in negative_results.values()
        ),
        "transport_rejected_count": sum(
            result["transport"]["rejected"] for result in negative_results.values()
        ),
        "m1_accepted_invalid": m1_accepted_invalid,
        "errors": required_failures,
        "real_positive_passed": runs["real_observation"]["exit_code"] == 0,
        "review_passed": not required_failures,
        "production_modified": False,
        "simulation_rerun": False,
        "Gowin_rerun": False,
    }
    dump(output / "review.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["review_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
