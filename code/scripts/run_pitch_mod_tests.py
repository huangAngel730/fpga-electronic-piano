#!/usr/bin/env python3
"""One-shot runner for M1 Pitch/Mod (M2 V0143 防假绿修正版, 2026-10-02).

修正内容：
  1. Icarus TB 改为必需（M2 有仿真器），vvp 失败必须非零退出
  2. 检查向量数量匹配 manifest，空文件/截断必须失败
  3. TB 输出必须含唯一 PASS、无 Fatal
  4. 所有 LUT 文件必须存在且非空

原离线步骤（LUT 生成、模型自检、RTL 语义等价）保持。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "code" / "model"
GEN = MODEL / "generated" / "pitch_mod"
TB = ROOT / "code" / "tb" / "audio" / "tb_pitch_mod_fcw.sv"
RTL = ROOT / "code" / "rtl" / "audio" / "pitch_mod_fcw.sv"

EXPECTED_VECTOR_COUNT = 62279    # M2 V0147: 同步新增饱和场景后的总数
TIMEOUT_SECONDS = 300            # M2 V0147: runner 超时


def run(name: str, args: list[str], required: bool = True, cwd=MODEL) -> tuple[bool, str]:
    print(f"\n=== {name} ===")
    try:
        proc = subprocess.run(args, cwd=cwd, text=True,
                              capture_output=True, encoding="utf-8",
                              timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        print(f"FAIL: {name} exceeded {TIMEOUT_SECONDS}s timeout")
        return False, "TIMEOUT"

    output = proc.stdout + proc.stderr
    sys.stdout.write(output)
    ok = proc.returncode == 0
    print(f"-> exit={proc.returncode} {'OK' if ok else 'FAIL'}")
    if required and not ok:
        print(f"MANDATORY STEP FAILED: {name}")
    return (ok or not required), output


def main() -> int:
    py = sys.executable
    results = {}

    # 离线步骤保持
    results["luts"], _ = run("generate luts",
                             [py, "-X", "utf8", "generate_pitch_mod_luts.py"])
    results["model"], _ = run("model self-check",
                              [py, "-X", "utf8", "test_pitch_mod.py"])
    results["vectors"], _ = run("generate vectors",
                                [py, "-X", "utf8", "generate_pitch_mod_vectors.py"])
    results["equiv"], _ = run("RTL equivalence",
                              [py, "-X", "utf8", "check_rtl_equivalence.py"])

    # M2 V0143: 检查向量数量，防空文件/截断
    vec_file = GEN / "pitch_mod_vectors.txt"
    if not vec_file.exists():
        print(f"FAIL: vectors file missing: {vec_file}")
        return 1
    vec_count = len([ln for ln in vec_file.read_text().split('\n') if ln.strip()])
    if vec_count != EXPECTED_VECTOR_COUNT:
        print(f"FAIL: vector count {vec_count} != expected {EXPECTED_VECTOR_COUNT}")
        return 1
    print(f"Vector count check: {vec_count} PASS")

    # M2 V0143: 检查所有 LUT 文件存在且非空
    for name in ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem"):
        lut = GEN / name
        if not lut.exists() or lut.stat().st_size == 0:
            print(f"FAIL: LUT {name} missing or empty")
            return 1

    # M2 V0143: Icarus TB 改为必需
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not (iverilog and vvp):
        print("\n=== Icarus TB ===")
        print("FAIL: iverilog/vvp required but not found in PATH")
        print("(原版标记为 SKIP，M2 V0143 改为必需)")
        return 1

    out = ROOT / "logs" / "tb_pitch_mod.vvp"
    out.parent.mkdir(parents=True, exist_ok=True)
    compile_ok, _ = run("iverilog compile",
                        [iverilog, "-g2012", "-o", str(out), str(TB), str(RTL)],
                        cwd=ROOT)
    if not compile_ok:
        return 1

    # M2 V0143: vvp 失败必须非零退出，检查唯一 PASS/无 Fatal
    sim_ok, sim_log = run("vvp run",
                          [vvp, str(out),
                           f"+VECTORS={vec_file}",
                           f"+OCT_PATH={GEN / 'oct_ratio_q16.mem'}",
                           f"+SUB_PATH={GEN / 'sub_ratio_q16.mem'}",
                           f"+LFO_PATH={GEN / 'lfo_sine_q15.mem'}"],
                          cwd=ROOT / "code")
    if not sim_ok:
        print("FAIL: vvp returned non-zero")
        return 1

    pass_count = sim_log.count("PASS: tb_pitch_mod_fcw")
    fatal_count = sim_log.lower().count("fatal")
    error_count = sim_log.lower().count("error:")
    if pass_count != 1:
        print(f"FAIL: expected exactly 1 PASS, got {pass_count}")
        return 1
    if fatal_count > 0 or error_count > 0:
        print(f"FAIL: found {fatal_count} Fatal and {error_count} Error in TB output")
        return 1
    print(f"TB verdict: 1 PASS, 0 Fatal - OK")

    results["icarus"] = True

    failed = [k for k, v in results.items() if not v]
    print("\n" + "=" * 60)
    if failed:
        print(f"RESULT: FAIL ({', '.join(failed)})")
        return 1
    print("RESULT: PASS (all steps including mandatory L2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
