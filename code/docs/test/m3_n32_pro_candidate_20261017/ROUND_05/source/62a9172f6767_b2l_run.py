"""Run only preparation/software tests/Icarus elaboration; NEVER launch Gowin."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from b2d_run import sources
from b2l_prepare import TOP, verify
from inventory import FROZEN, ROOT, identity, verify_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path,
                        default=Path("D:/Gowin/oss-cad-suite/bin/iverilog.exe"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT / "code/output" or not output.is_relative_to(ROOT / "code/output"):
        parser.error("Fresh child of code/output required")
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / "code/scripts"))
    from run_m3_polyphony_scaling_acceptance import Run
    run = Run(output)
    here = Path(__file__).resolve().parent
    protected = sources()[:-1] + list((FROZEN / "rom").glob("*.mem"))
    protected += list((FROZEN / "include").glob("*.svh"))
    protected += [ROOT / p for p in (
        "code/docs/当前状态.md", "code/docs/任务看板.md", "code/docs/验证记录.md",
        "code/docs/技术决策记录.md", "code/docs/模块接口规范.md",
        "code/rtl/board/electronic_piano_top.sv", "code/rtl/common/audio_defs_pkg.sv",
        "code/constraints/electronic_piano.cst")]
    doc = ROOT / "code/docs/hardware/polyphony_scaling_v1"
    protected += [p for d in doc.iterdir() if d.is_dir() for p in d.rglob("*") if p.is_file()]
    receipt = dict(status="FAIL", exit_code=1, stage="T061_B2L_PREPARATION_ONLY",
                   new_synthesis=False, new_PnR=False, new_RTL_simulation=False,
                   new_elaboration=True, physical_resources="UNKNOWN", physical_STA="NOT_RUN",
                   task_complete=False, step_limit_seconds=900, workflow_limit_seconds=1800,
                   command=[sys.executable, *sys.argv], sources_before=[identity(p) for p in sorted(here.glob("*.py"))],
                   protected_before=[identity(p) for p in protected], frozen_before=verify_manifest())
    try:
        run.command("preparation_unit", [sys.executable, "-B", "-X", "utf8", "-m", "unittest",
                    "discover", "-s", str(here), "-p", "test_b2l.py", "-v"])
        iv = args.iverilog.resolve()
        suite = iv.parent.parent
        run.extra_env = {"YOSYSHQ_ROOT": str(suite) + os.sep}
        run.extra_path = [str(suite / "bin"), str(suite / "lib")]
        run.command("iverilog_version", [str(iv), "-V"])
        receipt["profiles"] = []
        # Compile portability of generated wrappers only; none is a chosen
        # synthesis representative, and no VVP images are executed.
        for n in (4, 8, 16, 32):
            dest = output / f"N{n}_R1"
            run.command(f"N{n}_prepare", [sys.executable, "-B", "-X", "utf8",
                        str(here / "b2l_prepare.py"), "prepare", "--output", str(dest),
                        "--n", str(n), "--response", "1"])
            run.command(f"N{n}_verify", [sys.executable, "-B", "-X", "utf8",
                        str(here / "b2l_prepare.py"), "verify", "--output", str(dest)])
            spec = json.loads((dest / "inputs.json").read_text(encoding="utf-8"))
            run.command(f"N{n}_elaborate", [str(iv), "-g2012", "-I", str(dest / "include"),
                        "-s", TOP, "-o", str(output / f"N{n}.vvp")]
                        + [str(dest / p) for p in spec["sources"]])
            receipt["profiles"].append(verify(dest))
        receipt["status"] = "B2L_PREPARATION_L1_PASS_T061_PARTIAL"
        receipt["exit_code"] = 0
    except Exception as error:
        receipt["error"] = type(error).__name__ + ":" + str(error)
    receipt.update(steps=run.steps, elapsed_seconds=round(time.monotonic()-run.start, 6),
                   sources_after=[identity(p) for p in sorted(here.glob("*.py"))],
                   protected_after=[identity(p) for p in protected], frozen_after=verify_manifest())
    for key in ("sources", "protected", "frozen"):
        if receipt[key+"_before"] != receipt[key+"_after"]:
            receipt.update(status="FAIL", exit_code=1, error="INPUT_CHANGED:"+key)
    receipt["outputs"] = [identity(p) for p in output.rglob("*") if p.is_file()]
    with (output / "receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(status=receipt["status"], exit_code=receipt["exit_code"],
                          elapsed_seconds=receipt["elapsed_seconds"], receipt=str(output / "receipt.json"))))
    raise SystemExit(receipt["exit_code"])


if __name__ == "__main__":
    main()
