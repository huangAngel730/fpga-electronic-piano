"""
从 PDF 中提取内嵌图片，供视觉检查原理图。

原理图 PDF 通常是每页一张大位图，用本脚本导出为 PNG 后可直接查看。

只依赖 Pillow 和标准库，不需要 PyMuPDF 或 poppler。

用法：
    python -X utf8 代码/scripts/extract_pdf_images.py <pdf路径> <输出目录> [最小宽度]

输出文件名形如 page_000_img_000.png，按宽度降序排列，
最宽的通常是原理图主体。
"""

import re
import sys
import zlib
from pathlib import Path

from PIL import Image


def find_image_xobjects(pdf_bytes: bytes):
    """
    查找 PDF 中的图片 XObject。

    返回 [(obj_num, width, height, filter_name, data_bytes), ...]
    """
    results = []

    # 逐个对象扫描
    for m in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", pdf_bytes, re.DOTALL):
        obj_num = int(m.group(1))
        body = m.group(2)

        # 必须是图片 XObject
        if b"/Subtype" not in body or b"/Image" not in body:
            continue

        # 提取宽度和高度
        wm = re.search(rb"/Width\s+(\d+)", body)
        hm = re.search(rb"/Height\s+(\d+)", body)
        if not wm or not hm:
            continue
        width = int(wm.group(1))
        height = int(hm.group(1))

        # 提取流数据
        sm = re.search(rb"stream\r?\n", body)
        if not sm:
            continue
        start = sm.end()
        end = body.find(b"endstream", start)
        if end == -1:
            continue
        raw = body[start:end].rstrip(b"\r\n")

        # 判断过滤器
        fm = re.search(rb"/Filter\s*/(\w+)", body)
        filt = fm.group(1) if fm else b""

        data = raw
        if filt in (b"FlateDecode", b"Fl"):
            try:
                data = zlib.decompress(raw)
            except zlib.error:
                continue

        # 颜色空间与位深
        bpc_m = re.search(rb"/BitsPerComponent\s+(\d+)", body)
        bpc = int(bpc_m.group(1)) if bpc_m else 8

        cs = b""
        cs_m = re.search(rb"/ColorSpace\s*/(\w+)", body)
        if cs_m:
            cs = cs_m.group(1)

        results.append({
            "obj": obj_num,
            "width": width,
            "height": height,
            "filter": filt.decode("latin-1"),
            "data": data,
            "bpc": bpc,
            "colorspace": cs.decode("latin-1"),
        })

    return results


def to_image(entry) -> Image.Image | None:
    """把提取的数据转成 PIL 图像。"""
    w, h, data = entry["width"], entry["height"], entry["data"]
    bpc = entry["bpc"]
    cs = entry["colorspace"]

    try:
        if bpc == 8 and cs in ("DeviceRGB", "RGB", ""):
            if len(data) >= w * h * 3:
                return Image.frombytes("RGB", (w, h), data[: w * h * 3])
        if bpc == 8 and cs in ("DeviceGray", "G", ""):
            if len(data) >= w * h:
                return Image.frombytes("L", (w, h), data[: w * h])
        # 回退：按灰度尝试
        if bpc == 8 and len(data) >= w * h:
            return Image.frombytes("L", (w, h), data[: w * h])
        if bpc == 1:
            return Image.frombytes("1", (w, h), data[: (w * h + 7) // 8])
    except Exception as exc:  # noqa: BLE001
        print(f"    转换失败: {exc}")
        return None

    return None


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    min_width = int(sys.argv[3]) if len(sys.argv) > 3 else 200

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"读取: {pdf_path.name}")
    pdf_bytes = pdf_path.read_bytes()

    entries = find_image_xobjects(pdf_bytes)
    print(f"找到 {len(entries)} 个图片对象")

    entries = [e for e in entries if e["width"] >= min_width]
    entries.sort(key=lambda e: e["width"] * e["height"], reverse=True)

    saved = 0
    for i, e in enumerate(entries):
        img = to_image(e)
        if img is None:
            continue
        # 保存为 PNG
        name = f"img_{i:03d}_{e['width']}x{e['height']}.png"
        path = out_dir / name
        img.save(path)
        saved += 1
        print(f"  [{saved}] {name}  filter={e['filter']} cs={e['colorspace']} "
              f"bpc={e['bpc']}")

    print(f"\n共导出 {saved} 张图片到 {out_dir}")


if __name__ == "__main__":
    main()
