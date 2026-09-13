"""
从原理图 PDF 的压缩对象流中提取文字。

背景：CAD 导出的 PDF 常把字体和内容流放在 ObjStm 里，
直接扫描未压缩区会误判为"无文字"。本脚本先展开 ObjStm，
再提取字体 ToUnicode CMap 与页面内容流，还原可读文字。

用法：
    python -X utf8 代码/scripts/extract_schematic_text.py <pdf路径> [关键字...]
"""

import re
import sys
import zlib
from pathlib import Path


def iter_objstm(data: bytes):
    """展开所有 ObjStm，产出 (obj_num, content_bytes)。"""
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
            yield int(m.group(1)), zlib.decompress(raw)
        except zlib.error:
            continue


def iter_streams(data: bytes):
    """展开所有普通内容流。"""
    for m in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", data, re.DOTALL):
        body = m.group(2)
        if b"/ObjStm" in body:
            continue
        sm = re.search(rb"stream\r?\n", body)
        if not sm:
            continue
        start = sm.end()
        end = body.find(b"endstream", start)
        raw = body[start:end].rstrip(b"\r\n")
        try:
            yield int(m.group(1)), zlib.decompress(raw)
        except zlib.error:
            yield int(m.group(1)), raw


def build_cmap(cmap_bytes: bytes) -> dict:
    """解析 ToUnicode CMap，返回 {字符码: unicode} 映射。"""
    text = cmap_bytes.decode("latin-1", errors="replace")
    mapping = {}

    for m in re.finditer(
        r"beginbfchar(.*?)endbfchar", text, re.DOTALL
    ):
        for pair in re.finditer(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", m.group(1)):
            src = int(pair.group(1), 16)
            dst_hex = pair.group(2)
            try:
                dst = bytes.fromhex(dst_hex).decode("utf-16-be", errors="replace")
            except Exception:
                continue
            mapping[src] = dst

    for m in re.finditer(
        r"beginbfrange(.*?)endbfrange", text, re.DOTALL
    ):
        block = m.group(1)
        for r in re.finditer(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
        ):
            lo = int(r.group(1), 16)
            hi = int(r.group(2), 16)
            dst = int(r.group(3), 16)
            for i in range(hi - lo + 1):
                try:
                    mapping[lo + i] = chr(dst + i)
                except Exception:
                    pass

    return mapping


def main():
    pdf_path = Path(sys.argv[1])
    keywords = sys.argv[2:]
    data = pdf_path.read_bytes()

    print(f"文件: {pdf_path.name}")
    print("=" * 70)

    # 收集所有 CMap
    all_cmaps = []
    for num, content in iter_objstm(data):
        if b"beginbfchar" in content or b"beginbfrange" in content:
            all_cmaps.append(build_cmap(content))

    print(f"找到 {len(all_cmaps)} 个 ToUnicode CMap")

    merged = {}
    for cm in all_cmaps:
        merged.update(cm)
    print(f"合并后字符映射数: {len(merged)}")

    if merged:
        sample = list(merged.items())[:20]
        print(f"映射样例: {sample}")
    print()

    # 提取内容流文字
    texts = []
    for num, content in list(iter_objstm(data)) + list(iter_streams(data)):
        if b"Tj" not in content and b"TJ" not in content:
            continue
        for m in re.finditer(rb"\[(.*?)\]\s*TJ", content, re.DOTALL):
            parts = re.findall(rb"<([0-9A-Fa-f\s]+)>|\((.*?)(?<!\\)\)", m.group(1), re.DOTALL)
            s = ""
            for hexpart, litpart in parts:
                if hexpart:
                    h = bytes.fromhex(re.sub(rb"\s", b"", hexpart).decode())
                    codes = [int.from_bytes(h[i:i+2], "big") for i in range(0, len(h) - 1, 2)]
                    s += "".join(merged.get(c, "") for c in codes)
                elif litpart:
                    s += litpart.decode("latin-1", errors="replace")
            if s.strip():
                texts.append(s)
        for m in re.finditer(rb"<([0-9A-Fa-f\s]+)>\s*Tj", content):
            h = bytes.fromhex(re.sub(rb"\s", b"", m.group(1)).decode())
            codes = [int.from_bytes(h[i:i+2], "big") for i in range(0, len(h) - 1, 2)]
            s = "".join(merged.get(c, "") for c in codes)
            if s.strip():
                texts.append(s)

    print(f"提取出 {len(texts)} 个文本片段")
    print()

    if not keywords:
        seen = set()
        for t in texts:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                print(t)
        return

    lower_kw = [k.lower() for k in keywords]
    print("=" * 70)
    print(f"匹配: {', '.join(keywords)}")
    print("=" * 70)
    hits = 0
    seen = set()
    for t in texts:
        ts = t.strip()
        if not ts or ts in seen:
            continue
        if any(k in ts.lower() for k in lower_kw):
            seen.add(ts)
            hits += 1
            print(f"  {ts}")
    if hits == 0:
        print("  未匹配。")
        if texts:
            print("\n  样例（前 40 条）:")
            for t in texts[:40]:
                if t.strip():
                    print(f"    {t.strip()}")


if __name__ == "__main__":
    main()
