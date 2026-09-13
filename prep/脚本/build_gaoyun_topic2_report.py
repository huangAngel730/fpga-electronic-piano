from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path('高云选题2_实时多音色合成电子乐器引擎分析.docx')

def font(run, size=10.5, bold=False, color=None, family='微软雅黑'):
    run.font.name = family
    rp = run._element.get_or_add_rPr()
    for key in ('w:ascii', 'w:hAnsi', 'w:eastAsia'):
        rp.rFonts.set(qn(key), family)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def shade(cell, fill):
    node = OxmlElement('w:shd')
    node.set(qn('w:fill'), fill)
    cell._tc.get_or_add_tcPr().append(node)

def cell(cell_obj, value, header=False, center=False, size=8.5):
    cell_obj.text = ''
    p = cell_obj.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center or header else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(0)
    font(p.add_run(str(value)), size, header, (255,255,255) if header else None)
    cell_obj.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if header:
        shade(cell_obj, '1F4E79')

def table(headers, rows, widths):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(headers):
        cell(t.cell(0,i), h, header=True, size=8.5)
        t.cell(0,i).width = Cm(widths[i])
    trp = t.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement('w:tblHeader'); repeat.set(qn('w:val'),'true'); trp.append(repeat)
    for row_data in rows:
        r = t.add_row()
        r._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for i, value in enumerate(row_data):
            cell(r.cells[i], value, center=(i==0), size=8.3)
            r.cells[i].width = Cm(widths[i])
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
        font(p.add_run(lead), bold=True)
        font(p.add_run(text[len(lead):]))
    else:
        font(p.add_run(text))
    return p

def bullet(text):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(2)
    font(p.add_run(text), 10)

def number(text):
    p = doc.add_paragraph(style='List Number')
    p.paragraph_format.space_after = Pt(3)
    font(p.add_run(text), 10)

def diagram(lines):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.cell(0,0); shade(c,'F2F2F2'); c.text=''
    for i, line in enumerate(lines):
        p = c.paragraphs[0] if i == 0 else c.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        font(p.add_run(line), 8.5, family='Consolas')
    doc.add_paragraph().paragraph_format.space_after = Pt(0)

doc = Document()
sec = doc.sections[0]
sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(1.8)
sec.left_margin = sec.right_margin = Cm(2.2)
normal = doc.styles['Normal']
normal.font.name = '微软雅黑'; normal.font.size = Pt(10.5)
normal._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')
for name, size, color in [('Title',23,(0,0,0)),('Heading 1',16,(31,78,121)),('Heading 2',13,(47,84,114))]:
    s=doc.styles[name]; s.font.name='微软雅黑'; s.font.size=Pt(size); s.font.bold=True
    s.font.color.rgb=RGBColor(*color); s._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'微软雅黑')

# 封面
p=doc.add_paragraph(style='Title'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before=Pt(105); p.paragraph_format.space_after=Pt(22)
p.add_run('高云选题二实时多音色合成电子乐器引擎分析')
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run('2026年全国大学生嵌入式芯片与系统设计竞赛 FPGA创新设计赛道'),13)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run('选题决策与实施方案'),15,True,(31,78,121))
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(135)
font(p.add_run('分析日期 2026年9月8日'),10,(False),(89,89,89))
doc.add_page_break()

heading('一 结论与建议')
para('高云选题二适合作为本团队的重点候选。它的基础功能可以逐模块验证，FPGA承担完整的逐采样音频合成、包络和混音通路，技术贡献容易说明；同时，作品能通过声音、频谱和延迟测量形成直观证据。建议申请Tang Mega 60K，以32复音、48 kHz采样、三个交互维度、两种以上音色、低于5 ms的确定性延迟为主要目标。')
table(['维度','评价','依据'],[
 ['完赛难度','中等','数字模块可先仿真，I2S、传感器和模拟音频需要上板联调'],
 ['FPGA技术含量','高','音频生成、ADSR、多声部和效果器均在FPGA内部实时完成'],
 ['现场展示效果','很强','多音色、手势控制、频谱和效果器开关可即时呈现'],
 ['撞题程度','中低','公开同类方案少于常规Sobel和HDMI图像处理项目'],
 ['AI辅助空间','约80%至90%','RTL、Testbench、Python参考模型、脚本和文档适合自动化'],
 ['预算','约200至1600元','取决于是否成功申请Tang Mega 60K及演示结构复杂度'],
], [3.2,3.2,9.6])
para('项目的主要风险不是合成算法本身，而是输入去抖造成额外延迟、I2S时序错误、多声部混音溢出、DAC噪声和演示结构不稳定。应先完成最小发声链路，再扩展复音和交互，避免过早投入蓝牙App或复杂物理建模。')

heading('二 官方要求拆解')
para('赛题要求分为基础功能、拓展功能和现场验证三层。基础功能决定作品是否合规，拓展功能决定区分度，现场验证决定量化指标是否可信。')
heading('基础要求',2)
table(['官方要求','工程实现','验收证据'],[
 ['至少两个独立交互维度','按键或触摸选音，压力控制力度，光电或距离控制滑音','分别操作两个维度，参数和声音同步变化'],
 ['纯FPGA实时音频合成','逐采样生成波形，完成包络、混音和I2S输出','RTL代码、仿真波形和测试模式'],
 ['延迟不高于10 ms','缩短输入确认时间，以48 kHz音频节拍更新','示波器测量输入GPIO到DAC模拟输出'],
 ['基础复音数不少于4','四个以上独立声部维护相位、频率和包络','同时演奏和弦并显示活跃声部数'],
 ['实时变调和ADSR','频率控制字实时变化，每声部独立状态机','滑音、按键力度和释放尾音演示'],
 ['禁止播放预录PCM','只保存单周期波表或合成参数','工程中不存在完整音符或歌曲采样'],
], [4.0,6.5,5.5])
heading('拓展要求',2)
table(['拓展项','推荐目标','优先级'],[
 ['并行合成规模','32复音起步，资源允许时扩展64复音','最高'],
 ['多维表情控制','选音、力度、滑音或颤音三个独立维度','高'],
 ['多音色','波表风琴和二运算器FM，另加弹拨音色','高'],
 ['音频效果器','先延迟，再合唱，混响作为备用','高'],
 ['确定性低延迟','最大延迟低于3 ms，至少满足低于5 ms','最高'],
 ['视听反馈','活跃声部、波形、频谱和削波状态','中高'],
 ['手机联动','只用于参数配置或曲谱下载','低'],
], [4.3,8.2,3.5])
heading('核心评分口径',2)
para('官方以同时活跃且可闻的独立振荡器总数乘以实际采样率作为核心吞吐量依据，过采样不重复加分。独立振荡器需要具备独立相位、频率和包络状态。')
table(['配置','吞吐量','判断'],[
 ['4振荡器 48 kHz','192000振荡器采样每秒','满足基础要求'],
 ['32振荡器 48 kHz','1536000振荡器采样每秒','满足高阶规模要求'],
 ['64振荡器 48 kHz','3072000振荡器采样每秒','稳定后再挑战'],
], [5.0,5.0,6.0])

heading('三 推荐作品方案')
para('推荐作品名称为基于FPGA的32复音多维交互式光弦电子合成器。按键或电容触摸选择音符，压力控制力度和音色明亮度，光电或距离传感器控制拨弦、滑音或颤音。现场可切换波表和FM音色，并打开延迟或合唱效果。')
heading('演示流程',2)
number('演奏单音与和弦，显示当前音符和活跃声部数。')
number('改变压力，观察音量、包络峰值或音色亮度连续变化。')
number('移动手掌改变距离，实时控制滑音、颤音或合唱深度。')
number('切换波表风琴、FM铃声和弹拨音色，对比频谱差异。')
number('进入测试模式，输出多路不同频率并展示对应频谱峰。')
number('用示波器展示输入触发到DAC输出的延迟。')

heading('四 系统架构')
diagram([
 '按键触摸 ─┐',
 '压力传感 ─┼─> 输入采集与滤波 ─> 事件FIFO ─> 音符与声部分配器',
 '光电距离 ─┘                                  │',
 '                                              ├─> 频率控制字',
 '                                              ├─> ADSR参数',
 '                                              └─> 表情控制参数',
 '                                                       │',
 '                         32路独立声部状态与流水处理 <──┘',
 '                                      │',
 '                              波表或FM音色生成',
 '                                      │',
 '                              独立ADSR包络乘法',
 '                                      │',
 '                               宽位混音加法树',
 '                                      │',
 '                         延迟 合唱 简化混响效果器',
 '                                      │',
 '                            限幅 音量与削波检测',
 '                                      │',
 '                           I2S发送 ─> DAC ─> 音箱',
 '                                      │',
 '                           波形 频谱 活跃声部显示',
])
heading('RTL模块划分',2)
table(['模块组','主要模块','职责'],[
 ['时钟','audio_pll audio_tick_gen','产生系统时钟、采样使能、BCLK和LRCLK'],
 ['输入','key_scan debounce spi_adc filter','采集交互输入并形成确定时序事件'],
 ['调度','event_fifo voice_allocator','分配声部，处理note_on和note_off'],
 ['合成','phase_accumulator wavetable fm_operator','逐声部生成样本'],
 ['包络','adsr_envelope','维护每个声部的ADSR状态'],
 ['混音','mixer_tree gain saturator','宽位累加、增益和饱和截断'],
 ['效果','audio_delay chorus reverb','使用BRAM延迟线实现空间效果'],
 ['输出','i2s_tx','发送左右声道样本'],
 ['显示','waveform spectrum overlay','显示频谱、波形和运行状态'],
], [2.7,6.2,7.1])

heading('五 数值格式与关键算法')
heading('音频时钟',2)
para('推荐采用48 kHz立体声，内部使用18至24位有符号样本，I2S输出16位或24位。若每声道槽位占32个BCLK周期，则BCLK为3.072 MHz。建议使用不强制外部MCLK的PCM5102A三线I2S模块，降低时钟联调难度。')
heading('DDS与频率控制字',2)
para('每个声部使用32位相位累加器。频率控制字等于目标频率除以采样率，再乘以2的32次方并四舍五入。MIDI音符0至127的控制字离线生成后存入ROM。A4为440 Hz时，在48 kHz采样率下的控制字约为39367883。')
heading('波表与音色',2)
bullet('使用1024点单周期波表，地址取相位累加器高10位。')
bullet('至少提供正弦、三角、锯齿和风琴波表。')
bullet('高音区锯齿和方波使用分频段波表减少混叠。')
bullet('FM使用二运算器结构，调制指数和频率比可实时调节。')
bullet('只能保存单周期波表和参数，不保存完整音符录音或歌曲PCM。')
heading('ADSR与复音管理',2)
para('每个声部独立维护IDLE、ATTACK、DECAY、SUSTAIN和RELEASE状态，包络可采用Q1.15或Q1.16格式，每个采样周期更新一次。声部耗尽时优先回收已进入RELEASE且幅度最低的声部，其次回收持续时间最长的声部。')
heading('混音位宽',2)
para('32路16位样本相加至少需要21位。考虑包络乘法、效果反馈和动态余量，推荐使用26至32位内部混音通路，最终经过增益、四舍五入和饱和限幅后输出。禁止直接截取累加结果低16位，否则会产生回绕失真。')

heading('六 32复音实现策略')
para('系统时钟为100 MHz、采样率为48 kHz时，每个采样周期约有2083个系统时钟周期。顺序更新32个声部时，平均每个声部仍有约65个时钟周期，因此不必复制32套大型组合逻辑。')
para('推荐保存32套独立声部状态，使用4至8条流水处理通道分时完成波表读取、包络乘法和累加。这既保留每个声部独立的相位、频率和包络，也能降低DSP和布线压力。报告应分别列出音符复音数、每音符振荡器数、活跃振荡器总数和采样率。')

heading('七 音色与效果器优先级')
table(['功能','推荐实现','原因'],[
 ['波表风琴','多谐波分量或专用单周期波表','和弦稳定，适合复音演示'],
 ['FM铃声','二运算器FM','与波表差异明显，技术含量较好'],
 ['弹拨音色','锯齿或三角波加快速包络','适合光电拨弦交互'],
 ['延迟','BRAM环形缓冲和反馈','实现简单，效果明显'],
 ['合唱','低频振荡器调制短延迟','资源适中，增加声音宽度'],
 ['混响','梳状滤波器加全通滤波器','区分度高，但最后实现'],
], [3.2,6.2,6.6])

heading('八 硬件选型与预算')
para('首选Tang Mega 60K。它是高云对选题二推荐申请的板卡，具有约60K LUT4等效逻辑单元、片上BSRAM、DSP和丰富接口，能为32复音、效果器和频谱显示留出资源。Tang Nano 20K适合最小验证，但加入32复音、FFT和显示后的余量较小。')
table(['功能','推荐器件','接口','估计价格'],[
 ['FPGA平台','Tang Mega 60K','GPIO I2S HDMI','申请借用或自购数百元至近千元'],
 ['音频DAC','PCM5102A模块','I2S','15至35元'],
 ['音符输入','机械按键或TTP229','GPIO或串行','15至50元'],
 ['力度检测','FSR加MCP3008','SPI','25至60元'],
 ['表情控制','光电 距离传感器 编码器','GPIO I2C','20至80元'],
 ['声音输出','PAM8403或有源音箱','模拟音频','30至100元'],
 ['结构连接','面包板 PCB 线材 外壳','无','100至400元'],
 ['调试备用','备用DAC 传感器 接插件','无','100至200元'],
], [2.8,4.6,3.0,5.6])
para('成功申请Tang Mega 60K后，建议准备300至700元完成外设、结构和备用件。全部自购时建议准备900至1600元。价格是选题阶段预算，正式采购前应按板卡套装和国内渠道重新询价。')

heading('九 开发计划')
table(['阶段','主要工作','完成标准'],[
 ['第1周','工具链、基础工程、I2S固定正弦波','DAC稳定输出440 Hz，协议仿真正确'],
 ['第2周','单声部DDS、音符ROM、ADSR','按键演奏不同音符并自然释放'],
 ['第3周','4路至16路复音、声部分配','和弦稳定，无回绕爆音'],
 ['第4周','32复音、宽位混音','测试模式通过仿真和频谱验证'],
 ['第5周','压力、光电、距离或编码器','三个交互维度稳定，输入延迟可测'],
 ['第6周','第二音色、延迟、合唱','切换无明显毛刺'],
 ['第7周','波形、频谱、状态显示','显示活跃声部和削波状态'],
 ['第8周','回归、时序、演示结构','连续运行2小时，时序通过'],
 ['第9周','视频、报告、答辩材料','提交包可复现，队员能解释核心模块'],
], [2.3,6.4,7.3])
heading('开发顺序原则',2)
bullet('固定频率I2S发声是第一道生死线，未打通前不开发高级合成器。')
bullet('复音按4路、8路、16路和32路扩展，每一级保留自动回归。')
bullet('效果器在基础合成稳定后加入，并提供硬件旁路开关。')
bullet('显示和手机联动不得进入音频关键路径。')

heading('十 验证方案')
heading('逐采样参考比较',2)
para('使用Python建立DDS、ADSR、混音、饱和和效果器参考模型。相同事件同时输入Python与RTL，逐采样比较。基础模块建议将最大绝对误差控制在2 LSB以内，效果器按定点格式单独定义容差。')
heading('I2S协议验证',2)
bullet('检查LRCLK为48 kHz，BCLK与槽位宽度匹配。')
bullet('检查MSB相对声道切换延迟一个BCLK。')
bullet('检查左右声道、符号扩展、位宽和静音状态。')
bullet('在仿真中还原PCM样本并与发送前数据比较。')
heading('端到端延迟',2)
number('输入事件被接受时翻转调试GPIO。')
number('示波器通道一观察GPIO，通道二观察DAC模拟输出。')
number('测量输出首次超过阈值的时间，重复至少100次。')
number('报告平均值、最大值、最小值和峰峰抖动，目标最大值低于5 ms。')
heading('频谱与稳定性',2)
bullet('测试模式输出200 Hz、300 Hz、400 Hz等间隔充分的多路频率。')
bullet('通过电脑频谱、示波器FFT或内部FFT观察独立谱峰。')
bullet('32路全部激活并持续运行2小时。')
bullet('反复快速触发、释放、切换音色和效果器。')
bullet('记录削波次数、FIFO溢出、最大电平和复位恢复时间。')

heading('十一 主要风险与对策')
table(['风险','表现','对策'],[
 ['输入去抖过长','触发延迟超过10 ms','快速按下确认、较慢释放确认，并实测延迟'],
 ['I2S格式错误','杂音、无声或声道错位','先仿真解码，再用逻辑分析仪检查时钟'],
 ['混音溢出','爆音和回绕失真','宽位累加、增益、舍入和饱和限幅'],
 ['声部分配错误','丢音、卡音和释放不结束','事件FIFO、断言和随机事件回归'],
 ['波形混叠','高音刺耳和频谱折叠','分频段波表或限制高音区谐波'],
 ['效果反馈失控','延迟或混响自激','限制反馈系数，增加饱和和旁路'],
 ['模拟噪声','底噪和数字串扰','电源滤波、短线、合理接地和屏蔽'],
 ['范围失控','核心未完成却投入App','冻结32复音和低延迟目标，按优先级扩展'],
], [3.4,5.2,7.4])

heading('十二 获奖策略')
para('若目标是获得任意国家级奖项，应把稳定性和证据完整度放在功能数量之前。最低可竞争版本建议满足以下条件。')
bullet('8至16复音稳定运行，最终推荐达到32复音。')
bullet('至少两个独立交互维度，推荐三个。')
bullet('至少两种差异明显的音色。')
bullet('完整ADSR和无明显削波的多声部混音。')
bullet('至少一种FPGA内部效果器，推荐延迟加合唱。')
bullet('端到端最大延迟低于5 ms并报告重复测量。')
bullet('频谱或波形显示、活跃声部数和削波指示。')
bullet('Python参考、RTL回归、资源和时序报告。')
bullet('连续运行2小时及故障恢复测试。')
para('高完成度目标为32复音、48 kHz、三个交互维度、三种音色、延迟与合唱两个效果器、最大延迟低于3 ms、32路测试模式、实时频谱和完整自动回归。没有必要盲目追求128复音；32复音稳定、声音清晰、延迟可证和文档完整，更符合工程评分逻辑。')

heading('十三 立即执行事项')
number('提交Tang Mega 60K板卡申请，同时准备自购备用方案。')
number('采购PCM5102A、输入模块、ADC和基础传感器。')
number('建立Git工程结构，先编写I2S发送模块和仿真解码器。')
number('编写Python频率控制字、波表和参考音频生成脚本。')
number('第一周完成440 Hz固定正弦波的仿真和上板发声。')

heading('十四 资料来源')
bullet('全国大学生嵌入式芯片与系统设计竞赛2026 FPGA创新设计赛道选题指南 高云半导体。')
bullet('Sipeed Tang Mega 60K官方示例仓库和板卡文档。')
bullet('高云半导体大学计划板卡申请说明，选题二推荐Tang Mega 60K。')
para('预算与实施建议属于选题阶段工程估计，器件价格、板卡套装和申请政策应以采购和报名时的官方信息为准。')

for s in doc.sections:
    p=s.footer.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    begin=OxmlElement('w:fldChar'); begin.set(qn('w:fldCharType'),'begin')
    instr=OxmlElement('w:instrText'); instr.set(qn('xml:space'),'preserve'); instr.text='PAGE'
    end=OxmlElement('w:fldChar'); end.set(qn('w:fldCharType'),'end')
    p._p.extend([begin,instr,end])

doc.core_properties.title='高云选题二实时多音色合成电子乐器引擎分析'
doc.core_properties.subject='2026 FPGA创新设计赛道选题与实施方案'
doc.core_properties.author=''
doc.save(OUT)
print(OUT.resolve())
