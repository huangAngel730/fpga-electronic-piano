# MIDIPLUS X4 III 硬件与 MIDI 能力事实

更新时间：2026-09-21。

## 一 设备来源与证据边界

- 已购设备：二手 MIDIPLUS X4 III（三代）MIDI 键盘。
- 卖家页面描述：49 键、附延音踏板，并称带“表情轮”；价格与成色只属于采购记录，不作为技术规格依据。
- 官方资料：MIDIPLUS《X III Series User Manual EN v1.0》（2021-09-09），适用于 X4 III、X6 III、X8 III。
- 官方手册地址：`https://web-file.midiplus.com/upload/202109/09/X%20III%20Series%20User%20Manual%20EN%20v1.0_210909.pdf`
- 厂商支持页：`https://midiplus.com/support.aspx`

卖家所称“表情轮”不能直接解释为附送 EXP 表情踏板。官方结构是面板上的 Pitch Bend 与
Modulation 触控条，另有后面板 EXP 表情踏板输入。实物到手后需分别核对。

## 二 官方手册确认的规格

| 项目 | 官方事实 | 对本项目的意义 |
|---|---|---|
| 键数 | X4 III 为 49 键 | 覆盖约四个八度，FPGA 仍按 MIDI Note 0～127 处理 |
| 力度 | 标准尺寸力度感应琴键 | 可作为力度动态输入，但需抓包证明 Velocity 会变化 |
| Pitch 控制 | Pitch Bend 触控条 | 可生成滑音/弯音控制，待确认实际 14 位消息范围和回中值 |
| Mod 控制 | Modulation 触控条 | 可生成颤音深度控制，通常对应 CC1，待实物抓包 |
| MIDI 输出 | 后面板 DIN MIDI OUT | 可不经过电脑直接送入 FPGA 的 MIDI 接收电路 |
| USB | USB 同时用于供电和 MIDI 数据 | 可用 USB 电源给键盘供电，演奏数据走 DIN MIDI OUT |
| 延音输入 | `SUS` 踏板接口 | 卖家附送延音踏板，预期为 CC64，必须抓包确认极性和值域 |
| 表情输入 | `EXP` 表情踏板接口 | 支持额外连续踏板；不代表已附送踏板，默认 CC/可配置性待实测 |

官方手册的 MIDI CC 附录列出 CC1 Modulation、CC11 Expression、CC64 Sustain、CC67 Soft
Pedal 等标准编号；这只说明 MIDI 标准定义，不证明 X4 III 的 EXP 接口默认发送 CC11 或能直接配置
成 CC67。实际消息必须通过抓包确认。

## 三 项目采用的交互口径

电子钢琴主模式：

```text
琴键 Note On/Off + Velocity
延音踏板 Sustain
Pitch/Mod 触控条默认不参与普通钢琴演奏
```

拓展表情展示模式：

```text
Velocity        -> 力度动态
Pitch Bend      -> 滑音/弯音
Modulation CC1  -> LFO 颤音深度
Sustain CC64    -> 额外的钢琴延音控制
```

因此满足“≥3 维表情”的优先路线改为 Velocity、Pitch Bend、Modulation。弱音踏板不再是满足三维
指标的近期必购物料。EXP 踏板可以后续用于连续音量、音色明暗、弱音深度或其他表情，但必须先
确认键盘实际发出的 MIDI 消息。

## 四 FPGA 接入方式

```text
X4 III DIN MIDI OUT
    -> 标准 MIDI 电流环接收电路
    -> 光耦隔离与 3.3 V 逻辑整形
    -> FPGA midi_rx
    -> uart_rx（31250 baud, 8N1）
    -> midi_event_parser
```

安全约束：

- DIN MIDI OUT 不能直接连接 FPGA GPIO。
- 不把任何未知 5 V UART/踏板信号直接接到 3.3 V FPGA。
- 键盘可通过 USB 供电，但电脑不参与正式 MIDI 转发和音频合成。
- MIDI 输入引脚、光耦型号、限流电阻和 FPGA Bank 电压必须在正式接线前核实。

## 五 实物到手后的必测项目

1. 记录机身型号、序列号、49 键布局和后面板接口照片。
2. 确认 DIN MIDI OUT 在仅 USB 供电时仍可输出。
3. 同一琴键轻按/重按，记录 Note On Velocity 的范围和重复性。
4. Pitch 触控条：确认消息类型、中心值、上下范围、松手回中。
5. Modulation 触控条：确认是否发送 CC1、范围是否为 0～127。
6. 延音踏板：确认 CC64 极性、按下/松开值，以及是否只有 0/127。
7. EXP 接口：若后续接入表情踏板，记录实际 CC 编号、值域和踏板极性。
8. 测量从 MIDI 字节进入 FPGA 到事件输出、再到音频输出的端到端延迟。

以上项目未完成前，只能写“官方规格支持/方案可用”，不能写成“FPGA 已实现或已上板验证”。
