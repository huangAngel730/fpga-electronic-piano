#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 V0030 行插入 code/docs/验证记录.md 的表格中，并更新末尾回归说明。

插入位置：V0029 所在行之后的第一处空行之前。要求 V0030 尚不存在，
避免重复插入。

用法：python -X utf8 code/scripts/append_v0030.py
"""

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "代码" / "docs" / "验证记录.md"

V0030 = (
    "| V0030 | 2026-09-13 | 板级资料 / 外部整理稿入库 | "
    "`code/docs/reference/`（新建：`README.md`、`BOARD_CONTEXT_外部整理稿.md`、"
    "`DOC_INDEX_外部整理稿.md`）、`code/scripts/inject_reference_notice.py`（新建）、"
    "`code/scripts/verify_reference_digests.py`（新建）、"
    "`code/scripts/negtest_reference_digests.py`（新建）、`code/scripts/check_repo.ps1`、"
    "`code/constraints/electronic_piano.cst`、`code/constraints/README.md`、"
    "`code/docs/板级硬件事实.md` | L0 | 附件字节级入库 + SHA-256 溯源；"
    "入库前 pristine 哈希闸门；与 `板级硬件事实.md`/CST/31005 表逐条交叉核对；"
    "完整性检查的三种变异体负向测试；`check_repo.ps1` 全量 10 项 | "
    "PASS（**静态核对与文件校验，无仿真无实测**）。"
    "**起因**：用户提供两份外部整理的板卡资料，指示“你看要不要放到仓库里面”，"
    "并确认按“外部整理稿原样入库 + 来源声明头”“封装写法改标待定”"
    "“PDF 不入库只在索引标注”三条方案执行。"
    "**入库内容**：`BOARD_CONTEXT.md`（111107 字节，704 行，"
    "SHA-256 `EB24C3A0…A06B0F`）与 `DOC_INDEX.md`（5344 字节，48 行，"
    "SHA-256 `F2EBFAE6…2B02DE8`），**入库时哈希与来源逐字节一致**；"
    "改名为加 `_外部整理稿` 后缀存入新建的 `code/docs/reference/`，"
    "与厂商原始资料及本仓库自编文档分开。"
    "**为什么单列目录而不并入 `板级硬件事实.md`**：两者是**独立来源**，"
    "外部稿的输入资料与本仓库相同（同一份 31005 引脚事实表、同一份官方 CST，"
    "哈希均已核对一致），直接合并会产生“两个真相”。"
    "故定位为**只读衍生参考**，明确其价值在于把原始表格加工成"
    "建 RTL/建约束可直接查阅的形式，且反复声明"
    "“本文件不作为约束依据、冲突时以本仓库已冻结决策为准”。"
    "**入库改动仅两处，正文未动**："
    "(1) 追加来源声明头（说明出处、哈希、与 `板级硬件事实.md` 的关系、"
    "不入库的 PDF、其第 12 节“待用户确认”不等于本项目待办）；"
    "(2) 把 3 处断言式表述“IDE 显示封装 `PBG484A`、已确认”降级标注为"
    "**待定**，与 D018 第 2 项口径统一。"
    "**正文完整性经机器验证**：`BOARD_CONTEXT` 去头后正文 76086 字符、"
    "相对原文净增 264 字节，恰为三处入库注（中文 UTF-8 每字 3 字节）；"
    "`DOC_INDEX` 正文净增 0 字节，即正文逐字未改。"
    "**与仓库既有记录的交叉核对（4 项一致）**："
    "音频四脚 `i2s_bclk`=Y17/J2-26、`i2s_lrck`=AB17/J2-28、"
    "`i2s_din`=AA16/J2-30、`pa_en`=AB16/J2-36，均 `LVCMOS33`/Bank 7，"
    "与 `electronic_piano.cst` 及 D020 完全一致；"
    "`sys_clk`=V22、`sys_rst_n`=AA13、`uart_tx`=U15 亦一致；"
    "**其复位一节与 D018 更正完全吻合**——`sys_rst_n`=AA13 的真名是"
    "用户按键 `EX_KEY.0`，`RECONFIG`=N12 才是配置专用，二者不可混用。"
    "**发现的实质差异（3 条，已在 `reference/README.md` 与本记录留痕）**："
    "**差异一（补正本仓库旧记录）**——外部稿第 5.3 节明确记录"
    "**官方 CST 的 `LEDs[0]`–`LEDs[7]` 不是底板上的 8 颗板载 LED**，"
    "而是官方示例给 PMOD0 八根信号起的顶层别名，"
    "相同物理线同时复用为 `SDRAM1_D[0..7]`"
    "（来源标注“用户提供的核对截图”；引脚事实表 r48–r55）。"
    "据此复核本仓库：`板级硬件事实.md` 第 42 行与第 509 行"
    "**原本就写作“PMOD 外接”，是正确的**；"
    "但 `electronic_piano.cst` 第 83 行注释与 `constraints/README.md` 第 119 行"
    "曾误写为“板载 8 路 LED（与 PMOD0/SDRAM1 复用）”，**已更正**为"
    "“CST 的 `LEDs[0..7]` 是 PMOD0 别名、底板无可由 RTL 直接点亮的离散用户 LED、"
    "实际点亮电平取决于外接模块”，并注明来源。"
    "**本项目不使用这 8 根线，故更正不影响任何已定引脚**。"
    "**差异二**——外部稿称封装 `PBG484A` 已确认，与 D018 第 2 项的“待定”冲突，"
    "已按用户指示把外部稿该处降级，**首次上板读器件 ID 仍是最直接的确认手段**。"
    "**差异三**——外部稿索引记录的 2 个原理图 PDF"
    "（`tang_mega_60k_30354_schematics..pdf`、"
    "`Tang_Mega_NEO_Dock-138K_31005_Schematics (1).pdf`）"
    "**未入本仓库**，其 SHA-256 保留在索引中以便日后核对来源。"
    "**同时澄清**：外部稿索引所述“稳定资料基线为 4 个文件”"
    "**不适用于本仓库**（本仓库稳定基线是 1 个 Excel + 1 个官方 CST），"
    "且其声称的“149 条信号记录”与本仓库记录的 154 行口径不同，"
    "已在入库说明头中显式标注，避免读者误按外部目录结构找文件。"
    "**新增自动检查（`check_repo.ps1` 第 10 项）**："
    "调用 `verify_reference_digests.py` 断言两份整理稿仍带来源声明头、"
    "正文标题仍在、且正文字节数未相对原文减少（防止有人“顺手清理”掉说明块"
    "或截断正文，使读者误把外部稿当成本项目板级事实来源）。"
    "**负向测试（三种变异体，全部按预期 FAIL，且每次注入后还原为字节级一致）**："
    "① 整块删除来源声明头 → FAIL（banner 缺失 + body 缩小，3 项问题）；"
    "② 改写声明头措辞 → FAIL（banner 缺失）；"
    "③ 截断正文尾部 → FAIL（content was removed）。"
    "**过程中修正的自身缺陷（如实记录）**：(1) 首次负向测试**无效**——"
    "缺陷因沙箱拒绝写入而**从未真正注入**，检查却报 PASS，"
    "是“未失败过的检查等于未验证”的典型；提权后重做才暴露真实行为。"
    "(2) 第二次负向测试的注入方式**选错**——只替换 banner 后半段而保留了前缀，"
    "检测逻辑仍命中，故 PASS 属误判；改为整块删除后正确 FAIL。"
    "(3) 为在 PS 5.1 下比较中文而写的检测代码**引入了非 ASCII 字面量**，"
    "导致 `check_repo.ps1` 语法解析失败（正是 `code/AGENTS.md` 警告过的历史事故）；"
    "已把该检查**整体移入 Python**，`check_repo.ps1` 现为**纯 ASCII、0 语法错误**，"
    "中文比较不再经 PowerShell。"
    "(4) 备份文件因**每次 `pwsh` 调用落在不同沙箱临时目录**而丢失，"
    "改用“从附件重新复制 + 脚本内置 pristine 哈希闸门”重建，"
    "脚本对非 pristine 输入会拒绝执行。"
    "**未验证项**：两份外部稿的**内容真伪未逐条复核**——"
    "本次只核对了与本项目相关的 7 个引脚、复位定义与 LED 归属，"
    "其余（DDR3/SDRAM/HDMI/以太网/ADC/FAN 等本项目不使用的部分）"
    "仅做形式登记，未与原理图 PDF 对照；"
    "外部稿大量标注“待确认”的项也**未**逐条转化为本项目待办。"
)

FOOTER_OLD = (
    r"**T007 一键回归**：`.\code\scripts\run_t007_sim.ps1` "
    "编译运行顶层自检 testbench，"
    "全部 PASS 时退出码 0（当前 12 项检查）。"
    "对应 V0029。"
)
FOOTER_NEW = FOOTER_OLD + (
    " **板级资料一键校验**："
    r"`python -X utf8 .\code\scripts\verify_reference_digests.py` "
    "校验 `docs/reference/` 两份外部整理稿的"
    "来源声明头与正文完整性，"
    "全部 PASS 时退出码 0；"
    "已接入 `check_repo.ps1` 第 10 项。"
    "对应 V0030。"
)


def main() -> int:
    if not LOG.is_file():
        print(f"missing: {LOG}")
        return 1

    text = LOG.read_text(encoding="utf-8")
    if "| V0030 |" in text:
        print("V0030 already present; nothing to do")
        return 0
    if "| V0029 |" not in text:
        print("anchor V0029 not found")
        return 1

    lines = text.split("\n")

    # V0029 row is indented by two spaces in the current file.
    start = next(
        i for i, ln in enumerate(lines) if ln.lstrip().startswith("| V0029 |")
    )
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    row = indent + V0030
    j = start + 1
    while j < len(lines) and lines[j].strip():
        j += 1
    # lines[j] is the blank line (or EOF)
    lines.insert(j, row)

    text = "\n".join(lines)

    if FOOTER_OLD not in text:
        print("footer anchor not found; V0030 row inserted but footer untouched")
    else:
        text = text.replace(FOOTER_OLD, FOOTER_NEW, 1)

    LOG.write_text(text, encoding="utf-8")
    print(f"ok: inserted V0030 after line {start + 1} (before blank line {j + 1})")
    print(f"    indentation carried over: {len(indent)} space(s)")
    print(f"    new line count {len(text.split(chr(10)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
