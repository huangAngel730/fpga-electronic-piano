"""
Pitch Bend 与 control_id 编码方案的定量分析

目的：为 模块接口规范.md 3.2 节补上 Pitch Bend 中心点、弯音范围
      和 control_id 编码表，消除 v1.0 的语义空白。

本脚本计算三种候选中心点方案在 12 位字段下的量化误差，
为选型提供依据。
"""

# --- 来自冻结接口 v1.0 ---
CONTROL_VALUE_BITS = 12
CONTROL_VALUE_MAX = (1 << CONTROL_VALUE_BITS) - 1        # 4095
CONTROL_VALUE_SIGNED_MIN = -(1 << (CONTROL_VALUE_BITS - 1))   # -2048
CONTROL_VALUE_SIGNED_MAX = (1 << (CONTROL_VALUE_BITS - 1)) - 1  # 2047


def section(title):
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


def analyze_center(name, center, lo, hi, semitones):
    """分析一种中心点方案。"""
    print(f"\n【{name}】")
    print(f"  中心点            : {center}")
    print(f"  合法范围          : {lo} .. {hi}")
    print(f"  向上行程          : {hi - center}")
    print(f"  向下行程          : {center - lo}")
    symmetric = (hi - center) == (center - lo)
    print(f"  上下对称          : {'是' if symmetric else '否'}")

    if semitones:
        up_cents = semitones * 100.0 * (hi - center) / (hi - center or 1)
        # 每单位对应的音分
        cents_per_unit_up = semitones * 100.0 / (hi - center)
        cents_per_unit_dn = semitones * 100.0 / (center - lo)
        print(f"  ±{semitones} 半音时每单位  : 向上 {cents_per_unit_up:.3f} 音分, "
              f"向下 {cents_per_unit_dn:.3f} 音分")
        print(f"  1 单位最小分辨率  : ~{min(cents_per_unit_up, cents_per_unit_dn):.3f} 音分")
        print(f"     (人耳可辨约 5-10 音分)")
    return symmetric


def main():
    print("12 位 control_value 字段分析")
    print(f"  无符号范围 : 0 .. {CONTROL_VALUE_MAX}")
    print(f"  有符号范围 : {CONTROL_VALUE_SIGNED_MIN} .. {CONTROL_VALUE_SIGNED_MAX}")

    section("一 候选中心点方案")

    # 方案 A：有符号 0 为中心
    analyze_center("方案 A：有符号 0 为中心",
                   center=0,
                   lo=CONTROL_VALUE_SIGNED_MIN,
                   hi=CONTROL_VALUE_SIGNED_MAX,
                   semitones=2)

    # 方案 B：无符号 2048 为中心（MIDI 14 位惯例的中位）
    analyze_center("方案 B：无符号 2048 为中心",
                   center=2048,
                   lo=0,
                   hi=CONTROL_VALUE_MAX,
                   semitones=2)

    # 方案 C：无符号 2047 为中心（严格上下各 2048，且最大 4095）
    analyze_center("方案 C：无符号 2047 为中心",
                   center=2047,
                   lo=0,
                   hi=CONTROL_VALUE_MAX,
                   semitones=2)

    section("二 关键矛盾：12 位无法上下对称")
    print(f"  无符号满量程 {CONTROL_VALUE_MAX} 为奇数，中心必然偏移 0.5 个 LSB。")
    print(f"  2048 为中心 -> 向上 {CONTROL_VALUE_MAX - 2048}，向下 {2048}")
    print(f"  2047 为中心 -> 向上 {CONTROL_VALUE_MAX - 2047}，向下 {2047}")
    print()
    print("  结论：任一无符号方案都存在 1 个 LSB 的不对称。")
    print("        有符号方案（中心 0）上下各 2048，完全对称，但浪费 1 个编码。")

    section("三 分辨率需求核算")
    # 音高分辨率：人耳可辨约 5 音分
    for semitones in (2, 12):
        for span in (2047, 2048):
            cents = semitones * 100.0 / span
            print(f"  ±{semitones:2d} 半音，行程 {span}: "
                  f"每单位 {cents:.4f} 音分 -> "
                  f"{'足够' if cents < 1 else '偏粗'}")
    print()
    print("  结论：即便 ±2 半音，12 位分辨率也远超需求（0.1 音分/单位）。")
    print("        字段位宽不是瓶颈，中心点定义才是。")

    section("四 与 MIDI 惯例的对照")
    print("  MIDI Pitch Bend 为 14 位无符号，中心 8192（0x2000）。")
    print("  比例换算到 12 位：8192 / 16384 * 4096 = 2048")
    print()
    print("  -> 无符号中心 2048 与 MIDI 惯例一致，便于 MIDI 适配器实现。")
    print("  -> 但规范第 99 行明确写的是「有符号二进制补码解释」。")

    section("五 推荐结论")
    print("  采用方案 A：有符号补码，中心 0。")
    print()
    print("  理由：")
    print("  1. 规范第 99 行已明文写「按有符号二进制补码解释」，改无符号等于")
    print("     推翻已冻结表述，成本高于澄清。")
    print("  2. 中心 0 上下各 2048，完全对称，无需处理偏移，RTL 实现最简。")
    print("  3. 12 位分辨率远超音高需求，浪费 1 个编码无实际影响。")
    print("  4. MIDI 适配器只需做 saturate((midi14 - 8192) >> 3)，一行完成。")
    print()
    print("  需要补充定义的量：")
    print("  - 弯音范围（默认 ±2 半音，可通过 control_id 配置）")
    print("  - 中心点必须输出 0（无弯音时不得输出 -1 或 1）")


if __name__ == "__main__":
    main()
