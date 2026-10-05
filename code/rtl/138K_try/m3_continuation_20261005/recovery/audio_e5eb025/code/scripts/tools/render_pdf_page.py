"""
最小 PDF 矢量光栅化器。

用于把原理图 PDF（纯矢量、字体为自定义编码、无法提取文字）
渲染成 PNG，以便通过视觉方式读取标注内容。

只实现原理图常见的一小部分绘图操作符：
    m l c v y re h   — 路径构造
    S s f F f* B B* b b* n — 描边/填充
    q Q cm           — 图形状态与变换
    w J j d          — 线宽、线帽、连接
    RG rg G g        — 颜色
    W W*             — 裁剪（近似忽略）
    BT ET Td TD Tm T* Tj TJ — 文本（按字形轮廓不可得，忽略或画方块）

用法：
    python -X utf8 code/scripts/render_pdf_page.py <pdf路径> <输出png> [页号] [缩放]
"""

import re
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image


def expand_objstm(data: bytes) -> bytes:
    """把 ObjStm 展开拼接到主数据后面，便于统一扫描。"""
    extra = bytearray()
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
            extra += zlib.decompress(raw) + b"\n"
        except zlib.error:
            pass
    return bytes(extra)


def get_content_streams(data: bytes, objstm_text: bytes) -> list[bytes]:
    """收集所有看起来像页面内容流的流。"""
    streams = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        raw = data[start:end].rstrip(b"\r\n")
        try:
            dec = zlib.decompress(raw)
        except zlib.error:
            continue
        # 内容流应含绘图操作符
        if b" m" in dec or b" l" in dec or b"re" in dec:
            streams.append(dec)
    return streams


class Matrix:
    """2D 仿射变换 [a b c d e f]。"""

    __slots__ = ("a", "b", "c", "d", "e", "f")

    def __init__(self, a=1, b=0, c=0, d=1, e=0, f=0):
        self.a, self.b, self.c, self.d, self.e, self.f = a, b, c, d, e, f

    def mul(self, o):
        """返回 self × o（先应用 o 再应用 self）。"""
        return Matrix(
            self.a * o.a + self.b * o.c,
            self.a * o.b + self.b * o.d,
            self.c * o.a + self.d * o.c,
            self.c * o.b + self.d * o.d,
            self.e * o.a + self.f * o.c + o.e,
            self.e * o.b + self.f * o.d + o.f,
        )

    def apply(self, x, y):
        return (self.a * x + self.c * y + self.e,
                self.b * x + self.d * y + self.f)


def parse_operands(tokens):
    """把 token 列表解析为数值/字符串操作数。"""
    out = []
    for t in tokens:
        if isinstance(t, (int, float)):
            out.append(t)
        elif isinstance(t, str) and t.startswith("("):
            out.append(t)
        elif isinstance(t, str) and t.startswith("<"):
            out.append(t)
    return out


def tokenize(content: bytes):
    """把内容流切成 (操作数..., 操作符) 序列。"""
    text = content.decode("latin-1", errors="replace")

    # 去掉注释
    text = re.sub(r"%[^\r\n]*", "", text)

    token_re = re.compile(
        r"""
        (?P<num>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)
      | (?P<str>\((?:[^()\\]|\\.)*\))
      | (?P<hex><[0-9A-Fa-f\s]*>)
      | (?P<name>/[^\s/\[\]<>(){}]+)
      | (?P<arr>[\[\]])
      | (?P<op>[A-Za-z'"*]+)
        """,
        re.VERBOSE,
    )

    stack = []
    for m in token_re.finditer(text):
        kind = m.lastgroup
        val = m.group()
        if kind == "num":
            stack.append(float(val))
        elif kind in ("str", "hex", "name", "arr"):
            stack.append(val)
        else:  # op
            yield list(stack), val
            stack = []


def render(pdf: Path, out_png: Path, page: int = 0, scale: float = 2.0):
    data = pdf.read_bytes()
    objstm_text = expand_objstm(data)

    # 找到 MediaBox 确定页面尺寸
    all_bytes = data + objstm_text
    mb = re.findall(rb"/MediaBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)", all_bytes)
    if not mb:
        print("找不到 MediaBox，使用 A3 默认尺寸")
        W, H = 1191.0, 842.0
    else:
        # 取最大的一个作为整页
        boxes = [tuple(float(v) for v in b) for b in mb]
        x0, y0, x1, y1 = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        W, H = x1 - x0, y1 - y0
        print(f"MediaBox: {x0},{y0} -> {x1},{y1}  ({W:.0f} x {H:.0f} pt)")

    iw, ih = int(W * scale), int(H * scale)
    # 上限保护
    if iw * ih > 80_000_000:
        k = (80_000_000 / (iw * ih)) ** 0.5
        scale *= k
        iw, ih = int(W * scale), int(H * scale)
        print(f"尺寸过大，缩放调整为 {scale:.2f}")

    print(f"输出画布: {iw} x {ih}")

    # 白底
    canvas = Image.new("L", (iw, ih), 255)

    streams = get_content_streams(data, objstm_text)
    print(f"内容流数: {len(streams)}")

    # 逐流渲染（简化：不做页面归属判断，全部叠加）
    total_paths = 0
    for si, content in enumerate(streams):
        paths = collect_paths(content, scale, H)
        total_paths += len(paths)
        draw_paths(canvas, paths)

    print(f"绘制路径段: {total_paths}")
    canvas.save(out_png)
    print(f"已保存: {out_png}")


def collect_paths(content: bytes, scale: float, page_h: float):
    """从内容流收集线段（转换成像素坐标）。"""
    segs = []

    ctm = Matrix()
    stack = []
    cur = None      # 当前点
    start = None    # 子路径起点
    pts = []        # 当前路径的段
    lw = 1.0
    stroke_gray = 0.0
    fill_gray = None

    # PDF 用户空间 y 向上，图像 y 向下
    def to_px(x, y):
        return (x * scale, (page_h - y) * scale)

    for operands, op in tokenize(content):
        try:
            if op == "q":
                stack.append((Matrix(ctm.a, ctm.b, ctm.c, ctm.d, ctm.e, ctm.f),
                              lw, stroke_gray, fill_gray))
            elif op == "Q":
                if stack:
                    m, lw, stroke_gray, fill_gray = stack.pop()
                    ctm = m
            elif op == "cm" and len(operands) >= 6:
                m = Matrix(*[float(v) for v in operands[-6:]])
                ctm = ctm.mul(m)
            elif op == "w" and operands:
                lw = float(operands[-1])
            elif op == "RG" and len(operands) >= 3:
                stroke_gray = (float(operands[-3]) + float(operands[-2]) + float(operands[-1])) / 3
            elif op == "rg" and len(operands) >= 3:
                fill_gray = (float(operands[-3]) + float(operands[-2]) + float(operands[-1])) / 3
            elif op == "G" and operands:
                stroke_gray = float(operands[-1])
            elif op == "g" and operands:
                fill_gray = float(operands[-1])
            elif op == "m" and len(operands) >= 2:
                cur = (float(operands[-2]), float(operands[-1]))
                start = cur
            elif op == "l" and len(operands) >= 2:
                nxt = (float(operands[-2]), float(operands[-1]))
                if cur is not None:
                    p0 = ctm.apply(*cur)
                    p1 = ctm.apply(*nxt)
                    pts.append((to_px(*p0), to_px(*p1)))
                cur = nxt
            elif op in ("c", "v", "y") and len(operands) >= 4:
                # 贝塞尔：取末点，用直线近似（原理图多为短线段）
                nxt = (float(operands[-2]), float(operands[-1]))
                if cur is not None:
                    p0 = ctm.apply(*cur)
                    p1 = ctm.apply(*nxt)
                    pts.append((to_px(*p0), to_px(*p1)))
                cur = nxt
            elif op == "re" and len(operands) >= 4:
                x, y, w, h = (float(v) for v in operands[-4:])
                corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
                for i in range(4):
                    p0 = ctm.apply(*corners[i])
                    p1 = ctm.apply(*corners[i + 1])
                    pts.append((to_px(*p0), to_px(*p1)))
                cur = corners[0]
                start = cur
            elif op == "h":
                if cur is not None and start is not None:
                    p0 = ctm.apply(*cur)
                    p1 = ctm.apply(*start)
                    pts.append((to_px(*p0), to_px(*p1)))
                cur = start
            elif op in ("S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"):
                if pts:
                    segs.extend(pts)
                pts = []
        except Exception:
            pts = []
            continue

    return segs


def draw_paths(img: Image.Image, segs):
    """把线段画到图像上。用 numpy 加速。"""
    arr = np.array(img, dtype=np.uint8)  # 可写副本
    h, w = arr.shape

    for (x0, y0), (x1, y1) in segs:
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        n = min(n, 4000)
        if n <= 1:
            xi, yi = int(x0), int(y0)
            if 0 <= xi < w and 0 <= yi < h:
                arr[yi, xi] = 0
            continue
        xs = np.linspace(x0, x1, n).astype(np.int32)
        ys = np.linspace(y0, y1, n).astype(np.int32)
        ok = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
        arr[ys[ok], xs[ok]] = 0

    return Image.fromarray(arr)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    pdf_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    scale = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
    render(pdf_path, out_path, page, scale)
