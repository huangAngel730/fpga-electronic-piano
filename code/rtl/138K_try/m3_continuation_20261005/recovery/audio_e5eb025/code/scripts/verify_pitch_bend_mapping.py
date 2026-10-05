"""
验证 模块接口规范.md 3.2.1 节 MIDI Pitch Bend 映射公式

文档中的公式：
    control_value = $signed({1'b0, midi_bend_14bit} - 15'd8192) >>> 2

本脚本用 Python 复现该位运算，逐点校验边界、单调性与量化误差。
历史：初稿曾误用 >>> 3，导致只输出 50% 量程（最大 1023 而非 2047），
      最大误差达 100 音分。本脚本即为发现该错误的工具。
"""

BEND_BITS = 12
BEND_CENTER_12 = 0
BEND_MIN_12 = -2048
BEND_MAX_12 = 2047

MIDI_BEND_BITS = 14
MIDI_BEND_CENTER = 8192
MIDI_BEND_MIN = 0
MIDI_BEND_MAX = 16383


def wrap_signed(value, bits):
    """按指定位宽做二进制定点回绕，模拟 RTL 行为。"""
    mask = (1 << bits) - 1
    value &= mask
    if value >= (1 << (bits - 1)):
        value -= (1 << bits)
    return value


def make_formula(shift):
    """生成右移 shift 位的映射函数。"""
    def f(midi):
        diff = midi - MIDI_BEND_CENTER
        diff = wrap_signed(diff, MIDI_BEND_BITS)
        shifted = diff >> shift          # Python >> 对负数即算术右移
        return wrap_signed(shifted, BEND_BITS)
    return f


DOC_SHIFT = 2
doc_formula = make_formula(DOC_SHIFT)


def error_cents(fn, midi_value, semitone_range=2):
    """相对理想线性映射的音分误差。"""
    ideal = (midi_value - MIDI_BEND_CENTER) / MIDI_BEND_CENTER
    ideal_cents = ideal * semitone_range * 100.0
    actual = fn(midi_value) / 2048.0 * semitone_range * 100.0
    return actual - ideal_cents


def section(title):
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


def scan(fn):
    """全量程扫描，返回 (单调, 最大绝对音分误差, 最差点, 最小值, 最大值)。"""
    prev = None
    monotonic = True
    max_err = 0.0
    worst = None
    lo = hi = None
    for m in range(MIDI_BEND_MIN, MIDI_BEND_MAX + 1):
        v = fn(m)
        if lo is None or v < lo:
            lo = v
        if hi is None or v > hi:
            hi = v
        if prev is not None and v < prev:
            monotonic = False
        prev = v
        e = abs(error_cents(fn, m))
        if e > max_err:
            max_err = e
            worst = m
    return monotonic, max_err, worst, lo, hi


def main():
    section("一 关键点校验（文档公式 >>> 2）")
    points = [
        ("最小 0", MIDI_BEND_MIN),
        ("下四分之一", MIDI_BEND_CENTER // 2),
        ("中心", MIDI_BEND_CENTER),
        ("上四分之一", MIDI_BEND_CENTER + MIDI_BEND_CENTER // 2),
        ("最大 16383", MIDI_BEND_MAX),
    ]
    print(f"{'输入':<14}{'文档公式结果':>14}{'理想值':>12}{'误差(音分)':>14}")
    print("-" * 68)
    for name, m in points:
        got = doc_formula(m)
        ideal = (m - MIDI_BEND_CENTER) * 2048 / MIDI_BEND_CENTER
        err = error_cents(doc_formula, m)
        print(f"{name:<14}{got:>14}{ideal:>12.1f}{err:>14.3f}")

    section("二 中心点必须是 0")
    center_out = doc_formula(MIDI_BEND_CENTER)
    print(f"MIDI 中心 {MIDI_BEND_CENTER} -> {center_out}")
    print(f"判定: {'PASS' if center_out == 0 else 'FAIL'}（规范要求无弯音输出 0）")

    section("三 输出范围校验")
    mono, max_err, worst, lo, hi = scan(doc_formula)
    print(f"最小输入 {MIDI_BEND_MIN:>6} -> {lo:>6}")
    print(f"最大输入 {MIDI_BEND_MAX:>6} -> {hi:>6}")
    print(f"期望范围            : {BEND_MIN_12} .. {BEND_MAX_12}")
    full = (lo == BEND_MIN_12 and hi == BEND_MAX_12)
    print(f"用满全量程          : {'PASS' if full else 'FAIL'}")

    section("四 全量程单调性与最大误差扫描")
    print(f"扫描点数            : {MIDI_BEND_MAX - MIDI_BEND_MIN + 1}")
    print(f"单调不减            : {'PASS' if mono else 'FAIL'}")
    print(f"最大音分误差        : {max_err:.3f} 音分（出现在 MIDI 值 {worst}）")
    print(f"人耳可辨阈值约        : 5 至 10 音分")
    print(f"判定                : {'PASS' if max_err < 5 else 'FAIL'}")

    section("五 反例对比：初稿的 >>> 3")
    alt = make_formula(3)
    a_mono, a_err, a_worst, a_lo, a_hi = scan(alt)
    print(f">>> 3 输出范围      : {a_lo} .. {a_hi}")
    print(f">>> 3 最大误差      : {a_err:.3f} 音分（出现在 MIDI 值 {a_worst}）")
    print(f">>> 3 用满全量程    : {'是' if (a_lo == BEND_MIN_12 and a_hi == BEND_MAX_12) else '否'}")
    print()
    print("结论: >>> 3 只输出约 50% 量程，最大误差 1 个半音，判定不合格。")
    print("      该错误由本脚本在 v1.0 补充定义时发现并修正为 >>> 2。")

    section("六 结论")
    ok = (center_out == 0) and full and mono and max_err < 5
    print(f"文档 3.2.1 节 MIDI 映射公式（>>> {DOC_SHIFT}）验证: {'PASS' if ok else 'FAIL'}")
    print()
    print("数学依据: 14 位到 12 位相差 2 位，故右移 2。")
    print("          (16383 - 8192) >>> 2 = 2047 = 12 位有符号上限，无需饱和。")


if __name__ == "__main__":
    main()
