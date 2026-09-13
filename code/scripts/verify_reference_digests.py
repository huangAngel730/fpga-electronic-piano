#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 docs/reference/ 下两份外部整理稿的入库状态。

检查项：文件存在、字节数、行数、入库说明头是否在最前、正文是否仍然完整
（把说明头切掉后，正文必须以原始文件的首个标题开头）。

用法：python -X utf8 code/scripts/verify_reference_digests.py
"""

from pathlib import Path
import hashlib
import sys

REPO = Path(__file__).resolve().parents[2]
REF = REPO / "代码" / "docs" / "reference"

BANNER = "【本仓库入库说明"

# 文件名, 原始字节数, 原始 sha256, 正文首行
DIGESTS = [
    (
        "BOARD_CONTEXT_外部整理稿.md",
        111107,
        "EB24C3A069F1B31FF27E89DC5563F260ADD176C98FB1F4303E6AD24C53A06B0F",
        "# Tang Mega 60K 开发板硬件上下文",
    ),
    (
        "DOC_INDEX_外部整理稿.md",
        5344,
        "F2EBFAE62927DBDC7445E99290D26022F9C1CB95023A1B7380B40F54C2B02DE8",
        "# Tang Mega 60K 硬件资料索引",
    ),
]


def main() -> int:
    bad = 0
    for name, src_bytes, src_sha, first_line in DIGESTS:
        path = REF / name
        print(f"{name}")
        if not path.is_file():
            print("  MISSING")
            bad += 1
            continue

        raw = path.read_bytes()
        text = raw.decode("utf-8")
        lines = text.split("\n")

        ok_banner = lines[0].startswith("> **" + BANNER)
        # 正文起点：说明头之后第一个以原文首行开头的行
        idx = text.find(first_line)
        ok_body = idx > 0
        body = text[idx:] if ok_body else ""

        print(f"  bytes           {len(raw)}")
        print(f"  lines           {len(lines)}")
        print(f"  banner present  {ok_banner}")
        print(f"  body found      {ok_body} (offset {idx})")
        print(f"  body len        {len(body)} chars (source {src_bytes} bytes)")
        print(f"  sha256          {hashlib.sha256(raw).hexdigest()[:32]}...")
        print(f"  source sha256   {src_sha[:32]}...")

        if not ok_banner:
            print("  FAIL: provenance banner missing")
            bad += 1
        if not ok_body:
            print("  FAIL: original body heading not found")
            bad += 1

        # 正文必须比原文更长（我们只追加标注，不删除）
        growth = len(body.encode("utf-8")) - src_bytes
        print(f"  body growth     {growth:+d} bytes vs source")
        if growth < 0:
            print("  FAIL: body is smaller than the source (content was removed)")
            bad += 1
        print()

    if bad:
        print(f"FAILED: {bad} problem(s)")
        return 1
    print("OK: both digests are annotated and their bodies are intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
