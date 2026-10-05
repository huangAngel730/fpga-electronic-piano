#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为入库的外部整理稿添加来源声明头，并把封装写法降级为待定。

只做字符串层面的定点替换，不做任何正文改写。可重复执行（幂等）。
用法：python -X utf8 code/scripts/inject_reference_notice.py
"""

from pathlib import Path
import hashlib
import sys

REPO = Path(__file__).resolve().parents[2]
REF = REPO / "code" / "docs" / "reference"

SRC_SHA = "EB24C3A069F1B31FF27E89DC5563F260ADD176C98FB1F4303E6AD24C53A06B0F"
IDX_SHA = "F2EBFAE62927DBDC7445E99290D26022F9C1CB95023A1B7380B40F54C2B02DE8"
MARK = "【本仓库入库说明"

HEADER = """> **【本仓库入库说明 — 非原文，2026-09-13 追加】**
>
> 本文件是**外部整理稿**，不是本仓库编写的文档。原始文件由用户提供，
> SHA-256 `EB24C3A069F1B31FF27E89DC5563F260ADD176C98FB1F4303E6AD24C53A06B0F`（111107 字节）。
> 除本说明块与下方标注的 3 处“封装写法”措辞降级外，**正文未作任何改动**。
>
> - 它与 `code/docs/板级硬件事实.md` 是**两个独立来源**，后者才是本项目的板级事实单一来源。
>   两者冲突时以后者与 `技术决策记录.md` 的已冻结决策为准。详见本目录 `README.md`。
> - 本文件**不作为约束依据**。写 `IO_LOC`/`IO_PORT` 时以
>   `code/constraints/electronic_piano.cst` 与官方参考 CST 为准。
> - **已核对一致**：音频 4 脚（Y17/AB17/AA16/AB16）、`sys_clk`=V22、
>   `sys_rst_n`=AA13、`uart_tx`=U15 与本仓库记录完全一致；
>   复位一节与 D018 更正完全吻合。
> - **已核对差异**：① `LEDs[0..7]` 实为 PMOD0 别名而非板载 LED（本文件正确，
>   本仓库旧记录已据此更正）；② 封装写法按用户指示保持**待定**（见下方 3 处标注）；
>   ③ 本文件提到的 2 个原理图 PDF **未入本仓库**。
> - 本文件第 12 节“待用户确认”的 12 条**不等于本项目待办**，
>   实际跟踪状态见 `风险登记表.md` 与 `任务看板.md`。

"""

# (原文, 替换后) —— 均为整行精确匹配
EDITS = [
    (
        "- FPGA 工程器件已由用户确认：`GW5AT-LV60PG484AC1/I0`，IDE 显示封装 `PBG484A`、Device Version B。",
        "- FPGA 工程器件已由用户确认：`GW5AT-LV60PG484AC1/I0`，IDE 显示封装 `PBG484A`、Device Version B。"
        "**〔入库注：`PBG484A` 的写法按 D018 第 2 项保持待定，待首次上板读器件 ID 确认。〕**",
    ),
    (
        "| IDE 封装 | `PBG484A` | 用户确认；Excel `资料与版本!B8:C8` |",
        "| IDE 封装 | `PBG484A`**（待定）** | 用户确认；Excel `资料与版本!B8:C8`。"
        "**入库注：按 D018 第 2 项待定，非已核实结论** |",
    ),
    (
        "| 创建工程选择 | Device/Part：`GW5AT-LV60PG484AC1/I0`；Package：`PBG484A`；Device Version：B | 用户确认；Excel `资料与版本!B7:B8` |",
        "| 创建工程选择 | Device/Part：`GW5AT-LV60PG484AC1/I0`；Package：`PBG484A`**（待定）**；Device Version：B | "
        "用户确认；Excel `资料与版本!B7:B8`。**入库注：Package 写法按 D018 第 2 项待定** |",
    ),
]


IDX_HEADER = """> **【本仓库入库说明 — 非原文，2026-09-13 追加】**
>
> 本文件是**外部整理稿**的索引，不是本仓库编写的文档。原始文件由用户提供，
> SHA-256 `F2EBFAE62927DBDC7445E99290D26022F9C1CB95023A1B7380B40F54C2B02DE8`（5344 字节）。
> 除本说明块外，**正文未作任何改动**。
>
> **重要：本索引描述的是它自己那套资料目录，与本仓库的实际布局不同。**
> 它假设 Excel、官方 CST 和 2 个原理图 PDF 同处一个目录，但本仓库的实际位置是：
>
> | 索引里的文件 | 本仓库实际位置 |
> |---|---|
> | `Tang_Mega_60K_30354_NEO_31005_引脚事实表.xlsx` | `code/docs/`（已入库，哈希一致） |
> | `tang_mega_60K_pins.cst` | `code/constraints/tang_mega_60k_reference.cst`（已入库，哈希一致） |
> | `tang_mega_60k_30354_schematics..pdf` | **未入库**（可从 Sipeed 官方下载页获取） |
> | `Tang_Mega_NEO_Dock-138K_31005_Schematics (1).pdf` | **未入库**（同上） |
> | `BOARD_CONTEXT.md` | 本目录 `BOARD_CONTEXT_外部整理稿.md` |
> | `DOC_INDEX.md` | 本文件 |
>
> 因此本索引中"稳定资料基线为 4 个文件"的表述**不适用于本仓库**：
> 本仓库的稳定基线是 **1 个 Excel + 1 个官方 CST**（其余为衍生整理稿）。
> 索引记录的 4 个 SHA-256 中，Excel 与 CST 两项已与本仓库副本核对一致，
> 2 个 PDF 的哈希予以保留以便日后核对来源。
>
> 本文件**不作为约束依据**，详尽的差异说明见本目录 `README.md`。

"""


def _annotate(target: Path, pristine_sha: str, header: str, edits: list) -> int:
    """Add a provenance header and apply exact-match edits to one file."""
    if not target.is_file():
        print(f"missing: {target}")
        return 1

    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    text = raw.decode("utf-8")

    if MARK in text:
        print(f"already annotated: {target.name}")
        return 0

    if digest != pristine_sha:
        print(f"refuse: {target.name} sha256 is {digest}, expected pristine {pristine_sha}")
        return 1

    applied = 0
    for old, new in edits:
        if old not in text:
            print(f"refuse: {target.name} anchor not found -> {old[:50]}...")
            return 1
        if text.count(old) != 1:
            print(f"refuse: {target.name} anchor occurs {text.count(old)} times -> {old[:50]}...")
            return 1
        text = text.replace(old, new)
        applied += 1

    text = header + text
    target.write_bytes(text.encode("utf-8"))

    print(f"ok: annotated {target.name}")
    print(f"    pristine sha256 matched, {applied} edits applied")
    print(f"    new size {len(text.encode('utf-8'))} bytes")
    return 0


def main() -> int:
    rc = _annotate(
        REF / "BOARD_CONTEXT_外部整理稿.md", SRC_SHA, HEADER, EDITS
    )
    if rc != 0:
        return rc
    return _annotate(
        REF / "DOC_INDEX_外部整理稿.md", IDX_SHA, IDX_HEADER, []
    )


if __name__ == "__main__":
    sys.exit(main())
