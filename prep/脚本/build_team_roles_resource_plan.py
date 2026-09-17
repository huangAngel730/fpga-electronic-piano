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
    "本方案确定三人团队在 Tang Mega 60K 平台上的岗位划分、授权写入范围、复核关系、"
    "设备共用规则，以及软件工作量过多时的分担方式。方案适用于 2026 年 FPGA 创新设计赛道"
    "高云选题二项目的全部开发阶段，与仓库中的《角色分工》《三人协作执行手册》"
    "《Git 协作规范》和《板级硬件事实》配套使用。"
)
add_paragraph(
    "方案要解决三个问题。第一是责任人问题，每类交付物必须有唯一的主负责人，"
    "算法结果不能被多人分别解释。第二是设备问题，两套开发板和两台逻辑分析仪要同时服务"
    "三条并行工作线，需要明确共用方式。第三是瓶颈问题，算法建模、验证脚本和上位机"
    "都算软件工作量，集中在一人身上会拖慢关键路径，需要预先约定分担边界。"
)
add_paragraph(
    "主要结论是采用 M1、M2、M3 三个岗位：M1 负责音频算法、验证与竞赛交付；"
    "M2 负责 FPGA 技术与系统集成并兼任技术与集成负责人；M3 负责实体硬件、交互与上板验证。"
    "软件任务积压时由 M2 和 M3 分担实现工作，算法数学定义和最终验收始终由 M1 负责。"
)
add_paragraph(
    "有两条口径与早期版本不同，先在此说明，避免照旧稿执行。其一，设备不编号、不登记、"
    "不设每周配额：两块开发板与两台分析仪同型号可互换，编号只能靠实物贴标签维持，"
    "而逐次登记不产生新信息、只产生核对成本；设备管理的唯一落点是《板级硬件事实》"
    "的设备清单与共享使用注意一节。其二，不再使用按人长期分支：三人一律直接推 develop，"
    "复核统一归 M2；接口组共享文件改前先在群里说一句，编号只在推送前最后一步取。"
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
         "时钟、PLL、复位、CDC、FIFO、音频接口、顶层、约束、构建与时序收敛",
         "顶层工程与约束、综合与时序报告、稳定码流、集成窗口结论"],
        ["M3", "实体硬件、交互与上板验证负责人",
         "供电、电平、接线、传感器、DAC、功放、仪器实测",
         "接线与引脚表、测量数据、上板验证脚本、对比测试结论"],
    ],
    [1.6, 4.2, 5.6, 5.4],
)
add_paragraph(
    "决策权与一票否决同步明确。M1 决定定点格式、音色结构和验收阈值，可因算法结果与黄金模型"
    "不符而否决该次推送；M2 决定时钟复位方案、CDC 与 FIFO 结构、音频接口实现和构建流程，"
    "可因时序未收敛或 CDC 未做专项检查而否决该次推送；M3 决定选型接线、电平与供电方案"
    "和测量方法，可因电气安全风险或电平未核对而否决上电。"
)
add_paragraph(
    "三人的一票否决都只针对具体一次推送或一次上电，不构成对他人岗位所有权的长期接管。"
    "被否决的一方修正后重新提交，由原所有人继续负责，不转移归属。"
)

add_heading("三 关键边界划分", 1)
add_paragraph("以下边界最容易产生争议，在此冻结归属，避免重复实现或互相等待。")
add_table(
    ["事项", "归属", "说明"],
    [
        ["音频数字发送时序（rtl/audio_out）", "M2", "板载 PT8211 为 LSBJ 格式、非飞利浦标准 I2S；M1 提供 PCM 格式与位宽要求并复核数据相位"],
        ["DDS、波表、ADSR、复音、混音", "M1", "算法定义、实现和逐样本验证由 M1 负责"],
        ["延迟与合唱等数字效果器", "M1", "跨采样率切换和跨时钟域部分由 M2 参与实现"],
        ["顶层、公共接口、CST 与 SDC", "M2", "M3 提供引脚、电平和实物接线依据并复核一致性"],
        ["供电、电平、接线、传感器、DAC、功放", "M3", "涉及安全的改动任何人都可先断电再补记录"],
        ["串口与仪器自动化软件", "M3", "只用于测量和采集，不得替代 FPGA 生成正式音频"],
        ["算法数学定义与最终验收", "M1", "不随软件工作量分担而转移"],
        ["共享文件与编号表（共八处）", "共同", "接口组改前先在群里说一句；编号表组只按取号规则，编号在推送前最后一步取"],
    ],
    [4.4, 1.8, 10.6],
)

add_heading("四 授权写入范围与复核关系", 1)
add_paragraph("队员和 AI 只能修改任务单授权的目录。跨目录修改先停止，列出影响并取得授权。")
add_paragraph(
    "复核统一由 M2 承担，M2 自己主责的改动标记为自审。复核通过不强制留痕，"
    "只有发现问题时才补一行验证记录；任务自身的验证等级记录仍然必须写。"
)
add_table(
    ["目录", "主负责人", "复核"],
    [
        ["rtl/audio、synth、voice、mixer、effects", "M1", "M2"],
        ["model、docs/test", "M1", "M2"],
        ["rtl/audio_out（音频数字发送，i2s_tx.sv）", "M2", "自审"],
        ["rtl/common、rtl/board、顶层、constraints、sim", "M2", "自审"],
        ["rtl/input", "M3", "M2"],
        ["software、scripts（串口、仪器、采集）", "M3", "M2"],
        ["docs、README、.github", "任务单指定", "M2 或自审"],
    ],
    [8.4, 4.2, 4.2],
)
add_paragraph(
    "M1、M3 推送到 develop 之后，由 M2 复核该次推送的差异。复核结论使用通过、有条件通过"
    "或退回，并列出依据。涉及时钟、复位、CDC、FIFO 或引脚时，复核必须确认对应的专项检查已完成。"
    "作者与复核为同一人时标记自审，这是取消分支隔离后已知的强度损失，见《技术决策记录》D025"
    "的已知风险一节。"
)

add_heading("4.1 八处共享文件", 2)
add_paragraph(
    "以下八个文件都是公共文件，分接口组与编号表组。两组都留在清单里，但保护手段不同："
    "接口组改动前必须在群里说明；编号表组不需要提前说明，只受 4.2 的取号规则约束。"
)
add_table(
    ["组", "文件", "为什么在清单里", "保护手段"],
    [
        ["接口组", "rtl/board/electronic_piano_top.sv", "顶层端口，三人都要接", "改动前必须在群里说明"],
        ["接口组", "rtl/common/audio_defs_pkg.sv", "公共类型与打包事件定义", "同上"],
        ["接口组", "constraints/electronic_piano.cst", "引脚分配，改动影响实物接线", "同上"],
        ["接口组", "docs/模块接口规范.md", "接口的书面口径", "同上"],
        ["编号表组", "docs/验证记录.md（V00xx）", "三人都要追加行，Git 看不见重号", "不需提前说明，按 4.2 取号"],
        ["编号表组", "docs/技术决策记录.md（D0xx）", "同上", "同上"],
        ["编号表组", "docs/任务看板.md（T00xx 与状态列）", "同上", "同上"],
        ["编号表组", "docs/当前状态.md", "同上", "同上"],
    ],
    [1.8, 6.0, 5.4, 3.6],
)
add_paragraph(
    "编号表组是新增的。本项目实际发生过的两次编号撞号全部出在这几张表上，"
    "一处也不在原来的四个接口文件里；而且这些表三个岗位都要往里追加，"
    "按目录划分写入边界的办法对它们完全无效。"
)
add_paragraph(
    "但两组的保护手段后来做了修正。编号表组是每次任务收尾都要追加行的高频动作，"
    "而它的事故成因是取号时机：说一句「我要改验证记录」并不传递「我要用哪个号」，"
    "拦不住撞号。因此接口组继续要求改前说明，编号表组改为只受 4.2 的取号规则约束。"
    "清单仍保留八处，是为了让人查得到这八处都是公共文件。"
)

add_heading("4.2 取号时机", 2)
add_paragraph("编号指验证记录、技术决策记录、任务看板三张表里的 V00xx、D0xx、T0xx。取号顺序固定，不许提前。")
add_number("git fetch origin，然后 git pull --rebase origin develop。")
add_number("此时才打开编号表，看表末尾一行是什么，据此确定自己的编号。")
add_number("把编号写进表，做成一个只含编号与那一行的独立小提交。")
add_number("立刻推送。取号与推送之间不要隔夜，中间不夹别的改动。")
add_paragraph(
    "开工时不写编号，干活时不写编号，功能提交里不带编号。这么做的原因是：两次实际撞号"
    "都出在开工时先写死编号、几天后才推送，与分支无关。写号与推送之间的窗口越短，"
    "撞号概率越低。"
)

add_heading("4.3 撞号之后怎么处理", 2)
add_paragraph(
    "以 develop 上先推送成功的那一行为准，后推的人重排自己的编号，已经在别处写死的旧编号"
    "直接丢弃。不要用 git revert 去回改别人已经推上去的行，那会让整张表的序号出现空洞，"
    "并影响其他人已经写下的引用。"
)

add_heading("五 设备清单与共享使用", 1)
add_paragraph(
    "两套开发板和两台逻辑分析仪是同型号、可互换的共享资源。设备不编号、不贴标签、"
    "不建台账、不设每周配额；设备管理的唯一落点是《板级硬件事实》的设备清单与共享使用注意一节。"
)
add_table(
    ["设备", "数量", "说明"],
    [
        ["Tang Mega 60K 开发板（含 NEO Dock）", "2 套", "同型号可互换，不需要区分哪一块是哪一块"],
        ["逻辑分析仪", "2 台", "同型号可互换，优先跟随正在调试的那块板"],
        ["示波器、万用表、可调电源、USB 音频采集卡、焊台、热风枪", "按需", "放在实验室按需借用"],
    ],
    [5.6, 1.8, 9.4],
)
add_paragraph("不编号不等于没有约束。以下两条不变量与编号和登记无关，必须保持。")
add_number("随时有一块板能退回已知良好的码流版本。每次上电前确认板上运行的码流能追到具体提交号或标签，任何未验证的改动都能退回上一个已知良好版本。")
add_number("临时接线不得留作默认状态。临时接线只存在于本次实验期间，收工必须拆除；用于正式验收、演示或录像的板卡不得有临时飞线。")
add_paragraph(
    "判断某块板能否用于正式验收、演示或录像，看它当下的状态——跑的是通过验证的版本，"
    "并且板上没有临时飞线——不看它是哪一块。比赛前仍需用同一稳定码流在两块板上各下载一次，"
    "确认可重复下载。"
)

add_heading("5.1 上电顺序与调试线", 2)
add_paragraph("这一条是实际踩坑之后定下来的，顺序不能变。")
add_number("只插电源线。不要同时插电源线和调试线。")
add_number("按住电源键约两秒，看到多色闪烁的电源指示灯亮起，才算开机成功。")
add_number("确认开机成功之后再插调试线。调试线插上后会有四个橙色灯亮起，那不是电源指示灯，不能用来判断是否开机。")
add_paragraph(
    "调试线必须使用带数据传输功能的线，纯充电线不能用；调试线会长期固定使用，不要随意更换。"
    "曾经因为同时插电源线与调试线导致板卡无法开机，所以这条顺序是硬的。"
    "板上的现有拨码开关与跳线保持出厂状态，不要改动。接线变化后同步更新《板级硬件事实》。"
)

add_heading("六 仪器使用与电气安全", 1)
add_bullet("使用前确认探头衰减比、量程和耦合方式，避免把 3.3 V 信号按 50 欧输入测量。")
add_bullet("逻辑分析仪采样率必须满足被测信号最高频率，测音频接口时同时抓位时钟、帧时钟和数据三线。")
add_bullet("使用可调电源时先限流再逐步升压，避免直接满压上电。")
add_bullet("5 V 输出不得直接接到 3.3 V FPGA GPIO，必须先确认分压或电平转换。")
add_bullet("音频输出连接有源音箱、功放输入或采集设备，不直接驱动无源扬声器。")
add_bullet("引脚表和约束文件必须一致，接线变更后同步更新约束、接口文档和测试记录。")
add_bullet("引脚与约束中的 IO_LOC／IO_PORT 名称必须与顶层端口名逐字一致，物理约束只放在物理约束阶段。")
add_bullet("发现发热、异味或供电异常时立即断电，并在技术决策记录中写明原因。")

add_heading("七 板卡使用规范", 1)
add_paragraph("两块板不必区分身份，但同一时刻应保持一块板处于可交付状态。")
add_table(
    ["场景", "允许的操作", "禁止的操作"],
    [
        ["跑稳定码流的那块板", "只烧录通过仿真、综合、布局布线和时序检查的版本，并做复现验证",
         "做未验证的接线改动，或烧录来源不明的码流"],
        ["做实验的那块板", "试验新传感器、新引脚、新协议和临时接线",
         "把临时接线长期留在板上当作默认状态"],
    ],
    [3.6, 6.6, 6.6],
)
add_paragraph("改接线前先断电，核对 3.3 V 电平和共地关系。试验完成后把结论写入《板级硬件事实》或对应的引脚文档。")

add_heading("八 码流与版本追踪", 1)
add_paragraph("每块板上运行的码流必须能追到具体提交号或标签，不允许长期运行来源不明的码流。")
add_diagram([
    "分支与合并",
    "  main     稳定码流 只接受来自 develop 的合并 打标签后用于比赛复现",
    "  develop  集成版本 三人一律直接推到这里 不再使用按人长期分支",
    "",
    "码流归位",
    "  跑稳定码流的板  只运行 main 标签对应的版本",
    "  做实验的板      运行 develop 上通过模块测试的版本",
])
add_paragraph(
    "更换码流时在提交信息或群内记录里写明前后版本。禁止 git push --force 覆盖队友提交；"
    "需要回退时使用 git revert 产生新提交，保留完整历史。被远端拒绝时先 git pull --rebase 再重推。"
)

add_heading("九 记录与检查", 1)
add_paragraph("设备不建台账，但开发记录一项都不能省。以下四类记录是唯一的可追溯来源。")
add_table(
    ["记录", "写什么", "谁写"],
    [
        ["docs/验证记录.md（V00xx）", "任务完成时的验证等级、执行的命令、通过与否、未执行的部分", "任务执行人"],
        ["docs/技术决策记录.md（D0xx）", "改变接口、资源或流程的决定，含候选方案、理由和回退方案", "提议人"],
        ["docs/任务看板.md（T00xx）", "任务状态、复核人、验收条件", "任务负责人"],
        ["docs/当前状态.md", "当前在做什么、下一步、阻塞项", "任务负责人"],
    ],
    [4.6, 8.4, 3.0],
)
add_paragraph(
    "验证等级必须写明实际执行到哪一级：静态检查、仿真通过、综合通过、布局布线通过、时序收敛、"
    "已上板实测。未执行的阶段不能写成已通过。设备故障、码流回退和接线变更记入技术决策记录"
    "或《板级硬件事实》，不再有单独的异常与变更记录文件。"
)
add_paragraph(
    "推送前运行 .\\code\\scripts\\check_repo.ps1 并要求全部通过，这是取消分支隔离后的主要门槛。"
    "注意该检查目前不扫描 code/software/，上位机代码需要自行运行对应测试。"
)

add_heading("十 软件工作量分担规则", 1)
add_paragraph("算法模型、验证脚本、上位机和报告脚本都算软件工作量。当 M1 的任务积压并影响关键路径时，由 M1 在任务看板提出并注明分担范围。")
add_table(
    ["分担人", "可以承担", "不可承担"],
    [
        ["M2", "算法 RTL 的流水线划分、资源优化、FIFO 与 CDC 实现、音频接口与构建脚本", "算法数学定义、验收阈值"],
        ["M3", "按键与传感器驱动、串口协议、仪器控制、数据采集与自动化脚本", "算法数学定义、验收阈值"],
    ],
    [2.6, 8.6, 5.6],
)
add_paragraph("分担后仍由 M1 负责算法数学定义、黄金模型口径和最终验收。分担人完成的代码按第四节的目录归属复核，验证等级不得降低。")

add_heading("十一 结论与执行要求", 1)
add_number("三名队员确认自己的岗位代号，并按《角色分工》核对所有权、决策权和一票否决范围。")
add_number(
    "按第四节确认自己的授权写入目录。要动接口组的四个共享文件，先在群里说一句；"
    "编号表组不必提前说，但必须按取号顺序在推送前最后一步取号。"
)
add_number("推送前运行 .\\code\\scripts\\check_repo.ps1 并要求全部通过；编号在 git fetch 之后从表末尾取。")
add_number("上板前按第五节确认上电顺序，并确认那块板跑的是已知良好的版本、没有临时飞线。")
add_number("软件任务积压时按第十节分担，但算法定义与最终验收不转移。")
add_paragraph(
    "本方案的效果取决于执行一致性。复核、验证等级和编号只有在每次提交中如实记录，"
    "才能真正降低三人三 AI 并行开发的返工率。任何偏离本方案的安排都应写入技术决策记录"
    "并说明回退方案。"
)

footer = section.footer
add_page_number(footer.paragraphs[0])

document.core_properties.title = "三人分工与软硬件资源管理方案"
document.core_properties.subject = "Tang Mega 60K 双板与仪器共享执行说明"
document.core_properties.author = ""

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
document.save(OUTPUT)
print(OUTPUT)
