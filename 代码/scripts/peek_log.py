#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小工具：打印 代码/docs/验证记录.md 中指定编号的行摘要。

用法：python -X utf8 代码/scripts/peek_log.py V0030
"""

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "代码" / "docs" / "验证记录.md"


def main() -> int:
    want = sys.argv[1] if len(sys.argv) > 1 else "V0030"
    text = LOG.read_text(encoding="utf-8")
    lines = text.split("\n")
    print(f"total lines: {len(lines)}")
    hit = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith(f"| {want} |"):
            hit = True
            print(f"line {i + 1}: {len(ln)} chars")
            print(ln.strip())
            print()
    if not hit:
        print(f"{want} not found")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
