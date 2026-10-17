"""Bounded T060 counter audit, two complete negatives and synthetic units only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from closure_audit import DOC, ROOT, identity

HERE = Path(__file__).resolve().parent


def dump(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def protected_paths():
    manifest = json.loads((DOC / "ROUTER_EVIDENCE_MANIFEST_20261010.json").read_text(encoding="utf-8"))
    paths = {Path(i["path"]) for i in manifest["frozen_inputs"]}
    paths.update(p for p in DOC.iterdir() if p.is_file() and not p.name.startswith("CLOSURE_"))
    paths.update(ROOT / p for p in (
        "code/rtl/board/electronic_piano_top.sv", "code/rtl/common/audio_defs_pkg.sv",
        "code/constraints/electronic_piano.cst", "code/docs/模块接口规范.md",
        "code/docs/验证记录.md", "code/docs/技术决策记录.md",
        "code/docs/任务看板.md", "code/docs/当前状态.md"))
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    scope = ROOT / "code/output"
    if not out.is_relative_to(scope) or out == scope:
        raise ValueError("CLOSURE_OUTPUT_SCOPE")
    out.mkdir(parents=True, exist_ok=False)
    begin = time.monotonic()
    report = dict(status="FAIL", exit_code=1, t060_complete=False, steps=[],
                  limits=dict(total_seconds=300, step_seconds=90),
                  new_rtl_simulation=False, new_gowin_run=False,
                  new_pcm_math_replay=False)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")

    def command(label, argv, expected=0, diagnostic=None):
        elapsed = time.monotonic() - begin
        timeout = min(90, 300 - elapsed)
        if timeout <= 0:
            raise ValueError("CLOSURE_TOTAL_TIMEOUT")
        start = time.monotonic()
        timed_out = False
        with (out / (label + ".stdout.bin")).open("xb") as stdout, (out / (label + ".stderr.bin")).open("xb") as stderr:
            try:
                process = subprocess.run(argv, cwd=ROOT, env=env, stdout=stdout,
                                         stderr=stderr, timeout=timeout, check=False)
                code = process.returncode
            except subprocess.TimeoutExpired:
                code, timed_out = None, True
        elapsed = time.monotonic() - start
        step = dict(label=label, command=argv, cwd=str(ROOT), exit_code=code,
                    expected_exit=expected, timeout_seconds=timeout, timed_out=timed_out,
                    elapsed_seconds=elapsed, stdout=identity(out / (label + ".stdout.bin")),
                    stderr=identity(out / (label + ".stderr.bin")))
        report["steps"].append(step)
        if timed_out or code != expected or elapsed > timeout:
            raise ValueError("CLOSURE_STEP_FAILED:" + label)
        if diagnostic is not None:
            data = json.loads((out / (label + ".stdout.bin")).read_text(encoding="utf-8"))
            if data.get("status") != "REJECTED_CLOSURE" or data.get("diagnostic") != diagnostic:
                raise ValueError("CLOSURE_NEGATIVE_DIAGNOSTIC:" + label)
            step["specified_diagnostic"] = diagnostic

    try:
        protected = protected_paths()
        inputs = [args.bundle_root.resolve() / "original_Golden" / name
                  for name in ("audio_observation.jsonl", "midi_pcm.capture")]
        sources = sorted(HERE.glob("*.py"))
        report["protected_before"] = {str(p): identity(p) for p in protected}
        report["sources_before"] = {str(p): identity(p) for p in sources}
        report["inputs_before"] = {str(p): identity(p) for p in inputs}
        report["python"] = {"path": sys.executable, **identity(Path(sys.executable))}
        command("units12", [sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover",
                            "-s", str(HERE), "-p", "test_closure_audit.py", "-v"])
        command("audit", [sys.executable, "-B", "-X", "utf8", str(HERE / "closure_audit.py"),
                          "audit", "--bundle-root", str(args.bundle_root.resolve())])
        audit = json.loads((out / "audit.stdout.bin").read_text(encoding="utf-8"))
        if audit["status"] != "T060_TWO_COUNTERS_MATCH_PARTIAL" or audit["t060_complete"] is not False:
            raise ValueError("CLOSURE_AUDIT_STATUS")
        dump(out / "audit.json", audit)
        lines = inputs[1].read_text(encoding="utf-8").splitlines()
        if not lines[-1].startswith("END "):
            raise ValueError("CLOSURE_COMPLETE_END_REQUIRED")
        for label, index, diagnostic in (
            ("bad_full_pop_push", 3, "CLOSURE_END_FULL_POP_PUSH"),
            ("bad_edge_events", 5, "CLOSURE_END_EDGE_EVENTS"),
        ):
            changed = list(lines)
            end = changed[-1].split()
            end[index] = str(int(end[index]) + 1)
            changed[-1] = " ".join(end)
            path = out / (label + ".capture")
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write("\n".join(changed) + "\n")
            command(label, [sys.executable, "-B", "-X", "utf8", str(HERE / "closure_audit.py"),
                            "check", "--jsonl", str(inputs[0]), "--f-capture", str(path)],
                    expected=1, diagnostic=diagnostic)
        report["protected_after"] = {str(p): identity(p) for p in protected}
        report["sources_after"] = {str(p): identity(p) for p in sources}
        report["inputs_after"] = {str(p): identity(p) for p in inputs}
        for prefix in ("protected", "sources", "inputs"):
            if report[prefix + "_before"] != report[prefix + "_after"]:
                raise ValueError("CLOSURE_IDENTITY_DRIFT:" + prefix)
        if time.monotonic() - begin > 300:
            raise ValueError("CLOSURE_TOTAL_TIMEOUT")
        report.update(status="T060_COUNTER_AUDIT_L1_PASS_PARTIAL", exit_code=0,
                      tests_run=12, complete_negative_captures=2,
                      artifact_sha={p.name: identity(p) for p in out.iterdir() if p.is_file()})
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    report["elapsed_seconds"] = time.monotonic() - begin
    dump(out / "receipt.json", report)
    print(json.dumps({k: report[k] for k in ("status", "exit_code", "elapsed_seconds", "t060_complete")}))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
