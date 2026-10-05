"""
展开 PDF 的 ObjStm（对象流），查找图片 XObject 与页面资源。

用法：
    python -X utf8 code/scripts/expand_pdf_objstm.py <pdf路径>
"""

import re
import sys
import zlib
from pathlib import Path


def main():
    pdf_path = Path(sys.argv[1])
    data = pdf_path.read_bytes()

    print(f"文件: {pdf_path.name}")
    print("=" * 70)

    # 展开所有 ObjStm
    expanded = []
    for m in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", data, re.DOTALL):
        body = m.group(2)
        if b"/ObjStm" not in body:
            continue
        sm = re.search(rb"stream\r?\n", body)
        if not sm:
            continue
        start = sm.end()
        end = body.find(b"endstream", start)
        raw = body[start:end].rstrip(b"\r\n")
        try:
            content = zlib.decompress(raw)
        except zlib.error:
            continue
        expanded.append(content)
        print(f"ObjStm 对象 {m.group(1).decode()}: 解压后 {len(content)} 字节")

    print()
    print("=" * 70)
    print("在展开的对象流中搜索图片与资源")
    print("=" * 70)

    all_content = b"\n".join(expanded)

    # 统计 Subtype
    for subtype in [b"/Image", b"/Form", b"/Font", b"/Page"]:
        cnt = len(re.findall(re.escape(subtype), all_content))
        print(f"  {subtype.decode()}: {cnt}")

    # 查找 XObject 引用
    xobj = re.findall(rb"/XObject\s*<<(.*?)>>", all_content, re.DOTALL)
    print(f"\n  /XObject 字典数: {len(xobj)}")
    for x in xobj[:5]:
        print(f"    {x[:200]!r}")

    # 查找图片特有的键
    print()
    for key in [b"/Width", b"/Height", b"/BitsPerComponent", b"/Filter",
                b"/DCTDecode", b"/FlateDecode", b"/ColorSpace", b"/SMask"]:
        cnt = len(re.findall(re.escape(key), all_content))
        print(f"  {key.decode()}: {cnt}")

    # 查找 MediaBox，判断页面尺寸
    mb = re.findall(rb"/MediaBox\s*\[(.*?)\]", all_content, re.DOTALL)
    print(f"\n  MediaBox: {[x.strip()[:60] for x in mb[:5]]}")

    # 查找内容流长度，判断是否为矢量绘制
    lens = re.findall(rb"/Length\s+(\d+)", all_content)
    if lens:
        ints = sorted((int(x) for x in lens), reverse=True)
        print(f"  最大的 /Length 值: {ints[:10]}")
        print("  （内容流很大说明是矢量绘制而非嵌入位图）")


if __name__ == "__main__":
    main()
