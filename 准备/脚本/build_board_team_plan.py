from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


OUTPUT = Path(__file__).resolve().parents[1] / "高云选题二开发板配置与团队协作方案.docx"


def set_font(run, size=10.5, bold=False, color=None, family="微软雅黑"):
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


def add_table(headers, rows, widths, size=8.3):
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
            set_cell(row.cells[index], value, center=(index == 0), size=size)
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
        set_font(paragraph.add_run(line), size=8.5, family="Consolas")
    document.add_paragraph()


document = Document()
section = document.sections[0]
section.top_margin = Cm(1.9)
section.bottom_margin = Cm(1.8)
section.left_margin = Cm(2.1)
section.right_margin = Cm(2.1)

normal = document.styles["Normal"]
normal.font.name = "微软雅黑"
normal.font.size = Pt(10.5)
normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "微软雅黑")

for style_name, size, color in [
    ("Title", 23, (0, 0, 0)),
    ("Heading 1", 16, (31, 78, 121)),
    ("Heading 2", 13, (47, 84, 114)),
]:
    style = document.styles[style_name]
    style.font.name = "微软雅黑"
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = RGBColor(*color)
    style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "微软雅黑")

title = document.add_paragraph(style="Title")
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_before = Pt(115)
title.paragraph_format.space_after = Pt(25)
title.add_run("高云选题二开发板配置与团队协作方案")

subtitle = document.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(subtitle.add_run("三人团队与两套 Tang Mega 60K 使用规划"), size=14, bold=True, color=(31, 78, 121))

date = document.add_paragraph()
date.alignment = WD_ALIGN_PARAGRAPH.CENTER
date.paragraph_format.space_before = Pt(155)
set_font(date.add_run("编制日期 2026年9月10日"), size=10, color=(89, 89, 89))

document.add_page_break()

add_heading("一 结论")
add_paragraph(
    "团队成员不需要每人长期占用一块开发板。对于三人队伍，两套Tang Mega 60K完整开发套装已经足够，一套也可以推进项目。大量工作可以在电脑上通过Python参考模型、RTL仿真、综合及时序分析完成，只有板级接口、音频输出、传感器接入和整机验证需要使用实物开发板。"
)
add_paragraph(
    "两套板卡的最佳用法不是平均分给两名队员，而是固定为稳定主板和实验开发板。稳定主板始终保留当前可演示版本，实验板用于新RTL、新外设、新约束和高风险功能。实验功能验证完成后，再合并到稳定主板。"
)

add_table(
    ["问题", "结论", "说明"],
    [
        ["三个人是否需要三块板", "不需要", "音频RTL和软件验证的大量工作无需长期占板"],
        ["一块板是否能完成项目", "可以", "需要轮流上板，开发效率和备用能力较低"],
        ["两块板是否足够", "足够且较理想", "可保留稳定版本并并行测试新功能"],
        ["是否需要第三块板", "通常不需要", "预算投入仪器、传感器和备用外设更有效"],
    ],
    [5.0, 3.5, 7.5],
)

add_heading("二 为什么不需要每人一块开发板")
add_paragraph(
    "FPGA项目并不是每项工作都要在板卡上进行。模块设计、参考模型、Testbench、自动回归、资源估算和文档工作都可以脱离开发板完成。开发板主要用于验证工具生成结果与真实硬件是否一致。"
)

add_table(
    ["工作内容", "是否需要开发板", "主要工具"],
    [
        ["DDS和波表算法", "不需要", "Python和RTL仿真器"],
        ["ADSR包络", "不需要", "Python黄金模型和Testbench"],
        ["复音管理", "不需要", "随机事件仿真和断言"],
        ["混音与饱和", "不需要", "逐样本参考比较"],
        ["综合和资源分析", "通常不需要", "Gowin EDA"],
        ["时序分析", "通常不需要", "布局布线和时序报告"],
        ["I2S真实输出", "需要", "开发板、DAC、逻辑分析仪"],
        ["琴键和传感器", "需要", "开发板、外设和示波器"],
        ["音频试听和频谱", "需要", "开发板、音箱和音频采集"],
        ["整机稳定性", "需要", "完整硬件系统"],
    ],
    [5.0, 4.0, 7.0],
)

add_heading("三 两套板卡的角色")
add_heading("一号板 稳定主板", 2)
add_bullet("保存当前已经验证通过的整机工程。")
add_bullet("固定主要供电、音频和交互接线。")
add_bullet("用于演示、视频录制和阶段验收。")
add_bullet("新功能未经实验板验证前，不直接烧录到主板。")
add_bullet("比赛时作为正式展示板。")

add_heading("二号板 实验开发板", 2)
add_bullet("测试新版RTL和未验证的时钟、约束及接口。")
add_bullet("接入新琴键、ADC、压力、光电和距离传感器。")
add_bullet("测试PCM5102A、效果器、HDMI和频谱显示。")
add_bullet("用于高风险接线和电平验证。")
add_bullet("比赛时作为备用板，必要时恢复稳定码流。")

add_diagram([
    "一号板 稳定主板",
    "已验证音频核心 + 已冻结外设 + 可演示版本",
    "                       ^",
    "                       | 合并通过验收的功能",
    "                       |",
    "二号板 实验开发板",
    "新版RTL + 新传感器 + 新约束 + 效果器与显示实验",
])

add_heading("四 三人团队分工")
add_table(
    ["角色", "主要工作", "开发板需求"],
    [
        ["音频核心负责人", "DDS、波表、ADSR、复音、音色、混音、效果器、I2S及时序优化", "以电脑仿真为主，阶段性使用实验板"],
        ["交互与板级负责人", "琴键、传感器、ADC、接线、约束、电源、电平、仪器和PCB", "经常使用实验板"],
        ["软件验证负责人", "Python模型、Testbench、构建脚本、串口、录音、频谱和文档", "不需长期占板，验收时使用主板"],
    ],
    [4.0, 8.0, 4.0],
)

add_heading("音频核心负责人", 2)
add_bullet("建立48 kHz音频数据通路和定点格式。")
add_bullet("实现DDS、波表、多音色和独立ADSR。")
add_bullet("实现声部分配、宽位混音、限幅和效果器。")
add_bullet("根据综合及时序报告优化流水线。")

add_heading("交互与板级负责人", 2)
add_bullet("核对NEO Dock原理图、I/O Bank电压和引脚复用。")
add_bullet("对矩阵键盘、压力琴键、MIDI键床等候选方案进行小规模实验。")
add_bullet("完成外设驱动、接线表、CST约束和测试点。")
add_bullet("使用逻辑分析仪和示波器验证I2S、SPI、触发及延迟。")

add_heading("软件验证负责人", 2)
add_bullet("建立Python黄金参考和波表生成脚本。")
add_bullet("建立可自动判定PASS或FAIL的RTL回归测试。")
add_bullet("编写Gowin构建、烧录、串口采集和音频分析脚本。")
add_bullet("整理测试数据、报告、演示视频和答辩材料。")

add_heading("五 两块板如何并行开发")
add_paragraph(
    "项目初期可以在一号板验证音频核心，在二号板验证交互输入。两边通过统一演奏事件接口解耦。交互模块只要输出相同的Note On、Note Off、Velocity和连续控制参数，就可以接入音频核心，不需要同时修改合成器。"
)

add_diagram([
    "一号板 音频链路",
    "UART或测试事件 -> 复音管理 -> DDS -> ADSR -> 混音 -> I2S",
    "",
    "二号板 交互链路",
    "琴键 传感器 ADC -> 滤波 -> 统一演奏事件 -> UART验证",
    "",
    "接口验收通过后",
    "交互链路 + 音频链路 -> 一号板稳定整机版本",
])

add_table(
    ["开发阶段", "一号板", "二号板", "电脑端"],
    [
        ["基础阶段", "官方音频和固定测试音", "LED、UART和GPIO实验", "Python模型和Testbench"],
        ["音频阶段", "DDS、ADSR和复音", "琴键、ADC和传感器", "逐样本比较和构建脚本"],
        ["扩展阶段", "稳定整机版本", "FM、效果器和显示", "频谱、资源和时序分析"],
        ["提交阶段", "录制视频和最终演示", "恢复稳定版本作为备用", "文档、归档和复现检查"],
    ],
    [3.2, 4.6, 4.6, 3.6],
)

add_heading("六 必须确认是两套完整开发板")
add_paragraph(
    "两块60K SOM核心板但只有一个NEO Dock，不等同于两套可并行使用的开发板。单独SOM缺少方便使用的供电、JTAG、UART、音频和扩展接口，第二块核心板主要只能作为备件。"
)

add_table(
    ["配置", "实际能力", "判断"],
    [
        ["60K SOM一块加NEO Dock一块", "一套完整开发环境", "可以完成项目"],
        ["60K SOM两块加NEO Dock一块", "只能方便地同时使用一套", "备用核心板配置"],
        ["60K SOM两块加NEO Dock两块", "两套独立开发环境", "三人队伍理想配置"],
        ["完整套装三套", "可以三路并行，但利用率有限", "通常没有必要"],
    ],
    [5.0, 7.0, 4.0],
)

add_heading("七 购买与申请建议")
add_paragraph(
    "高云板卡申请通常以每支队伍一块为单位，因此免费申请到一套即可满足赛事基本开发条件。若预算允许，可以自购第二套完整Tang Mega 60K基础套餐，用于并行实验和比赛备用。"
)
add_table(
    ["预算情况", "建议配置", "说明"],
    [
        ["预算紧张", "一套完整60K", "通过排期轮流上板，电脑端并行开发"],
        ["正常竞赛预算", "两套完整60K", "稳定主板加实验备用板"],
        ["已有一套借用板", "再自购一套完整60K", "兼顾并行开发和赛场保险"],
        ["考虑第三套", "优先不购买", "将预算投入仪器、传感器、DAC和PCB"],
    ],
    [4.0, 5.0, 7.0],
)

add_heading("八 两套板的使用规范")
add_number("为每块板粘贴明显标签，分别标记稳定主板和实验板。")
add_number("稳定主板只烧录通过仿真、综合、时序和实验板验证的版本。")
add_number("实验板改动接线前先断电，并核对3.3 V电平和共地关系。")
add_number("两块板使用同一代码仓库，不允许维护两套无法合并的主工程。")
add_number("使用Git分支区分稳定版本和实验功能，合并前执行全回归。")
add_number("每次上板记录码流版本、CST约束、接线表和测试结果。")
add_number("比赛前将同一稳定码流、约束和配置烧录到两块板进行复现。")

add_heading("九 版本与分支建议")
add_diagram([
    "main",
    "`-- 始终保持可仿真 可综合 可演示",
    "",
    "develop",
    "|-- feature/input_interface",
    "|-- feature/fm_timbre",
    "|-- feature/audio_delay",
    "`-- feature/display",
    "",
    "实验板使用 feature 或 develop",
    "稳定主板只使用 main 或 release 标签",
])

add_heading("十 替代第三块板的设备投入")
add_paragraph("与购买第三套开发板相比，下列设备更能提高调试效率和项目可靠性。")
add_table(
    ["设备", "建议数量", "价值"],
    [
        ["USB逻辑分析仪", "2个", "音频组和硬件组可以同时检查I2S与SPI"],
        ["PCM5102A", "2至3个", "主输出、实验和现场备用"],
        ["USB音频采集卡", "1个", "自动录音、频谱和ADSR测量"],
        ["传感器样品", "每类1至2个", "比较交互方案后再批量购买"],
        ["PCB打样", "预留两轮", "功能稳定后提高连接可靠性"],
        ["电源和线材", "主备各一套", "降低现场供电和接触故障"],
    ],
    [4.0, 3.0, 9.0],
)

add_heading("十一 当前执行建议")
add_number("确认现有两块板是否都是60K SOM加NEO Dock完整套装。")
add_number("选定一号稳定主板和二号实验板，并贴标签。")
add_number("建立统一Git仓库和稳定、开发、功能分支。")
add_number("在一号板优先打通官方音频和固定440 Hz测试音。")
add_number("在二号板验证UART、琴键、ADC和候选传感器。")
add_number("冻结统一演奏事件接口，让两个方向可以独立开发。")
add_number("功能合并前执行模块仿真、全回归、综合和时序检查。")

add_heading("十二 最终结论")
add_paragraph(
    "三人队伍不需要三套开发板。两套完整Tang Mega 60K已经是理想配置，其中一套负责稳定整机，另一套负责实验开发和比赛备用。音频核心负责人和软件验证负责人可以长期在电脑端并行工作，交互与板级负责人主要使用实验板。项目效率取决于统一接口、版本管理和验证流程，而不是让每名队员各自维护一块互不兼容的开发板。"
)

document.core_properties.title = "高云选题二开发板配置与团队协作方案"
document.core_properties.subject = "三人团队与两套Tang Mega 60K使用规划"
document.core_properties.author = ""
document.save(OUTPUT)
print(OUTPUT)
