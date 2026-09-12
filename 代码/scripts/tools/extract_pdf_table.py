#!/usr/bin/env python3
"""Extract a PDF page's text preserving rough table layout via coordinates.

The generic extractor in this directory emits text in content-stream order,
which shreds tables: a value can land many lines away from its label.
For datasheet parameter tables we need rows, so this script groups text
runs by their Y coordinate and sorts each row by X.

Read-only: writes nothing except stdout.

Usage:
    python extract_pdf_table.py <file.pdf> [page_index]
"""
from __future__ import annotations

import re
import sys
import zlib
from pathlib import Path


def decompress_streams(data: bytes) -> list[bytes]:
    """Return every FlateDecode stream that decompresses cleanly."""
    out: list[bytes] = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        raw = data[start:end]
        try:
            out.append(zlib.decompress(raw))
        except zlib.error:
            continue
    return out


TOKEN = re.compile(
    rb"BT(.*?)ET",
    re.S,
)
# Td / TD / Tm give position; Tj / TJ give text
TEXT_SHOW = re.compile(rb"\((?:[^()\\]|\\.)*\)|<[0-9A-Fa-f\s]+>")


def decode_pdf_string(raw: bytes) -> str:
    """Decode a PDF literal string, handling escapes."""
    if raw.startswith(b"<"):
        hexs = re.sub(rb"[^0-9A-Fa-f]", b"", raw)
        if len(hexs) % 2:
            hexs += b"0"
        try:
            return bytes.fromhex(hexs.decode("ascii")).decode("latin-1")
        except ValueError:
            return ""
    body = raw[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c == 0x5C and i + 1 < len(body):  # backslash
            nxt = body[i + 1]
            mapping = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
            if 0x30 <= nxt <= 0x37:  # octal
                j = i + 1
                digits = b""
                while j < len(body) and len(digits) < 3 and 0x30 <= body[j] <= 0x37:
                    digits += body[j : j + 1]
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(c)
        i += 1
    return out.decode("latin-1")


def extract_rows(streams: list[bytes], ytol: float = 2.5, xgap: float = 8.0):
    """Group glyphs into lines, then into cells separated by horizontal gaps.

    This PDF positions nearly every glyph individually, so a naive
    "one string = one cell" approach shatters words into single letters.
    Instead we cut a line into cells wherever the horizontal gap between
    consecutive glyphs exceeds xgap points.
    """
    glyphs: list[tuple[float, float, str]] = []

    for s in streams:
        for m in TOKEN.finditer(s):
            block = m.group(1)
            x = y = 0.0
            for tm in re.finditer(
                rb"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+(Tm|Td|TD)",
                block,
            ):
                vals = [float(tm.group(i)) for i in range(1, 7)]
                op = tm.group(7)
                if op == b"Tm":
                    x, y = vals[4], vals[5]
                else:
                    x += vals[4]
                    y += vals[5]
            for sm in TEXT_SHOW.finditer(block):
                txt = decode_pdf_string(sm.group(0))
                if txt.strip():
                    glyphs.append((y, x, txt))

    # cluster into lines by y
    glyphs.sort(key=lambda t: (-t[0], t[1]))
    lines: list[list[tuple[float, float, str]]] = []
    for g in glyphs:
        if lines and abs(lines[-1][0][0] - g[0]) <= ytol:
            lines[-1].append(g)
        else:
            lines.append([g])

    # drop the y used for clustering, keep (x, text) sorted by x
    out: list[list[tuple[float, str]]] = []
    for ln in lines:
        out.append(sorted(((g[1], g[2]) for g in ln), key=lambda t: t[0]))
    return out


def merge_cells(glyph_line: list[tuple[float, str]], xgap: float = 8.0) -> str:
    """Join glyphs into cells, inserting a separator at wide horizontal gaps."""
    if not glyph_line:
        return ""
    parts: list[str] = []
    prev_x = glyph_line[0][0]
    buf = glyph_line[0][1]
    for x, txt in glyph_line[1:]:
        if x - prev_x > xgap:
            parts.append(buf)
            buf = txt
        else:
            buf += txt
        prev_x = x
    parts.append(buf)
    return "  |  ".join(p.strip() for p in parts if p.strip())


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"file not found: {path}")
        return 1

    data = path.read_bytes()
    streams = decompress_streams(data)
    print(f"# {path.name}: {len(data)} bytes, {len(streams)} streams decoded")

    rows = extract_rows(streams)
    for r in rows:
        line = merge_cells(r)
        if line.strip():
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
