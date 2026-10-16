"""Build a local schematic-derived Pro pin reference; never programs hardware."""
import hashlib
import html
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
REPO = Path(r"E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano")
INPUTS = REPO / "code/docs/test/m3_m2td_audio_endpoint_audit_20261015/successor_R03/input_audit_verify_r02/derived_original_bytes/inputs"
AMP_URL = "https://datasheet.datasheetarchive.com/originals/crawler/xptek.com.cn/2a166963eb40adf24042f57411cef03b.pdf"
rows = []


def add(group, net, ball, bank, endpoint, dock="—", core="—", note="", source=""):
    voltage = {2: "3.3 V（可选1.8 V）", 3: "3.3 V", 4: "3.3 V（可选1.8 V）", 5: "3.3 V（可选1.8 V）", 7: "1.5 V", 10: "3.3 V"}.get(bank, "不适用/待确认")
    rows.append(dict(group=group, net=net, ball=ball, bank=str(bank) if bank else "—", voltage=voltage,
                     endpoint=endpoint, dock=dock, core=core, note=note, source=source))


def btb(ref, pin):
    """Adjacent odd/even mirror, verified against the two schematic drawings."""
    counterpart = {"J6": "J1", "J7": "J2", "J8": "J3"}[ref]
    return f"{ref}/{pin}", f"{counterpart}/{pin + 1 if pin % 2 else pin - 1}"


def add_btb(group, net, ball, bank, endpoint, ref, pin, note="", source=""):
    dock, core = btb(ref, pin)
    add(group, net, ball, bank, endpoint, dock, core, note, source)


add("时钟", "P16_EMCCLK", "P16", 3, "核心板 U8 OUT(3) 经 R38 22Ω", note="50 MHz固定有源晶振；建议作为迁移的主输入候选，尚未验证PLL路由。不是底板U8。", source="4072 p7")
add_btb("时钟", "USR_CLK_IN", "N22", 3, "底板 U2 MS5351M CLK2(6) 经 R2", "J6", 75, "可编程时钟；频率依赖MS5351配置，不默认等于50 MHz。", "4071 p3、p5；4072 p5、p7")
for i, (ball, bank, pin) in enumerate([("K16", 4, 59), ("F15", 5, 61), ("G15", 5, 63), ("G16", 5, 65)]):
    add_btb("底板按键", f"USR_KEY.{i}", ball, bank, f"底板 S{i}", "J8", pin,
            "外部1.5kΩ上拉至3.3 V，按下接地、低有效；与LCD.INT复用。S0可作低有效复位候选，S1/S2可作音符键候选，均未实现。", "4071 p5、p15；4072 p6")
add_btb("核心板按键", "CPU_RST / U4_USR_KEY", "U4", 7, "核心板 SW5", "J7", 57,
        "与底板S0不同；1.5 V域，上电阻接1.5 V、下拉到GND，按下为高；不能沿用底板低有效复位假设。", "4072 p7、p8；4071 p5")
add_btb("配置", "RECONFIG_N", "AE16", 10, "核心板 SW2", "J7", 55, "按下为低，重新配置；不是音符键。与底板电源SW2同号但不在同一PCB。", "4072 p7；4071 p5")
for net, ball, led in [("CFG_DONE", "W10", "LED2"), ("CFG_READY", "V11", "LED1")]:
    add("配置", net, ball, 10, f"核心板 {led}", note="专用配置状态信号，不作为普通用户LED复用。", source="4072 p7")
add_btb("UART", "DBG_UART.TX / FPGA_TXD", "P15", 3, "底板 R128 0Ω → BL616 U9 GPIO11(10)；核心板J5/7", "J6", 66,
        "FPGA→电脑；115200 8N1是当前RTL要求；Pro BL616 GPIO11接收，不能照搬NEO GPIO27。", "4071 p5、p6；4072 p5、p7")
add_btb("UART", "DBG_UART.RX / FPGA_RXD", "N16", 3, "BL616 U9 GPIO10(9) → 底板 R95 0Ω；核心板J5/6", "J6", 63,
        "电脑→FPGA；当前四复音顶层没有使用此方向。", "4071 p5、p6；4072 p5、p7")
for net, ball, pin, gpio, u9pin, j5pin in [("TMS", "H11", 87, 0, 4, 2), ("TCK", "H12", 81, 1, 5, 4), ("TDO", "J10", 85, 2, 6, 3), ("TDI", "H10", 83, 3, 7, 5)]:
    add_btb("JTAG", f"JTAG.{net}", ball, 10, f"BL616 U9 GPIO{gpio}({u9pin})；核心板J5/{j5pin}", "J8", pin,
            "底板调试USB为J10；不要占为用户GPIO。", "4071 p5、p6；4072 p6、p7")
for net, ball, bank, pin, chip_pin in [("I2S_BCLK", "E22", 5, 22, 1), ("I2S_LRCK", "F24", 4, 18, 2), ("I2S_DIN", "G24", 4, 16, 3)]:
    add_btb("音频", net, ball, bank, f"底板 U6 PT8211-S/{chip_pin}", "J8", pin,
            "FPGA输出；PT8211使用16位LSBJ右对齐（非Philips I2S）；当前发送器可作为复用候选。", "4071 p5、p18；4072 p6")
add_btb("音频", "PA_EN", "H17", 5, "底板 U32 XPT4809 EN/SD(5)，R248 100kΩ下拉", "J8", 24,
        "高=正常工作，低=关闭，和当前NEO顶层低有效功放控制相反；需改顶层极性。", "4071 p5、p18；4072 p6；XPT4809数据手册p3")
add("音频", "HP_OUTL / HP_OUTR / GNDA", "—", None, "底板 J29：L=5，R=4，GND=3", note="3.5mm耳机口是J29；J25是DC电源口。U6 pin5=3V3A、pin4=GND。", source="4071 p2、p18")
add("音频", "SPK_AUDIO", "—", None, "底板 J30/2（信号）、J30/1（GNDA）", note="右声道模拟输出经隔直电容；不是NEO的2×3W功放拓扑，不据连接器名称承诺可驱动无源大喇叭。", source="4071 p18")

pmods = [
    (0, "J22", [("N18", 3, "J6", 93), ("N26", 3, "J6", 82), ("R16", 3, "J7", 52), ("R17", 3, "J7", 50), ("M26", 3, "J6", 84), ("N17", 3, "J6", 69), ("L24", 3, "J6", 27), ("T24", 3, "J7", 15)]),
    (1, "J24", [("C24", 5, "J8", 8), ("E25", 4, "J8", 12), ("L17", 4, "J8", 60), ("H14", 5, "J8", 66), ("B24", 5, "J8", 10), ("D25", 4, "J8", 14), ("L18", 4, "J8", 62), ("H15", 5, "J8", 68)]),
    (2, "J26", [("C21", 5, "J8", 70), ("B20", 5, "J8", 74), ("B19", 5, "J8", 80), ("A17", 5, "J8", 86), ("B21", 5, "J8", 72), ("A20", 5, "J8", 76), ("A19", 5, "J8", 82), ("A18", 5, "J8", 88)]),
]
pmod_pins = [11, 9, 7, 5, 12, 10, 8, 6]
sspi = {0: "SSPI_SO", 2: "SSPI_CLK", 3: "SSPI_WP_N", 5: "SSPI_SI", 6: "SSPI_CS_N", 7: "SSPI_HOLD_N"}
for group, connector, values in pmods:
    for i, (ball, bank, ref, pin) in enumerate(values):
        note = "连接器1/2=3.3 V，3/4=GND；针号按原理图，不推断实物观察方向。"
        if group == 0:
            note += "与麦克风阵列J28复用。"
            if i in sspi:
                note += f"还与{sspi[i]}配置功能复用；使用前核对配置模式。"
        if group == 0 and i == 1:
            note = "冲突：BTB页p5标N26，外接页p16标L22；MIC_D1亦标L22。暂不用于接线，需官方CST/PCB或断电通断确认。"
            ball = "N26（p5）/ L22（p16）"
        if group == 0 and i == 3:
            note += "R17在Pro是PMOD0_IO3、J22/5，不是NEO的PMOD0_IO5/J9/8；当前midi_rx同名球位但不得据此判断旧.fs物理路由正确。"
        if group == 2 and i == 0:
            note += "可作为避开PMOD0配置复用的MIDI输入候选，需M2批准并修改约束后使用。"
        add_btb(f"PMOD{group}", f"PMOD{group}_IO{i}", ball, bank, f"底板 {connector}/{pmod_pins[i]}", ref, pin, note,
                "4071 p5、p16；4072 p5/p6/p7/p9")
for i, (ball, bank, ref, pin) in enumerate([("J14", 2, "J7", 51), ("R26", 3, "J6", 30), ("L20", 3, "J6", 40), ("M25", 3, "J6", 73), ("N21", 3, "J6", 77), ("N23", 3, "J6", 76)]):
    add_btb("用户LED", f"USR_LED.{i}", ball, bank, f"底板 LED{i}，R{31+i} 3.3kΩ", ref, pin,
            "LED阳极接3.3 V，FPGA拉低点亮。", "4071 p5、p15；4072 p5/p9")
for net, ball, pin, hdmi_pin in [("D0.P", "AB24", 5, 7), ("D0.N", "AC24", 3, 9), ("D1.P", "V24", 17, 4), ("D1.N", "W24", 15, 6), ("D2.P", "AA22", 9, 1), ("D2.N", "AA23", 7, 3), ("CLK.P", "Y22", 13, 10), ("CLK.N", "Y23", 11, 12)]:
    add_btb("HDMI输出", f"DVI_TX.{net}", ball, 2, f"底板 HDMI J11/{hdmi_pin}（DVI A TX）", "J6", pin,
            "经100nF耦合、电阻网络及ESD器件；须按官方差分约束、序列化及PLL重新核验，不直接套普通LVCMOS单端约束。", "4071 p5、p8；4072 p5")
add_btb("HDMI输出", "DVI_TX_HPD", "T15", 2, "HDMI J11/19 经 R94 5.1kΩ", "J7", 40, source="4071 p5、p8；4072 p9")
add_btb("HDMI输出", "CEC_TX", "T14", 2, "HDMI J11/13 经 R89 100Ω", "J7", 42, source="4071 p5、p8；4072 p9")
for net, ball, pin in [("SYS_TWI.SCL", "K25", 90), ("SYS_TWI.SDA", "K26", 92), ("TWI_MUX.S0", "N19", 36), ("TWI_MUX.S1", "P19", 34), ("TWI_MUX.S2", "P26", 32)]:
    add_btb("I2C与时钟配置", net, ball, 3, "底板TWI复用网络", "J6", pin,
            "MS5351、HDMI DDC等经复用选择；底板p3 PLL0选择S[0..2]=0,1,1，PLL1=1,0,0。", "4071 p3、p4、p5、p8；4072 p5/p7")
add_btb("状态灯", "WS2812", "H16", 5, "底板 R27 100Ω → U4 DIN(3)；J27/3", "J8", 67,
        "J27/1=GND，J27/4=受控5V；当前工程不使用。", "4071 p5、p15；4072 p6")
for net, ball, pin, endpoint in [("FAN.TAC", "T18", 30, "风扇M1/3"), ("FAN.PWM", "T17", 32, "R266 15Ω → Q9；M1/4的R265为未装")]:
    add_btb("风扇", net, ball, 2, endpoint, "J7", pin, "当前工程不使用；不把MOS供电控制和标准4线PWM控制视为相同。", "4071 p5、p15；4072 p9")

sdram = [("D0", "U16", 2), ("D1", "V16", 2), ("D2", "U15", 2), ("D3", "V17", 2), ("D4", "W21", 2), ("D5", "Y21", 2), ("D6", "P21", 3), ("D7", "U17", 2), ("D15", "P23", 3), ("D14", "P24", 3), ("+5V", "—", None), ("GND", "—", None), ("D13", "T23", 3), ("D12", "R23", 3), ("D11", "R25", 3), ("D10", "T25", 3), ("D9", "W23", 2), ("D8", "P25", 3), ("A12", "U24", 2), ("CLK", "V23", 2), ("A9", "AC26", 2), ("A11", "U25", 2), ("A7", "AB25", 2), ("A8", "AB26", 2), ("A5", "AA25", 2), ("A6", "AA24", 2), ("WE_N", "Y26", 2), ("A4", "Y25", 2), ("DM0", "L22（p16标注，未闭合）", 3), ("DM1", "M24（p16标注，未闭合）", 3), ("CAS_N", "W26", 2), ("RAS_N", "W25", 2), ("CS_N", "U26", 2), ("BA0", "V26", 2), ("BA1", "W20", 2), ("A10", "Y20", 2), ("A0", "V19", 2), ("A1", "W19", 2), ("A2", "U22", 2), ("A3", "V22", 2)]
for i, (net, ball, bank) in enumerate(sdram, 1):
    note = "外接SDRAM排针，不是板载DDR3；与PMOD0等存在复用。"
    if net in ("DM0", "DM1"):
        note = "待确认：p16标注球位与p5的PCIE_WAKE/M.2_GPIO0用途不闭合，未给出可靠BTB连线；不得用于新约束。"
    if net == "+5V":
        note = "5 V电源脚，不是3.3 V FPGA输入。"
    add("扩展SDRAM", "SDRAM_"+net if bank else net, ball, bank, f"底板 J23/{i}", note=note, source="4071 p5、p16；4072 p5/p7/p9")

comparisons = [
    ["sys_clk", "V22", "P16", "核心U8的50 MHz固定时钟", "Pro同名V22标为SDRAM_A3；应换目标器件、时钟球位，重建PLL与SDC。"],
    ["sys_rst_n", "AA13", "K16（底板S0候选）", "底板按键低有效", "Pro同名AA13是SerDes Q1_REFCLK1.P，不能照搬；核心SW5/U4为另一组高有效1.5 V按键。"],
    ["key_n[0]", "AB13", "F15（底板S1候选）", "按下为低", "Pro同名AB13是SerDes Q1_REFCLK1.N；键位选择需批准后实现。"],
    ["key_n[1]", "Y12", "G15（底板S2候选）", "按下为低", "Pro同名Y12在核心p4为VSS；不能沿用。"],
    ["uart_tx", "U15", "P15", "R128→BL616 GPIO11→调试USB J10", "Pro同名U15接扩展SDRAM_D2/J23第3脚；旧UART约束不适配。"],
    ["i2s_bclk", "Y17", "E22", "U6/1 BCK", "Pro同名Y17在核心p4为NC；新时钟预期3.072 MHz（48k/64）。"],
    ["i2s_lrck", "AB17", "F24", "U6/2 WS", "Pro同名AB17在核心p4为NC；新WS预期48 kHz。"],
    ["i2s_din", "AA16", "G24", "U6/3 DIN", "Pro同名AA16在核心p4为VSS；继续使用PT8211的LSBJ格式。"],
    ["pa_en", "AB16（0=开）", "H17（1=开）", "U32 XPT4809/5", "不仅换球位，还需改变顶层使能极性；复位/PLL失锁时应输出0关闭。"],
    ["midi_rx", "R17，NEO PMOD0_IO5", "R17，Pro PMOD0_IO3", "Pro J22/5、J28/8复用", "同名球位可作候选，但插座针号、配置复用不同；也可提议改用C21/J26/11，未实施。"],
    ["tmds_data_p[0]", "J14,H14", "AB24,AC24", "HDMI A J11：D0+/D0-", "差分P/N顺序分别对应；需重做封装与差分约束。"],
    ["tmds_data_p[1]", "J15,H15", "V24,W24", "HDMI A J11：D1+/D1-", "不能沿用旧布局位置。"],
    ["tmds_data_p[2]", "K17,J17", "AA22,AA23", "HDMI A J11：D2+/D2-", "不能沿用旧布局位置。"],
    ["tmds_clk_p", "G15,G16", "Y22,Y23", "HDMI A J11：CK+/CK-", "Pro同名G15/G16是底板S2/S3按键；旧CST不能机械复用。"],
]
conflicts = [
    ["实物身份", "两份PDF证明资料针对4072核心板Rev1.10、4071f底板Rev1.5；不能证明手上实物就是同修订。", "拍摄/核对核心板、底板丝印和芯片版本；采购名称或JTAG家族ID不代替封装确认。"],
    ["器件符号", "4072原理图符号写GW5AT-LV138FPG676A；官方工具表列GW5AST-LV138FPG676AC1/I0。原件标注保留。", "工程完整料号与B/C步进按实物和官方工具支持表选，不凭PDF封面猜。"],
    ["PMOD0_IO1", "4071 p5 BTB标N26，p16 J22/9及MIC_D1标L22；N26与L22均真实存在，但指向不同网络。", "暂不使用该线；补官方对应Rev CST/PCB或断电通断测量。"],
    ["SDRAM_DM0/DM1", "p16标L22/M24，但p5这两个球位用于PCIE_WAKE/M.2_GPIO0，DM信号未闭合至BTB。", "保留注记，不用于本次音频迁移；若使用SDRAM再查PCB/官方CST。"],
    ["Bank默认电压", "p2画Bank2/4/5默认3.3 V，可通过选装电阻切到1.8 V；Bank3核心固定3.3 V。", "接入3.3 V MIDI模块前确认实际焊接与VCCIO读数；原理图默认不代替实测。"],
    ["PT8211标签", "原理图网络名I2S_OUT不等于Philips I2S协议。当前RTL发送的是PT8211要求的LSBJ右对齐。", "保留LSBJ时序，重新核帧格式、声道和实际采样率。"],
    ["旧.fs解读边界", "对照表比较的是CST球位名称与Pro原理图用途。跨封装旧.fs的真实pad映射未回读鉴定。", "不能把同名球位对照当作旧.fs当前在Pro上确实驱动哪根线的证据，也不能判断板卡已损坏。"],
]
adaptation = [
    ["可复用候选", "DDS、声部分配、MIDI解析、包络、混音、延迟和PT8211 LSBJ发送器", "保持内部40 MHz、48 kHz和既有模块接口；复用不代签Pro功能通过。"],
    ["必须重新建立", "目标FPG676工程器件/版本、顶层CST、差分约束、PLL/IP及SDC", "已有PG484布局布线、时序报告和.fs不适用于Pro；需要商业版支持环境并重跑。"],
    ["明确RTL差异", "功放使能", "当前顶层 pa_en = ~rst_sync_n | ~core_async_rst_n 为低有效；Pro应工作时高、复位及失锁时低，需要受控顶层变更。"],
    ["按键与MIDI", "底板S0低有效复位候选，S1/S2音符候选；R17/J22/5或C21/J26/11候选", "这些是供M2选择的方案，尚未修改端口、约束或实际接线。"],
    ["验证顺序", "正确供电/复位/50 MHz → UART心跳 → 音频时钟与固定音 → MIDI四声部 → HDMI", "当前音频依赖视频PLL锁定；先保证锁定与40 MHz核心时钟，不能只接线就认为可发声。"],
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = []
for path in sorted(ROOT.glob("*.pdf")):
    sources.append(dict(name=path.name, path=str(path), bytes=path.stat().st_size, sha256=sha(path)))
for relative in ["constraints/audio_visual.cst", "sources/m2_fourvoice_timbre_delay_board_top.sv", "sources/i2s_tx.sv"]:
    path = INPUTS / relative
    sources.append(dict(name=path.name, path=str(path), bytes=path.stat().st_size, sha256=sha(path)))

data = dict(title="Tang Mega 138K Pro 引脚关系与四复音迁移核对", date="2026-10-16",
            validation="L0 原理图/源码静态核对，未构建Pro工程、未烧录、未上板验证", rows=rows,
            comparisons=comparisons, conflicts=conflicts, adaptation=adaptation, sources=sources,
            amp_datasheet=dict(url=AMP_URL, source="矽普特原厂数据手册，第三方镜像", page=3, logic="SD=0掉电，SD=1正常工作"))
(OUT / "pin_relationships.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def table(headers, values, cls=""):
    return '<div class="tablewrap"><table class="'+cls+'"><thead><tr>'+''.join('<th>'+html.escape(str(h))+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in values)+'</tbody></table></div>'


body = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>138K Pro 引脚关系与四复音适配</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f8;color:#172b3a;font:15px/1.6 'Microsoft YaHei','Segoe UI',sans-serif}
main{max-width:1540px;margin:auto;padding:32px}h1{font-size:28px;margin:0 0 10px}h2{font-size:21px;margin:30px 0 12px}h3{font-size:17px}
.lead{font-size:18px;max-width:1000px}.meta{color:#526575;font-size:13px}.notice{background:#fff3db;border-left:5px solid #b46a00;padding:16px 20px;margin:20px 0}
.card{background:white;border:1px solid #dbe1e6;border-radius:8px;padding:20px;margin:16px 0}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;background:white}
th,td{border-bottom:1px solid #dbe1e6;padding:11px 12px;text-align:left;vertical-align:top}th{background:#e8eef3;position:sticky;top:0;white-space:nowrap}td{min-width:90px}td:last-child{min-width:220px}
.pins{min-width:1510px;font-size:13px}.pins td:nth-child(6){min-width:230px}.pins td:nth-child(9){min-width:280px}a{color:#005a9c}code{background:#edf1f5;padding:1px 5px}summary{cursor:pointer;font-weight:bold}
input,select,button{font:inherit;padding:8px 12px;border:1px solid #b7c3cd;border-radius:5px;background:white;margin:3px 7px 3px 0}input{width:330px}.small{font-size:13px;color:#526575}
.sha{font:12px Consolas,monospace;overflow-wrap:anywhere}nav{margin:16px 0}nav a{margin-right:20px}.keytable td:nth-child(5){min-width:290px}
@media print{body{background:white;font-size:10px}main{padding:0}.controls,nav{display:none}.tablewrap{overflow:visible}.pins{min-width:0;font-size:8px}td,th{padding:5px;min-width:0!important}th{position:static}h2{break-after:avoid}tr{break-inside:avoid}.card{border:0;padding:0}details:not([open])>*:not(summary){display:block}}
</style><main>
<h1>Tang Mega 138K Pro 引脚关系表</h1>
<p class="lead">这套 Pro 的硬件可以作为四复音工程的迁移目标。当前 PG484 / NEO Dock 码流不适配，需重新建立 FPG676 工程、约束和 PLL，并改变功放使能极性。</p>
<p class="meta">资料：4072 核心板 Rev 1.10（2024-03-25），4071f 底板 Rev 1.5（2025-03-25） · 核对日期：2026-10-16</p>
<div class="notice"><strong>本表是资料静态核对，不是可直接烧录的约束，也不是实物板型确认。</strong><br>当前验证等级 L0。原 RTL、CST、码流和历史下载证据均保留。实物修订、器件步进、Bank 电压及已标出的资料冲突仍需确认。</div>
<nav><a href="#critical">当前工程对应</a><a href="#allpins">引脚关系</a><a href="#issues">冲突与待确认</a><a href="#plan">适配判断</a><a href="#sources">原件来源</a></nav>
<section id="critical"><h2>当前四复音工程对应关系</h2><p>“Pro 候选”是迁移方案，尚未实现。旧球位在 Pro 的用途仅按同名球位查原理图，不代表旧跨封装码流的真实 pad 映射。</p>
"""
body += table(["当前端口", "现有普通版CST", "Pro球位/候选", "Pro终点", "差异与处理"], comparisons, "keytable")
body += """<div class="card"><h3>音频路径与现场位置</h3><p>FPGA E22/F24/G24 → 底板 U6 PT8211-S → LMV321 低通/缓冲 → U32 XPT4809 → J29 耳机口。H17 控制 U32/5，高电平工作、低电平关闭。J25 是 DC 电源接口。</p><p>PT8211 的接口是 16 位 LSBJ 右对齐。正常48 kHz/64 BCLK时，U6/1应见3.072 MHz，U6/2应见48 kHz；该预期以新的正确Pro工程运行作为前提。</p></div></section>
<section id="allpins"><h2>引脚关系明细</h2><p>范围：本次四音迁移所需的时钟、复位、按键、UART、音频、HDMI，以及三组PMOD、用户LED、扩展SDRAM排针、I2C、风扇与WS2812。不是整板360个BTB接点的完整约束文件。</p>
<p class="small">表中电压是原理图的供电设计/默认装配，不是现场实测。BTB是细间距板间插座，不建议直接探针测量。针号按原理图，不等同于实物正面观察的左右方向。</p>
<div class="controls"><input id="search" aria-label="搜索引脚" placeholder="搜索 R17、UART、J22、待确认…"><select id="group" aria-label="筛选接口"><option value="">全部接口</option>"""
body += ''.join('<option>'+html.escape(g)+'</option>' for g in dict.fromkeys(r["group"] for r in rows))
body += '</select><button onclick="window.print()">打印 / 保存PDF</button><span id="count"></span></div>'
headers = ["接口", "网络", "FPGA球位", "Bank", "设计电压", "可接触终点", "底板BTB", "核心板BTB", "电平/复用/限制", "依据（PDF页码）"]
keys = ["group", "net", "ball", "bank", "voltage", "endpoint", "dock", "core", "note", "source"]
body += table(headers, [[r[k] for k in keys] for r in rows], "pins")
body += """<div class="card"><strong>BTB 镜像核对</strong><p>底板J6 ↔ 核心J1，底板J7 ↔ 核心J2，底板J8 ↔ 核心J3。两边图纸的同一物理接点编号是相邻奇偶号互换，不能按同号对接。例如P15为底板J6/66、核心J1/65；E22为底板J8/22、核心J3/21；R17为底板J7/50、核心J2/49。</p></div></section>
<section id="issues"><h2>冲突与待确认</h2>"""
body += table(["项目", "已发现事实/限制", "处理"], conflicts)
body += '</section><section id="plan"><h2>能否使用这套 Pro</h2>'
body += table(["范围", "内容", "适配要求"], adaptation)
body += """<p>结论：可以迁移，当前文件不能直接作为Pro正式码流。除引脚外，功放极性是已证实的RTL修改点。当前没有改代码、没有执行综合/PnR/仿真、没有新增下载。</p></section>
<section id="sources"><h2>原件、版本与证据</h2><p>两份原始PDF未修改。页码按PDF顺序（1起算）。</p>"""
for source in sources:
    link = Path(source["path"]).as_uri()
    body += f'<div class="card"><a href="{html.escape(link)}">{html.escape(source["name"])}</a><br><span class="small">{source["bytes"]:,} bytes</span><div class="sha">SHA-256 {source["sha256"]}</div></div>'
body += f'<p>功放逻辑补充来源：<a href="{AMP_URL}">XPT4809 原厂数据手册（第三方镜像），p3 管脚描述</a>：SD=0掉电，SD=1正常工作。与底板图纸的EN名称对照后确定H17控制极性。</p>'
body += '<p>官方器件选型参考：<a href="https://wiki.sipeed.com/hardware/zh/tang/common-doc/get_started/install-the-ide.html">Sipeed 安装IDE与板卡器件表</a>；实物步进仍需核实。</p>'
body += '<details><summary>已直接查看的原理图页面图像</summary>'
for tag, pages in [("core", [3, 5, 6, 7, 9]), ("dock", [2, 3, 5, 6, 8, 15, 16, 18])]:
    body += '<p>'+''.join(f'<a href="evidence/{tag}_p{i}.png" style="margin-right:16px">{tag} p{i}</a>' for i in pages)+'</p>'
body += '</details></section><p class="small">此报告位于仓库外的chat10资料目录，未提交或推送Git，未向其他对话发送。受控工程修改与正式发布仍需M2按项目流程处理。</p></main>'
body += """<script>
const search=document.querySelector('#search'),group=document.querySelector('#group'),trs=[...document.querySelectorAll('.pins tbody tr')];
function filter(){let shown=0;const q=search.value.trim().toLowerCase();for(const tr of trs){const ok=(!group.value||tr.cells[0].textContent===group.value)&&(!q||tr.textContent.toLowerCase().includes(q));tr.hidden=!ok;if(ok)shown++;}document.querySelector('#count').textContent=`显示 ${shown} / ${trs.length} 条`;}
search.addEventListener('input',filter);group.addEventListener('change',filter);filter();
</script></html>"""
report_path = OUT / "138K_Pro_引脚关系与适配核对.html"
report_path.write_text(body, encoding="utf-8")

# Authoring checks: constraints/source identity and internally consistent table.
assert len(comparisons) == 14
assert len({(r["group"], r["net"]) for r in rows}) == len(rows)
assert sum(r["group"].startswith("PMOD") for r in rows) == 24
assert sum(r["group"] == "扩展SDRAM" for r in rows) == 40
assert sum(r["group"] == "底板按键" for r in rows) == 4
assert next(r for r in rows if r["net"] == "PA_EN")["ball"] == "H17"
assert next(r for r in rows if r["net"] == "I2S_DIN")["endpoint"].endswith("/3")
import re
cst = (INPUTS / "constraints/audio_visual.cst").read_text(encoding="utf-8")
locs = dict(re.findall(r'IO_LOC\s+"([^"]+)"\s+([^;]+);', cst))
for item in comparisons:
    assert locs[item[0]].strip() == item[1].split("（")[0].split("，")[0], item[0]
for source in sources:
    assert sha(Path(source["path"])) == source["sha256"]

validation = dict(level="L0_STATIC_ONLY", row_count=len(rows), comparisons=len(comparisons),
                  input_files_unchanged=True, old_cst_locations_verified=True,
                  schematic_rendering_review="核心p3/5/6/7/9、底板p2/3/5/6/8/15/16/18；核心p4文字核NC/VSS",
                  unresolved=[item[0] for item in conflicts[:5]],
                  pro_compilation_run=False, programming_run=False, hardware_pass=False)
old_fs = ROOT.parent / 'chat9/M2_138K_C_M1TD_DIAGNOSTIC_SRAM_ONLY_20261015/m2_fourvoice_timbre_delay_board_top.fs'
assert sha(old_fs) == '5f4960d91ffb7ccd22ac5f79526cf45b55bbc20836285a5f9b328cc3cfc27c10'
validation['old_bitstream_sha256'] = sha(old_fs)
validation['old_bitstream_unchanged'] = True
(OUT / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
(OUT / "入口说明.txt").write_text("打开 138K_Pro_引脚关系与适配核对.html 查看可搜索的引脚关系表。\n"
    "pin_relationships.json 为相同内容的结构化数据；evidence 是原理图页面图像。\n"
    "本次仅原理图/现有源码静态分析（L0），原始PDF和RTL/CST/.fs未修改，未执行Pro构建或硬件下载。\n"
    "关键结论：可迁移到Pro；必须适配FPG676器件/约束/PLL/SDC，功放H17高有效，需要修改当前低有效顶层控制。\n"
    "原始资料的PMOD0_IO1和SDRAM_DM0/DM1冲突已保留；实物版本、步进、电压待确认。\n"
    "本表不是可直接烧录的CST；候选接线须在正确Pro工程完成后执行。\n", encoding="utf-8")
print(json.dumps(validation, ensure_ascii=False, indent=2))
print(report_path)
