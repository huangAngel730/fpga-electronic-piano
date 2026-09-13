from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path('高云选题2_提前购买与准备清单.docx')

def set_font(run, size=10.5, bold=False, color=None, family='微软雅黑'):
    run.font.name = family
    rp = run._element.get_or_add_rPr()
    for key in ('w:ascii','w:hAnsi','w:eastAsia'):
        rp.rFonts.set(qn(key), family)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def shade(cell, fill):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    cell._tc.get_or_add_tcPr().append(shd)

def set_cell(cell, text, header=False, center=False, size=8.5, bold=False):
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center or header else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    set_font(p.add_run(str(text)), size=size, bold=header or bold, color=(255,255,255) if header else None)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header:
        shade(cell, '1F4E79')

def add_table(headers, rows, widths, font_size=8.3):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(headers):
        set_cell(t.cell(0,i), h, header=True, size=8.5)
        t.cell(0,i).width = Cm(widths[i])
    prop = t.rows[0]._tr.get_or_add_trPr()
    hdr = OxmlElement('w:tblHeader'); hdr.set(qn('w:val'),'true'); prop.append(hdr)
    for row_data in rows:
        row = t.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for i, value in enumerate(row_data):
            set_cell(row.cells[i], value, center=(i==0), size=font_size)
            row.cells[i].width = Cm(widths[i])
    spacer = doc.add_paragraph(); spacer.paragraph_format.space_after = Pt(0)
    return t

def heading(text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(10 if level == 1 else 6)
    p.paragraph_format.space_after = Pt(4)
    return p

def para(text, lead=None):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.22
    p.paragraph_format.space_after = Pt(5)
    if lead and text.startswith(lead):
        set_font(p.add_run(lead), bold=True)
        set_font(p.add_run(text[len(lead):]))
    else:
        set_font(p.add_run(text))
    return p

def bullet(text, level=0):
    p = doc.add_paragraph(style='List Bullet' if level == 0 else 'List Bullet 2')
    p.paragraph_format.space_after = Pt(2)
    set_font(p.add_run(text), size=10)

def check(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.35)
    p.paragraph_format.space_after = Pt(2)
    set_font(p.add_run('□  ' + text), size=10)

doc = Document()
sec = doc.sections[0]
sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(1.8)
sec.left_margin = sec.right_margin = Cm(2.1)

normal = doc.styles['Normal']
normal.font.name = '微软雅黑'; normal.font.size = Pt(10.5)
normal._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')
for name, size, color in [('Title',23,(0,0,0)),('Heading 1',16,(31,78,121)),('Heading 2',13,(47,84,114))]:
    s=doc.styles[name]; s.font.name='微软雅黑'; s.font.size=Pt(size); s.font.bold=True
    s.font.color.rgb=RGBColor(*color); s._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')

# Cover
p=doc.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before=Pt(110); p.paragraph_format.space_after=Pt(24)
p.add_run('高云选题二提前购买与准备清单')
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
set_font(p.add_run('实时多音色合成电子乐器引擎'),15,True,(31,78,121))
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
set_font(p.add_run('板卡 外设 软件 仪器 接线与首周验收'),12)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(140)
set_font(p.add_run('编制日期 2026年9月8日'),10.5,color=(89,89,89))
doc.add_page_break()

heading('一 最重要的当前事项')
para('高云2026竞赛板卡申请截止日期为2026年9月15日。当前日期为2026年9月8日，板卡申请只剩7天。应先取得比赛团队编号，然后申请选题二对应的Tang Mega 60K。每支队伍只能申请一块板卡，申请成功后板卡为借用，完赛后需要按要求寄回。')
check('确认比赛报名已完成并取得团队编号')
check('在2026年9月15日前提交Tang Mega 60K板卡申请')
check('申请说明中写明32复音 48 kHz 三维交互 低于5 ms延迟和频谱验证')
check('保留申请截图 联系方式和快递信息')
check('同步准备自购板卡方案 不把借用成功作为唯一前提')

heading('板卡型号确认',2)
para('如果需要自购，应确认购买Tang Mega 60K SOM加Tang Mega NEO Dock底板的完整套装，不要只购买SOM核心板。完整Dock提供USB JTAG和串口、PMOD、2乘20排针、HDMI、耳机输出、扬声器输出、SD卡和DDR3等资源。')
add_table(['确认项','正确要求','常见错误'],[
 ['板卡','Tang Mega 60K SOM加NEO Dock完整套装','只买SOM核心板'],
 ['器件','GW5AT-LV60PG484A对应版本','买成Tang Mega 138K或其他板'],
 ['附件','确认电源 USB线 排针和扬声器接口','默认认为所有附件都包含'],
 ['音频','先验证板载audio_i2s示例','未看原理图就购买大量音频模块'],
], [3.0,7.0,6.0])

heading('二 第一批建议采购')
para('第一批器材应以低成本、通用、能立即开始输入和I2S验证为原则。关键模块建议买两个备用，但不要一次购买大量不同型号传感器。')
add_table(['物品','数量','用途','预算'],[
 ['大号面包板','2块','搭建输入与传感器电路','20至40元'],
 ['杜邦线 公公 公母 母母','各1至2组','模块连接和临时调试','30至60元'],
 ['2.54 mm排针排母','若干','转接和焊接','10至20元'],
 ['4乘4矩阵键盘','2个','第一版16键音符输入','10至20元'],
 ['EC11旋转编码器模块','3个','音量 音色 效果参数','15至30元'],
 ['FSR402压力传感器','3个','力度和音色明亮度','30至80元'],
 ['MCP3008 SPI ADC模块','2个','采集压力和其他模拟量','30至70元'],
 ['PCM5102A三线I2S DAC','2个','外接音频和比赛备用','30至70元'],
 ['有源小音箱','1个','直接接DAC线路输出','40至120元'],
 ['USB逻辑分析仪','1个','检查I2S SPI和按键时序','30至150元'],
 ['常用电阻电容套装','1套','分压 限流 去耦和滤波','25至60元'],
 ['防静电袋或防静电垫','1套','存放与操作FPGA板','20至60元'],
], [4.4,2.0,6.3,3.3])

heading('第一批采购预算',2)
para('不计FPGA板卡、显示器和示波器，第一批建议准备300至700元。若实验室已有逻辑分析仪、有源音箱、面包板和常用元件，可以将预算压缩至150至350元。')

heading('三 交互传感器选择')
para('赛题基础要求至少两个独立演奏维度，拓展阶段建议达到三个。最稳妥的顺序是矩阵键盘、旋转编码器、压力传感器，最后再加入无接触测距或光电控制。')
add_table(['演奏维度','首选器件','备用器件','控制内容','风险'],[
 ['选音与和弦','4乘4矩阵键盘','TTP229触摸键盘','音符 八度 和弦','触摸模块电平需确认'],
 ['力度','FSR402加MCP3008','滑动电位器','音量 包络峰值','需要滤波和校准'],
 ['滑音或颤音','EC11编码器','VL53L0X测距','音高弯曲 颤音深度','测距数据存在抖动'],
 ['拨弦触发','光电开关','普通按键','触发音符或改变包络','受环境光影响'],
], [3.1,4.2,3.6,3.7,3.0])

heading('建议后期购买的模块',2)
add_table(['物品','数量','购买时机','说明'],[
 ['TTP229 16键触摸模块','2个','机械键盘稳定后','确认可在3.3 V下工作'],
 ['VL53L0X测距模块','2个','基础三维交互完成后','用于无接触滑音或效果深度'],
 ['光电反射模块','2个','需要拨弦交互时','数字输出必须为3.3 V'],
 ['PAM8403功放模块','2个','需要无源扬声器时','PCM5102A不能直接驱动扬声器'],
 ['8欧3瓦扬声器','4个','确认接口和功放后','两只使用 两只备用'],
 ['USB音频采集卡','1个','开始频谱验证时','连接电脑采集模拟音频'],
 ['OLED显示模块','1个','确定不做HDMI时','否则优先利用板载HDMI'],
], [4.2,1.8,4.5,6.1])

heading('四 暂时不要购买')
add_table(['物品','不建议原因','替代方案'],[
 ['HC-SR04超声波模块','常见Echo输出接近5 V 可能损坏3.3 V FPGA','使用VL53L0X或旋转编码器'],
 ['MP3或WAV播放模块','声音不是FPGA实时合成 不符合核心要求','使用DDS 波表 FM或物理建模'],
 ['带成品音源的MIDI模块','无法证明声音由FPGA逐采样生成','只传输控制事件 声音在FPGA生成'],
 ['复杂蓝牙或ESP32方案','容易消耗时间且不增加核心吞吐指标','基础系统稳定后再做参数配置'],
 ['昂贵独立显示屏','Dock已有HDMI接口','使用现有HDMI显示器'],
 ['大量不同型号传感器','增加接线和调试负担','每个核心模块购买两个备用'],
], [4.0,7.0,5.0])

heading('五 板卡到手后的检查')
check('核对SOM和Dock型号 芯片和封装')
check('检查12 V电源 USB线 JTAG串口和排针是否随板提供')
check('阅读原理图 确认耳机 扬声器和音频芯片连接')
check('核对PMOD DVP HDMI和2乘20排针的复用关系')
check('运行PMOD LED或流水灯示例')
check('运行USB串口回环或输出示例')
check('运行官方audio_i2s示例')
check('确认板载耳机或扬声器输出可用')
check('根据接口实物再购买扬声器插头和电源附件')

heading('六 软件环境准备')
add_table(['软件或资料','准备内容','完成标准'],[
 ['Gowin EDA教育版','安装支持Tang Mega 60K的版本','能新建工程并选择正确器件'],
 ['Gowin Programmer','安装独立下载工具和驱动','能识别板载USB JTAG'],
 ['官方示例仓库','下载audio_i2s HDMI DDR3和LED示例','本地保存并记录对应工具版本'],
 ['约束文件和原理图','建立自己的引脚分配表','每个接口有电压 方向和复用说明'],
 ['Git','建立代码仓库和分支规则','每个可运行节点有标签'],
 ['Python','安装NumPy SciPy Matplotlib soundfile','可以生成波表和参考音频'],
 ['RTL仿真','准备Icarus Verilog或Verilator及cocotb','能自动运行Testbench'],
 ['音频分析','安装Audacity或频谱工具','可以采集波形并显示FFT'],
], [4.0,7.0,5.0])

heading('需要提前编写的脚本',2)
add_table(['文件','用途'],[
 ['generate_note_fcw.py','生成MIDI音符到DDS频率控制字的ROM'],
 ['generate_wavetable.py','生成单周期正弦 三角 锯齿和风琴波表'],
 ['reference_synth.py','建立DDS ADSR 混音和效果器黄金参考'],
 ['generate_test_events.py','生成note_on note_off和随机压力事件'],
 ['compare_rtl_output.py','逐采样比较RTL和Python输出'],
 ['plot_spectrum.py','验证音高 谐波和多路独立频谱峰'],
], [6.2,9.8])

heading('七 实验仪器准备')
para('示波器和逻辑分析仪不仅用于调试，也是证明低延迟和I2S正确性的证据。应现在确认实验室借用渠道，不要等到提交前再找仪器。')
add_table(['仪器','建议规格','用途','获取方式'],[
 ['双通道示波器','20 MHz以上','测量输入GPIO到DAC模拟输出的延迟','优先向实验室借用'],
 ['逻辑分析仪','24 MHz最低 100 MHz更稳妥','解码3.072 MHz I2S和SPI','建议自购一个'],
 ['数字万用表','普通自动量程','测电源 短路 分压和静态电平','自备或借用'],
 ['可调直流电源','带限流','外设独立供电和故障保护','非必需'],
 ['焊台','恒温可调','排针 接口和演示PCB','实验室借用'],
 ['USB音频采集','支持48 kHz','频谱和录音证据','自购或使用电脑声卡'],
 ['HDMI显示器','普通1080p','显示波形 频谱和状态','利用现有设备'],
], [3.3,4.0,5.6,3.1])

heading('八 接线与电压安全')
para('Tang Mega 60K外部GPIO按3.3 V系统处理。接入模块前应查明供电电压和数字输出电平，不能因为模块使用5 V供电就默认其输出对FPGA安全。')
check('FPGA和所有外设共地')
check('所有进入FPGA的数字信号不高于3.3 V')
check('MCP3008使用3.3 V供电和3.3 V参考电压')
check('5 V传感器输出先经过电阻分压或电平转换')
check('不把两个推挽输出直接相连')
check('每个传感器旁放置100 nF去耦电容')
check('DAC和功放电源做好滤波 音频线远离高速数字线')
check('未断电时不插拔SOM FPC和裸排针')
check('通电前用万用表检查3.3 V和5 V对地是否短路')

heading('九 引脚规划表模板')
add_table(['功能','接口','计划引脚','电压','方向','复用冲突','状态'],[
 ['I2S BCLK','GPIO','','3.3 V','输出','','待定'],
 ['I2S LRCLK','GPIO','','3.3 V','输出','','待定'],
 ['I2S DATA','GPIO','','3.3 V','输出','','待定'],
 ['矩阵键盘行','GPIO','','3.3 V','输出','','待定'],
 ['矩阵键盘列','GPIO','','3.3 V','输入','','待定'],
 ['MCP3008 SPI','SPI','','3.3 V','双向','','待定'],
 ['编码器','GPIO','','3.3 V','输入','','待定'],
 ['VL53L0X','I2C','','3.3 V','双向','','待定'],
 ['调试GPIO','GPIO','','3.3 V','输出','','待定'],
 ['HDMI显示','板载接口','','板载','输出','','后期'],
], [3.0,2.2,2.8,2.0,2.0,2.8,2.0], font_size=7.8)

heading('十 首周验收计划')
add_table(['时间','任务','必须保留的证据'],[
 ['第1天','安装EDA Programmer和驱动 下载示例','工具版本截图和工程日志'],
 ['第2天','运行LED和串口示例','板卡照片 串口输出'],
 ['第3天','运行官方audio_i2s示例','耳机或音箱正常输出视频'],
 ['第4天','仿真自己的I2S发送器','BCLK LRCLK DATA波形'],
 ['第5天','输出固定440 Hz正弦波','示波器波形和频谱'],
 ['第6天','加入DDS频率ROM','不同音符频率误差表'],
 ['第7天','按键触发单声部和简单包络','演示视频和Git标签'],
], [2.3,7.0,6.7])

heading('首周生死线',2)
para('首周结束前必须实现自己编写的固定440 Hz正弦波，经I2S输出到DAC或板载音频并稳定发声。如果这一链路尚未打通，不应继续开发32复音、FFT、手机App或复杂传感器。')

heading('十一 预算汇总')
add_table(['场景','预计支出','说明'],[
 ['成功借到Tang Mega 60K且实验室仪器齐全','150至350元','只购买基础输入 DAC备用和耗材'],
 ['成功借板并完成较完整三维交互','300至700元','含备用模块 功放 扬声器和演示结构'],
 ['未借到板卡 全部自购','900至1600元','板卡套装价格以实际渠道为准'],
 ['增加定制PCB和完整外壳','再增加200至600元','应在面包板版本稳定后投入'],
], [6.0,4.0,6.0])
para('建议在计算出的预算上额外预留15%的运费、备件和返工费用。贵重板卡不应重复购买，容易损坏或交期不稳定的小模块应准备两个。')

heading('十二 最终采购清单')
for item in [
    'Tang Mega 60K SOM加NEO Dock完整套装 申请或自购',
    '4乘4矩阵键盘2个',
    'EC11旋转编码器模块3个',
    'FSR402压力传感器3个',
    'MCP3008 SPI ADC模块2个',
    'PCM5102A三线I2S DAC模块2个',
    '有源小音箱1个和3.5 mm音频线2根',
    'VL53L0X测距模块2个 后期购买',
    'PAM8403功放模块2个和8欧3瓦扬声器4个 后期购买',
    '大号面包板2块 杜邦线各1至2组 排针排母若干',
    '电阻电容套装1套',
    'USB逻辑分析仪1个',
    'USB音频采集卡1个 后期购买',
    '防静电袋或防静电垫1套',
]:
    check(item)

heading('十三 资料依据')
bullet('高云半导体2026 FPGA创新设计赛道选题指南。')
bullet('高云半导体大学计划2026板卡申请页面。')
bullet('Sipeed Tang Mega 60K官方硬件文档和示例仓库。')
bullet('Texas Instruments PCM5102A数据手册。')
bullet('Microchip MCP3008数据手册。')
para('价格为2026年9月选题阶段预算，不代表固定销售价格。采购前应核对板卡套装、连接器、供电要求和模块逻辑电平。')

for section in doc.sections:
    p=section.footer.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    begin=OxmlElement('w:fldChar'); begin.set(qn('w:fldCharType'),'begin')
    instr=OxmlElement('w:instrText'); instr.set(qn('xml:space'),'preserve'); instr.text='PAGE'
    end=OxmlElement('w:fldChar'); end.set(qn('w:fldCharType'),'end')
    p._p.extend([begin,instr,end])

doc.core_properties.title='高云选题二提前购买与准备清单'
doc.core_properties.subject='实时多音色合成电子乐器引擎采购和准备方案'
doc.core_properties.author=''
doc.save(OUT)
print(OUT.resolve())
