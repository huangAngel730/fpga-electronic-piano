"""
原理图 PDF 结构分析。用于判断文本是否为自定义编码字体子集，
以及能否通过 ToUnicode CMap 还原。

用法：
    python -X utf8 code/scripts/analyze_pdf_fonts.py <pdf路径>
"""

import re
import sys
import zlib
from pathlib import Path


def main():
    pdf_path = Path(sys.argv[1])
    data = pdf_path.read_bytes()

    print(f"文件: {pdf_path.name}  ({len(data)} 字节)")
    print(f"版本: {data[:8]}")
    print()

    # 统计对象类型
    objs = re.findall(rb"(\d+)\s+0\s+obj(.*?)endobj", data, re.DOTALL)
    print(f"对象总数: {len(objs)}")

    kinds = {}
    for num, body in objs:
        head = body[:400]
        if b"/Type" in head:
            m = re.search(rb"/Type\s*/(\w+)", head)
            if m:
                k = m.group(1).decode("latin-1")
                kinds[k] = kinds.get(k, 0) + 1

    print("对象类型分布:")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # 查找 ToUnicode CMap
    tounicode_count = len(re.findall(rb"/ToUnicode", data))
    print(f"\n/ToUnicode 引用数: {tounicode_count}")

    font_count = len(re.findall(rb"/Type\s*/Font", data))
    print(f"字体对象数: {font_count}")

    # 尝试解压一个 ToUnicode CMap，看映射表内容
    if tounicode_count > 0:
        print("\n尝试解析 ToUnicode CMap...")
        for m in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", data, re.DOTALL):
            body = m.group(2)
            if b"/ToUnicode" not in body and b"beginbfchar" not in body \
               and b"beginbfrange" not in body:
                continue
            sm = re.search(rb"stream\r?\n", body)
            if not sm:
                continue
            start = sm.end()
            end = body.find(b"endstream", start)
            raw = body[start:end].rstrip(b"\r\n")
            try:
                cmap = zlib.decompress(raw)
            except zlib.error:
                cmap = raw
            text = cmap.decode("latin-1", errors="replace")
            if "beginbfchar" in text or "beginbfrange" in text:
                print(f"  找到 CMap 对象 {m.group(1).decode()}:")
                print("  " + text[:800].replace("\n", "\n  "))
                break
    else:
        print("\n没有 /ToUnicode，文本无法从编码直接还原。")
        print("原理图文字很可能是矢量图形（转曲线）或使用了无映射的字体子集。")


if __name__ == "__main__":
    main()
