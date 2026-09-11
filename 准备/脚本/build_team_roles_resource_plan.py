"""生成《06 三人分工与软硬件资源管理方案》Word 报告。

运行方式（在 准备 目录下）：
    Set-Location 准备
    python .\脚本\build_team_roles_resource_plan.py
"""

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUTPUT = Path(__file__).resolve().parents[1] / "文档" / "06 三人分工与软硬件资源管理方案.docx"

FONT = "微软雅黑"


def set_font(run, size=10.5, bold=False, color=None, family=FONT):
    run.font.name = family
    properties = run._element.get_or_add_rPr()
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        properties.rFonts.set(qn(key), family)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def shade(cell, fill):
    node = OxmlElement("w:shd")
    node.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(node)


def set_cell(cell, text, header=False, center=False, size=8.5):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if center or header else WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    set_font(
        paragraph.add_run(str(text)),
        size=size,
        bold=header,
        color=(255, 255, 255) if header else None,
    )
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header:
        shade(cell, "1F4E79")


def add_table(headers, rows, widths, size=8.3, center_first=True):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for index, header in enumerate(headers):
        set_cell(table.cell(0, index), header, header=True)
        table.cell(0, index).width = Cm(widths[index])
    header_property = OxmlElement("w:tblHeader")
    header_property.set(qn("w:val"), "true")
    table.rows[0]._tr.get_or_add_trPr().append(header_property)
    for row_values in rows:
        row = table.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for index, value in enumerate(row_values):
            centered = center_first and index == 0
            set_cell(row.cells[index], value, center=centered, size=size)
            row.cells[index].width = Cm(widths[index])
    document.add_paragraph()


def add_heading(text, level=1):
    paragraph = document.add_heading(text, level=level)
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(10 if level == 1 else 6)
    paragraph.paragraph_format.space_after = Pt(4)


def add_paragraph(text):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.line_spacing = 1.22
    paragraph.paragraph_format.space_after = Pt(5)
    set_font(paragraph.add_run(text))


def add_bullet(text):
    paragraph = document.add_paragraph(style="List Bullet")
    paragraph.paragraph_format.space_after = Pt(2)
    set_font(paragraph.add_run(text), size=10)


def add_number(text):
    paragraph = document.add_paragraph(style="List Number")
    paragraph.paragraph_format.space_after = Pt(3)
    set_font(paragraph.add_run(text), size=10)


def add_diagram(lines):
    table = document.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    cell = table.cell(0, 0)
    cell.text = ""
    shade(cell, "F2F2F2")
    for index, line in enumerate(lines):
        paragraph = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        set_font(paragraph.add_run(line), size=9, family=FONT)
    document.add_paragraph()


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    begin_run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin_run._r.append(begin)
    set_font(begin_run, size=9, color=(110, 110, 110))

    instr_run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    instr_run._r.append(instr)
    set_font(instr_run, size=9, color=(110, 110, 110))

    end_run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run._r.append(end)
    set_font(end_run, size=9, color=(110, 110, 110))


document = Document()
section = document.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
section.top_margin = Cm(1.9)
section.bottom_margin = Cm(1.8)
section.left_margin = Cm(2.1)
section.right_margin = Cm(2.1)

normal = document.styles["Normal"]
normal.font.name = FONT
normal.font.size = Pt(10.5)
normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)

for style_name, size, color in [
    ("Title", 23, (0, 0, 0)),
    ("Heading 1", 16, (31, 78, 121)),
    ("Heading 2", 13, (47, 84, 114)),
]:
    style = document.styles[style_name]
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = RGBColor(*color)
    style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)

title = document.add_paragraph(style="Title")
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_before = Pt(120)
title.paragraph_format.space_after = Pt(22)
title.add_run("三人分工与软硬件资源管理方案")

subtitle = document.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(subtitle.add_run("Tang Mega 60K 双板与仪器共享执行说明"), size=14, bold=True, color=(31, 78, 121))

date = document.add_paragraph()
date.alignment = WD_ALIGN_PARAGRAPH.CENTER
date.paragraph_format.space_before = Pt(150)
set_font(date.add_run("2026 年 9 月"), size=11)

document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

add_heading("一 文档目的与适用范围", 1)
add_paragraph(
    "本方案确定三人团队在 Tang Mega 60K 平台上的岗位划分、板卡与逻辑分析仪的使用规则，"
    "以及软件工作量过多时的分担方式。方案适用于 2026 年 FPGA 创新设计赛道高云选题二项目的全部开发阶段，"
    "与仓库中的角色分工、协作执行手册和资源使用记录配套使用。"
)
add_paragraph(
    "方案要解决三个问题。第一是责任人问题，每类交付物必须有唯一的主负责人，算法结果不能被多人分别解释。"
    "第二是资源问题，两套开发板和两台逻辑分析仪要同时服务三条并行工作线，必须给出可执行的配额和冲突处理顺序。"
    "第三是瓶颈问题，算法建模、验证脚本和上位机都算软件工作量，集中在一人身上会拖慢关键路径，需要预先约定分担边界。"
)
add_paragraph(
    "主要结论是采用 M1、M2、M3 三个岗位：M1 负责音频算法、验证与竞赛交付；M2 负责 FPGA 技术与系统集成并兼任技术与集成负责人；"
    "M3 负责实体硬件、交互与上板验证。两块开发板合计每周四十小时配额，两台逻辑分析仪合计每周四十小时配额，"
    "配额是预约基准而非个人所有权，未使用份额回到共享池。软件任务积压时由 M2 和 M3 分担实现工作，"
    "算法数学定义和最终验收始终由 M1 负责。"
)

add_heading("二 三人岗位与所有权", 1)
add_paragraph("岗位代号是本项目的正式称谓，表格给出各岗位的所有权范围和主要交付物。")
add_table(
    ["岗位", "定位", "所有权核心", "主要交付物"],
    [
        ["M1", "音频算法、验证与竞赛交付负责人",
         "算法定义、Python 黄金模型、算法 RTL 行为、逐样本验证",
         "模型与测试向量、算法 RTL、验证记录、报告与答辩材料"],
        ["M2", "FPGA 技术与系统集成负责人",
         "时钟、PLL、复位、CDC、FIFO、I2S、顶层、约束、构建与时序收敛",
         "顶层工程与约束、综合与时序报告、稳定码流、集成窗口结论"],
        ["M3", "实体硬件、交互与上板验证负责人",
         "供电、电平、接线、传感器、DAC、功放、仪器实测",
         "接线与引脚表、测量数据、上板验证脚本、对比测试结论"],
    ],
    [1.6, 4.2, 5.6, 5.4],
)
add_paragraph(
    "决策权与一票否决同步明确。M1 决定定点格式、音色结构和验收阈值，可因算法结果与模型不符而否决合并；"
    "M2 决定时钟复位方案、CDC 与 FIFO 结构、I2S 实现和构建流程，可因时序未收敛或 CDC 未做专项检查而否决合并；"
    "M3 决定选型接线、电平与供电方案和测量方法，可因电气安全风险或电平未核对而否决上电。"
)

add_heading("三 关键边界划分", 1)
add_paragraph("以下边界最容易产生争议，在此冻结归属，避免重复实现或互相等待。")
add_table(
    ["事项", "归属", "说明"],
    [
        ["I2S 数字发送", "M2", "本质是接口时序与约束问题，M1 提供 PCM 格式与位宽要求并复核数据相位"],
        ["DDS、波表、ADSR、复音、混音", "M1", "按软件工作管理，算法定义、实现和逐样本验证由 M1 负责"],
        ["延迟与合唱等数字效果器", "M1", "跨采样率切换和跨时钟域部分由 M2 参与实现"],
        ["顶层、公共接口、CST 与 SDC", "M2", "M3 提供引脚、电平和实物接线依据并复核一致性"],
        ["供电、电平、接线、传感器、DAC、功放", "M3", "涉及安全的改动任何人都可先断电再补记录"],
        ["串口与仪器自动化软件", "M3", "只用于测量和采集，不得替代 FPGA 生成正式音频"],
        ["算法数学定义与最终验收", "M1", "不随软件工作量分担而转移"],
    ],
    [4.4, 1.8, 10.6],
)

add_heading("四 授权写入范围与复核关系", 1)
add_paragraph("队员和 AI 只能修改任务单授权的目录。跨目录修改先停止，列出影响并取得授权。")
add_table(
    ["目录", "主负责人", "必须复核人"],
    [
        ["rtl/audio、synth、voice、mixer、effects", "M1", "M2"],
        ["model、docs/test", "M1", "M3"],
        ["rtl/audio_out（I2S 数字发送）", "M2", "M1"],
        ["rtl/common、rtl/board、顶层、constraints、sim", "M2", "M3"],
        ["rtl/input", "M3", "M2"],
        ["software、scripts（串口、仪器、采集）", "M3", "M1"],
        ["docs、README、.github", "任务单指定", "至少一名非作者"],
    ],
    [8.4, 4.2, 4.2],
)
add_paragraph(
    "复核人不得是作者本人，必须实际运行测试或查看报告。复核结论使用通过、有条件通过或退回，并列出依据。"
    "涉及时钟、复位、CDC、FIFO 或引脚时，复核人必须确认对应的专项检查已完成。"
)

add_heading("五 板卡与仪器资源清单", 1)
add_paragraph("两套开发板和两台逻辑分析仪均为实验室共享资源，使用前确认设备已粘贴编号标签。")
add_table(
    ["编号", "名称", "定位", "默认配套"],
    [
        ["BD-01", "Tang Mega 60K 加 NEO Dock", "稳定集成板", "LA-01"],
        ["BD-02", "Tang Mega 60K 加 NEO Dock", "实验开发板", "LA-02"],
        ["LA-01", "逻辑分析仪", "优先跟随 BD-01", "BD-01"],
        ["LA-02", "逻辑分析仪", "优先跟随 BD-02", "BD-02"],
    ],
    [2.2, 6.0, 4.4, 4.2],
)
add_paragraph("其他仪器包括示波器、万用表、可调电源、USB 音频采集卡、焊台和热风枪，统一放在实验室按需借用并登记。")

add_heading("六 每周使用配额", 1)
add_paragraph("配额是每周可优先预约的机时上限，用于保证关键路径上的开发时间，不代表所有权。")
add_table(
    ["使用人", "开发板每周配额", "逻辑分析仪每周配额"],
    [
        ["M1", "6 小时", "4 小时"],
        ["M2", "14 小时", "14 小时"],
        ["M3", "10 小时", "12 小时"],
        ["共同集成", "10 小时", "10 小时"],
        ["合计", "40 小时", "40 小时"],
    ],
    [4.4, 6.2, 6.2],
)
add_paragraph(
    "逻辑分析仪配额指单独占用分析仪的时间。与共同集成时段同时使用时不重复计算。"
    "连续两周未使用配额的，份额自动让给关键路径任务。"
)

add_heading("七 预约与冲突处理", 1)
add_number("在资源使用记录中登记预约，写明日期、时段、板卡编号、仪器编号和用途。")
add_number("同一时段冲突时，优先级顺序为：上板验证关键路径任务、共同集成窗口、算法仿真需要上板确认的实验、个人探索性实验。")
add_number("仍然冲突时由 M2 作为技术与集成负责人协调，必要时把探索性实验改到下一周。")
add_number("预约后不用的，应在时段开始前释放，让份额回到共享池。")
add_number("未登记的使用不参与下周配额，但需要在同步会上说明原因。")

add_heading("八 板卡使用规范", 1)
add_paragraph("两块板卡承担不同角色，混用会破坏稳定版本的可复现性。")
add_table(
    ["板卡", "允许的操作", "禁止的操作"],
    [
        ["BD-01 稳定集成板", "烧录通过仿真、综合、布局布线和时序检查的版本并做复现验证",
         "做未验证的接线改动，或烧录来源不明的码流"],
        ["BD-02 实验开发板", "试验新传感器、新引脚、新协议和临时接线",
         "把临时接线长期留在板上当作默认状态"],
    ],
    [3.6, 6.6, 6.6],
)
add_paragraph("在 BD-02 上改接线前先断电，核对 3.3 V 电平和共地关系。试验完成后把结论写入硬件或引脚文档。")

add_heading("九 码流与版本追踪", 1)
add_paragraph("每块板上运行的码流必须能追到具体提交号或标签，不允许长期运行来源不明的码流。")
add_diagram([
    "主干与分支",
    "  main     稳定码流 只接受来自 develop 的合并 打标签后用于比赛复现",
    "  develop  通过模块测试的集成版本",
    "  feature  单一功能开发     fix  缺陷修复     docs  文档与规范",
    "",
    "码流归位",
    "  BD-01  只运行 main 标签对应的稳定码流",
    "  BD-02  运行 feature 或 develop 的实验码流",
])
add_paragraph("更换码流后在资源使用记录备注栏写明前后版本。禁止强制推送覆盖队友提交，需要回退时使用 revert 产生新提交。")

add_heading("十 仪器使用与电气安全", 1)
add_bullet("使用前确认探头衰减比、量程和耦合方式，避免把 3.3 V 信号按 50 欧输入测量。")
add_bullet("逻辑分析仪采样率必须满足被测信号最高频率，测 I2S 时同时抓 BCLK、LRCLK 和 DATA。")
add_bullet("使用可调电源时先限流再逐步升压，避免直接满压上电。")
add_bullet("5 V 输出不得直接接到 3.3 V FPGA GPIO，必须先确认分压或电平转换。")
add_bullet("音频输出连接有源音箱、功放输入或采集设备，不直接驱动无源扬声器。")
add_bullet("引脚表和约束文件必须一致，接线变更后同步更新约束、接口文档和测试记录。")
add_bullet("发现发热、异味或供电异常时立即断电，并在技术决策记录中写明原因。")

add_heading("十一 记录与检查", 1)
add_paragraph(
    "每次使用板卡或仪器后在资源使用记录中登记实际时长和结果，结果必须写明验证等级。"
    "每周三方同步时核对配额使用情况，确认是否有份额需要释放。每月核对一次实际占用与登记是否一致，"
    "不一致时以登记为准并补齐记录。板卡故障、仪器损坏、码流回退和接线改动记入异常与变更记录。"
)

add_heading("十二 软件工作量分担规则", 1)
add_paragraph("算法模型、验证脚本、上位机和报告脚本都算软件工作量。当 M1 的任务积压并影响关键路径时，由 M1 在任务看板提出并注明分担范围。")
add_table(
    ["分担人", "可以承担", "不可承担"],
    [
        ["M2", "算法 RTL 的流水线划分、资源优化、FIFO 与 CDC 实现、I2S 与构建脚本", "算法数学定义、验收阈值"],
        ["M3", "按键与传感器驱动、串口协议、仪器控制、数据采集与自动化脚本", "算法数学定义、验收阈值"],
    ],
    [2.6, 8.6, 5.6],
)
add_paragraph("分担后仍由 M1 负责算法数学定义、黄金模型口径和最终验收。分担人完成的代码按第四节的目录归属复核，验证等级不得降低。")

add_heading("十三 结论与执行要求", 1)
add_number("三名队员确认自己的岗位代号，并按角色分工文件核对所有权和复核关系。")
add_number("在 BD-01 和 BD-02 上粘贴编号标签，两台逻辑分析仪同样贴标签并登记首次使用。")
add_number("在资源使用记录中登记本周预约，未登记的使用不参与下周配额。")
add_number("每次合并请求使用仓库模板，写明运行命令、验证等级和未验证的硬件项目。")
add_number("软件任务积压时按第十二节分担，但算法定义与最终验收不转移。")
add_paragraph(
    "本方案的效果取决于执行一致性。配额、复核和验证等级只有在每次提交中如实记录，"
    "才能真正降低三人三 AI 并行开发的返工率。任何偏离本方案的安排都应写入技术决策记录并说明回退方案。"
)

footer = section.footer
add_page_number(footer.paragraphs[0])

document.core_properties.title = "三人分工与软硬件资源管理方案"
document.core_properties.subject = "Tang Mega 60K 双板与仪器共享执行说明"
document.core_properties.author = ""

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
document.save(OUTPUT)
print(OUTPUT)
