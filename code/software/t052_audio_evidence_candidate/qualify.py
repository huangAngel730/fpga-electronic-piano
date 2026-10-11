"""Bounded software qualification and replayable seal; no RTL/EDA/device access."""

import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

import evidence as tool
import test_evidence as fixture


ROOT = tool.ROOT
HERE = Path(__file__).resolve().parent
DOC = ROOT / "code/docs/hardware/t052_audio_evidence_v1"
STATUS = "SOFTWARE_QUALIFIED_SYNTHETIC_ONLY_T052_PARTIAL"
SHARED = ("code/rtl/board/electronic_piano_top.sv", "code/rtl/common/audio_defs_pkg.sv",
          "code/constraints/electronic_piano.cst", "code/docs/模块接口规范.md",
          "code/docs/验证记录.md", "code/docs/技术决策记录.md",
          "code/docs/任务看板.md", "code/docs/当前状态.md")


def digest_paths(paths):
    return {str(p.resolve()): tool.sha(p.read_bytes()) for p in sorted(paths)}


def sources():
    return list(HERE.glob("*.py")) + list(HERE.glob("*.json"))


def fresh_output(path):
    path = path.resolve()
    path.relative_to(ROOT / "code/output")
    path.mkdir(parents=True, exist_ok=False)
    return path


def run(out, m1_reference):
    begin = time.monotonic()
    source_before = digest_paths(sources())
    protected = [ROOT / p for p in SHARED]
    protected += [tool.MODEL / p for p in tool.REFERENCE_SHA]
    # M1 v2 is an optional read-only inventory, not a prerequisite or a test result.
    if m1_reference is not None:
        protected += list(m1_reference.resolve().glob("*.*"))
    protected_before = digest_paths(protected)
    steps = []
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")

    def command(label, argv, expected):
        remaining = 300 - (time.monotonic() - begin)
        if remaining <= 0:
            raise ValueError("QUALIFICATION_DEADLINE")
        started = time.monotonic()
        timed_out = False
        try:
            result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
                                    timeout=min(60, remaining))
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b"", error.stderr or b"", -1
            timed_out = True
        (out / (label + ".stdout.txt")).write_bytes(stdout)
        (out / (label + ".stderr.txt")).write_bytes(stderr)
        steps.append(dict(label=label, command=argv, cwd=str(ROOT), exit_code=code,
                          expected_exit=expected, timed_out=timed_out,
                          elapsed_seconds=time.monotonic() - started,
                          stdout_sha256=tool.sha(stdout), stderr_sha256=tool.sha(stderr)))
        tool.dump(out / "progress.json", steps)
        if code != expected or timed_out:
            raise ValueError("COMMAND_EXIT:" + label)
        return stdout, stderr

    try:
        command("unit_tests", [sys.executable, "-B", "-X", "utf8",
                str(HERE / "test_evidence.py"), "--receipt", str(out / "unit.json")], 0)
        unit = json.loads((out / "unit.json").read_text(encoding="utf-8"))
        if unit["tests_run"] < 29 or any(unit[k] for k in ("errors", "failures", "skipped")):
            raise ValueError("UNIT_NOT_COMPLETE")
        samples = fixture.synthesis()
        rail = samples.copy()
        rail[3], rail[5] = -32768, 32767
        cases = [
            ("positive_mono16", fixture.encode_pcm([samples]), 0, None),
            ("positive_stereo24", fixture.encode_pcm([fixture.synthesis(bits=24),
              fixture.synthesis(bits=24)], 24), 0, None),
            ("positive_stereo32", fixture.encode_pcm([fixture.synthesis(bits=32),
              [-s for s in fixture.synthesis(bits=32)]], 32), 0, None),
            ("missing_tone", fixture.encode_pcm([fixture.synthesis([263, 431, 659])]),
             2, "TARGET_TONE_LIMIT"),
            ("wrong_frequency", fixture.encode_pcm([fixture.synthesis([263, 431, 659, 1012])]),
             2, "TARGET_TONE_LIMIT"),
            ("silence", fixture.encode_pcm([[0] * 8192]), 2, "SILENT_OR_DC_ONLY"),
            ("right_silent", fixture.encode_pcm([samples, [0] * 8192]),
             2, "SILENT_OR_DC_ONLY"),
            ("dc", fixture.encode_pcm([fixture.synthesis(dc=0.1)]), 2, "DC_LIMIT"),
            ("rails", fixture.encode_pcm([rail]), 2, "DIGITAL_RAIL_LIMIT"),
            ("truncated", fixture.encode_pcm([samples])[:-1], 1, "WAV_RIFF_LENGTH"),
            ("wrong_rate", fixture.encode_pcm([samples], rate=44100),
             1, "WAV_CONFIG_RATE_MISMATCH"),
            ("missing_file", None, 1, "INPUT_NOT_FOUND"),
        ]
        cfg_path = out / "synthetic_config.json"
        cfg_path.write_bytes((HERE / "example_synthetic_config.json").read_bytes())
        observations = []
        for label, raw, expected, diagnostic in cases:
            wav, result_dir = out / (label + ".wav"), out / label
            if raw is not None:
                wav.write_bytes(raw)
            _, stderr = command(label, [sys.executable, "-B", "-X", "utf8",
                str(HERE / "evidence.py"), "--wav", str(wav), "--config", str(cfg_path),
                "--output", str(result_dir)], expected)
            if expected in (0, 2):
                report = json.loads((result_dir / "analysis.json").read_text(encoding="utf-8"))
                reasons = {r for channel in report["channels"] for r in channel["reasons"]}
                if (report["criteria_met"] != (expected == 0)
                        or any(report[k] for k in ("physical_validation", "t052_complete",
                           "independent_voice_count_proven", "provenance_verified"))
                        or (diagnostic is not None and diagnostic not in reasons)):
                    raise ValueError("WRONG_SEMANTIC_RESULT:" + label)
                replay, _ = tool.analyze(raw, cfg_path.read_bytes())
                if replay != report:
                    raise ValueError("CLI_API_REPLAY:" + label)
            elif diagnostic not in stderr.decode("utf-8", errors="replace"):
                raise ValueError("WRONG_INPUT_DIAGNOSTIC:" + label)
            observations.append(dict(label=label, expected_exit=expected,
                                     diagnostic=diagnostic, input_kind="synthetic_only"))
        source_after, protected_after = digest_paths(sources()), digest_paths(protected)
        if source_before != source_after or protected_before != protected_after:
            raise ValueError("SOURCE_OR_PROTECTED_CHANGED")
        outputs = digest_paths(p for p in out.rglob("*") if p.is_file())
        receipt = dict(status=STATUS, exit_code=0, sources=source_before,
                       sources_after=source_after, protected_before=protected_before,
                       protected_after=protected_after, outputs=outputs, steps=steps,
                       cases=observations, unit_tests=unit["tests_run"],
                       elapsed_seconds=time.monotonic() - begin,
                       input_kind="synthetic_only", physical_validation=False,
                       t052_complete=False, new_RTL_run=False, EDA_run=False)
        tool.dump(out / "receipt.json", receipt)
        print(json.dumps({k: receipt[k] for k in ("status", "exit_code", "unit_tests",
                                                 "elapsed_seconds")}))
    except Exception as error:
        tool.dump(out / "receipt.json", dict(status="FAIL", exit_code=1, error=str(error),
                  steps=steps, sources=source_before, protected_before=protected_before))
        raise


def verify(package):
    manifest = tool.load_json((package / "manifest.json").read_bytes())
    raw = (package / "evidence.zip").read_bytes()
    if tool.sha(raw) != manifest["zip_sha256"]:
        raise ValueError("ARCHIVE_SHA")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if archive.testzip() or len(names) != len(set(names)) or set(names) != set(manifest["members"]):
            raise ValueError("ZIP_MEMBERS")
        for name, item in manifest["members"].items():
            if (name.startswith("/") or ".." in Path(name).parts
                    or ":" in name or "\\" in name):
                raise ValueError("UNSAFE_MEMBER")
            data = archive.read(name)
            if len(data) != item["bytes"] or tool.sha(data) != item["sha256"]:
                raise ValueError("MEMBER_SHA:" + name)
        receipt = tool.load_json(archive.read(manifest["receipt"]))
        if (receipt["status"] != STATUS or receipt["exit_code"] != 0
                or receipt["sources"] != receipt["sources_after"]
                or receipt["protected_before"] != receipt["protected_after"]
                or receipt["unit_tests"] < 29 or receipt["physical_validation"]
                or receipt["t052_complete"] or len(receipt["steps"]) != 13):
            raise ValueError("UNQUALIFIED_RECEIPT")
        sealed_root = Path(manifest["repository_at_seal"])
        for path, digest in dict(receipt["sources"], **receipt["outputs"]).items():
            if tool.sha(archive.read(Path(path).relative_to(sealed_root).as_posix())) != digest:
                raise ValueError("RECEIPT_SHA:" + path)
        for path, digest in receipt["sources"].items():
            current = ROOT / Path(path).relative_to(sealed_root)
            if tool.sha(current.read_bytes()) != digest:
                raise ValueError("CURRENT_SOURCE_IDENTITY:" + path)
        run_dir = Path(manifest["receipt"]).parent.as_posix()
        for step in receipt["steps"]:
            if step["exit_code"] != step["expected_exit"] or step["timed_out"]:
                raise ValueError("STEP_EXIT")
            for stream in ("stdout", "stderr"):
                data = archive.read(run_dir + "/" + step["label"] + "." + stream + ".txt")
                if tool.sha(data) != step[stream + "_sha256"]:
                    raise ValueError("STEP_LOG_SHA")
        replayed = 0
        for case in receipt["cases"]:
            if case["expected_exit"] not in (0, 2):
                continue
            label = case["label"]
            result, _ = tool.analyze(archive.read(run_dir + "/" + label + ".wav"),
                                    archive.read(run_dir + "/synthetic_config.json"))
            original = tool.load_json(archive.read(run_dir + "/" + label + "/analysis.json"))
            if result != original:
                raise ValueError("SEALED_REPLAY:" + label)
            replayed += 1
    return dict(status="SEAL_AND_WAV_REPLAY_PASS", replayed=replayed,
                members=len(names), zip_sha256=tool.sha(raw), physical_validation=False,
                t052_complete=False)


def seal(run_dir, package, history):
    run_dir = run_dir.resolve()
    run_dir.relative_to(ROOT / "code/output")
    receipt = tool.load_json((run_dir / "receipt.json").read_bytes())
    if receipt["status"] != STATUS:
        raise ValueError("UNQUALIFIED_RUN")
    package = package.resolve()
    package.relative_to(DOC)
    package.mkdir(parents=True, exist_ok=False)
    paths = list(run_dir.rglob("*")) + sources() + list(DOC.glob("*.md"))
    for previous in history or []:
        previous = previous.resolve()
        previous.relative_to(ROOT / "code/output")
        if tool.load_json((previous / "receipt.json").read_bytes())["status"] != "FAIL":
            raise ValueError("HISTORY_NOT_FAILED_RUN")
        paths += list(previous.rglob("*"))
    paths += [tool.MODEL / p for p in tool.REFERENCE_SHA]
    payload = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in paths if p.is_file()}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
    raw = stream.getvalue()
    (package / "evidence.zip").write_bytes(raw)
    tool.dump(package / "manifest.json", dict(schema=1, zip_sha256=tool.sha(raw),
         repository_at_seal=str(ROOT),
         zip_bytes=len(raw), receipt=(run_dir / "receipt.json").relative_to(ROOT).as_posix(),
         members={name: dict(bytes=len(data), sha256=tool.sha(data))
                  for name, data in sorted(payload.items())},
         publication_state_at_seal="not_yet_committed_or_pushed", physical_validation=False,
         note="Integrity/replay seal, not a signature or authenticated physical capture"))
    tool.dump(package / "verification.json", verify(package))
    print(json.dumps(verify(package)))


def seal_selftest(package, output):
    """Tamper only private temporary copies; never overwrite the original seal."""
    original_manifest = (package / "manifest.json").read_bytes()
    original_archive = (package / "evidence.zip").read_bytes()
    outcomes = []
    with tempfile.TemporaryDirectory(prefix="t052_seal_negative_") as directory:
        target = Path(directory)
        for mode, expected in (("archive_flip", "ARCHIVE_SHA"),
                               ("member_removed", "ZIP_MEMBERS"),
                               ("forged_analysis", "SEALED_REPLAY")):
            manifest = tool.load_json(original_manifest)
            raw = original_archive
            if mode == "archive_flip":
                raw = raw[:-1] + bytes([raw[-1] ^ 1])
            else:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    payload = {name: archive.read(name) for name in archive.namelist()}
                if mode == "member_removed":
                    payload.pop(next(iter(payload)))
                else:
                    run_dir = Path(manifest["receipt"]).parent.as_posix()
                    analysis_name = run_dir + "/positive_mono16/analysis.json"
                    report = tool.load_json(payload[analysis_name])
                    report["physical_validation"] = True
                    payload[analysis_name] = (json.dumps(report) + "\n").encode()
                    receipt = tool.load_json(payload[manifest["receipt"]])
                    key = next(p for p in receipt["outputs"]
                               if p.replace("\\", "/").endswith("positive_mono16/analysis.json"))
                    receipt["outputs"][key] = tool.sha(payload[analysis_name])
                    payload[manifest["receipt"]] = (json.dumps(receipt) + "\n").encode()
                    # Re-signing an entire manifest is still insufficient: replay differs.
                    manifest["members"] = {name: dict(bytes=len(data), sha256=tool.sha(data))
                                           for name, data in payload.items()}
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                    for name, data in payload.items():
                        archive.writestr(name, data)
                raw = stream.getvalue()
                manifest["zip_sha256"] = tool.sha(raw)
            (target / "evidence.zip").write_bytes(raw)
            tool.dump(target / "manifest.json", manifest)
            try:
                verify(target)
            except ValueError as error:
                if not str(error).startswith(expected):
                    raise
                outcomes.append(dict(case=mode, exit_code=1, diagnostic=str(error)))
            else:
                raise ValueError("TAMPER_ACCEPTED:" + mode)
    if (original_archive != (package / "evidence.zip").read_bytes()
            or original_manifest != (package / "manifest.json").read_bytes()):
        raise ValueError("ORIGINAL_SEAL_CHANGED")
    tool.dump(output, dict(status="THREE_SEAL_TAMPERS_REJECTED", exit_code=0,
                           cases=outcomes, original_zip_sha256=tool.sha(original_archive)))
    print("THREE_SEAL_TAMPERS_REJECTED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "seal", "verify", "selftest"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--m1-reference", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--history", type=Path, nargs="*")
    parser.add_argument("--package", type=Path, default=DOC / "EVIDENCE_20261011")
    args = parser.parse_args()
    if args.mode == "run":
        run(fresh_output(args.output), args.m1_reference)
    elif args.mode == "seal":
        seal(args.run, args.package, args.history)
    elif args.mode == "verify":
        print(json.dumps(verify(args.package)))
    else:
        if args.output.exists():
            raise ValueError("REFUSE_EXISTING_SELFTEST_OUTPUT")
        seal_selftest(args.package, args.output)


if __name__ == "__main__":
    main()
