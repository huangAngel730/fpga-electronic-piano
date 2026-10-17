"""10/17 D-only tool/input preflight; no EDA or Git mutation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D"


def identity(path):
    path = Path(path).resolve()
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    output = DOCS / "preflight_20261017"
    output.mkdir(parents=True, exist_ok=False)
    base = Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/M1_M2_M3_Pro夜间任务与并行窗口_20261016")
    files = [base / n for n in ("M3_夜间五小时_Pro四声基础_2026-10-16.md",
             "M3_并行拓展双滑块窗口_2026-10-16.md", "夜间任务通用执行规范.md")]
    files += [ROOT / p for p in ("AGENTS.md", "code/AGENTS.md", "code/rtl/input/AGENTS.md",
        "code/docs/协作入口.md", "code/docs/夜间任务通用执行规范.md", "code/rtl/audio_out/i2s_tx.sv",
        "code/docs/test/m3_pro_fourvoice_trace_20261016/D/coordinator/NIGHT_PLAN_20261017.md")]
    dependencies = [Path(sys.executable), Path(sys.prefix) / "python312.dll", Path(sys.prefix) / "python3.dll",
                    Path(json.__file__), Path(subprocess.__file__), Path(platform.__file__), Path(hashlib.__file__)]
    argv = [sys.executable, "--version"]
    start = time.monotonic()
    with (output / "python_version.stdout").open("xb") as out, (output / "python_version.stderr").open("xb") as err:
        call = subprocess.run(argv, cwd=ROOT, stdout=out, stderr=err, timeout=5, check=False)
    data = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "origin_develop": subprocess.check_output(["git", "rev-parse", "origin/develop"], cwd=ROOT, text=True).strip(),
        "machine": platform.node(), "platform": platform.platform(), "python_version": sys.version,
        "argv": argv, "cwd": str(ROOT), "exit_code": call.returncode, "seconds": time.monotonic() - start,
        "time_utc": datetime.now(timezone.utc).isoformat(), "dependencies": [identity(p) for p in dependencies],
        "input_facts": [identity(p) for p in files], "stdout": identity(output / "python_version.stdout"),
        "stderr": identity(output / "python_version.stderr"), "Icarus_selected": False,
        "ModelSim_Gowin_invocations": 0, "board_release_allowed": False,
        "Pro_source_ROM_top_trace_and_M1_golden": "NOT_AVAILABLE_TO_THIS_FIXTURE"}
    with (output / "PREFLIGHT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    assert call.returncode == 0
    print(json.dumps({"python": str(Path(sys.executable)), "version": sys.version, "preflight_exit": call.returncode}))


if __name__ == "__main__":
    main()
