"""Bounded software-only original capture replay, complete PCM counterexamples."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from inventory import ROOT, identity

HERE = Path(__file__).resolve().parent


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write("\n")


def changed(raw, kind, request=1):
    """Change ALL valid edges for one request: remains HOLD-consistent for K.

    Input transactions, phases, FCWs, timing, CASE and complete END are intact.
    The old timing checker MUST accept; only independent PCM math rejects it.
    """
    from b2m_check import FIELDS

    lines = raw.decode("ascii").splitlines()
    modified = []
    for index, line in enumerate(lines):
        fields = line.split()
        if fields and fields[0] == "T":
            row = dict(zip(FIELDS, map(int, fields[1:])))
            if row["rv"] and row["rid"] == request:
                left, right = row["left"], row["right"]
                if kind == "both_1lsb":
                    left, right = left + 1, right + 1
                elif kind == "left_1lsb":
                    left += 1
                elif kind == "right_1lsb":
                    right += 1
                elif kind == "zero_sound":
                    left = right = 0
                elif kind == "wrong_sign":
                    left, right = -left, -right
                elif kind == "wrong_gain_256":
                    left, right = left + 256, right + 256
                else:
                    raise ValueError("B2M_NEGATIVE_KIND")
                require_change = (left, right) != (row["left"], row["right"])
                if not require_change:
                    raise ValueError("B2M_MUTATION_NO_CHANGE")
                row.update(left=left, right=right)
                lines[index] = "T " + " ".join(str(row[key]) for key in FIELDS)
                modified.append(row["cycle"])
    if not modified:
        raise ValueError("B2M_MUTATION_NO_TARGET")
    return ("\n".join(lines) + "\n").encode("ascii"), modified


def main():
    # Closure repair is a separate bounded run, never the old sixteen steps.
    if "--closure-only" in sys.argv:
        from b2m_closure import main as closure_main

        return closure_main(["run", *[a for a in sys.argv[1:] if a != "--closure-only"]])
    if "--legacy-math-replay" not in sys.argv:
        raise ValueError("B2M_USE_CLOSURE_ONLY_OLD_MATH_ALREADY_SIGNED")
    sys.argv.remove("--legacy-math-replay")
    from b2m_inputs import PACKAGE, originals
    from b2m_check import STATUS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out == ROOT / "code/output" or not out.is_relative_to(ROOT / "code/output"):
        raise ValueError("B2M_OUTPUT_SCOPE")
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    report = dict(status="FAIL", exit_code=1, task_complete=False, steps=[],
        new_RTL_simulation=False, new_synthesis=False, new_PnR=False,
        device_operations=False, total_limit_seconds=300, step_limit_seconds=90,
        command=[sys.executable, *sys.argv], profiles=[], negatives=[])
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", B2M_FIXTURE_ROOT=str(out))

    def command(label, argv, expected=0, diagnostic=None):
        timeout = min(90, 300 - (time.monotonic() - start))
        if timeout <= 0:
            raise ValueError("B2M_TOTAL_TIMEOUT")
        begin = time.monotonic()
        timed_out, code = False, None
        stdout_path, stderr_path = out / (label + ".stdout.bin"), out / (label + ".stderr.bin")
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            try:
                code = subprocess.run(argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                                      timeout=timeout, check=False).returncode
            except subprocess.TimeoutExpired:
                timed_out = True
        elapsed = time.monotonic() - begin
        report["steps"].append(dict(label=label, command=argv, cwd=str(ROOT),
            elapsed_seconds=elapsed, timeout_seconds=timeout, timed_out=timed_out,
            exit_code=code, expected_exit=expected,
            stdout=identity(stdout_path), stderr=identity(stderr_path)))
        if timed_out or code != expected or elapsed > timeout:
            raise ValueError("B2M_STEP_FAILED:" + label)
        data = stdout_path.read_bytes()
        if diagnostic and not json.loads(data).get("diagnostic", "").startswith(diagnostic):
            raise ValueError("B2M_NEGATIVE_DIAGNOSTIC:" + label)
        return data

    protected = source_paths = []
    try:
        captures, old_sources, original = originals()
        report["original_seal"] = original
        protected = [ROOT / name for name in old_sources]
        protected += list(PACKAGE.iterdir())
        protected += [ROOT / name for name in (
            "code/rtl/board/electronic_piano_top.sv", "code/rtl/common/audio_defs_pkg.sv",
            "code/constraints/electronic_piano.cst", "code/docs/模块接口规范.md",
            "code/docs/当前状态.md", "code/docs/任务看板.md",
            "code/docs/技术决策记录.md", "code/docs/验证记录.md")]
        protected = sorted(set(protected))
        source_paths = [HERE / name for name in ("b2m_check.py", "b2m_inputs.py", "b2m_run.py", "test_b2m.py")]
        report["protected_before"] = [identity(p) for p in protected]
        report["sources_before"] = [identity(p) for p in source_paths]
        report["python"] = dict(path=sys.executable, bytes=Path(sys.executable).stat().st_size)
        report["original_inputs"] = {}
        for label, item in captures.items():
            path = out / (label + ".capture")
            with path.open("xb") as stream:
                stream.write(item["raw"])
            report["original_inputs"][label] = dict(original_member=item["original_member"],
                original_identity=item["original_identity"], restored_identity=identity(path))
        command("units12", [sys.executable, "-B", "-X", "utf8", "-m", "unittest",
                "discover", "-s", str(HERE), "-p", "test_b2m.py", "-v"])
        for label in captures:
            path, result = out / (label + ".capture"), out / (label + ".json")
            command(label, [sys.executable, "-B", "-X", "utf8", str(HERE / "b2m_check.py"),
                           "--input", str(path), "--output", str(result)])
            data = json.loads(result.read_text(encoding="utf-8"))
            if data["status"] != STATUS or data["task_complete"] is not False:
                raise ValueError("B2M_PROFILE_SCOPE")
            report["profiles"].append(data)
        for i, (kind, request) in enumerate((
                ("both_1lsb", 1), ("left_1lsb", 21), ("right_1lsb", 33),
                ("zero_sound", 35), ("wrong_sign", 39), ("wrong_gain_256", 41))):
            profile = "N4_R1" if i < 3 else "N32_R64"
            raw, cycles = changed(captures[profile]["raw"], kind, request)
            path = out / (kind + ".capture")
            with path.open("xb") as stream:
                stream.write(raw)
            command(kind + "_old_clock_accepts", [sys.executable, "-B", "-X", "utf8",
                str(HERE / "b2k_check.py"), "--input", str(path)])
            command(kind + "_math_rejects", [sys.executable, "-B", "-X", "utf8",
                str(HERE / "b2m_check.py"), "--input", str(path)], 1, "B2M_PCM:")
            report["negatives"].append(dict(kind=kind, profile=profile, request=request,
                modified_cycles=cycles, old_clock_exit=0, new_math_exit=1, diagnostic="B2M_PCM"))
        report.update(status="B2M_RECOVERY_PCM_SOFTWARE_PASS_T061_PARTIAL", exit_code=0,
                      tests_run=12, complete_negatives=6)
    except Exception as error:
        report["error"] = type(error).__name__ + ":" + str(error)
    finally:
        report["protected_after"] = [identity(p) for p in protected]
        report["sources_after"] = [identity(p) for p in source_paths]
        for prefix in ("protected", "sources"):
            if report.get(prefix + "_before") != report[prefix + "_after"]:
                report.update(status="FAIL", exit_code=1, error="B2M_INPUT_DRIFT:" + prefix)
        report["elapsed_seconds"] = time.monotonic() - start
        if report["elapsed_seconds"] > 300:
            report.update(status="FAIL", exit_code=1, error="B2M_TOTAL_TIMEOUT")
        report["artifacts"] = [identity(p) for p in out.iterdir() if p.is_file()]
        dump(out / "receipt.json", report)
    print(json.dumps({k: report.get(k) for k in ("status", "exit_code", "elapsed_seconds", "error")}))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
