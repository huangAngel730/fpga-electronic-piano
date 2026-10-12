"""Run only the bounded standard-library pin-projection software checks."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/hardware/polyphony_frame_acceptance_20261012/pin_projection_20261012"
REFERENCES = [
    ROOT / "code/rtl/audio_out/m2_polyphony_frame_candidate_20261012/premixed_frame_adapter.sv",
    ROOT / "code/rtl/audio_out/pcm_result_hold.sv",
    ROOT / "code/rtl/audio_out/pcm_frame_buffer.sv",
    ROOT / "code/rtl/common/polyphony_scaling_candidate/b2d_event_audio.sv",
    ROOT / "code/rtl/common/m2_n32_clipped_candidate_20261012/b2d_event_audio_clipped.sv",
    ROOT / "code/docs/M2_selectorless唯一综合与clipped后继结果_2026-10-12.md",
]
REFERENCE_SHA256 = {
    "premixed_frame_adapter.sv":
        "d7952a5f986eb8b609cbe657907e418cfe751c6492d6e49469b5e37c390bb56c",
    "pcm_result_hold.sv":
        "7656fd0089efd140de784352d1e7809169240e6a09263c8ce9428298b424d52f",
    "pcm_frame_buffer.sv":
        "f8bc454a2e627809c2f9f9029c1e5128acf2fd543d7fcc2d3d83b50685f40997",
    "b2d_event_audio.sv":
        "5f1a0d2e89fcb6f2d6ff97964e96953c2e9247e828536b521a43327d80c0a0ce",
    "b2d_event_audio_clipped.sv":
        "3fd292ab7a3748f10054ec5eb26d44f20b83880073a220aa6b4ddc2f1a98427f",
}
STDLIB = {"argparse", "ast", "base64", "copy", "hashlib", "io", "json", "os",
          "pathlib", "shutil", "subprocess", "sys", "tempfile", "time",
          "unittest", "zipfile"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def identity(paths):
    return {str(path.resolve()): {"bytes": path.stat().st_size,
                                 "sha256": sha(path.read_bytes())}
            for path in paths}


def audit(paths):
    local = {path.stem for path in paths}
    result = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(item.name.split(".")[0] for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    raise ValueError("RELATIVE_IMPORT_FORBIDDEN")
                names.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                called = ast.unparse(node.func)
                if called in {"eval", "exec", "__import__", "os.system", "os.popen"}:
                    raise ValueError("DYNAMIC_EXEC_FORBIDDEN:" + called)
        extra = names - STDLIB - local
        if extra:
            raise ValueError("DEPENDENCY_OUTSIDE_CLOSURE:" + str(sorted(extra)))
        result[path.name] = sorted(names)
    return result


def run(output):
    output = output.resolve()
    output.relative_to(ROOT / "code/output")
    if output.exists():
        raise ValueError("RUN_REFUSE_OVERWRITE")
    output.mkdir(parents=True)
    start = time.monotonic()
    steps = []
    failure = None
    sources = sorted(HERE.glob("*.py"))
    docs = sorted(DOC.glob("*.md"))
    observed = sources + docs + REFERENCES + [Path(sys.executable)]
    before = identity(observed)
    try:
        for path in REFERENCES[:5]:
            if sha(path.read_bytes()) != REFERENCE_SHA256[path.name]:
                raise ValueError("READONLY_REFERENCE_SHA:" + path.name)
        dump(output / "source_input_before.json", before)
        dump(output / "closure.json", audit(sources))
        snapshot = output / "snapshot"
        snapshot.mkdir()
        for path in sources:
            shutil.copyfile(path, snapshot / path.name)
        refs = output / "readonly_references"
        refs.mkdir()
        for index, path in enumerate(REFERENCES):
            shutil.copyfile(path, refs / (str(index) + "_" + path.name))
        copied_docs = output / "docs"
        copied_docs.mkdir()
        for path in docs:
            shutil.copyfile(path, copied_docs / path.name)
        snapshot_before = identity(sorted(snapshot.glob("*.py")))
        dump(output / "executed_snapshot_before.json", snapshot_before)
        dump(output / "execution_closure.json", audit(sorted(snapshot.glob("*.py"))))

        def command(label, script, arguments, expected=0, diagnostic=None):
            remaining = 300 - (time.monotonic() - start)
            if remaining <= 0:
                raise ValueError("TOTAL_BUDGET_EXHAUSTED")
            limit = min(90, remaining)
            argv = [sys.executable, "-I", "-S", "-B", "-X", "utf8",
                    str(snapshot / script), *arguments]
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONHOME", None)
            begin = time.monotonic()
            try:
                process = subprocess.run(argv, cwd=snapshot, env=environment,
                                         capture_output=True, timeout=limit)
                stdout, stderr = process.stdout, process.stderr
                code, timed_out = process.returncode, False
            except subprocess.TimeoutExpired as error:
                stdout, stderr = error.stdout or b"", error.stderr or b""
                code, timed_out = -1, True
            (output / (label + ".stdout.txt")).write_bytes(stdout)
            (output / (label + ".stderr.txt")).write_bytes(stderr)
            step = {"label": label, "argv": argv, "cwd": str(snapshot),
                    "limit_seconds": limit, "elapsed_seconds": time.monotonic() - begin,
                    "exit_code": code, "expected_exit": expected,
                    "timed_out": timed_out, "diagnostic": diagnostic,
                    "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}
            steps.append(step)
            dump(output / "progress.json", steps)
            print(label + ": exit " + str(code), flush=True)
            if timed_out or code != expected:
                raise ValueError("STEP_EXIT:" + label)
            combined = stdout + stderr
            if diagnostic and diagnostic.encode() not in combined:
                raise ValueError("STEP_DIAGNOSTIC:" + label)
            if time.monotonic() - start > 300:
                raise ValueError("TOTAL_BUDGET_EXCEEDED")

        command("01_projection_tests", "test_projection.py", [])
        corpus = output / "corpus"
        command("02_generate_traces", "vectors.py", ["--output", str(corpus)])
        corpus_before = identity(sorted(corpus.glob("*")))
        dump(output / "trace_input_before.json", corpus_before)
        manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
        for name, item in manifest["positives"].items():
            command("positive_" + name, "projection_check.py",
                    ["--trace", str(corpus / item["file"])])
        for name, item in manifest["negatives"].items():
            command("negative_" + name, "projection_check.py",
                    ["--trace", str(corpus / item["file"])], expected=1,
                    diagnostic=item["diagnostic"])
        command("missing_file_refused", "projection_check.py",
                ["--trace", str(corpus / "MISSING.jsonl")], expected=1,
                diagnostic="PIN_PROJECTION_REJECT")
        command("overwrite_refused", "vectors.py", ["--output", str(corpus)],
                expected=1, diagnostic="VECTORS_REFUSE_OVERWRITE")
        corpus_after = identity(sorted(corpus.glob("*")))
        dump(output / "trace_input_after.json", corpus_after)
        if corpus_before != corpus_after:
            raise ValueError("TRACE_INPUT_CHANGED")
        snapshot_after = identity(sorted(snapshot.glob("*.py")))
        dump(output / "executed_snapshot_after.json", snapshot_after)
        if snapshot_before != snapshot_after:
            raise ValueError("EXECUTED_SOURCE_CHANGED")
    except Exception as error:
        failure = str(error)
    after = identity(observed)
    dump(output / "source_input_after.json", after)
    if before != after and failure is None:
        failure = "SOURCE_OR_REFERENCE_CHANGED"
    elapsed = time.monotonic() - start
    if elapsed > 300 and failure is None:
        failure = "TOTAL_BUDGET_EXCEEDED"
    receipt = {
        "status": "FAIL" if failure else "PIN_PROJECTION_SOFTWARE_L0_L1_PASS",
        "exit_code": int(failure is not None), "error": failure, "steps": steps,
        "elapsed_seconds": elapsed, "total_limit_seconds": 300,
        "per_step_limit_seconds": 90, "source_and_inputs_unchanged": before == after,
        "positive_traces": 2, "complete_negative_traces": 5,
        "raw_qualified_handshake_distinguished": True,
        "pending_held_frame_timing_distinguished": True,
        "software_epoch_mapped": False, "abstract_backpressure_mapped": False,
        "original_b2d_exact_clipped": False,
        "clipped_successor_source_bound": True,
        "level": "L0/L1_SOFTWARE_ONLY", "RTL_run": False, "EDA_run": False,
        "math_verified": False, "physical_verified": False,
        "production_integrated": False, "t060_complete": False,
        "t061_complete": False, "no_retry": True,
    }
    dump(output / "receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return receipt["exit_code"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
