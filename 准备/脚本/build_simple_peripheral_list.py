from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(__file__).resolve().parents[1] / '外设模块采购清单.docx'

def set_font(run, size=10.5, bold=False, color=None):
    run.font.name = '微软雅黑'
    props = run._element.get_or_add_rPr()
    for key in ('w:ascii', 'w:hAnsi', 'w:eastAsia'):
        props.rFonts.set(qn(key), '微软雅黑')
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def shade(cell, fill):
    node = OxmlElement('w:shd')
    node.set(qn('w:fill'), fill)
    cell._tc.get_or_add_tcPr().append(node)

def add_table(headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i, header in enumerate(headers):
        c = table.cell(0, i)
        c.text = ''
        shade(c, '1F4E79')
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(header), size=9, bold=True, color=(255, 255, 255))
        c.width = Cm(widths[i])
    for row_data in rows:
        row = table.add_row()
        for i, value in enumerate(row_data):
            c = row.cells[i]
            c.text = ''
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i in (0, 1, len(headers)-1) else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(0)
            set_font(p.add_run(str(value)), size=8.5)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            c.width = Cm(widths[i])
    doc.add_paragraph()

def heading(text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p

def paragraph(text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.2
    set_font(p.add_run(text))

def check(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    set_font(p.add_run('□  ' + text), size=10)

doc = Document()
section = doc.sections[0]
section.top_margin = Cm(1.8)
section.bottom_margin = Cm(1.8)
section.left_margin = Cm(2.0)
section.right_margin = Cm(2.0)

normal = doc.styles['Normal']
normal.font.name = '微软雅黑'
normal._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '微软雅黑')
normal.font.size = Pt(10.5)

for style_name, size, color in [
    ('Title', 22, (0, 0, 0)),
    ('Heading 1', 16, (31, 78, 121)),
    ('Heading 2', 13, (47, 84, 114)),
]:
    style = doc.styles[style_name]
    style.font.name = '微软雅黑'
    style._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '微软雅黑')
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = RGBColor(*color)

p = doc.add_paragraph(style='Title')
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run('高云选题二外设模块采购清单')
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(p.add_run('适配 Tang Mega 60K 基础套餐'), size=13, bold=True, color=(31, 78, 121))
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(p.add_run('更新日期 2026年9月8日'), size=9.5, color=(89, 89, 89))

heading('一 已确定的主板')
paragraph('淘宝选择 Tang Mega 60K 基础套餐，截图价格为739元。套餐包含60K SOM核心板、Tang Mega NEO Dock底板、USB-C数据线、两根8P端子线和USB-C母口转DC5521转接头。图片未显示独立电源适配器。')
add_table(
    ['项目', '数量', '说明', '是否另购'],
    [
        ['Tang Mega 60K SOM', '1', 'FPGA核心板', '套餐包含'],
        ['Tang Mega NEO Dock', '1', 'JTAG UART HDMI 音频 扩展接口', '套餐包含'],
        ['USB-C数据线', '1', '下载和串口连接', '套餐包含'],
        ['8P端子线', '2', '调试接口转接', '套餐包含'],
        ['USB-C转DC5521', '1', '需要支持12 V输出的PD电源', '套餐包含'],
        ['12 V电源', '1', '向客服确认PD电源或DC5521适配器规格', '可能另购'],
    ],
    [4.0, 2.0, 7.0, 3.0],
)

heading('二 第一批必须购买')
add_table(
    ['模块', '数量', '作用', '参考预算'],
    [
        ['4乘4矩阵键盘', '2个', '16个音符按键，一个开发一个备用', '10至20元'],
        ['EC11旋转编码器模块', '3个', '音量、音色和效果参数', '15至30元'],
        ['FSR402压力传感器', '3个', '控制力度、包络峰值或音色亮度', '30至80元'],
        ['MCP3008 SPI ADC模块', '2个', '采集FSR和其他模拟传感器', '30至70元'],
        ['PCM5102A三线I2S DAC', '2个', '独立验证I2S并作为板载音频备用', '30至70元'],
        ['3.5 mm有源小音箱', '1个', '直接播放DAC线路输出', '40至120元'],
        ['USB逻辑分析仪', '1个', '检查I2S、SPI、按键和编码器时序', '30至150元'],
        ['大号面包板', '2块', '搭建传感器和输入电路', '20至40元'],
        ['杜邦线三种规格', '各1至2组', '公公、公母、母母', '30至60元'],
        ['电阻电容套装', '1套', '分压、限流、去耦和滤波', '25至60元'],
    ],
    [4.5, 2.2, 6.3, 3.0],
)
paragraph('第一批外设预算约260至700元。实验室已有音箱、逻辑分析仪、面包板和元件时，可以明显降低支出。')

heading('三 三个演奏控制维度')
add_table(
    ['控制维度', '推荐模块', '作用', '开发顺序'],
    [
        ['音符与和弦', '4乘4矩阵键盘', '选择音符、八度和和弦', '第一个完成'],
        ['力度', 'FSR402加MCP3008', '控制音量、ADSR峰值和亮度', '第二个完成'],
        ['滑音与颤音', 'EC11编码器', '控制音高弯曲和颤音深度', '第三个完成'],
        ['无接触控制', 'VL53L0X测距模块', '后期替代编码器控制滑音或效果', '核心稳定后'],
        ['触摸演奏', 'TTP229触摸键盘', '后期替代机械矩阵键盘', '核心稳定后'],
    ],
    [3.5, 4.5, 5.5, 2.5],
)

heading('四 第二批后期购买')
add_table(
    ['模块', '数量', '购买条件', '参考预算'],
    [
        ['TTP229 16键触摸模块', '1至2个', '机械键盘版稳定后', '15至50元'],
        ['VL53L0X测距模块', '1至2个', '需要无接触滑音时', '20至60元'],
        ['USB音频采集卡', '1个', '开始自动频谱和音频测试时', '20至80元'],
        ['PAM8403功放模块', '2个', '需要驱动无源扬声器时', '10至20元'],
        ['8欧3瓦扬声器', '4个', '确认功放和接口后', '20至50元'],
        ['定制PCB和外壳', '1套', '面包板版本稳定后', '200至600元'],
    ],
    [4.5, 2.2, 6.0, 3.3],
)

heading('五 暂时不要购买')
add_table(
    ['模块', '原因', '替代方案'],
    [
        ['HC-SR04', '常见Echo输出为5 V，直接接FPGA有风险', 'VL53L0X或编码器'],
        ['DFPlayer或MP3模块', '属于播放预录音频，不符合纯FPGA实时合成要求', 'DDS、波表或FM'],
        ['带成品音源的MIDI模块', '无法证明声音由FPGA逐采样生成', 'MIDI只传事件，FPGA生成声音'],
        ['ESP32和复杂蓝牙方案', '会分散核心开发时间', '32复音和低延迟完成后再考虑'],
        ['昂贵独立显示屏', 'NEO Dock已有HDMI', '使用现有HDMI显示器'],
    ],
    [4.2, 7.0, 4.8],
)

heading('六 接线安全')
for item in [
    '所有进入FPGA的数字信号不得高于3.3 V',
    'MCP3008使用3.3 V供电和3.3 V参考电压',
    'FPGA与全部外设共地',
    '5 V模块输出必须经过分压或电平转换',
    'PCM5102A线路输出接有源音箱，不能直接驱动无源扬声器',
    '首次通电前用万用表检查3.3 V和5 V是否对地短路',
    '未断电时不要插拔SOM核心板或裸排针',
]:
    check(item)

heading('七 立即下单清单')
for item in [
    'Tang Mega 60K基础套餐 739元',
    '向客服确认是否缺少12 V电源',
    '4乘4矩阵键盘2个',
    'EC11编码器模块3个',
    'FSR402压力传感器3个',
    'MCP3008 SPI ADC模块2个',
    'PCM5102A三线I2S DAC模块2个',
    '3.5 mm有源小音箱1个',
    'USB逻辑分析仪1个',
    '面包板2块和杜邦线三种规格',
    '常用电阻电容套装1套',
]:
    check(item)

heading('八 最小购买方案')
paragraph('如果希望先控制预算，只购买矩阵键盘、EC11、PCM5102A、有源音箱、面包板、杜邦线和逻辑分析仪，就可以开始I2S、DDS、ADSR和基础复音开发。FSR、MCP3008、VL53L0X、功放和外壳可以后买。')

doc.core_properties.title = '高云选题二外设模块采购清单'
doc.core_properties.author = ''
doc.save(OUT)
print(OUT)
