"""
从原理图 PDF 中提取文本，用于查找板载晶振频率等硬件事实。

不依赖第三方 PDF 库：直接解析 PDF 的 FlateDecode 流，
解压后提取括号内的文本对象（Tj / TJ 操作符）。

用法：
    python -X utf8 代码/scripts/extract_pdf_text.py <pdf路径> [关键字...]
"""

import re
import sys
import zlib
from pathlib import Path


def extract_streams(pdf_bytes: bytes) -> list[bytes]:
    """提取 PDF 中所有可解压的内容流。"""
    streams = []
    # 匹配 stream ... endstream
    for m in re.finditer(rb"stream\r?\n", pdf_bytes):
        start = m.end()
        end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            continue
        raw = pdf_bytes[start:end]
        # 去掉尾部换行
        raw = raw.rstrip(b"\r\n")
        try:
            streams.append(zlib.decompress(raw))
        except zlib.error:
            # 未压缩的流直接保留
            streams.append(raw)
    return streams


def extract_text_from_content(content: bytes) -> list[str]:
    """从内容流中提取文本。"""
    texts = []

    # PDF 文本操作符： (text) Tj   或   [(a) -1 (b)] TJ
    # 先处理 TJ 数组
    for m in re.finditer(rb"\[(.*?)\]\s*TJ", content, re.DOTALL):
        arr = m.group(1)
        parts = re.findall(rb"\((.*?)(?<!\\)\)", arr, re.DOTALL)
        s = b"".join(parts)
        if s:
            texts.append(decode_pdf_string(s))

    # 再处理单个 Tj
    for m in re.finditer(rb"\((.*?)(?<!\\)\)\s*Tj", content, re.DOTALL):
        texts.append(decode_pdf_string(m.group(1)))

    return texts


def decode_pdf_string(raw: bytes) -> str:
    """解码 PDF 字符串，处理转义。"""
    # 处理常见转义
    raw = raw.replace(b"\\(", b"(").replace(b"\\)", b")")
    raw = raw.replace(b"\\\\", b"\\")

    # 尝试 UTF-16BE（PDF 常用）
    if raw.startswith(b"\xfe\xff"):
        try:
            return raw[2:].decode("utf-16-be", errors="replace")
        except Exception:
            pass

    # 尝试 UTF-8
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # 回退 latin-1
    return raw.decode("latin-1", errors="replace")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    keywords = sys.argv[2:]

    if not pdf_path.exists():
        print(f"文件不存在: {pdf_path}")
        sys.exit(1)

    print(f"读取: {pdf_path.name} ({pdf_path.stat().st_size} 字节)")
    pdf_bytes = pdf_path.read_bytes()

    streams = extract_streams(pdf_bytes)
    print(f"解压出 {len(streams)} 个内容流")

    all_text = []
    for content in streams:
        all_text.extend(extract_text_from_content(content))

    print(f"提取出 {len(all_text)} 个文本片段")

    if not keywords:
        # 无关键字时输出全部（去重后按出现顺序）
        seen = set()
        for t in all_text:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                print(t)
        return

    # 有关键字时，输出包含关键字的片段及其上下文
    lower_kw = [k.lower() for k in keywords]
    print()
    print("=" * 70)
    print(f"匹配关键字: {', '.join(keywords)}")
    print("=" * 70)

    hits = 0
    seen = set()
    for i, t in enumerate(all_text):
        t_str = t.strip()
        if not t_str or t_str in seen:
            continue
        tl = t_str.lower()
        if any(k in tl for k in lower_kw):
            seen.add(t_str)
            hits += 1
            print(f"[{hits}] {t_str}")
            # 输出前后各 3 个片段作为上下文
            ctx_before = [x.strip() for x in all_text[max(0, i-3):i] if x.strip()]
            ctx_after = [x.strip() for x in all_text[i+1:i+4] if x.strip()]
            if ctx_before:
                print(f"      前文: {' | '.join(ctx_before[-3:])}")
            if ctx_after:
                print(f"      后文: {' | '.join(ctx_after[:3])}")
            print()

    if hits == 0:
        print("未匹配到关键字。")
        print()
        print("可能原因：")
        print("  1. 原理图文字是矢量图形（已转曲线），无法提取文本")
        print("  2. 文本使用了自定义编码的字体子集")
        print("  3. 关键字拼写不同")


if __name__ == "__main__":
    main()
