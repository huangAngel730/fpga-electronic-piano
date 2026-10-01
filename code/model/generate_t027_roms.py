#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T027 波表 ROM 文件生成器

生成两个波表的 Verilog hex 文件：
- sine_wavetable.hex
- triangle_wavetable.hex
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from t027_timbre_model import (
    generate_sine_wavetable,
    generate_triangle_wavetable,
    generate_rom_hex
)


def main():
    """生成波表 ROM 文件"""
    output_dir = Path(__file__).resolve().parent / "generated"
    output_dir.mkdir(exist_ok=True)

    # 生成波表
    sine = generate_sine_wavetable()
    triangle = generate_triangle_wavetable()

    # 生成 hex 文件
    sine_hex = generate_rom_hex(sine, "Sine")
    triangle_hex = generate_rom_hex(triangle, "Triangle")

    # 写入文件
    sine_path = output_dir / "sine_wavetable.hex"
    triangle_path = output_dir / "triangle_wavetable.hex"

    with open(sine_path, 'w', encoding='utf-8') as f:
        f.write(sine_hex)

    with open(triangle_path, 'w', encoding='utf-8') as f:
        f.write(triangle_hex)

    print("=" * 70)
    print("T027 波表 ROM 生成完成")
    print("=" * 70)
    print(f"✓ {sine_path}")
    print(f"✓ {triangle_path}")
    print(f"\n波表规格：")
    print(f"  - 长度：1024 点")
    print(f"  - 格式：16 位有符号（Q15）")
    print(f"  - 编码：十六进制（无符号表示）")
    print(f"\n可用于 RTL：")
    print(f"  $readmemh(\"sine_wavetable.hex\", sine_rom);")
    print(f"  $readmemh(\"triangle_wavetable.hex\", triangle_rom);")


if __name__ == "__main__":
    main()
