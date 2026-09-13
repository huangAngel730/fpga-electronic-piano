from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


OUTPUT = Path(__file__).resolve().parents[1] / "高云选题二模块化主方案.docx"


def set_font(run, size=10.5, bold=False, color=None, family="微软雅黑"):
    run.font.name = family
    props = run._element.get_or_add_rPr()
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        props.rFonts.set(qn(key), family)
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
        set_cell(table.cell(0, index), header, header=True, size=8.5)
        table.cell(0, index).width = Cm(widths[index])
    header_property = OxmlElement("w:tblHeader")
    header_property.set(qn("w:val"), "true")
    table.rows[0]._tr.get_or_add_trPr().append(header_property)
    for values in rows:
        row = table.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for index, value in enumerate(values):
            set_cell(row.cells[index], value, center=(index == 0), size=size)
            row.cells[index].width = Cm(widths[index])
    document.add_paragraph()
    return table


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


def add_code(lines):
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

# Cover
title = document.add_paragraph(style="Title")
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_before = Pt(110)
title.paragraph_format.space_after = Pt(24)
title.add_run("高云选题二模块化主方案")

subtitle = document.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(subtitle.add_run("基于 Tang Mega 60K 的实时多音色合成电子乐器引擎"), size=14, bold=True, color=(31, 78, 121))

description = document.add_paragraph()
description.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(description.add_run("系统模块划分 方案冻结范围与后续细化原则"), size=11.5)

date = document.add_paragraph()
date.alignment = WD_ALIGN_PARAGRAPH.CENTER
date.paragraph_format.space_before = Pt(145)
set_font(date.add_run("编制日期 2026年9月9日"), size=10, color=(89, 89, 89))

document.add_page_break()

add_heading("一 作品名称与简介")
add_heading("作品名称", 2)
add_paragraph(
    "暂定作品名称为：灵弦——基于Tang Mega 60K的多维交互实时多音色合成电子乐器。名称中的多维交互只描述系统能力，不提前限定琴键、压力、光电或其他传感器的具体实现。"
)

add_heading("作品简介", 2)
add_paragraph(
    "本作品拟基于Tang Mega 60K FPGA构建一套低延迟、高复音、可扩展的实时多音色合成电子乐器。系统采用模块化架构，将交互输入、演奏事件处理、复音管理、音频合成、包络与音色控制、混音与效果处理、音频输出以及调试可视化划分为相互独立的功能模块。交互输入子系统负责采集音符、触发、力度、滑音和其他连续表情参数，并通过统一演奏事件接口与音频核心连接；具体琴键和传感器方案将在后续实物实验中确定。FPGA内部拟实现DDS与波表合成、独立ADSR包络、多声部实时混音、音色切换及数字音频效果，通过I2S接口输出音频。系统以48 kHz采样率、低于5 ms的端到端延迟和32个独立活跃振荡器为阶段目标，并通过RTL仿真、Python黄金参考、频谱分析、时序报告和上板测量验证功能与性能。"
)

add_heading("精简申报简介", 2)
add_paragraph(
    "本作品基于Tang Mega 60K FPGA设计实时多音色合成电子乐器，采用可替换的多维交互输入和统一演奏事件接口，在FPGA内部完成DDS波表合成、ADSR包络、复音管理、多声部混音、音色切换及数字音频效果处理，并通过I2S实时输出。项目目标为48 kHz采样、32个独立活跃振荡器和低于5 ms的端到端延迟，具体琴键与传感器方案将在音频核心完成后通过实验确定。"
)

add_heading("预期特点", 2)
add_bullet("纯FPGA逐采样实时合成，不播放完整预录PCM音频。")
add_bullet("交互输入采用可替换模块，琴键和传感器细节不会影响音频核心。")
add_bullet("支持多复音、多音色、ADSR以及连续演奏表情参数。")
add_bullet("通过统一事件接口支持后续接入矩阵键盘、压力琴键、MIDI键床或光电控制。")
add_bullet("保留UART、错误计数器、调试GPIO、波形和频谱等可观测手段。")

add_heading("二 方案原则")
add_paragraph(
    "本项目当前阶段应先冻结系统级架构、模块职责和模块接口，不提前锁死琴键、压力传感器、触摸板、光电模块等交互细节。琴键只是交互输入模块中的一种实现方案，后续可以根据响应速度、稳定性、成本和演奏体验进行实验选择。"
)
add_paragraph(
    "通过统一演奏事件接口隔离外部交互硬件与音频核心，后续即使更换琴键或传感器，也只需修改输入适配模块，不影响复音管理、DDS、ADSR、混音、效果器和I2S输出。当前开发重点是先完成可验证的音频核心，再逐步细化交互结构。"
)

add_heading("三 总体模块划分")
add_code([
    "实时多音色合成电子乐器",
    "|",
    "|-- 1 交互输入模块",
    "|-- 2 演奏事件处理模块",
    "|-- 3 复音管理模块",
    "|-- 4 音频合成模块",
    "|-- 5 包络与音色控制模块",
    "|-- 6 混音与效果处理模块",
    "|-- 7 音频输出模块",
    "`-- 8 调试与可视化模块",
])

add_table(
    ["一级模块", "核心职责", "当前状态"],
    [
        ["交互输入", "采集音符、触发、力度和连续表情参数", "职责冻结，硬件待选"],
        ["演奏事件处理", "将不同输入转换成统一事件并缓存", "接口需要优先冻结"],
        ["复音管理", "分配、释放和抢占多个独立声部", "目标冻结，策略待细化"],
        ["音频合成", "使用DDS、波表、FM等产生原始样本", "DDS波表作为基础方案"],
        ["包络与音色控制", "处理ADSR、力度、滑音和音色参数", "基础功能冻结"],
        ["混音与效果", "多声部累加、限幅、延迟和合唱", "混音冻结，效果可分阶段"],
        ["音频输出", "通过I2S输出到板载音频或外部DAC", "协议冻结，器件待验证"],
        ["调试与可视化", "提供UART、计数器、波形和频谱", "基础可观测性必须早期加入"],
    ],
    [4.0, 8.0, 4.0],
)

add_heading("四 交互输入模块")
add_paragraph(
    "交互输入模块负责把演奏动作转换为数字控制量。系统层面只要求它能够提供至少两个独立演奏维度，竞赛目标为三个或更多维度，并且不会使端到端延迟超过目标。具体使用哪一种琴键或传感器暂不确定。"
)

add_heading("系统级要求", 2)
add_bullet("至少支持两个独立可控演奏维度，目标达到三个或更多维度。")
add_bullet("能够产生音符选择、音符触发、初始力度或持续表情参数。")
add_bullet("输入模块的处理延迟不能破坏系统低于5 ms的目标。")
add_bullet("任何具体输入硬件最终都应转换为统一演奏事件。")

add_heading("候选实现", 2)
add_table(
    ["候选方案", "可提供的信息", "定位"],
    [
        ["普通矩阵键盘", "音符选择 Note On Note Off", "基础验证候选"],
        ["FSR压力琴键", "音符 力度 触后压力", "候选"],
        ["双触点力度键盘", "音符 按键速度", "候选"],
        ["TTP229触摸键盘", "音符 触摸触发", "候选"],
        ["废旧MIDI键床", "音符 速度 可能带压力", "候选"],
        ["光电拨弦", "独立触发维度", "可选拓展"],
        ["摇杆或编码器", "滑音 颤音 参数控制", "可选拓展"],
        ["距离传感器", "无接触音高或效果控制", "可选拓展"],
    ],
    [5.0, 7.0, 4.0],
)

add_paragraph(
    "主方案中的正式表述为：系统设置可替换的多维交互输入子系统，负责采集音符、触发、力度及连续表情参数。具体琴键和传感器方案将在音频核心完成后，通过响应速度、稳定性、成本和演奏体验实验确定。"
)

add_heading("五 演奏事件处理模块")
add_paragraph(
    "演奏事件处理模块是外部硬件与音频核心之间的隔离层。无论前端使用矩阵键盘、FSR压力琴键还是MIDI键床，进入复音管理模块的数据格式都保持一致。"
)

add_table(
    ["事件或参数", "含义", "典型来源"],
    [
        ["Note On", "开始一个音符", "按键、触摸或光电触发"],
        ["Note Off", "释放一个音符", "琴键松开或触发结束"],
        ["Velocity", "音符触发时的初始力度", "压力斜率、双触点时间差或默认值"],
        ["Aftertouch", "音符持续期间的压力变化", "FSR或其他连续压力传感器"],
        ["Pitch Bend", "连续改变音高", "摇杆、编码器、距离传感器"],
        ["Control Change", "音色和效果器参数", "旋钮、触摸条或上位机"],
    ],
    [4.0, 6.0, 6.0],
)

add_code([
    "performance_event",
    "|-- event_type",
    "|-- note_number",
    "|-- velocity",
    "|-- expression",
    "|-- control_id",
    "`-- control_value",
    "",
    "event_valid <--> event_ready",
])

add_paragraph(
    "矩阵键盘版本可以使用默认Velocity；FSR版本可由压力斜率生成Velocity，并持续更新Aftertouch；MIDI键盘版本直接解析标准音符和力度。三种输入对后续复音管理模块没有区别。"
)

add_heading("六 复音管理模块")
add_paragraph(
    "复音管理模块负责维护多个同时发声的独立声部。基础要求为不少于4复音，当前正式目标为32个独立活跃振荡器或32复音能力。每个声部必须保存独立相位、频率、包络和音色状态。"
)

add_heading("每个声部的状态", 2)
add_bullet("激活标志和音符编号。")
add_bullet("频率控制字和相位累加器。")
add_bullet("初始力度和持续表情参数。")
add_bullet("ADSR阶段和当前包络电平。")
add_bullet("音色编号、声部年龄和释放状态。")

add_heading("后续再确定的细节", 2)
add_bullet("32个声部是完全物理并行还是分时流水处理。")
add_bullet("采用4条还是8条音频处理流水线。")
add_bullet("声部耗尽时的抢占优先级。")
add_bullet("每个音符包含一个还是多个振荡器。")
add_bullet("最终最大复音数是32还是64。")

add_heading("七 音频合成模块")
add_paragraph(
    "音频合成模块负责产生原始音频样本。基础版本确定使用DDS加单周期波表，这是实现和验证风险最低、能够明确证明逐采样实时合成的路线。其他算法作为可替换或可叠加的音色单元。"
)

add_table(
    ["合成方式", "用途", "当前定位"],
    [
        ["正弦波表", "基础发声和频率验证", "必做"],
        ["多波表切换", "形成多种基础音色", "必做"],
        ["加法合成", "构造风琴类和富谐波音色", "推荐"],
        ["二运算器FM", "构造铃声和电钢琴类音色", "推荐"],
        ["Karplus Strong", "构造拨弦音色", "后期可选"],
        ["复杂物理建模", "高级创新音色", "暂不确定"],
    ],
    [4.5, 7.0, 4.5],
)

add_paragraph(
    "正式方案只冻结可扩展音频合成结构和DDS波表基础路线，不提前承诺全部音色算法。后续根据资源报告、声音效果和开发进度，再决定是否加入加法合成、FM或物理建模。"
)

add_heading("八 包络与音色控制模块")
add_paragraph(
    "该模块负责把Velocity、Aftertouch、Pitch Bend及其他控制参数映射到振荡器频率、ADSR电平、FM调制指数、谐波比例和效果器参数。输入参数的物理来源由交互输入模块决定，本模块不依赖具体传感器。"
)
add_bullet("必须实现独立ADSR包络。")
add_bullet("必须支持实时变调和音色参数切换。")
add_bullet("定点运算需要明确符号、位宽、小数位、舍入和饱和策略。")
add_bullet("压力等连续控制量应经过滤波、死区和曲线映射。")

add_heading("九 混音与效果处理模块")
add_heading("混音基础功能", 2)
add_bullet("多声部使用足够位宽累加，预留位宽增长。")
add_bullet("实现主音量、舍入、饱和限幅和静音控制。")
add_bullet("加入削波计数器，不能用无说明的低位截断。")
add_bullet("效果器必须支持旁路，避免影响基础音频链路。")

add_heading("效果器候选", 2)
add_table(
    ["效果器", "实现顺序", "当前状态"],
    [
        ["延迟", "第一优先", "正式目标"],
        ["合唱", "第二优先", "推荐目标"],
        ["简化混响", "第三优先", "后期可选"],
        ["数字滤波器", "根据音色需要", "待验证"],
        ["动态压缩", "资源和时间充足后", "待验证"],
    ],
    [4.5, 5.0, 6.5],
)

add_heading("十 音频输出模块")
add_paragraph(
    "音频输出模块负责将内部PCM样本按照I2S协议发送至板载音频链路或外部DAC。当前冻结48 kHz目标采样率、I2S协议和有符号定点音频通路，具体输出器件和位宽需要在Tang Mega 60K到手后验证。"
)

add_table(
    ["项目", "当前决策", "后续确认"],
    [
        ["采样率", "目标48 kHz", "根据PLL和音频链路实测确认"],
        ["接口协议", "I2S", "确认数据相位和槽位长度"],
        ["输出器件", "板载音频或PCM5102A", "上板比较稳定性和噪声"],
        ["数据位宽", "内部18至24位", "最终输出16位或24位待定"],
        ["扬声器链路", "有源音箱优先", "后期决定是否集成功放"],
        ["立体声", "接口预留", "声像控制是否加入待定"],
    ],
    [4.0, 6.0, 6.0],
)

add_heading("十一 调试与可视化模块")
add_paragraph(
    "调试与可视化不是项目末期装饰，而是AI协作、模块联调和现场验证所需的基础设施。第一阶段应先提供UART固定字段日志、错误计数器和调试GPIO，后期再加入波形、频谱和图形界面。"
)

add_heading("第一阶段可观测信息", 2)
add_code([
    "sample_rate=48000",
    "active_voices=0",
    "clip_count=0",
    "event_fifo_overflow=0",
    "audio_underrun=0",
    "max_processing_cycles=0",
])

add_bullet("调试GPIO至少引出event_received、sample_tick、i2s_frame_start和audio_clip。")
add_bullet("后期显示内容包括音符、活跃声部、波形、频谱、削波和效果器状态。")
add_bullet("显示方式可以是HDMI、OLED或串口上位机，当前不锁定。")

add_heading("十二 方案冻结状态")
add_table(
    ["项目", "当前状态", "说明"],
    [
        ["赛题", "已冻结", "高云选题二"],
        ["开发板", "已冻结", "Tang Mega 60K加NEO Dock"],
        ["核心数据通路", "已冻结", "音频生成、包络、混音和效果均由FPGA完成"],
        ["采样率", "基本冻结", "目标48 kHz"],
        ["输出协议", "已冻结", "I2S"],
        ["基础合成", "已冻结", "DDS加单周期波表"],
        ["包络", "已冻结", "每声部独立ADSR"],
        ["规模目标", "阶段目标", "基础4复音，正式目标32个独立活跃振荡器"],
        ["混音", "已冻结", "宽位累加、舍入和饱和限幅"],
        ["效果器", "阶段目标", "延迟优先，合唱推荐"],
        ["交互硬件", "待验证", "只冻结统一输入模块与事件接口"],
        ["琴键结构", "待验证", "矩阵、FSR、双触点、MIDI键床均为候选"],
        ["显示方式", "待验证", "HDMI、OLED或上位机"],
        ["最终DAC", "待验证", "板载音频和PCM5102A上板比较"],
        ["PCB", "待验证", "先用模块和杜邦线联调"],
    ],
    [4.3, 3.2, 8.5],
)

add_heading("十三 暂缓锁定的细节")
add_paragraph("以下内容不得在当前主方案中写成不可修改的唯一实现。")
add_bullet("固定使用8个FSR压力琴键。")
add_bullet("固定使用4乘4矩阵键盘或TTP229触摸板。")
add_bullet("固定使用VL53L0X作为表情控制。")
add_bullet("固定每个琴键都具有独立压力传感器。")
add_bullet("固定采用三种指定音色。")
add_bullet("固定使用HDMI显示频谱。")
add_bullet("固定使用PCM5102A作为正式输出。")
add_bullet("固定制作PCB或固定最大复音数为64。")
add_bullet("固定采用Karplus Strong或复杂物理建模。")

add_heading("十四 开发顺序")
add_table(
    ["阶段", "主要内容", "完成标准"],
    [
        ["第一阶段", "音频时钟和I2S输出", "固定测试音能够正确输出"],
        ["第二阶段", "单声部DDS和波表", "频率和波形通过参考模型验证"],
        ["第三阶段", "ADSR和基础混音", "触发和释放自然，无回绕削波"],
        ["第四阶段", "4至32声部管理", "声部分配、释放和压力测试通过"],
        ["第五阶段", "统一演奏事件接口", "UART和Testbench可模拟全部事件"],
        ["第六阶段", "接入临时按键或UART输入", "不依赖最终琴键即可演奏"],
        ["第七阶段", "比较琴键和压力方案", "通过实测选择正式交互硬件"],
        ["第八阶段", "效果器和显示", "旁路稳定，加入量化展示"],
        ["第九阶段", "最终结构和PCB", "接口和引脚冻结后再设计"],
    ],
    [3.0, 7.0, 6.0],
)

add_heading("十五 前期脱离琴键开发")
add_paragraph(
    "在琴键结构尚未确定时，可以通过UART、Testbench或普通按键产生统一Note On和Note Off事件，提前完成复音、ADSR、音色、混音、效果器和输出模块。交互模块只要最终输出相同事件格式，即可无缝替换临时输入。"
)
add_code([
    "NOTE_ON 60 800",
    "NOTE_ON 64 500",
    "NOTE_ON 67 700",
    "AFTERTOUCH 60 620",
    "PITCH_BEND 120",
    "NOTE_OFF 60",
])

add_heading("十六 文档维护方式")
add_paragraph(
    "后续方案文档应始终区分已冻结、候选方案和待验证三种状态。实验结果足以支持决策后，再把对应条目从候选或待验证更新为已冻结。具体琴键、传感器、位宽和效果器参数应记录在各模块设计文档中，不应频繁改写系统总体架构。"
)

add_table(
    ["状态", "含义", "变更要求"],
    [
        ["已冻结", "已确认且会影响其他模块接口", "修改前评估全系统影响"],
        ["候选方案", "存在多个可行选项，等待对比", "通过实验数据选择"],
        ["待验证", "依赖板卡、资源或实物测试", "验证完成后更新状态"],
    ],
    [3.5, 7.0, 5.5],
)

add_heading("十七 当前下一步")
add_number("建立代码目录和统一演奏事件数据结构。")
add_number("下载并验证Tang Mega 60K官方LED、UART和音频示例。")
add_number("完成48 kHz音频节拍和I2S发送模块。")
add_number("使用Python生成波表和频率控制字，完成单声部DDS。")
add_number("在没有最终琴键的情况下，通过Testbench和UART验证Note On、Note Off和Velocity。")
add_number("音频核心稳定后，再对琴键、压力和无接触控制方案做小规模实物实验。")

document.core_properties.title = "高云选题二模块化主方案"
document.core_properties.subject = "实时多音色合成电子乐器引擎系统模块划分与方案冻结"
document.core_properties.author = ""
document.save(OUTPUT)
print(OUTPUT)
