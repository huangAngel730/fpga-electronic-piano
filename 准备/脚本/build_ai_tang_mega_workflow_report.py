from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path('高云选题2_AI全程开发可行性与协作方案.docx')

def font(run, size=10.5, bold=False, color=None, family='微软雅黑'):
    run.font.name = family
    rp=run._element.get_or_add_rPr()
    for key in ('w:ascii','w:hAnsi','w:eastAsia'):
        rp.rFonts.set(qn(key),family)
    run.font.size=Pt(size); run.bold=bold
    if color: run.font.color.rgb=RGBColor(*color)

def shade(cell, fill):
    node=OxmlElement('w:shd'); node.set(qn('w:fill'),fill)
    cell._tc.get_or_add_tcPr().append(node)

def set_cell(c, value, header=False, center=False, size=8.5, bold=False):
    c.text=''; p=c.paragraphs[0]
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if center or header else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after=Pt(0)
    font(p.add_run(str(value)),size,header or bold,(255,255,255) if header else None)
    c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header: shade(c,'1F4E79')

def table(headers, rows, widths, size=8.3):
    t=doc.add_table(rows=1,cols=len(headers)); t.style='Table Grid'
    t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
    for i,h in enumerate(headers):
        set_cell(t.cell(0,i),h,header=True,size=8.5); t.cell(0,i).width=Cm(widths[i])
    prop=t.rows[0]._tr.get_or_add_trPr(); hdr=OxmlElement('w:tblHeader'); hdr.set(qn('w:val'),'true'); prop.append(hdr)
    for data in rows:
        row=t.add_row(); row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for i,v in enumerate(data):
            set_cell(row.cells[i],v,center=(i==0),size=size); row.cells[i].width=Cm(widths[i])
    doc.add_paragraph().paragraph_format.space_after=Pt(0)
    return t

def heading(text,level=1):
    p=doc.add_heading(text,level=level); p.paragraph_format.keep_with_next=True
    p.paragraph_format.space_before=Pt(10 if level==1 else 6); p.paragraph_format.space_after=Pt(4)

def para(text, lead=None):
    p=doc.add_paragraph(); p.paragraph_format.line_spacing=1.22; p.paragraph_format.space_after=Pt(5)
    if lead and text.startswith(lead):
        font(p.add_run(lead),bold=True); font(p.add_run(text[len(lead):]))
    else: font(p.add_run(text))

def bullet(text):
    p=doc.add_paragraph(style='List Bullet'); p.paragraph_format.space_after=Pt(2); font(p.add_run(text),10)

def number(text):
    p=doc.add_paragraph(style='List Number'); p.paragraph_format.space_after=Pt(3); font(p.add_run(text),10)

def code(lines):
    t=doc.add_table(rows=1,cols=1); t.alignment=WD_TABLE_ALIGNMENT.CENTER
    t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
    c=t.cell(0,0); c.text=''; shade(c,'F2F2F2')
    for i,line in enumerate(lines):
        p=c.paragraphs[0] if i==0 else c.add_paragraph(); p.paragraph_format.space_after=Pt(0)
        font(p.add_run(line),8.3,family='Consolas')
    doc.add_paragraph().paragraph_format.space_after=Pt(0)

doc=Document(); sec=doc.sections[0]
sec.top_margin,sec.bottom_margin=Cm(2.0),Cm(1.8); sec.left_margin=sec.right_margin=Cm(2.2)
normal=doc.styles['Normal']; normal.font.name='微软雅黑'; normal.font.size=Pt(10.5)
normal._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')
for name,size,color in [('Title',23,(0,0,0)),('Heading 1',16,(31,78,121)),('Heading 2',13,(47,84,114))]:
    s=doc.styles[name]; s.font.name='微软雅黑'; s.font.size=Pt(size); s.font.bold=True; s.font.color.rgb=RGBColor(*color)
    s._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')

# Cover
p=doc.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before=Pt(110); p.paragraph_format.space_after=Pt(25)
p.add_run('高云选题二 AI全程开发可行性与协作方案')
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run('Tang Mega 60K实时多音色合成电子乐器引擎'),14,True,(31,78,121))
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run('代码 仿真 综合 下载 上板验证与人机分工'),11.5)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(145)
font(p.add_run('编制日期 2026年9月8日'),10.5,color=(89,89,89))
doc.add_page_break()

heading('一 结论')
para('可以让AI贯穿高云选题二的整个开发过程，并承担大多数代码、测试、构建和文档工作。合理目标是AI主导架构、RTL、Testbench、Python参考模型、综合和问题分析，队员负责板卡连接、供电、接线、仪器操作、声音判断、机械结构和现场答辩。')
para('在Tang Mega 60K连接到当前电脑，Gowin工具、JTAG、UART和音频采集都能被脚本访问的条件下，代码与工具流程自动化程度可以达到约80%至90%。这不等于项目可以无人值守完成；没有实物反馈，AI无法可靠判断底噪、接触不良、功放自激、传感器安装和示波器探头问题。')
table(['结论项','判断','条件'],[
 ['AI是否能写完整工程','可以','接口、时钟、约束和验收标准明确'],
 ['AI是否能自动仿真','可以','仿真器和Python可从命令行运行'],
 ['AI是否能自动综合','可以','Gowin工程使用Tcl或命令行脚本'],
 ['AI是否能自动下载','大部分可以','Programmer和JTAG能由脚本访问'],
 ['AI是否能判断声音','部分可以','使用USB音频采集卡提供WAV数据'],
 ['AI是否能完成物理操作','不可以','接线、焊接、供电和探头操作需人工'],
 ['AI是否能代替答辩','不可以','队员必须理解设计并能现场解释'],
], [4.2,3.2,8.6])

heading('二 AI可承担的工作范围')
table(['工作','AI承担程度','交付内容'],[
 ['系统架构','约95%','模块边界、时钟域、数据格式和验收指标'],
 ['RTL编写','90%至95%','DDS、ADSR、复音调度、混音、效果器和I2S'],
 ['Testbench','约95%','定向测试、随机事件、断言和回归脚本'],
 ['Python参考模型','约95%','频率ROM、波表、黄金音频和频谱分析'],
 ['约束和工程脚本','80%至90%','CST约束、Tcl工程和PowerShell构建脚本'],
 ['综合与时序分析','约90%','读取报告、定位路径、提出流水线优化'],
 ['下载与串口测试','70%至95%','码流下载、COM口采集和状态检查'],
 ['音频数据分析','80%至95%','频率、频谱、削波、ADSR和噪声分析'],
 ['模拟音频判断','约50%','需要录音、波形或人工描述'],
 ['报告和答辩材料','约90%','架构图、测试表、演示流程和问答'],
], [4.0,3.0,9.0])

heading('三 自动化开发闭环')
code([
 'AI修改RTL和测试代码',
 '        |',
 '        v',
 '运行RTL仿真 -----> 与Python参考模型逐采样比较',
 '        |                         |',
 '        | 失败                    | 误差报告',
 '        +<------------------------+',
 '        | 通过',
 '        v',
 '调用Gowin综合和布局布线',
 '        |',
 '        v',
 '读取资源 时序 警告和错误报告',
 '        |',
 '        v',
 '生成码流并通过JTAG下载',
 '        |',
 '        v',
 '读取UART 音频采集 示波器或逻辑分析结果',
 '        |',
 '        +--------> AI继续修改和验证',
])
para('闭环质量取决于反馈是否机器可读。只有口头描述声音正常或不正常时，定位效率有限；如果同时提供串口日志、WAV录音、逻辑分析仪文件和示波器CSV，AI可以进行更可靠的自动分析。')

heading('四 必要的软硬件条件')
heading('板卡与连接',2)
bullet('Tang Mega 60K SOM加NEO Dock完整套装。')
bullet('USB DEBUG连接，用于JTAG和UART。')
bullet('板卡稳定供电，并确认开机、下载器和串口正常。')
bullet('板载音频或PCM5102A、音箱和测试按键。')
bullet('至少一个调试GPIO，用于端到端延迟测量。')
bullet('推荐增加USB音频采集卡和逻辑分析仪。')

heading('软件环境',2)
table(['软件','作用','自动化要求'],[
 ['Gowin EDA','综合、布局布线、生成码流','确认安装路径并建立Tcl构建脚本'],
 ['Gowin Programmer','JTAG下载和器件识别','尽量提供命令行或可脚本接口'],
 ['Icarus或Verilator','RTL仿真','命令行运行并返回退出码'],
 ['Python','参考模型和数据分析','安装NumPy SciPy Matplotlib soundfile'],
 ['cocotb','自动化Testbench','与仿真器集成'],
 ['Git','版本控制和回退','每个可运行节点建立标签'],
 ['Audacity或采集脚本','录音和频谱检查','优先输出标准WAV文件'],
], [3.7,5.0,7.3])

heading('首次人工配置清单',2)
number('安装Gowin EDA、Programmer和USB驱动。')
number('连接板卡并在设备管理器确认JTAG和COM口。')
number('在Programmer中首次识别目标器件，确认器件和封装。')
number('告诉AI实际COM口、工具安装路径和板卡版本。')
number('运行官方LED、UART和audio_i2s示例，证明硬件基础正常。')
number('确认DAC、音箱和输入模块接线后再启动自动下载。')

heading('五 推荐工程目录')
code([
 'gaoyun_fpga_synth/',
 '|-- README.md',
 '|-- rtl/',
 '|   |-- clock/',
 '|   |-- input/',
 '|   |-- synth/',
 '|   |-- mixer/',
 '|   |-- effects/',
 '|   |-- output/',
 '|   `-- top/',
 '|-- sim/',
 '|   |-- tb/',
 '|   |-- vectors/',
 '|   `-- run_sim.ps1',
 '|-- python/',
 '|   |-- reference_synth.py',
 '|   |-- generate_wavetable.py',
 '|   |-- generate_note_fcw.py',
 '|   `-- compare_output.py',
 '|-- constraints/tang_mega_60k.cst',
 '|-- gowin/project.tcl',
 '|-- scripts/',
 '|   |-- build.ps1',
 '|   |-- program.ps1',
 '|   |-- serial_test.py',
 '|   `-- full_test.ps1',
 '|-- reports/',
 '`-- docs/',
])
para('工程必须支持一条命令完成数据生成、仿真、结果比较、综合、时序检查和报告归档。下载和实物测试可根据板卡是否连接选择性执行。')

heading('六 一键流程设计')
table(['脚本','输入','输出和退出条件'],[
 ['generate_assets.ps1','采样率、波表长度、音色参数','生成ROM和参考向量'],
 ['run_sim.ps1','RTL和测试事件','全部断言通过才返回成功'],
 ['compare_output.py','RTL样本和Python样本','误差超过阈值即失败'],
 ['build.ps1','Gowin工程和约束','生成码流、资源和时序报告'],
 ['check_reports.py','综合和实现报告','时序违例、关键警告或资源超限即失败'],
 ['program.ps1','码流和目标器件','JTAG下载成功并校验'],
 ['serial_test.py','COM口和测试命令','输出声部、削波、FIFO和周期统计'],
 ['capture_audio.py','USB音频设备','生成WAV、FFT、频率和电平报告'],
 ['full_test.ps1','全部配置','汇总生成带日期的测试结果目录'],
], [4.2,5.0,6.8])

heading('七 建议加入的机器可读反馈')
heading('UART状态接口',2)
code([
 'sample_rate=48000',
 'active_voices=32',
 'peak_level=812734',
 'clip_count=0',
 'event_fifo_overflow=0',
 'note_on_count=1256',
 'max_processing_cycles=287',
 'audio_underrun=0',
])
para('串口输出应使用固定字段名，便于Python解析。不要只输出自由文本。异常计数器应保持累加，复位命令单独提供。')

heading('USB音频采集',2)
para('将DAC线路输出接入USB音频采集卡，使用脚本录制标准48 kHz WAV。AI可以据此自动计算基频误差、独立频谱峰数量、削波、直流偏置、ADSR时间和效果器延迟。声音是否自然、是否具有乐器表现力仍需要人工试听。')

heading('示波器与逻辑分析',2)
para('若示波器支持USB或LAN控制，可以用SCPI自动捕获输入GPIO和DAC输出并计算延迟。普通示波器则由队员连接探头、设置触发并导出CSV或截图。逻辑分析仪适合检查BCLK、LRCLK、DATA、SPI和输入事件时序。')

heading('八 人机分工')
table(['工作','AI负责','队员负责'],[
 ['需求和架构','拆解指标、设计模块和数据格式','确认演示目标和优先级'],
 ['代码','编写RTL、测试和脚本','理解接口和审查关键模块'],
 ['仿真','运行回归并分析差异','确认测试覆盖真实场景'],
 ['综合实现','运行工具、分析时序和资源','提供工具授权和板卡文件'],
 ['板卡下载','编写和运行下载脚本','首次识别器件和处理连接故障'],
 ['传感器','编写驱动、滤波和校准算法','接线、安装和操作'],
 ['音频','分析WAV、频谱和削波','试听、排查功放和接地'],
 ['仪器','分析CSV和截图','连接探头和确认量程'],
 ['报告答辩','整理数据、图表和问题清单','掌握设计并现场讲解'],
], [3.0,6.4,6.6])

heading('九 AI无法独立完成的部分')
bullet('插拔杜邦线、焊接、固定传感器和处理接触不良。')
bullet('首次供电、检查短路、判断芯片是否异常发热。')
bullet('调整示波器探头、量程、触发和接地夹。')
bullet('仅凭RTL判断底噪、工频干扰、功放自激和扬声器破音。')
bullet('代替队员参加能力考核、演示和答辩。')
bullet('在没有日志、录音或仪器数据时可靠定位实物问题。')

heading('十 质量门槛')
table(['阶段','必须满足','不满足时的处理'],[
 ['模块提交','独立Testbench和接口说明齐全','不进入上层集成'],
 ['RTL回归','全部断言通过，无未知态扩散','修复后重新运行全回归'],
 ['参考比较','基础音频最大误差不超过定义容差','检查位宽、舍入和时序对齐'],
 ['综合','无错误，关键警告有解释','禁止忽略未约束时钟和锁存器'],
 ['时序','所有目标时钟满足约束','增加流水线或调整结构'],
 ['下载','器件识别、码流校验和复位通过','停止自动循环，人工检查连接'],
 ['音频','无持续削波、欠载和明显毛刺','降低增益并检查I2S'],
 ['稳定性','32声部压力测试运行2小时','保存日志并定位首次异常'],
 ['提交','工程可从空目录复现','补齐脚本、版本和依赖说明'],
], [3.2,7.4,5.4])

heading('十一 推荐开发节奏')
table(['阶段','AI主要工作','队员主要工作','验收'],[
 ['第1周','I2S、DDS、仿真和构建脚本','接板、运行示例、连接音频','固定440 Hz稳定发声'],
 ['第2周','音符ROM和ADSR','按键接线和试听','单声部自然触发释放'],
 ['第3周','4至16复音和混音','和弦演奏和音量检查','无卡音和爆音'],
 ['第4周','32复音、UART统计和压力测试','采集频谱和运行日志','32路测试通过'],
 ['第5周','压力、光电和编码器驱动','安装校准三个交互维度','延迟和控制稳定'],
 ['第6周','第二音色、延迟和合唱','试听并调整参数','切换无毛刺'],
 ['第7周','频谱、波形和显示','布置演示结构','现场信息清晰'],
 ['第8周','全回归和时序优化','连续运行和故障恢复','稳定运行2小时'],
 ['第9周','报告、视频和答辩问答','理解设计并演练','提交包可复现'],
], [2.2,5.3,5.0,3.5], size=7.9)

heading('十二 首次协作需要提供的信息')
bullet('Tang Mega 60K具体板卡版本和套装照片。')
bullet('高云EDA与Programmer安装路径及版本。')
bullet('Windows设备管理器中的COM口和JTAG识别情况。')
bullet('板卡原理图、官方CST约束和audio_i2s示例。')
bullet('使用板载音频还是PCM5102A，以及DAC模块照片和接口标注。')
bullet('计划使用的按键、ADC和传感器型号。')
bullet('实验室示波器、逻辑分析仪和USB音频采集条件。')
bullet('目标采样率、输出位宽、复音数和最终演示功能。')

heading('十三 风险控制')
table(['风险','影响','控制方法'],[
 ['AI代码未经验证','上板后难以定位错误','任何RTL必须先通过模块仿真和参考比较'],
 ['只会运行不会解释','答辩和能力考核失分','每个核心模块安排队员讲解和手写框图'],
 ['GUI流程无法自动化','构建和下载效率低','优先建立Tcl和命令行脚本'],
 ['物理反馈不足','AI无法判断真实故障','增加UART、录音和仪器数据'],
 ['自动下载误操作','板卡状态异常或下载失败','器件ID校验，异常时停止而非循环重试'],
 ['项目范围膨胀','基础链路未完成','冻结32复音和低于5 ms为第一目标'],
], [4.2,5.2,6.4])

heading('十四 最终实施建议')
para('本项目应采用AI主导开发、人工完成物理操作、数据闭环驱动迭代的方式。第一阶段不要追求完整乐器外观，应先把固定正弦波、DDS、ADSR、4复音和32复音逐级做通。')
para('当Gowin命令行构建、JTAG下载、UART日志和USB音频采集全部接入脚本后，AI可以持续修改代码并根据真实板卡结果迭代。队员应同步学习DDS、ADSR、复音调度、混音位宽和I2S时序，保证最终工程不仅能够运行，而且能够被解释、复现和答辩。')

heading('十五 资料依据')
bullet('OpenAI官方Codex文档，用于确认本地文件修改、命令执行和测试迭代能力。')
bullet('高云Gowin EDA Tcl命令行模式用户指南。')
bullet('Sipeed Tang Mega 60K官方硬件文档和示例仓库。')
bullet('高云半导体2026 FPGA创新设计赛道选题指南。')

for section in doc.sections:
    p=section.footer.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    begin=OxmlElement('w:fldChar'); begin.set(qn('w:fldCharType'),'begin')
    instr=OxmlElement('w:instrText'); instr.set(qn('xml:space'),'preserve'); instr.text='PAGE'
    end=OxmlElement('w:fldChar'); end.set(qn('w:fldCharType'),'end')
    p._p.extend([begin,instr,end])

doc.core_properties.title='高云选题二 AI全程开发可行性与协作方案'
doc.core_properties.subject='Tang Mega 60K实时多音色合成电子乐器引擎AI协作开发'
doc.core_properties.author=''
doc.save(OUT)
print(OUT.resolve())
